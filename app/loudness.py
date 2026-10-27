"""Loudness evening-out: measure every track once, in the background, and turn the result into a playback gain.

Nothing here changes an audio file. The measurement (integrated loudness in LUFS and true peak in dBTP) is stored in
the database and the gain is applied to the voice stream while playing, so switching the feature off takes effect
immediately and needs no re-processing.
"""
from __future__ import annotations

import json
import logging
import math
import re
import shutil
import subprocess
import threading
from pathlib import Path

from .config import Settings
from .db import tx
from .library import track_path

log = logging.getLogger("melomancer.loudness")

PEAK_CEILING_DB = -1.0   # a boosted track never gets a peak above this
MIN_GAIN_DB = -24.0      # a very loud track is never turned down by more than this
MEASURE_TIMEOUT = 900
IDLE_POLL_SECONDS = 15
SETTING_NORMALIZE = "normalize"
SETTING_TARGET = "normalize_target"
SETTING_BOOST = "normalize_max_boost"
DEFAULT_TARGET = -16.0               # LUFS: a comfortable level for music over Discord, with some headroom
DEFAULT_MAX_BOOST = 6.0              # dB: a very quiet track is raised by at most this much
TARGET_RANGE = (-30.0, -8.0)
BOOST_RANGE = (0.0, 12.0)


def measure(path: Path) -> tuple[float, float] | None:
    """Return (integrated LUFS, true peak dBTP), or None when the file is silent, unreadable or too slow."""
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", str(path), "-vn",
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]
    if shutil.which("nice"):  # keep the measurement from competing with the voice stream for CPU
        cmd = ["nice", "-n", "10", *cmd]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=MEASURE_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    blocks = re.findall(r"\{[^{}]*\}", result.stderr or "")
    if not blocks:
        return None
    try:
        data = json.loads(blocks[-1])
        loudness, peak = float(data["input_i"]), float(data["input_tp"])
    except (ValueError, KeyError, TypeError):
        return None
    if not (math.isfinite(loudness) and math.isfinite(peak)):  # digital silence reports -inf
        return None
    return loudness, peak


def gain_db(loudness: float | None, peak: float | None, target: float, max_boost: float) -> float:
    """Decibels to add so that the track lands on the target loudness, without boosting into clipping."""
    if loudness is None:
        return 0.0
    gain = min(target - loudness, max_boost)
    if peak is not None:
        gain = min(gain, PEAK_CEILING_DB - peak)
    return max(gain, MIN_GAIN_DB)


def linear_gain(loudness: float | None, peak: float | None, target: float, max_boost: float) -> float:
    return 10 ** (gain_db(loudness, peak, target, max_boost) / 20)


class RuntimeSettings:
    """Settings an administrator changes in the panel while the bot runs; they are kept in the database."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.normalize = True
        self.target = DEFAULT_TARGET
        self.max_boost = DEFAULT_MAX_BOOST

    def load(self) -> None:
        with tx(self._settings.db_path) as conn:
            stored = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM app_settings")}
        if SETTING_NORMALIZE in stored:
            self.normalize = stored[SETTING_NORMALIZE] == "1"
        for key, attr, (low, high) in ((SETTING_TARGET, "target", TARGET_RANGE), (SETTING_BOOST, "max_boost", BOOST_RANGE)):
            try:
                setattr(self, attr, min(max(float(stored[key]), low), high))
            except (KeyError, ValueError):
                pass  # not set (or damaged): the default stays

    def update(self, *, normalize: bool | None = None, target: float | None = None,
               max_boost: float | None = None) -> None:
        changes: dict[str, str] = {}
        if normalize is not None:
            self.normalize = normalize
            changes[SETTING_NORMALIZE] = "1" if normalize else "0"
        if target is not None:
            self.target = min(max(float(target), TARGET_RANGE[0]), TARGET_RANGE[1])
            changes[SETTING_TARGET] = f"{self.target:g}"
        if max_boost is not None:
            self.max_boost = min(max(float(max_boost), BOOST_RANGE[0]), BOOST_RANGE[1])
            changes[SETTING_BOOST] = f"{self.max_boost:g}"
        with tx(self._settings.db_path) as conn:
            for key, value in changes.items():
                conn.execute("INSERT INTO app_settings(key, value) VALUES (?, ?) "
                             "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def counts(settings: Settings) -> dict:
    with tx(settings.db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS total, COALESCE(SUM(loudness IS NOT NULL), 0) AS measured, "
                           "COALESCE(SUM(loudness IS NULL AND loudness_tried = 0), 0) AS waiting "
                           "FROM tracks WHERE deleted_at IS NULL").fetchone()
    return {"total": row["total"], "measured": row["measured"], "waiting": row["waiting"]}


class LoudnessWorker:
    """Measures tracks that have no measurement yet, newest first, one at a time."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread:
            return
        with tx(self.settings.db_path) as conn:  # a measurement that failed once (restart, timeout) gets another go
            conn.execute("UPDATE tracks SET loudness_tried=0 WHERE loudness IS NULL AND loudness_tried=1")
        self._thread = threading.Thread(target=self._run, name="loudness", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def wake(self) -> None:
        self._wake.set()

    def process_one(self) -> bool:
        """Measure one track. Returns False when nothing is waiting."""
        with tx(self.settings.db_path) as conn:
            row = conn.execute("SELECT id, ext FROM tracks WHERE deleted_at IS NULL AND loudness_tried=0 "
                               "ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
        if row is None:
            return False
        path = track_path(self.settings, row["id"], row["ext"])
        result = measure(path) if path.is_file() else None
        with tx(self.settings.db_path) as conn:
            conn.execute("UPDATE tracks SET loudness=?, peak=?, loudness_tried=1 WHERE id=?",
                         (result[0] if result else None, result[1] if result else None, row["id"]))
        if result:
            log.info("Measured %s: %.1f LUFS, peak %.1f dBTP", row["id"][:8], result[0], result[1])
        else:
            log.info("No loudness for %s (silent or unreadable)", row["id"][:8])
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                busy = self.process_one()
            except Exception:  # noqa: BLE001 - the worker must outlive one bad file
                log.exception("Loudness measurement failed")
                busy = False
            if not busy:
                self._wake.wait(timeout=IDLE_POLL_SECONDS)
                self._wake.clear()
