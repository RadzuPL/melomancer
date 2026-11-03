"""The PCM mixer with fake streams: fades, queued tracks, timing, clean-up. No Discord and no ffmpeg involved."""
from __future__ import annotations

import time
from array import array

import app.mixer as mixer_mod
from app.mixer import FRAME_BYTES, Layer, Mixer


class Tone:
    """A fake FFmpegPCMAudio: `frames` frames of a constant level, then the end."""

    def __init__(self, level: int, frames: int, delay: float = 0.0) -> None:
        self.level, self.left, self.delay = level, frames, delay
        self.cleaned = False

    def read(self) -> bytes:
        if self.delay:
            time.sleep(self.delay)
        if self.left <= 0:
            return b""
        self.left -= 1
        return array("h", [self.level]) .tobytes() * (FRAME_BYTES // 2)

    def cleanup(self) -> None:
        self.cleaned = True


def level(frame: bytes) -> int:
    return array("h", frame)[0]


def wait_for(condition, seconds: float = 3.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return
        time.sleep(0.005)
    raise AssertionError("timed out")


def ready(layer: Layer) -> Layer:
    wait_for(lambda: layer.state() != "wait")
    return layer


def start(m: Mixer, tone: Tone, **kw) -> Layer:
    layer = Layer(tone, **kw)
    assert m.switch_to(layer, 0, 0)
    return ready(layer)


def read_audio(m: Mixer) -> bytes:
    """One real frame. The mixer hands out silence while a stream has not decoded its next frame yet, which only
    happens here because the tests read far faster than 20 ms apart; wait for the decoder instead of counting it."""
    for _ in range(2000):
        frame = m.read()
        if frame != mixer_mod.SILENCE:
            return frame
        time.sleep(0.001)
    raise AssertionError("no audio")


def play(m: Mixer, tone: Tone, **kw) -> tuple[Layer, bytes]:
    """Start a layer and read its first frame, which is what makes it part of the mix."""
    layer = start(m, tone, **kw)
    return layer, read_audio(m)


def drain(m: Mixer, limit: int = 2000) -> list[bytes]:
    frames = []
    for _ in range(limit):
        frame = m.read()
        if frame == b"":
            return frames
        if frame == mixer_mod.SILENCE:
            time.sleep(0.001)
            continue
        frames.append(frame)
    raise AssertionError("the stream never ended")


def test_one_layer_passes_through_with_volume_and_gain_and_then_ends():
    m = Mixer(volume=0.5)
    tone = Tone(10000, 5)
    layer = start(m, tone)
    layer.gain = 0.5
    frames = drain(m)
    assert len(frames) == 5 and all(len(f) == FRAME_BYTES for f in frames)
    assert {level(f) for f in frames} == {2500}  # 10000 * volume 0.5 * gain 0.5
    assert m.ended
    wait_for(lambda: tone.cleaned)


def test_switching_crossfades_without_a_gap_and_frees_the_old_stream():
    m = Mixer()
    old, new = Tone(8000, 400), Tone(16000, 400)
    start(m, old)
    assert [level(read_audio(m)) for _ in range(5)] == [8000] * 5
    assert m.switch_to(Layer(new), 0.2, 0.2)  # 10 frames
    ready(m.layers()[-1])
    frames = [read_audio(m) for _ in range(14)]
    assert all(len(f) == FRAME_BYTES for f in frames)
    assert abs(level(frames[0]) - 8000) < 800            # starts at the old level
    assert all(level(f) <= 17900 for f in frames)        # never louder than the two added in power
    assert level(frames[11]) == 16000                    # then only the new one
    wait_for(lambda: old.cleaned)
    assert not new.cleaned


def test_a_track_queued_with_set_next_takes_over_when_the_current_one_has_the_fade_time_left():
    preroll, transitions = [], []
    m = Mixer(crossfade=0.5, on_preroll=preroll.append, on_transition=transitions.append)
    first, second = Tone(8000, 100), Tone(16000, 100)  # both exactly 2.0 s
    a, frame = play(m, first, duration=2.0)
    frames = [frame]
    assert preroll == [a]  # 2.0 s left is inside the crossfade + preroll window
    b = Layer(second, duration=2.0)
    assert m.set_next(b, fade=0.5, after=a, token="second")
    ready(b)
    assert transitions == []
    frames += drain(m)
    assert transitions == ["second"]
    assert [level(f) for f in frames[:70]] == [8000] * 70  # a plain first track until the fade
    assert len(frames) == 175                              # 100 + 100 frames, 25 of them overlapped
    assert level(frames[-1]) == 16000 and level(frames[-30]) == 16000
    wait_for(lambda: first.cleaned and second.cleaned)


def test_the_transition_starts_at_the_right_moment():
    transitions = []
    m = Mixer(crossfade=0.5, on_preroll=lambda layer: None, on_transition=transitions.append)
    a, _ = play(m, Tone(8000, 100), duration=2.0)
    b = Layer(Tone(16000, 100), duration=2.0)
    assert m.set_next(b, fade=0.5, after=a, token="t")
    ready(b)
    reads = 1
    while not transitions:
        read_audio(m)
        reads += 1
        assert reads < 100
    assert 75 <= reads <= 77  # 0.5 s before the end of a 2 s track is frame 75


def test_a_queued_track_that_never_produces_audio_is_dropped_and_the_current_one_plays_on():
    transitions = []
    m = Mixer(crossfade=0.5, on_preroll=lambda layer: None, on_transition=transitions.append)
    a, first = play(m, Tone(8000, 100), duration=2.0)
    dead = Tone(1, 0)
    assert m.set_next(Layer(dead, duration=2.0), fade=0.5, after=a, token="never")
    frames = [first] + drain(m)
    assert transitions == [] and len(frames) == 100 and {level(f) for f in frames} == {8000}
    wait_for(lambda: dead.cleaned)


def test_if_the_current_track_ends_first_the_queued_one_just_starts():
    transitions = []
    m = Mixer(crossfade=0.5, on_preroll=lambda layer: None, on_transition=transitions.append)
    a, first = play(m, Tone(8000, 50), duration=10.0)  # claims 10 s but ends after 1 s
    b = Layer(Tone(16000, 50), duration=10.0)
    assert m.set_next(b, fade=0.5, after=a, token="t")
    ready(b)
    levels = [level(f) for f in drain(m)]
    assert transitions == ["t"]
    assert levels[-1] == 16000 and len(levels) >= 90  # no gap: the second track follows the first


def test_a_manual_switch_cancels_the_queued_track():
    m = Mixer(crossfade=0.5, on_preroll=lambda layer: None)
    a, _ = play(m, Tone(8000, 400), duration=8.0)
    queued = Tone(1, 100)
    assert m.set_next(Layer(queued, duration=8.0), fade=0.5, after=a, token="x")
    assert not m.set_next(Layer(Tone(2, 100)), fade=0.5, after=a, token="y")  # only one queued track at a time
    assert m.switch_to(Layer(Tone(3, 100)), 0, 0)
    wait_for(lambda: queued.cleaned)


def test_the_preroll_fires_once_and_can_be_rearmed():
    preroll = []
    far = Mixer(crossfade=0.5, on_preroll=preroll.append)
    play(far, Tone(8000, 400), duration=8.0)
    far.read()
    assert preroll == []                       # 8 s left: too early

    m = Mixer(crossfade=0.5, on_preroll=preroll.append)
    near, _ = play(m, Tone(8000, 400), duration=2.0)
    assert preroll == [near]
    m.read()
    assert preroll == [near]                   # once only ...
    m.cancel_pending(rearm=True)
    m.read()
    assert preroll == [near, near]             # ... until asked again

    off = Mixer(crossfade=0.0, on_preroll=preroll.append)
    play(off, Tone(8000, 400), duration=2.0)
    assert len(preroll) == 2                   # crossfade 0: no preroll at all


def test_quick_skipping_never_mixes_more_than_three_streams():
    m = Mixer()
    start(m, Tone(1000, 5000))
    m.read()
    for n in range(6):
        assert m.switch_to(Layer(Tone(1000 + n, 5000)), 1.0, 1.0)
        ready(m.layers()[-1])
        m.read()
        assert len(m.layers()) <= mixer_mod.MAX_SLOTS


def test_a_slow_layer_adds_silence_and_a_dead_one_is_given_up():
    old = mixer_mod.START_TIMEOUT
    mixer_mod.START_TIMEOUT = 0.2
    try:
        m = Mixer()
        assert m.switch_to(Layer(Tone(5, 10, delay=1.0)), 0, 0)
        assert m.read() == mixer_mod.SILENCE            # waiting for the first frame: silence, not the end
        time.sleep(0.3)
        assert m.read() == b"" and m.ended               # given up
    finally:
        mixer_mod.START_TIMEOUT = old


def test_close_frees_everything_and_a_finished_mixer_refuses_new_layers():
    m = Mixer()
    tone, other = Tone(1, 100), Tone(2, 100)
    a, _ = play(m, tone, duration=5.0)
    assert m.set_next(Layer(other, duration=5.0), fade=0.5, after=a, token="t")
    m.close()
    wait_for(lambda: tone.cleaned and other.cleaned)
    assert m.read() == b""
    assert not m.switch_to(Layer(Tone(3, 1)), 0, 0)


def test_a_layer_with_stop_at_ends_there_even_though_the_file_goes_on():
    m = Mixer()
    tone = Tone(7000, 500)
    start(m, tone, stop_at=1.0)         # 1.0 s = 50 frames
    assert len(drain(m)) == 50
    wait_for(lambda: tone.cleaned)


def test_stop_at_counts_from_the_position_in_the_file_not_from_the_start_of_the_layer():
    m = Mixer()
    start(m, Tone(7000, 500), offset=0.6, stop_at=1.0)   # starts 0.6 s into the file: 0.4 s = 20 frames left
    assert len(drain(m)) == 20


def test_a_volume_change_glides_instead_of_jumping():
    m = Mixer(volume=1.0, glide=0.07)
    start(m, Tone(10000, 2000))
    assert [level(read_audio(m)) for _ in range(3)] == [10000] * 3
    m.volume = 0.1                                   # the slider was clicked at 10 % while it stood at 100 %
    levels = [level(read_audio(m)) for _ in range(60)]
    steps = [a - b for a, b in zip([10000] + levels, levels)]
    assert 5000 < levels[0] < 10000, levels[:3]      # the first frame has hardly moved
    assert max(steps) < 2500 and min(steps) >= 0, steps[:5]   # no frame drops by more than a quarter of the range
    assert levels == sorted(levels, reverse=True)    # a smooth descent, no overshoot
    assert levels[-1] == 1000                        # and it lands exactly on the target


def test_raising_the_volume_glides_too_and_never_overshoots():
    m = Mixer(volume=0.1, glide=0.07)
    start(m, Tone(10000, 2000))
    read_audio(m)
    m.volume = 1.0
    levels = [level(read_audio(m)) for _ in range(60)]
    assert levels == sorted(levels) and max(levels) <= 10000 and levels[-1] == 10000
    assert levels[0] < 3000


def test_a_change_of_the_loudness_gain_glides_as_well():
    m = Mixer(glide=0.07)
    layer = start(m, Tone(10000, 2000))
    read_audio(m)
    layer.gain = 0.5                                 # the administrator switched evening-out on
    levels = [level(read_audio(m)) for _ in range(60)]
    assert levels[0] > 8000 and levels == sorted(levels, reverse=True) and levels[-1] == 5000


def test_a_new_layer_starts_at_its_gain_without_gliding_up_from_nothing():
    m = Mixer(volume=0.5)
    layer = Layer(Tone(10000, 100), gain=0.5)
    assert m.switch_to(layer, 0, 0)
    ready(layer)
    assert level(read_audio(m)) == 2500


def test_the_default_glide_is_gentle_and_a_longer_one_is_gentler_still():
    def descent(glide):
        m = Mixer(volume=1.0, glide=glide)
        start(m, Tone(10000, 3000))
        read_audio(m)
        m.volume = 0.1
        return [level(read_audio(m)) for _ in range(200)]

    default = descent(mixer_mod.GLIDE_SECONDS)
    assert mixer_mod.GLIDE_SECONDS == 0.25
    assert default[0] > 9300                              # the first frame has hardly moved: no jolt
    assert default[25] > 2000 and default[50] > 1100      # half a second in it is still on its way down
    assert default == sorted(default, reverse=True) and default[-1] == 1000
    slower = descent(1.0)
    assert slower[25] > default[25] and slower[0] > default[0]
    instant = descent(0.0)
    assert instant[0] < default[0] and instant[1] == 1000  # 0 means one 20 ms frame, for anyone who wants it quick


# ---- sound effects (the sampler's bus) -----------------------------------------------------------------------------

def fx(m: Mixer, tone, key="k", **kw) -> Layer:
    layer = Layer(tone, **{k: v for k, v in kw.items() if k in ("gain", "stop_at")})
    assert m.add_fx(layer, key, loop=kw.get("loop", False), momentary=kw.get("momentary", False))
    return ready(layer)


def test_an_effect_is_mixed_on_top_of_the_music_at_a_volume_of_its_own():
    m = Mixer(volume=0.5, glide=0, fx_volume=0.25)
    start(m, Tone(1000, 500))
    fx(m, Tone(2000, 500))
    frame = read_audio(m)
    assert level(frame) == 500 + 500, "music at 0.5 plus the effect at 0.25, each with its own volume"
    m.fx_volume = 1.0
    for _ in range(40):                       # the effect volume glides, it does not jump
        frame = m.read()
    assert level(frame) == 500 + 2000


def test_effects_play_without_music_and_the_mixer_ends_with_the_last_one():
    m = Mixer(glide=0)
    assert m.read() == b"", "nothing to play: a mixer without music or effects is finished"
    m = Mixer(glide=0)
    fx(m, Tone(1000, 5))
    frames = drain(m)
    assert len(frames) == 5 and all(level(f) == 1000 for f in frames)
    assert m.ended and not m.add_fx(Layer(Tone(1, 1)), "x", loop=False, momentary=False)


def test_pausing_freezes_the_music_but_not_the_effects():
    m = Mixer(glide=0)
    music = start(m, Tone(1000, 500))
    assert level(read_audio(m)) == 1000
    m.paused = True
    played = music.frames
    assert m.read() == mixer_mod.SILENCE and music.frames == played, "paused: silence, and the music does not move"
    fx(m, Tone(300, 500))
    assert level(m.read()) == 300 and music.frames == played, "an effect sounds over a paused mix"
    m.paused = False
    assert level(read_audio(m)) == 1300 and music.frames == played + 1


def test_a_paused_mixer_with_nothing_else_is_silent_but_not_finished():
    m = Mixer(glide=0)
    start(m, Tone(1000, 50))
    m.paused = True
    for _ in range(20):
        assert m.read() == mixer_mod.SILENCE
    assert not m.ended


def test_stopping_an_effect_fades_it_out_and_frees_its_stream():
    m = Mixer(glide=0)
    tone = Tone(1000, 10000)
    fx(m, tone)
    assert level(read_audio(m)) == 1000
    assert m.stop_fx("k") and m.fx_info() == [], "a stopped effect no longer counts as playing"
    frames = []
    for _ in range(10):
        frame = m.read()
        if frame == b"":
            break
        frames.append(level(frame))
    assert len(frames) >= 2 and frames[0] < 1000 and frames == sorted(frames, reverse=True), "fading out, not a cut"
    wait_for(lambda: tone.cleaned)
    assert m.read() == b"" and m.ended
    assert not m.stop_fx("k"), "nothing left to stop"


def test_the_same_key_again_replaces_the_running_effect_and_other_keys_are_independent():
    m = Mixer(glide=0)
    first = Tone(100, 10000)
    fx(m, first, key="a")
    fx(m, Tone(200, 10000), key="b")
    assert [e["key"] for e in m.fx_info()] == ["a", "b"]
    fx(m, Tone(300, 10000), key="a")
    wait_for(lambda: first.cleaned)
    assert sorted(e["key"] for e in m.fx_info()) == ["a", "b"] and level(read_audio(m)) == 200 + 300


def test_only_so_many_effects_at_once():
    m = Mixer(glide=0)
    for n in range(mixer_mod.MAX_FX):
        fx(m, Tone(10, 10000), key=n)
    assert not m.add_fx(Layer(Tone(10, 10000)), "extra", loop=False, momentary=False)
    assert len(m.fx_info()) == mixer_mod.MAX_FX


def test_a_momentary_effect_can_be_stopped_on_its_own():
    m = Mixer(glide=0)
    fx(m, Tone(100, 10000), key="held", momentary=True)
    fx(m, Tone(200, 10000), key="latched")
    assert m.stop_fx(momentary_only=True)
    assert [e["key"] for e in m.fx_info()] == ["latched"]


def test_the_owner_hears_when_the_music_ends_under_a_running_effect_but_not_otherwise():
    ended = []
    m = Mixer(glide=0, on_music_end=lambda _: ended.append(1))
    start(m, Tone(1000, 3))
    fx(m, Tone(50, 10000))
    for _ in range(10):
        m.read()
    assert ended == [1], "the mixer goes on for the effect: the player has to be told that the music is over"
    for _ in range(10):
        m.read()
    assert ended == [1], "once"
    quiet = []
    m = Mixer(glide=0, on_music_end=lambda _: quiet.append(1))
    start(m, Tone(1000, 3))
    assert len(drain(m)) == 3 and quiet == [], "without an effect the mixer simply ends"


def test_clearing_the_music_leaves_the_effects_playing():
    m = Mixer(glide=0)
    music = Tone(1000, 10000)
    start(m, music)
    fx(m, Tone(50, 10000))
    m.clear_music()
    wait_for(lambda: music.cleaned)
    assert level(m.read()) == 50 and not m.ended


def test_a_looping_source_starts_over_and_never_runs_dry():
    made = []

    def factory():
        made.append(Tone(700, 3))
        return made[-1]

    m = Mixer(glide=0)
    layer = Layer(mixer_mod.LoopingSource(factory))
    assert m.add_fx(layer, "loop", loop=True, momentary=False)
    ready(layer)
    frames = [level(read_audio(m)) for _ in range(12)]
    assert frames == [700] * 12 and len(made) >= 4
    assert m.stop_fx("loop")
    for _ in range(6):
        m.read()
    assert m.read() == b""


def test_a_loop_of_a_trimmed_track_restarts_where_the_wanted_part_ends():
    made = []

    def factory():
        made.append(Tone(900, 100))     # the file goes on for much longer than the part that is wanted
        return made[-1]

    source = mixer_mod.LoopingSource(factory, frames=4)
    assert [len(source.read()) for _ in range(10)] == [FRAME_BYTES] * 10
    assert len(made) == 3 and made[0].cleaned and made[1].cleaned, "each pass starts a new stream and frees the last"


def test_a_source_that_cannot_be_read_ends_the_loop_instead_of_restarting_for_ever():
    source = mixer_mod.LoopingSource(lambda: Tone(1, 0))
    assert source.read() == b""
