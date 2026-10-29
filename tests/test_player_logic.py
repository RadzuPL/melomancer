"""GuildPlayer without Discord: a fake voice client records what would be played, and the test plays the part of the
voice client's audio thread by asking the real mixer for frames."""
from __future__ import annotations

import asyncio
import time
from array import array
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.mixer as mixer_mod
import app.player as player_mod
from app.player import GuildPlayer, PlayerError, QueueItem

DEFAULT_FRAMES = 6000  # a 120 s track
CREATED: list = []
FRAMES: dict[str, int] = {}


class FakeSource:
    """Stands in for discord.FFmpegPCMAudio: frames of a constant level (track n has level (n + 1) * 1000)."""

    def __init__(self, path, before_options=None, options=None):
        self.path, self.before_options, self.options = path, before_options, options
        stem = Path(path).stem  # not rsplit("/"): paths have backslashes on Windows
        offset = float(before_options.split()[1]) if before_options else 0.0
        self.left = max(0, FRAMES.get(stem, DEFAULT_FRAMES) - int(offset * 50))
        self.frame = array("h", [(int(stem) + 1) * 1000]).tobytes() * (mixer_mod.FRAME_BYTES // 2)
        self.cleaned = False
        CREATED.append(self)

    def read(self):
        if self.left <= 0:
            return b""
        self.left -= 1
        return self.frame

    def cleanup(self):
        self.cleaned = True


class FakeVoiceClient:
    def __init__(self):
        self.sources, self.afters, self.stops = [], [], 0
        self._playing = self._paused = False
        self.source = None
        self.channel = SimpleNamespace(id=5, name="Voice")

    def pause(self): self._paused = True
    def resume(self): self._paused = False
    def is_connected(self): return True
    def is_playing(self): return self._playing and not self._paused
    def is_paused(self): return self._paused

    def play(self, source, after=None):
        assert not self._playing, "Already playing audio."
        self.sources.append(source)
        self.afters.append(after)
        self.source, self._playing = source, True

    def stop(self):
        self.stops += 1
        self._playing = self._paused = False


def wait_for(condition, seconds=3.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return
        time.sleep(0.002)
    raise AssertionError("timed out")


@pytest.fixture
def rig(tmp_path, monkeypatch):
    CREATED.clear()
    FRAMES.clear()
    monkeypatch.setattr(player_mod.discord, "FFmpegPCMAudio", FakeSource)
    vc = FakeVoiceClient()
    guild = SimpleNamespace(voice_client=vc)
    fades = {"crossfade": 0.0, "scrub": 0.0, "trim": False}
    manager = SimpleNamespace(client=SimpleNamespace(get_guild=lambda gid: guild),
                              loop=SimpleNamespace(call_soon_threadsafe=lambda fn, *a: fn(*a)),
                              gain_for=lambda item: 1.0,
                              crossfade_seconds=lambda: fades["crossfade"], scrub_seconds=lambda: fades["scrub"],
                              trim_silence=lambda: fades["trim"], glide_seconds=lambda: 0.07)
    items = []
    for n in range(4):
        path = tmp_path / f"{n}.opus"
        path.write_bytes(b"x")
        items.append(QueueItem(f"t{n}", f"Track {n}", str(path), 120.0))
    player = GuildPlayer(manager, 1, 1.0)
    return SimpleNamespace(player=player, vc=vc, items=items, fades=fades, manager=manager)


def start(rig, **kw):
    options = dict(loop=True, shuffle=False, fade=0.0, volume=None)
    options.update(kw)
    asyncio.run(rig.player.play(rig.items, {"id": 1, "name": "P", "set": "S"}, {"id": 1, "username": "u"}, **options))


def played_paths(rig):
    return [Path(src.path).name for src in CREATED]


def settle(rig):
    """Wait until every stream of the mix has decoded its first frame (ffmpeg needs a moment in real life)."""
    mixer = rig.player._mixer
    wait_for(lambda: all(layer.state() != "wait" for layer in mixer.layers()))


def pull(rig):
    """What the voice client's audio thread does: ask for the next frame. Returns its level, None at the end."""
    for _ in range(3000):
        frame = rig.vc.source.read()
        if frame == b"":
            return None
        if frame != mixer_mod.SILENCE:
            return array("h", frame)[0]
        time.sleep(0.001)
    raise AssertionError("no audio")


def test_jump_switches_the_running_mix_to_the_chosen_track(rig):
    start(rig)
    settle(rig)
    assert pull(rig) == 1000
    assert played_paths(rig) == ["0.opus"]
    rig.player.jump(2)
    assert played_paths(rig) == ["0.opus", "2.opus"]
    assert len(rig.vc.sources) == 1                  # the same voice-client source goes on: no gap, no restart
    settle(rig)
    assert pull(rig) == 3000                         # hard cut with a cross-fade of 0
    assert rig.player.snapshot()["now"]["index"] == 2


def test_a_late_report_from_a_replaced_mix_changes_nothing(rig):
    start(rig)
    rig.player.stop()
    start(rig)
    assert len(rig.vc.sources) == 2
    rig.vc.afters[0](None)  # the first mix reports its end late: it is no longer the current one
    assert len(CREATED) == 2 and rig.player.state == "playing"


def test_next_after_a_jump_continues_from_there(rig):
    start(rig)
    rig.player.jump(2)
    rig.player.skip(1)
    assert played_paths(rig)[-1] == "3.opus"
    rig.player.skip(-1)
    rig.player.skip(-1)
    assert played_paths(rig)[-1] == "1.opus"


def test_jump_with_shuffle_lands_on_the_chosen_track_and_keeps_every_track_in_the_order(rig):
    start(rig, shuffle=True)
    rig.player.jump(1)
    assert played_paths(rig)[-1] == "1.opus"
    assert sorted(rig.player.order) == [0, 1, 2, 3]
    assert rig.player.snapshot()["now"]["index"] == 1


def test_jump_rejects_bad_requests(rig):
    with pytest.raises(PlayerError) as idle:
        rig.player.jump(0)
    assert idle.value.code == "not_playing"
    start(rig)
    with pytest.raises(PlayerError) as bad:
        rig.player.jump(9)
    assert bad.value.code == "bad_index" and bad.value.status == 400


def test_jump_while_paused_starts_playing_again(rig):
    start(rig)
    rig.player.pause()
    assert rig.vc._paused
    rig.player.jump(3)
    assert rig.player.state == "playing" and not rig.vc._paused
    assert played_paths(rig)[-1] == "3.opus"
    settle(rig)
    assert pull(rig) == 4000


def test_snapshot_lists_the_queue_only_while_something_plays(rig):
    assert rig.player.snapshot()["queue"] == []
    start(rig)
    snap = rig.player.snapshot()
    assert [q["title"] for q in snap["queue"]] == ["Track 0", "Track 1", "Track 2", "Track 3"]
    rig.player.stop()
    assert rig.player.snapshot()["queue"] == []


def test_stop_silences_the_voice_client_and_frees_the_streams(rig):
    start(rig)
    settle(rig)
    mixer = rig.player._mixer
    rig.player.stop()
    assert rig.vc.stops == 1 and rig.player._mixer is None and rig.player.state == "idle"
    wait_for(lambda: CREATED[0].cleaned)
    assert mixer.closed


def test_seek_restarts_the_track_from_that_position(rig):
    start(rig, fade=2.0)
    rig.player.seek(45)
    last = CREATED[-1]
    assert last.path.endswith("0.opus") and last.before_options == "-ss 45.00"
    assert "afade=t=out:st=73.00" in last.options  # 120 s track, 45 s in: the fade-out starts 73 s into the rest
    snap = rig.player.snapshot()
    assert snap["state"] == "playing" and 45 <= snap["now"]["elapsed"] < 50 and snap["now"]["index"] == 0


def test_seek_keeps_a_paused_player_paused_and_waits_for_the_resume(rig):
    start(rig)
    settle(rig)
    assert pull(rig) == 1000
    rig.player.pause()
    rig.player.seek(30)
    assert rig.player.state == "paused" and rig.vc._paused
    assert rig.player.snapshot()["now"]["elapsed"] == 30
    assert CREATED[-1].before_options == "-ss 30.00" and len(rig.vc.sources) == 1
    assert len(rig.player._mixer.layers()) == 2        # the old position and the new one, waiting for the resume
    rig.player.resume()
    assert rig.player.state == "playing"
    settle(rig)
    assert pull(rig) is not None
    assert len(rig.player._mixer.layers()) == 1        # the switch happened once playback went on


def test_seek_is_clamped_and_validated(rig):
    with pytest.raises(PlayerError) as idle:
        rig.player.seek(5)
    assert idle.value.code == "not_playing"
    start(rig)
    rig.player.seek(9999)  # past the end: the last two seconds are left
    assert CREATED[-1].before_options == "-ss 118.00"
    rig.items[0].duration = None
    rig.player.items[0].duration = None
    with pytest.raises(PlayerError) as unknown:
        rig.player.seek(10)
    assert unknown.value.code == "bad_seek"


def test_seek_uses_the_short_scrub_fade(rig):
    rig.fades["scrub"] = 0.2
    start(rig)
    settle(rig)
    assert pull(rig) == 1000
    rig.player.seek(60)
    settle(rig)
    levels = [pull(rig) for _ in range(14)]
    assert all(1000 <= level <= 1415 for level in levels)  # no gap, no dip; two uncorrelated halves would never exceed this
    assert levels[-1] == 1000 and len(rig.player._mixer.layers()) == 1  # the old position faded out and was dropped


def settled(rig, frames=80):
    """The level after the volume has had time to glide to where it was told to go."""
    level = None
    for _ in range(frames):
        level = pull(rig)
    return level


def test_loudness_gain_and_volume_multiply_and_follow_changes(rig):
    rig.manager.gain_for = lambda item: 0.5
    start(rig)
    rig.player.set_volume(0.4)
    settle(rig)
    assert settled(rig) == 200                                  # 1000 * volume 0.4 * gain 0.5
    rig.player.set_volume(0.8)
    assert 200 < pull(rig) < 400                                # glides there, it does not jump
    assert settled(rig) == 400                                  # the slider and the gain multiply
    rig.manager.gain_for = lambda item: 1.0                     # the administrator switched evening-out off
    rig.player.refresh_settings()
    assert settled(rig) == 800


def test_a_new_playlist_is_crossfaded_into_the_running_one(rig):
    start(rig)
    settle(rig)
    assert pull(rig) == 1000
    rig.fades["crossfade"] = 0.2
    start(rig, loop=False)  # another playlist
    assert len(rig.vc.sources) == 1 and len(rig.player._mixer.layers()) == 2
    settle(rig)
    for _ in range(12):
        assert pull(rig) is not None
    assert len(rig.player._mixer.layers()) == 1


def short_tracks(rig, frames=100, count=4):
    for n in range(count):
        FRAMES[str(n)] = frames
        rig.items[n].duration = frames / 50


def test_the_next_track_fades_in_by_itself_before_the_current_one_ends(rig):
    rig.fades["crossfade"] = 0.5
    short_tracks(rig)
    start(rig)
    settle(rig)
    levels, index_seen = [], []
    while len(levels) < 3 * 100 - 50:
        settle(rig)  # the test reads far faster than 20 ms apart: give the queued track time to decode
        level = pull(rig)
        assert level is not None, "the stream ended: the crossfade failed to take over"
        levels.append(level)
        index_seen.append(rig.player.snapshot()["now"]["index"])
    assert len(rig.vc.sources) == 1 and rig.player.state == "playing"      # one continuous source, never restarted
    assert levels[0] < 1000 and 1000 in levels                              # the first track fades in from silence
    assert 2000 in levels and 3000 in levels                                # then track 1, then track 2
    assert index_seen[0] == 0 and index_seen[-1] >= 2
    assert index_seen == sorted(index_seen)                                 # the position only moves forward
    assert 98 <= levels.index(2000) <= 103                                  # track 1 began 0.5 s before track 0's end
    assert played_paths(rig)[:3] == ["0.opus", "1.opus", "2.opus"]


def test_the_playlist_wraps_around_with_a_crossfade_when_it_loops(rig):
    rig.fades["crossfade"] = 0.5
    short_tracks(rig, count=2)
    rig.items = rig.items[:2]
    start(rig)
    settle(rig)
    seen = set()
    for _ in range(280):
        settle(rig)
        level = pull(rig)
        assert level is not None
        seen.add(level)
    assert seen >= {1000, 2000} and rig.player.state == "playing"
    assert played_paths(rig)[:3] == ["0.opus", "1.opus", "0.opus"]


def test_without_a_crossfade_the_mix_runs_dry_and_the_player_goes_on_with_the_next_track(rig):
    short_tracks(rig, frames=30)
    start(rig)
    settle(rig)
    assert [pull(rig) for _ in range(30)] == [1000] * 30
    assert pull(rig) is None                     # the stream ended: discord now calls `after`
    rig.vc.afters[-1](None)
    assert len(rig.vc.sources) == 2 and played_paths(rig)[-1] == "1.opus"
    assert rig.player.snapshot()["now"]["index"] == 1


def test_the_last_track_of_a_playlist_that_does_not_loop_ends_the_player(rig):
    rig.fades["crossfade"] = 0.2
    short_tracks(rig, frames=60, count=2)
    rig.items = rig.items[:2]
    start(rig, loop=False)
    settle(rig)
    while True:
        level = pull(rig)
        if level is None:
            break
    rig.vc.afters[-1](None)
    assert rig.player.state == "idle" and rig.player._mixer is None
    assert played_paths(rig) == ["0.opus", "1.opus"]


def test_a_broken_track_is_skipped_and_a_playlist_of_broken_tracks_stops(rig):
    short_tracks(rig, frames=0)
    start(rig)
    for _ in range(12):
        if rig.player.state == "idle":
            break
        for _ in range(50):
            frame = rig.vc.source.read()
            if frame == b"":
                break
            time.sleep(0.002)
        rig.vc.afters[-1](None)
    assert rig.player.state == "idle"
    assert len(CREATED) == len(rig.items) + 1        # every track tried once, plus one retry before giving up


def test_shuffling_or_looping_while_playing_makes_the_mix_plan_the_next_track_again(rig):
    rig.fades["crossfade"] = 0.5
    short_tracks(rig)
    start(rig)
    settle(rig)
    for _ in range(3):
        pull(rig)
    mixer = rig.player._mixer
    assert mixer.layers()                                       # the next track is already queued ...
    rig.player.set_options(loop=False, shuffle=None)
    assert len(mixer.layers()) == 1 or not mixer._pending      # ... and the old plan is forgotten


def with_silence(rig, lead=1.0, trail=1.0, frames=200):
    """Four 4 s tracks with `lead` s of silence at the start and `trail` s at the end."""
    for n in range(4):
        FRAMES[str(n)] = frames
        rig.items[n].duration = frames / 50
        rig.items[n].lead, rig.items[n].trail = lead, trail
    rig.fades["trim"] = True


def test_silence_is_skipped_at_the_start_and_cut_at_the_end(rig):
    with_silence(rig)
    start(rig)
    settle(rig)
    assert CREATED[0].before_options == "-ss 1.00"
    assert 1.0 <= rig.player.snapshot()["now"]["elapsed"] < 1.5          # the clock starts at the first sound
    frames = 0
    while pull(rig) is not None:
        frames += 1
    assert frames == 100                                                  # 1.0 s to 3.0 s of a 4 s file


def test_without_the_trim_setting_the_whole_file_plays(rig):
    with_silence(rig)
    rig.fades["trim"] = False
    start(rig)
    settle(rig)
    assert CREATED[0].before_options is None
    frames = 0
    while pull(rig) is not None:
        frames += 1
    assert frames == 200


def test_the_crossfade_is_timed_from_the_last_sound_not_from_the_end_of_the_file(rig):
    rig.fades["crossfade"] = 0.5
    with_silence(rig)
    start(rig)
    settle(rig)
    levels = []
    while len(levels) < 130:
        settle(rig)
        level = pull(rig)
        assert level is not None
        levels.append(level)
    assert 98 <= levels.index(2000) <= 103   # the next track is fully in 2 s (the audible part) after the first began
    assert CREATED[1].before_options == "-ss 1.00"  # and it also skips its own silent start


def test_trimming_that_would_leave_next_to_nothing_is_ignored(rig):
    with_silence(rig, lead=2.0, trail=1.5)    # 4 s file: only 0.5 s would remain
    start(rig)
    assert CREATED[0].before_options is None


def test_seeking_is_measured_in_file_time_and_clamped_to_the_audible_end(rig):
    with_silence(rig)
    start(rig)
    rig.player.seek(9999)
    assert CREATED[-1].before_options == "-ss 1.00"   # 3 s is the audible end of a 4 s file, minus 2 s


def test_a_start_set_by_hand_wins_over_the_analysis_and_works_with_the_switch_off(rig):
    with_silence(rig, lead=1.0, trail=1.0)
    rig.items[0].trim_start = 0.5
    start(rig)
    assert CREATED[0].before_options == "-ss 0.50"      # not the 1.0 s the analysis found
    rig.fades["trim"] = False
    rig.player.jump(0)
    assert CREATED[-1].before_options == "-ss 0.50"      # hand-set points apply even with the analysis switched off
    rig.player.jump(1)
    assert CREATED[-1].before_options is None            # a track without them follows the switch


def test_each_side_is_decided_on_its_own(rig):
    with_silence(rig, lead=1.0, trail=1.0)               # 4 s tracks, analysis says 1.0 to 3.0
    rig.items[0].trim_end = 3.8                            # only the end is set by hand
    start(rig)
    settle(rig)
    assert CREATED[0].before_options == "-ss 1.00"        # the start still comes from the analysis
    frames = 0
    while pull(rig) is not None:
        frames += 1
    assert frames == 140                                   # 1.0 s to 3.8 s


def test_zero_means_no_cut_at_the_start_even_when_silence_was_found(rig):
    with_silence(rig, lead=1.0, trail=0.0)
    rig.items[0].trim_start = 0.0
    start(rig)
    assert CREATED[0].before_options is None


def test_a_hand_set_end_at_the_end_of_the_file_cancels_an_automatic_cut(rig):
    with_silence(rig, lead=0.0, trail=1.0)
    rig.items[0].trim_end = 4.0
    start(rig)
    settle(rig)
    frames = 0
    while pull(rig) is not None:
        frames += 1
    assert frames == 200
