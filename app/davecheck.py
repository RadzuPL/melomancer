"""Detects the library pairing that joins a voice channel and then stays silent.

davey 0.2 stopped installing the encryption key inside ``process_commit`` / ``process_welcome``: the caller has to
call ``prepare_transition`` and ``execute_transition``. discord.py 2.7.1 does not, so the bot connects, even lights up
as speaking, and nothing is heard. No error is logged anywhere, which is why the pairing is worth a warning of its own.
Standard library only.
"""
from __future__ import annotations

import re
from pathlib import Path

VOICE_FILES = ("voice_state.py", "gateway.py")


def _major_minor(version: str) -> tuple[int, int]:
    major, minor = ([int(n) for n in re.findall(r"\d+", version)[:2]] + [0, 0])[:2]
    return major, minor


def silent_voice_problem(davey_version: str | None, discord_dir: Path | str | None) -> str | None:
    """A warning text when davey 0.2 or newer meets a discord.py that never prepares transitions, else None.

    Unknown means fine: a missing package, an unreadable folder or a layout without the voice files give None, so
    this can only warn about a pairing it actually saw.
    """
    if not davey_version or not discord_dir:
        return None
    if _major_minor(davey_version) < (0, 2):
        return None
    source = ""
    for name in VOICE_FILES:
        try:
            source += (Path(discord_dir) / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    if not source or "prepare_transition" in source:
        return None
    return (
        f"davey {davey_version} needs prepare_transition, which this discord.py never calls: the bot will join "
        "voice and play in silence. Install davey<0.2 until discord.py supports it."
    )
