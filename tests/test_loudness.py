"""Loudness evening-out: measuring, the gain maths, the background worker and the administrator's switch."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.db import tx
from app.loudness import LoudnessWorker, Measurement, RuntimeSettings, _trim_from, counts, gain_db, linear_gain, measure
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
    assert 19 < loud.loudness - soft.loudness < 21, (loud, soft)  # 20 dB apart, give or take the tolerance
    assert loud.peak < 0 and soft.peak < loud.peak                 # true peaks, below digital full scale
    assert (loud.lead, loud.trail) == (None, None)                 # a plain tone has no silence to trim


def test_measure_gives_no_loudness_for_silence_and_nothing_for_junk(tmp_path):
    silent = tmp_path / "silent.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", "2", str(silent)], check=True)
    assert measure(silent) == Measurement(None, None, None, None)  # all silent: nothing sensible to trim either
    junk = tmp_path / "junk.wav"
    junk.write_bytes(b"not audio at all")
    assert measure(junk) is None
    assert measure(tmp_path / "missing.wav") is None


def silent_ends_wav(path: Path, lead: float = 1.5, tone: float = 3.0, tail: float = 2.0) -> Path:
    graph = (f"[0:a]atrim=0:{lead}[a0];[1:a]atrim=0:{tone}[a1];[2:a]atrim=0:{tail}[a2];"
             "[a0][a1][a2]concat=n=3:v=0:a=1")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100,aformat=channel_layouts=stereo",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex", graph, str(path)], check=True)
    return path


def test_silence_at_the_start_and_the_end_is_measured(tmp_path):
    result = measure(silent_ends_wav(tmp_path / "gap.wav"), duration=6.5)
    assert result.lead == pytest.approx(1.45, abs=0.1)     # the sound starts at 1.5 s, a little margin is kept
    assert result.trail == pytest.approx(1.85, abs=0.15)   # it stops at 4.5 s of 6.5 s, 0.15 s of tail is kept
    assert result.loudness is not None


def test_a_stricter_threshold_hears_less_silence(tmp_path):
    quiet_edges = tmp_path / "quiet.wav"
    graph = ("[0:a]atrim=0:1.5,volume=-45dB[a0];[1:a]atrim=0:3[a1];[a0][a1]concat=n=2:v=0:a=1")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=44100,aformat=channel_layouts=stereo",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100,aformat=channel_layouts=stereo",
                    "-filter_complex", graph, str(quiet_edges)], check=True)
    assert measure(quiet_edges, -50.0, 4.5).lead == pytest.approx(1.45, abs=0.1)   # -63 dBFS is silence at -50 dB
    assert measure(quiet_edges, -70.0, 4.5).lead is None                             # ... but not at -70 dB


def test_trimming_rules_on_ffmpeg_output():
    def lines(*spans):
        return "\n".join(f"[silencedetect @ 0x1] silence_start: {a}\n[silencedetect @ 0x1] silence_end: {b} | silence_duration: {b - a}"
                         for a, b in spans)
    assert _trim_from("", 60.0) == (None, None)
    assert _trim_from(lines((0, 2.0)), 2.0) == (None, None)                          # the whole track is silent
    assert _trim_from(lines((0, 3.0), (57.0, 60.0)), 60.0) == pytest.approx((2.95, 2.85))
    assert _trim_from(lines((0, 0.1)), 60.0) == (None, None)                         # too short to bother
    assert _trim_from(lines((0, 0.3), (59.9, 60.0)), 60.0) == (pytest.approx(0.25), None)
    assert _trim_from(lines((20.0, 25.0)), 60.0) == (None, None)                     # silence in the middle stays
    assert _trim_from(lines((57.0, 60.0)), 60.0) == (None, pytest.approx(2.85))
    assert _trim_from(lines((57.0, 59.0)), 60.0) == (None, None)                     # it does not reach the end


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
    assert manager.gain_for(item) == pytest.approx(10 ** (6 / 20))  # +10 wanted, +6 allowed by default
    runtime.max_boost, runtime.target = 3.0, -20.0
    assert manager.gain_for(item) == pytest.approx(10 ** (3 / 20))  # now only +3 allowed
    runtime.max_boost = 12.0
    assert manager.gain_for(item) == pytest.approx(10 ** (6 / 20))  # +6 wanted to reach -20
    runtime.normalize = False
    assert manager.gain_for(item) == 1.0
    assert manager.gain_for(QueueItem("u", "U", "/y", 60.0)) == 1.0


def test_worker_measures_what_is_waiting_and_marks_unusable_files(env):
    login(env, "admin")
    for n, db in enumerate((-6, -20)):
        assert upload(env, quiet_wav(env.tmp / f"t{n}.wav", db, 300 + n * 100)).status_code == 201
    silent = env.tmp / "silent.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "2",
                    str(silent)], check=True)
    assert upload(env, silent).status_code == 201

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
    assert (info["normalize"], info["normalize_target"], info["normalize_max_boost"]) == (True, -16.0, 6.0)
    assert info["loudness"] == {"total": 0, "measured": 0, "waiting": 0}
    assert env.client.patch("/api/system", json={"normalize": False}).status_code == 403

    login(env, "admin")
    res = env.client.patch("/api/system", json={"normalize": False})
    assert res.status_code == 200 and res.json()["normalize"] is False
    assert env.bot.settings_refreshed == 1  # what is playing right now was told to follow

    fresh = RuntimeSettings(env.settings)
    assert fresh.normalize is True  # the built-in default ...
    fresh.load()
    assert fresh.normalize is False  # ... until the stored choice is read, as happens at start-up


def test_target_and_boost_are_stored_and_validated(env):
    login(env, "admin")
    res = env.client.patch("/api/system", json={"normalize_target": -20, "normalize_max_boost": 3})
    assert res.status_code == 200
    assert (res.json()["normalize"], res.json()["normalize_target"], res.json()["normalize_max_boost"]) == (True, -20.0, 3.0)
    assert env.bot.settings_refreshed == 1

    fresh = RuntimeSettings(env.settings)
    fresh.load()
    assert (fresh.normalize, fresh.target, fresh.max_boost) == (True, -20.0, 3.0)  # survives a restart

    for bad in ({"normalize_target": -5}, {"normalize_target": -40}, {"normalize_max_boost": 20},
                {"normalize_max_boost": -1}, {"crossfade_seconds": 30}, {"crossfade_seconds": -1},
                {"scrub_seconds": 5}):
        assert env.client.patch("/api/system", json=bad).status_code == 422, bad
    assert env.client.get("/api/system").json()["normalize_target"] == -20.0  # nothing was changed by the bad ones


def test_fade_times_default_to_three_seconds_and_a_third_are_stored_and_validated(env):
    login(env, "admin")
    info = env.client.get("/api/system").json()
    assert (info["crossfade_seconds"], info["scrub_seconds"], info["volume_glide_seconds"]) == (3.0, 0.3, 0.25)
    res = env.client.patch("/api/system", json={"crossfade_seconds": 5, "scrub_seconds": 0, "volume_glide_seconds": 0.6})
    assert res.status_code == 200 and (res.json()["crossfade_seconds"], res.json()["scrub_seconds"],
                                       res.json()["volume_glide_seconds"]) == (5.0, 0.0, 0.6)
    fresh = RuntimeSettings(env.settings)
    fresh.load()
    assert (fresh.crossfade, fresh.scrub, fresh.glide) == (5.0, 0.0, 0.6)  # 0 is valid: a hard cut / no glide
    for bad in ({"volume_glide_seconds": -1}, {"volume_glide_seconds": 5}):
        assert env.client.patch("/api/system", json=bad).status_code == 422, bad
    assert env.bot.settings_refreshed == 1


def test_a_changed_silence_threshold_makes_the_worker_measure_everything_again(env):
    login(env, "admin")
    for n in range(2):
        assert upload(env, quiet_wav(env.tmp / f"t{n}.wav", -10, 300 + n * 100)).status_code == 201
    runtime = RuntimeSettings(env.settings)
    worker = LoudnessWorker(env.settings, runtime)
    assert [worker.process_one() for _ in range(3)] == [True, True, False]
    assert counts(env.settings, runtime.silence_db)["waiting"] == 0
    runtime.update(silence_db=-60)
    assert counts(env.settings, runtime.silence_db)["waiting"] == 2
    assert [worker.process_one() for _ in range(3)] == [True, True, False]
    with tx(env.settings.db_path) as conn:
        assert {r["silence_db"] for r in conn.execute("SELECT silence_db FROM tracks")} == {-60.0}


def test_the_worker_stores_silence_and_the_trim_settings_are_validated(env):
    login(env, "admin")
    assert upload(env, silent_ends_wav(env.tmp / "gap.wav")).status_code == 201
    LoudnessWorker(env.settings, RuntimeSettings(env.settings)).process_one()
    with tx(env.settings.db_path) as conn:
        row = conn.execute("SELECT silence_lead, silence_trail, silence_db FROM tracks").fetchone()
    assert row["silence_lead"] == pytest.approx(1.45, abs=0.1) and row["silence_trail"] == pytest.approx(1.85, abs=0.2)
    assert row["silence_db"] == -50.0

    info = env.client.get("/api/system").json()
    assert (info["trim_silence"], info["silence_threshold"]) == (True, -50.0)
    res = env.client.patch("/api/system", json={"trim_silence": False, "silence_threshold": -60})
    assert res.status_code == 200 and (res.json()["trim_silence"], res.json()["silence_threshold"]) == (False, -60.0)
    fresh = RuntimeSettings(env.settings)
    fresh.load()
    assert (fresh.trim_silence, fresh.silence_db) == (False, -60.0)
    for bad in ({"silence_threshold": -80}, {"silence_threshold": -20}):
        assert env.client.patch("/api/system", json=bad).status_code == 422, bad
