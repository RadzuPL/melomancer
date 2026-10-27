"""Loudness evening-out: measuring, the gain maths, the background worker and the administrator's switch."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.db import tx
from app.loudness import LoudnessWorker, RuntimeSettings, counts, gain_db, linear_gain, measure
from app.player import BotManager, QueueItem
from .conftest import login, make_user, upload


def quiet_wav(path: Path, db: float, frequency: int = 440) -> Path:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=frequency={frequency}:duration=3", "-af", f"volume={db}dB", str(path)], check=True)
    return path


def test_measure_follows_the_real_level_of_the_audio(tmp_path):
    loud = measure(quiet_wav(tmp_path / "loud.wav", -6))
    soft = measure(quiet_wav(tmp_path / "soft.wav", -26))
    assert loud and soft
    assert 19 < loud[0] - soft[0] < 21, (loud, soft)  # 20 dB apart, give or take the measurement's tolerance
    assert loud[1] < 0 and soft[1] < loud[1]  # true peaks, below digital full scale


def test_measure_gives_nothing_for_silence_and_for_junk(tmp_path):
    silent = tmp_path / "silent.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", "2", str(silent)], check=True)
    assert measure(silent) is None
    junk = tmp_path / "junk.wav"
    junk.write_bytes(b"not audio at all")
    assert measure(junk) is None
    assert measure(tmp_path / "missing.wav") is None


def test_gain_brings_tracks_to_the_target_but_never_into_clipping():
    assert gain_db(-26.0, -10.0, -16.0, 6.0) == 6.0           # wants +10, capped at the boost limit
    assert gain_db(-20.0, -10.0, -16.0, 6.0) == 4.0           # quieter track is raised exactly to the target
    assert gain_db(-9.0, -0.5, -16.0, 6.0) == -7.0            # loud track is turned down
    assert gain_db(-26.0, -2.0, -16.0, 6.0) == 1.0            # only 1 dB of headroom before -1 dBTP
    assert gain_db(10.0, 0.0, -16.0, 6.0) == -24.0            # absurd loudness is limited
    assert gain_db(None, None, -16.0, 6.0) == 0.0             # unknown loudness: leave alone
    assert linear_gain(-20.0, -10.0, -16.0, 6.0) == pytest.approx(10 ** (4 / 20))


def test_the_bot_applies_the_gain_only_while_evening_out_is_on(tmp_path):
    settings = Settings.from_env()
    runtime = RuntimeSettings(settings)
    manager = BotManager(settings, runtime)
    item = QueueItem("t", "T", "/x", 60.0, loudness=-26.0, peak=-10.0)
    runtime.normalize = True
    assert manager.gain_for(item) == pytest.approx(10 ** (6 / 20))  # +10 wanted, +6 allowed by default
    runtime.normalize = False
    assert manager.gain_for(item) == 1.0
    assert manager.gain_for(QueueItem("u", "U", "/y", 60.0)) == 1.0


def test_worker_measures_what_is_waiting_and_marks_unusable_files(env):
    login(env, "admin")
    for n, db in enumerate((-6, -20)):
        assert upload(env, quiet_wav(env.tmp / f"t{n}.wav", db, 300 + n * 100)).status_code == 200
    silent = env.tmp / "silent.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "2",
                    str(silent)], check=True)
    assert upload(env, silent).status_code == 200

    assert counts(env.settings) == {"total": 3, "measured": 0, "waiting": 3}
    worker = LoudnessWorker(env.settings)
    assert [worker.process_one() for _ in range(4)] == [True, True, True, False]
    assert counts(env.settings) == {"total": 3, "measured": 2, "waiting": 0}  # the silent one is not retried
    with tx(env.settings.db_path) as conn:
        levels = [r["loudness"] for r in conn.execute(
            "SELECT loudness FROM tracks WHERE loudness IS NOT NULL ORDER BY loudness")]
        unusable = conn.execute("SELECT COUNT(*) FROM tracks WHERE loudness IS NULL AND loudness_tried=1").fetchone()[0]
    assert 13 < levels[1] - levels[0] < 15, levels  # the two tones were 14 dB apart
    assert unusable == 1


def test_system_shows_the_switch_and_only_an_admin_can_flip_it(env):
    make_user(env, "bob")
    login(env, "bob")
    info = env.client.get("/api/system").json()
    assert info["normalize"] is True and info["normalize_target"] == -16.0
    assert info["loudness"] == {"total": 0, "measured": 0, "waiting": 0}
    assert env.client.patch("/api/system", json={"normalize": False}).status_code == 403

    login(env, "admin")
    res = env.client.patch("/api/system", json={"normalize": False})
    assert res.status_code == 200 and res.json()["normalize"] is False
    assert env.bot.gain_refreshed == 1  # what is playing right now was told to follow

    fresh = RuntimeSettings(env.settings)
    assert fresh.normalize is True  # the environment's default ...
    fresh.load()
    assert fresh.normalize is False  # ... until the stored choice is read, as happens at start-up


def test_a_stored_choice_beats_the_environment_default(env):
    login(env, "admin")
    assert env.client.patch("/api/system", json={"normalize": False}).status_code == 200
    assert env.client.patch("/api/system", json={"normalize": True}).status_code == 200
    fresh = RuntimeSettings(env.settings)
    fresh.load()
    assert fresh.normalize is True
