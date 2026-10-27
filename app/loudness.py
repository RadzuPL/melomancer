"""Track analysis done once, in the background: loudness (for evening-out) and silence at the start and end.

Nothing here changes an audio file. The measurements (integrated loudness in LUFS, true peak in dBTP, seconds of
silence to skip at the start and to cut at the end) are stored in the database and applied to the voice stream while
playing, so switching a feature off takes effect immediately and needs no re-processing.
"""
from __future__ import annotations

from dataclasses import dataclass
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
SETTING_CROSSFADE = "crossfade_seconds"
SETTING_SCRUB = "scrub_seconds"
DEFAULT_CROSSFADE = 3.0              # seconds of overlap between two tracks (0 = hard cut)
DEFAULT_SCRUB = 0.3                  # seconds of overlap when jumping inside a track (0 = hard cut)
CROSSFADE_RANGE = (0.0, 12.0)
SCRUB_RANGE = (0.0, 2.0)
SETTING_TRIM = "trim_silence"
SETTING_SILENCE_DB = "silence_threshold"
DEFAULT_SILENCE_DB = -50.0           # dB: quieter than this counts as silence
SILENCE_RANGE = (-70.0, -30.0)
SILENCE_MIN_LENGTH = 0.2             # seconds a quiet stretch must last to be noticed at all
MIN_TRIM = 0.25                      # a silence shorter than this at the start or end is left alone
LEAD_MARGIN = 0.05                   # the cut at the start lands this much before the first sound
TRAIL_KEEP = 0.15                    # this much of the silent tail is kept, so a decay is not clipped


@dataclass(frozen=True)
class Measurement:
    loudness: float | None   # integrated LUFS, None for a silent track
    peak: float | None       # true peak in dBTP
    lead: float | None       # seconds of silence at the start to skip, None when there is nothing to skip
    trail: float | None      # seconds of silence at the end to cut off, None when there is nothing to cut


def _trim_from(stderr: str, duration: float | None) -> tuple[float | None, float | None]:
    """Silence to skip at the start and to cut at the end, from ffmpeg's silencedetect lines."""
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", stderr)]
    spans = list(zip(starts, ends))  # a silence that runs into the end of the file is closed there
    if not spans:
        return None, None
    total = duration or spans[-1][1]
    first_start, first_end = spans[0]
    last_start, last_end = spans[-1]
    if len(spans) == 1 and first_start <= 0.05 and last_end >= total - 0.3:
        return None, None  # the whole track is silent: nothing sensible to trim
    lead = trail = None
    if first_start <= 0.05 and first_end - first_start >= MIN_TRIM and first_end < total * 0.5:
        lead = max(0.0, first_end - LEAD_MARGIN)
    if last_end >= total - 0.3 and last_start > total * 0.5:
        cut = total - (last_start + TRAIL_KEEP)
        if cut >= MIN_TRIM:
            trail = cut
    return lead, trail


