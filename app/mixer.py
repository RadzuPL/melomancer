"""A small PCM mixer: it lets the bot overlap tracks (cross-fade) and fade between positions of the same track.

Discord asks the audio source for one 20 ms frame at a time (48 kHz, 16-bit, stereo). The mixer keeps several decoded
streams ("layers"), fades them against each other and hands out the sum. A layer wraps anything with `read()` (one
frame, or b"" at the end) and `cleanup()`, in production a `discord.FFmpegPCMAudio`. Every layer is read ahead by its
own thread, so the audio thread never waits on a pipe.

The mixer knows nothing about playlists. It reports three events to its owner (from the audio thread, so the owner
must hand them over to its own thread):

* `on_preroll(layer)`: the layer is about to end, start preparing whatever follows it (see `set_next`);
* `on_transition(token)`: the track prepared with `set_next` has begun to fade in;
* `on_music_end()`: the music ran out while sound effects keep the mixer alive (without effects the mixer itself ends).

Next to the music there is a second bus for sound effects (the sampler): any number of short layers, each with a key,
started and stopped by hand, mixed on top of the music at a volume of their own. Effects play while the music is paused
(`paused` freezes the music only) and keep the mixer, and with it the voice connection's stream, alive when no music
plays. A looping effect is a `LoopingSource`.
"""
from __future__ import annotations

import audioop
import logging
import math
import queue
import threading
import time
from typing import Any, Callable

log = logging.getLogger("melomancer.mixer")

FRAME_BYTES = 3840            # 20 ms of 48 kHz 16-bit stereo, the unit Discord asks for
FRAME_SECONDS = 0.02
SILENCE = bytes(FRAME_BYTES)
EOF = b""
PREROLL_SECONDS = 2.5         # the next track is started this long before its cross-fade begins
READ_AHEAD_FRAMES = 100       # 2 s of audio buffered per layer
START_TIMEOUT = 5.0           # a layer that delivers nothing for this long is given up
MAX_SLOTS = 3                 # most streams mixed at once (quick skipping would otherwise pile up ffmpeg processes)
SUBBLOCKS = 4                 # a fade changes the gain four times per frame, so slow fades stay smooth
GLIDE_SECONDS = 0.25          # time constant of the volume and loudness-gain changes: they glide, they never jump
MAX_FX = 8                    # most sound effects at once
FX_FADE_IN = 0.01             # an effect starts and stops with a very short fade: a cut in the signal is a click
FX_FADE_OUT = 0.06


def glide_alpha(seconds: float) -> float:
    """How far a value moves towards its target in one frame, for a time constant of `seconds` (0 = at once)."""
    return 1.0 if seconds <= 0.005 else 1 - math.exp(-FRAME_SECONDS / seconds)


