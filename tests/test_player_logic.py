"""GuildPlayer without Discord: a fake voice client records what would be played."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import app.player as player_mod
from app.player import GuildPlayer, PlayerError, QueueItem


class FakeSource:
    def __init__(self, path, before_options=None, options=None):
        self.path, self.before_options, self.options = path, before_options, options


class FakeVolume:
    def __init__(self, source, volume=1.0):
        self.source, self.volume = source, volume


class FakeVoiceClient:
    def __init__(self):
        self.sources, self.afters, self.stops = [], [], 0
        self._playing = self._paused = False
        self.source = None
        self.channel = SimpleNamespace(id=5, name="Voice")

    def pause(self): self._paused = True
    def resume(self): self._paused = False
    def is_connected(self): return True
    def is_playing(self): return self._playing
    def is_paused(self): return self._paused

    def play(self, source, after=None):
        self.sources.append(source)
        self.afters.append(after)
        self.source, self._playing = source, True

    def stop(self):
        self.stops += 1
        self._playing = self._paused = False


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setattr(player_mod.discord, "FFmpegPCMAudio", FakeSource)
    monkeypatch.setattr(player_mod.discord, "PCMVolumeTransformer", FakeVolume)
    vc = FakeVoiceClient()
    guild = SimpleNamespace(voice_client=vc)
    manager = SimpleNamespace(client=SimpleNamespace(get_guild=lambda gid: guild),
                              loop=SimpleNamespace(call_soon_threadsafe=lambda fn, *a: fn(*a)),
                              gain_for=lambda item: 1.0)
    items = []
    for n in range(4):
        path = tmp_path / f"{n}.opus"
        path.write_bytes(b"x")
        items.append(QueueItem(f"t{n}", f"Track {n}", str(path), 120.0))
    player = GuildPlayer(manager, 1, 0.4)
    return SimpleNamespace(player=player, vc=vc, items=items)


def start(rig, **kw):
    options = dict(loop=True, shuffle=False, fade=0.0, volume=None)
    options.update(kw)
    asyncio.run(rig.player.play(rig.items, {"id": 1, "name": "P", "set": "S"}, {"id": 1, "username": "u"}, **options))


def played_paths(rig):
    return [s.source.path.rsplit("/", 1)[1] for s in rig.vc.sources]


def test_jump_plays_the_chosen_track_and_ignores_the_old_source(rig):
    start(rig)
    assert played_paths(rig) == ["0.opus"]
    rig.player.jump(2)
    assert played_paths(rig) == ["0.opus", "2.opus"]
    assert rig.player.snapshot()["now"]["index"] == 2

    rig.vc.afters[0](None)  # the replaced source reports its end late: must change nothing
    assert played_paths(rig) == ["0.opus", "2.opus"]


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
    rig.player.jump(3)
    assert rig.player.state == "playing"
    assert played_paths(rig)[-1] == "3.opus"


def test_snapshot_lists_the_queue_only_while_something_plays(rig):
    assert rig.player.snapshot()["queue"] == []
    start(rig)
    snap = rig.player.snapshot()
    assert [q["title"] for q in snap["queue"]] == ["Track 0", "Track 1", "Track 2", "Track 3"]
    rig.player.stop()
    assert rig.player.snapshot()["queue"] == []


def test_seek_restarts_the_track_from_that_position(rig):
    start(rig, fade=2.0)
    rig.player.seek(45)
    last = rig.vc.sources[-1].source
    assert last.path.endswith("0.opus") and last.before_options == "-ss 45.00"
    assert "afade=t=out:st=73.00" in last.options  # 120 s track, 45 s in: the fade-out starts 73 s into the rest
    snap = rig.player.snapshot()
    assert snap["state"] == "playing" and 45 <= snap["now"]["elapsed"] < 50 and snap["now"]["index"] == 0


def test_seek_keeps_a_paused_player_paused_and_ignores_the_old_source(rig):
    start(rig)
    rig.player.pause()
    rig.player.seek(30)
    assert rig.player.state == "paused" and rig.vc._paused
    assert rig.player.snapshot()["now"]["elapsed"] == 30
    rig.vc.afters[0](None)  # the replaced source reports its end late
    assert len(rig.vc.sources) == 2


def test_seek_is_clamped_and_validated(rig):
    with pytest.raises(PlayerError) as idle:
        rig.player.seek(5)
    assert idle.value.code == "not_playing"
    start(rig)
    rig.player.seek(9999)  # past the end: the last two seconds are left
    assert rig.vc.sources[-1].source.before_options == "-ss 118.00"
    rig.items[0].duration = None
    rig.player.items[0].duration = None
    with pytest.raises(PlayerError) as unknown:
        rig.player.seek(10)
    assert unknown.value.code == "bad_seek"


def test_loudness_gain_scales_the_volume_of_each_track_and_follows_changes(rig):
    rig.player.manager.gain_for = lambda item: 0.5
    start(rig)
    assert rig.vc.source.volume == pytest.approx(0.4 * 0.5)
    rig.player.set_volume(0.8)
    assert rig.vc.source.volume == pytest.approx(0.8 * 0.5)  # the slider and the gain multiply
    rig.player.manager.gain_for = lambda item: 1.0  # the administrator switched evening-out off
    rig.player.refresh_gain()
    assert rig.vc.source.volume == pytest.approx(0.8)