def measure(path: Path, threshold: float = DEFAULT_SILENCE_DB, duration: float | None = None) -> Measurement | None:
    """Analyse a file in one pass. None when ffmpeg could not read it (or took too long)."""
    graph = (f"silencedetect=noise={threshold:g}dB:d={SILENCE_MIN_LENGTH:g},"
             "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json")
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", graph, "-f", "null", "-"]
    if shutil.which("nice"):  # keep the measurement from competing with the voice stream for CPU
        cmd = ["nice", "-n", "10", *cmd]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=MEASURE_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    stderr = result.stderr or ""
    blocks = re.findall(r"\{[^{}]*\}", stderr)
    if not blocks:
        return None
    loudness = peak = None
    try:
        data = json.loads(blocks[-1])
        loudness, peak = float(data["input_i"]), float(data["input_tp"])
    except (ValueError, KeyError, TypeError):
        pass
    if loudness is None or peak is None or not (math.isfinite(loudness) and math.isfinite(peak)):
        loudness = peak = None  # digital silence reports -inf
    lead, trail = _trim_from(stderr, duration)
    return Measurement(loudness, peak, lead, trail)


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
        self.crossfade = DEFAULT_CROSSFADE
        self.scrub = DEFAULT_SCRUB
        self.trim_silence = True
        self.silence_db = DEFAULT_SILENCE_DB

    def load(self) -> None:
        with tx(self._settings.db_path) as conn:
            stored = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM app_settings")}
        if SETTING_NORMALIZE in stored:
            self.normalize = stored[SETTING_NORMALIZE] == "1"
        if SETTING_TRIM in stored:
            self.trim_silence = stored[SETTING_TRIM] == "1"
        for key, attr, (low, high) in ((SETTING_TARGET, "target", TARGET_RANGE), (SETTING_BOOST, "max_boost", BOOST_RANGE),
                                       (SETTING_CROSSFADE, "crossfade", CROSSFADE_RANGE),
                                       (SETTING_SCRUB, "scrub", SCRUB_RANGE),
                                       (SETTING_SILENCE_DB, "silence_db", SILENCE_RANGE)):
            try:
                setattr(self, attr, min(max(float(stored[key]), low), high))
            except (KeyError, ValueError):
                pass  # not set (or damaged): the default stays

    def update(self, *, normalize: bool | None = None, target: float | None = None,
               max_boost: float | None = None, crossfade: float | None = None, scrub: float | None = None,
               trim_silence: bool | None = None, silence_db: float | None = None) -> None:
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
        if crossfade is not None:
            self.crossfade = min(max(float(crossfade), CROSSFADE_RANGE[0]), CROSSFADE_RANGE[1])
            changes[SETTING_CROSSFADE] = f"{self.crossfade:g}"
        if scrub is not None:
            self.scrub = min(max(float(scrub), SCRUB_RANGE[0]), SCRUB_RANGE[1])
            changes[SETTING_SCRUB] = f"{self.scrub:g}"
        if trim_silence is not None:
            self.trim_silence = trim_silence
            changes[SETTING_TRIM] = "1" if trim_silence else "0"
        if silence_db is not None:
            self.silence_db = min(max(float(silence_db), SILENCE_RANGE[0]), SILENCE_RANGE[1])
            changes[SETTING_SILENCE_DB] = f"{self.silence_db:g}"
        with tx(self._settings.db_path) as conn:
            for key, value in changes.items():
                conn.execute("INSERT INTO app_settings(key, value) VALUES (?, ?) "
                             "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


_NEEDS_ANALYSIS = "(loudness_tried = 0 OR silence_db IS NULL OR silence_db != ?)"


def counts(settings: Settings, threshold: float = DEFAULT_SILENCE_DB) -> dict:
    """How many live tracks there are, how many have a loudness, and how many still wait for an analysis."""
    with tx(settings.db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS total, COALESCE(SUM(loudness IS NOT NULL), 0) AS measured, "
                           f"COALESCE(SUM({_NEEDS_ANALYSIS}), 0) AS waiting "
                           "FROM tracks WHERE deleted_at IS NULL", (threshold,)).fetchone()
    return {"total": row["total"], "measured": row["measured"], "waiting": row["waiting"]}


class LoudnessWorker:
    """Analyses tracks that have not been analysed yet (or with another silence threshold), newest first."""

    def __init__(self, settings: Settings, runtime: RuntimeSettings | None = None) -> None:
        self.settings = settings
        self.runtime = runtime or RuntimeSettings(settings)
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
        """Analyse one track. Returns False when nothing is waiting."""
        threshold = self.runtime.silence_db
        with tx(self.settings.db_path) as conn:
            row = conn.execute(f"SELECT id, ext, duration FROM tracks WHERE deleted_at IS NULL AND {_NEEDS_ANALYSIS} "
                               "ORDER BY created_at DESC, rowid DESC LIMIT 1", (threshold,)).fetchone()
        if row is None:
            return False
        path = track_path(self.settings, row["id"], row["ext"])
        result = measure(path, threshold, row["duration"]) if path.is_file() else None
        result = result or Measurement(None, None, None, None)
        with tx(self.settings.db_path) as conn:
            conn.execute("UPDATE tracks SET loudness=?, peak=?, loudness_tried=1, silence_lead=?, silence_trail=?, "
                         "silence_db=? WHERE id=?",
                         (result.loudness, result.peak, result.lead, result.trail, threshold, row["id"]))
        if result.loudness is not None:
            log.info("Analysed %s: %.1f LUFS, peak %.1f dBTP, trim %s s at the start and %s s at the end",
                     row["id"][:8], result.loudness, result.peak, result.lead, result.trail)
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
