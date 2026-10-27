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
