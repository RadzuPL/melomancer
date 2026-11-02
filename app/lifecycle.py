"""Lets a part of the program ask for the program to end: the launcher says how, the update installer asks.

Only the launcher knows what is running (the tray icon with the server in a thread, or the server in a console), so it
registers the way to stop it here, and the rest of the application stays free of that knowledge.
"""
from __future__ import annotations

from typing import Callable

_hook: Callable[[], None] | None = None
_original_env: dict[str, str] | None = None


def set_quit_hook(hook: Callable[[], None] | None) -> None:
    global _hook
    _hook = hook


def set_original_env(env: dict[str, str]) -> None:
    """The environment the program was started with, before the launcher added the settings file, the version and the
    path of the bundled tools to it. A new version started by the update helper must get this one: with the launcher's
    additions (APP_VERSION, DISCORD_TOKEN ...) it would take the old version number and the old settings for its own."""
    global _original_env
    _original_env = dict(env)


def original_env() -> dict[str, str] | None:
    return None if _original_env is None else dict(_original_env)


def request_quit() -> bool:
    """Asks the program to end (the web server stops, which ends everything else). False when nobody registered."""
    if _hook is None:
        return False
    _hook()
    return True