class Layer:
    """One decoded stream, read ahead by a thread."""

    def __init__(self, source: Any, *, item: Any = None, offset: float = 0.0, duration: float | None = None,
                 gain: float = 1.0, stop_at: float | None = None) -> None:
        self.source = source
        self.item = item
        self.offset = offset          # where in the track the layer starts (seconds)
        self.duration = duration      # where the audible part of the track ends (seconds), None if unknown
        self.stop_at = stop_at        # end the layer here even if the file goes on (a silent tail is cut off)
        self.gain = gain              # per-track loudness correction, changeable while playing
        self.frames = 0               # frames handed to the mixer so far
        self._queue: queue.Queue[bytes | None] = queue.Queue(maxsize=READ_AHEAD_FRAMES)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._eof = False
        self._closed = False

    def start(self) -> "Layer":
        if self._thread is None:
            self._thread = threading.Thread(target=self._pump, name="mixer-layer", daemon=True)
            self._thread.start()
        return self

    def _put(self, item: bytes | None) -> bool:
        while not self._stop.is_set():
            try:
                self._queue.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def _pump(self) -> None:
        while not self._stop.is_set():
            try:
                data = self.source.read()
            except Exception:  # noqa: BLE001 - the process was killed under us: that is the end of the stream
                data = EOF
            if len(data) != FRAME_BYTES:
                self._put(None)
                return
            if not self._put(data):
                return

    def state(self) -> str:
        """'data' (a real frame is waiting), 'eof' (the stream ended without more data) or 'wait'."""
        with self._queue.mutex:
            if not self._queue.queue:
                return "eof" if self._eof else "wait"
            return "eof" if self._queue.queue[0] is None else "data"

    def pull(self) -> bytes | None:
        """A frame, None when nothing is buffered yet, or EOF at the end of the stream."""
        if self._eof:
            return EOF
        if self.stop_at is not None and self.offset + self.frames * FRAME_SECONDS >= self.stop_at:
            self._eof = True
            return EOF
        try:
            data = self._queue.get_nowait()
        except queue.Empty:
            return None
        if data is None:
            self._eof = True
            return EOF
        self.frames += 1
        return data

    def remaining(self) -> float | None:
        """Seconds of the track left to play, None when its length is unknown."""
        if not self.duration:
            return None
        return self.duration - (self.offset + self.frames * FRAME_SECONDS)

    def close(self) -> None:
        """Stop reading and kill the process. Done on a thread: it must never stall the audio thread."""
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        threading.Thread(target=self._cleanup, name="mixer-cleanup", daemon=True).start()

    def _cleanup(self) -> None:
        try:
            self.source.cleanup()
        except Exception:  # noqa: BLE001
            log.debug("Cleaning up a layer failed", exc_info=True)


class _Slot:
    """A layer being mixed, with its fade. `level` is the gain the fade has reached."""

    def __init__(self, layer: Layer, level: float) -> None:
        self.layer = layer
        self.level = level
        self.f_from = self.f_to = level
        self.f_total = self.f_done = 0
        self.preroll_fired = False
        self.gain_now = layer.gain    # the layer's loudness gain as applied; glides towards layer.gain

    def fade(self, to: float, frames: int) -> None:
        if frames <= 0:
            self.level = self.f_from = self.f_to = to
            self.f_total = self.f_done = 0
            return
        self.f_from, self.f_to, self.f_total, self.f_done = self.level, to, frames, 0

    @property
    def fading(self) -> bool:
        return self.f_done < self.f_total

    @property
    def leaving(self) -> bool:
        return self.f_to == 0 and self.f_total > 0

    def _gain_at(self, done: int) -> float:
        p = done / self.f_total
        # Equal-power curves: a fade-in follows sin, a fade-out cos, so the sum of two layers keeps its loudness.
        shape = math.sin(p * math.pi / 2) if self.f_to >= self.f_from else 1 - math.cos(p * math.pi / 2)
        return self.f_from + (self.f_to - self.f_from) * shape

    def glide(self, alpha: float) -> tuple[float, float]:
        """The loudness gain at the start and at the end of the frame, moving smoothly towards the wanted one."""
        start, goal = self.gain_now, self.layer.gain
        end = start + (goal - start) * alpha
        self.gain_now = goal if abs(goal - end) < 0.002 else end
        return start, self.gain_now

    def step(self) -> tuple[float, float]:
        """Gain at the start and at the end of the frame about to be mixed."""
        if not self.fading:
            return self.level, self.level
        start = self._gain_at(self.f_done)
        self.f_done += 1
        self.level = self._gain_at(self.f_done) if self.fading else self.f_to
        return start, self.level


class _FxSlot(_Slot):
    """A sound effect being mixed. `key` says which pad it is; `momentary` effects stop when the button is released."""

    def __init__(self, layer: Layer, key: Any, *, loop: bool, momentary: bool) -> None:
        super().__init__(layer, 0.0)
        self.key, self.loop, self.momentary = key, loop, momentary


