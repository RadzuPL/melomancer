"""What is played of a track: where it starts and ends. Shared by the Discord player and the browser player."""
from __future__ import annotations

MIN_PLAYED = 1.0  # a trim that would leave less than this of a track is ignored


def span(duration: float | None, lead: float, trail: float, trim_start: float | None, trim_end: float | None,
         automatic: bool, offset: float = 0.0) -> tuple[float, float | None, bool]:
    """(start, end, cut): where in the file the audio starts and ends, and whether the end is a cut.

    A start or end set by hand (`trim_start`, `trim_end`) wins over the silence analysis (`lead`, `trail`), each side on
    its own and whatever `automatic` (the administrator's switch) says; without one, the analysis applies while the
    switch is on. `offset` is a position the listener asked for (a seek), which replaces the start.
    """
    first = trim_start if trim_start is not None else (lead if automatic else 0.0)
    end = duration
    if duration:
        if trim_end is not None:
            end = min(trim_end, duration)
        elif automatic and trail:
            end = duration - trail
    start = offset if offset > 0 else first
    if duration and end - start < MIN_PLAYED:
        return offset, duration, False
    return start, end, bool(duration and end < duration - 0.01)


def entry(row, runtime) -> dict:
    """What the browser player needs of one track row: the part of the file to play and the loudness gain.

    Both are worked out here, with the same rules as the Discord player, so that the two never disagree.
    """
    from .loudness import linear_gain  # late: loudness imports the database layer

    start, end, cut = span(row["duration"], row["silence_lead"] or 0.0, row["silence_trail"] or 0.0,
                           row["trim_start"], row["trim_end"], runtime.trim_silence)
    gain = linear_gain(row["loudness"], row["peak"], runtime.target, runtime.max_boost) if runtime.normalize else 1.0
    return {"track_id": row["id"], "title": row["title"], "duration": row["duration"],
            "start": start, "end": end, "cut": cut, "gain": gain}