class LoopingSource:
    """Plays a source again from its start whenever it ends, so that an effect can sound for as long as it is wanted.

    The thread that reads ahead for a `Layer` calls `read()`, so restarting a process here never delays the audio
    thread, and the two seconds that are read ahead cover the moment of the restart. `frames` is the length of one pass
    when the source plays on after the part that is wanted (a trimmed track): the pass ends there.
    """

    def __init__(self, factory: Callable[[], Any], frames: int | None = None) -> None:
        self._factory, self._frames = factory, frames
        self._source = factory()
        self._count = 0

    def read(self) -> bytes:
        if self._frames is not None and self._count >= self._frames:
            self._restart()
        data = self._source.read()
        if len(data) != FRAME_BYTES:
            self._restart()
            data = self._source.read()
            if len(data) != FRAME_BYTES:
                return EOF          # nothing can be read from the start either: end instead of restarting for ever
        self._count += 1
        return data

    def _restart(self) -> None:
        old, self._source, self._count = self._source, self._factory(), 0
        try:
            old.cleanup()
        except Exception:  # noqa: BLE001
            log.debug("Cleaning up a looped source failed", exc_info=True)

    def cleanup(self) -> None:
        self._source.cleanup()


class _Pending:
    """A layer waiting for its turn: for its first frame, and, for an automatic one, for the track before it to end."""

    def __init__(self, layer: Layer, *, fade_in: float, fade_out: float, after: Layer | None = None,
                 fade: float = 0.0, token: Any = None) -> None:
        self.layer, self.fade_in, self.fade_out = layer, fade_in, fade_out
        self.after, self.fade, self.token = after, fade, token
        self.created = time.monotonic()


def _frames(seconds: float) -> int:
    return max(0, round(seconds / FRAME_SECONDS))


def _scale(frame: bytes, g0: float, g1: float) -> bytes:
    if g0 == g1:
        if g0 == 1.0:
            return frame
        if g0 == 0.0:
            return SILENCE
        return audioop.mul(frame, 2, g0)
    size = FRAME_BYTES // SUBBLOCKS
    return b"".join(
        audioop.mul(frame[k * size:(k + 1) * size], 2, g0 + (g1 - g0) * (k + 0.5) / SUBBLOCKS) for k in range(SUBBLOCKS))


class Mixer:
    def __init__(self, *, volume: float = 1.0, crossfade: float = 0.0, glide: float = GLIDE_SECONDS,
                 on_preroll: Callable[[Layer], None] | None = None,
                 on_transition: Callable[[Any], None] | None = None,
                 on_music_end: Callable[[Any], None] | None = None, fx_volume: float = 1.0) -> None:
        self.volume = volume          # the wanted volume; what is applied glides towards it (see _mix_locked)
        self._volume_now = volume
        self.crossfade = crossfade    # seconds; 0 switches preroll off
        self.glide = glide            # seconds; how slowly volume changes are followed (0 = at once)
        self._on_preroll = on_preroll
        self._on_transition = on_transition
        self._on_music_end = on_music_end
        self.fx_volume = fx_volume    # the wanted volume of the effects; glides like `volume`
        self._fx_volume_now = fx_volume
        self.paused = False           # the music is frozen (effects go on); the voice client itself is never paused
        self._had_music = False
        self._slots: list[_Slot] = []
        self._fx: list[_FxSlot] = []
        self._pending: _Pending | None = None
        self._lock = threading.Lock()
        self.ended = False
        self.closed = False

    # ---- control (any thread) ---------------------------------------------

    def switch_to(self, layer: Layer, fade_in: float, fade_out: float) -> bool:
        """Play this layer instead of what plays now: it fades in as soon as it has audio, the rest fades out.

        Returns False, leaving the layer untouched, when the mixer is already finished: the caller then needs a
        new one.
        """
        with self._lock:
            if self.ended or self.closed:
                return False
            self._drop_pending_locked()
            self._pending = _Pending(layer.start(), fade_in=fade_in, fade_out=fade_out)
            return True

    def set_next(self, layer: Layer, *, fade: float, after: Layer, token: Any) -> bool:
        """Queue the track that follows `after`: it starts fading in when `after` has `fade` seconds left."""
        with self._lock:
            if self.ended or self.closed or self._pending is not None:
                return False
            self._pending = _Pending(layer.start(), fade_in=fade, fade_out=fade, after=after, fade=fade, token=token)
            return True

    def cancel_pending(self, rearm: bool = False) -> None:
        """Forget the queued track; `rearm` lets the current track ask for a new one (the plan changed)."""
        with self._lock:
            self._drop_pending_locked()
            if rearm:
                for slot in self._slots:
                    slot.preroll_fired = False

    # ---- sound effects -----------------------------------------------------

    def add_fx(self, layer: Layer, key: Any, *, loop: bool, momentary: bool) -> bool:
        """Start an effect. The same key again replaces the running one. False when the mixer is finished or full."""
        with self._lock:
            if self.ended or self.closed:
                return False
            for old in [s for s in self._fx if s.key == key]:
                self._remove_fx_locked(old)
            if len(self._fx) >= MAX_FX:
                return False
            slot = _FxSlot(layer.start(), key, loop=loop, momentary=momentary)
            slot.fade(1.0, _frames(FX_FADE_IN))
            self._fx.append(slot)
            return True

    def stop_fx(self, key: Any = None, *, momentary_only: bool = False) -> bool:
        """Fade an effect out (all of them for key None). True when something was stopped."""
        stopped = False
        with self._lock:
            for slot in self._fx:
                if (key is None or slot.key == key) and not slot.leaving and (slot.momentary or not momentary_only):
                    slot.fade(0.0, _frames(FX_FADE_OUT))
                    stopped = True
        return stopped

    def fx_info(self) -> list[dict]:
        """The effects that sound now (those fading out are already counted as stopped)."""
        with self._lock:
            return [{"key": s.key, "loop": s.loop, "momentary": s.momentary} for s in self._fx if not s.leaving]

    def has_fx(self) -> bool:
        with self._lock:
            return bool(self._fx)

    def clear_music(self) -> None:
        """Drop the music at once and leave the effects alone (stopping the music must not cut a thunder short)."""
        with self._lock:
            self._drop_pending_locked()
            for slot in self._slots:
                slot.layer.close()
            self._slots.clear()
            self._had_music = False

    def layers(self) -> list[Layer]:
        with self._lock:
            return [s.layer for s in self._slots] + ([self._pending.layer] if self._pending else [])

    def close(self) -> None:
        with self._lock:
            self.closed = True
            self._drop_pending_locked()
            for slot in self._slots + self._fx:
                slot.layer.close()
            self._slots.clear()
            self._fx.clear()

    # ---- the audio thread --------------------------------------------------

    def read(self) -> bytes:
        events: list[tuple[Callable, Any]] = []
        with self._lock:
            if self.closed:
                return EOF
            frame = self._mix_locked(events)
            if frame == EOF:
                self.ended = True
        for callback, argument in events:
            try:
                callback(argument)
            except Exception:  # noqa: BLE001
                log.exception("Mixer callback failed")
        return frame

    def _mix_locked(self, events: list) -> bytes:
        if not self.paused:
            self._activate_pending_locked(events)
        # A change of the volume takes a few frames: a step in the signal is heard as a click or a jolt.
        alpha = glide_alpha(self.glide)
        v0 = self._volume_now
        v1 = v0 + (self.volume - v0) * alpha
        v1 = self.volume if abs(self.volume - v1) < 0.002 else v1
        self._volume_now = v1
        mix: bytes | None = None
        for slot in ([] if self.paused else list(self._slots)):
            frame = slot.layer.pull()
            if frame == EOF:
                self._remove_locked(slot)
                continue
            if frame is None:      # not decoded yet: this layer adds silence for now and its fade waits
                continue
            g0, g1 = slot.step()
            a0, a1 = slot.glide(alpha)
            part = _scale(frame, g0 * a0 * v0, g1 * a1 * v1)
            mix = part if mix is None else audioop.add(mix, part, 2)
            if slot.leaving and not slot.fading:
                self._remove_locked(slot)
            elif self._on_preroll and self.crossfade > 0 and not slot.preroll_fired and not slot.leaving:
                left = slot.layer.remaining()
                if left is not None and left <= self.crossfade + PREROLL_SECONDS:
                    slot.preroll_fired = True
                    events.append((self._on_preroll, slot.layer))
        effects = self._mix_fx_locked(alpha)
        if effects is not None:
            mix = effects if mix is None else audioop.add(mix, effects, 2)
        if self._slots or self._pending:
            self._had_music = True
        elif self._had_music:
            self._had_music = False
            if self._fx and self._on_music_end:   # without effects the mixer ends and the owner learns that from the voice client
                events.append((self._on_music_end, None))
        if mix is not None:
            return mix
        return SILENCE if (self._slots or self._pending or self._fx or self.paused) else EOF

    def _mix_fx_locked(self, alpha: float) -> bytes | None:
        f0 = self._fx_volume_now
        f1 = f0 + (self.fx_volume - f0) * alpha
        f1 = self.fx_volume if abs(self.fx_volume - f1) < 0.002 else f1
        self._fx_volume_now = f1
        mix: bytes | None = None
        for slot in list(self._fx):
            frame = slot.layer.pull()
            if frame == EOF:
                self._remove_fx_locked(slot)
                continue
            if frame is None:
                continue
            g0, g1 = slot.step()
            a0, a1 = slot.glide(alpha)
            part = _scale(frame, g0 * a0 * f0, g1 * a1 * f1)
            mix = part if mix is None else audioop.add(mix, part, 2)
            if slot.leaving and not slot.fading:
                self._remove_fx_locked(slot)
        return mix

    def _remove_fx_locked(self, slot: _FxSlot) -> None:
        if slot in self._fx:
            self._fx.remove(slot)
        slot.layer.close()

    def _activate_pending_locked(self, events: list) -> None:
        pending = self._pending
        if pending is None:
            return
        state = pending.layer.state()
        if state == "eof" or (state == "wait" and time.monotonic() - pending.created > START_TIMEOUT):
            log.warning("A queued track produced no audio, dropping it")
            self._drop_pending_locked()
            return
        if state != "data":
            return
        fade_in, fade_out = pending.fade_in, pending.fade_out
        if pending.after is not None:
            current = next((s for s in self._slots if s.layer is pending.after and not s.leaving), None)
            if current is not None:
                left = current.layer.remaining()
                if left is not None and left > pending.fade:
                    return                      # not yet time
                fade_in = fade_out = min(pending.fade, max(left if left is not None else 0.0, FRAME_SECONDS))
            else:
                fade_in = fade_out = 0.0        # the track before it ended first: just carry on
        self._pending = None
        for slot in list(self._slots):
            if slot.leaving:
                continue
            if fade_out <= 0:
                self._remove_locked(slot)
            else:
                slot.fade(0.0, _frames(fade_out))
        slot = _Slot(pending.layer, 0.0 if fade_in > 0 else 1.0)
        if fade_in > 0:
            slot.fade(1.0, _frames(fade_in))
        self._slots.append(slot)
        while len(self._slots) > MAX_SLOTS:     # keep the number of ffmpeg processes bounded
            leaving = [s for s in self._slots if s.leaving]
            if not leaving:
                break
            self._remove_locked(min(leaving, key=lambda s: s.level))
        if pending.token is not None and self._on_transition:
            events.append((self._on_transition, pending.token))

    def _remove_locked(self, slot: _Slot) -> None:
        if slot in self._slots:
            self._slots.remove(slot)
        slot.layer.close()

    def _drop_pending_locked(self) -> None:
        if self._pending is not None:
            self._pending.layer.close()
            self._pending = None
