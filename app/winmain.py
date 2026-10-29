"""Starts Melomancer on a desktop: a small web server on this computer plus the Discord bot, no container.

    runtime\\python.exe -m app.winmain            (what Melomancer.cmd in the Windows package runs)

The same application as in the container. What differs is only where it finds things: settings come from a
`config.toml` (created with explanations on the first start) instead of environment variables, the data lives in
%LOCALAPPDATA%\\Melomancer, ffmpeg and deno are looked up in the `bin` folder of the package, and the panel listens on
127.0.0.1 so that Windows has no reason to ask about the firewall. An environment variable that is already set always
wins over the file.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import tomllib
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, MutableMapping

from .hostenv import default_config_path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
LAUNCHER_KEYS = ("host", "port")   # read by the launcher itself, not passed on as environment variables

TEMPLATE = """\
# Melomancer settings. Remove the # in front of a line to use it, then start Melomancer again.
# Every other name is an environment variable in lower case, see docs/en/configuration.md for the list.
# Use single quotes for Windows paths: 'D:\\Music\\Melomancer'

# Bot token from https://discord.com/developers/applications (how to get it: docs/en/discord-bot.md).
# Without it the panel works and the bot stays offline.
# discord_token = ''

# The first administrator, created only while the database is empty (at least 10 characters).
# Without a password a random one is generated and written once to the window that runs Melomancer.
# admin_username = 'admin'
# admin_password = ''

# Where the panel listens. 127.0.0.1 is this computer only. 0.0.0.0 opens it to your network, and Windows
# will then ask whether to allow it through the firewall.
# host = '127.0.0.1'
# port = 8080

# Folders. The default data folder is %LOCALAPPDATA%\\Melomancer\\data (database and, unless music_dir is set, the music).
# data_dir = 'D:\\Melomancer\\data'
# music_dir = 'D:\\Music\\Melomancer'
"""


def read_config(path: Path) -> dict[str, Any]:
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"{path} is not valid TOML: {exc}\nFix the file or delete it to get a fresh one.") from None


def env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def apply_config(values: dict[str, Any], environ: MutableMapping[str, str]) -> list[str]:
    """Sets NAME from `name = ...` unless the environment already has it. Returns the names that were set."""
    applied = []
    for key, value in values.items():
        if key in LAUNCHER_KEYS or isinstance(value, dict):
            continue
        name = key.upper()
        if name not in environ:
            environ[name] = env_value(value)
            applied.append(name)
    return applied


def ensure_config(path: Path) -> bool:
    """Writes the commented template when there is no file yet. True when it was created."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE, encoding="utf-8")
    return True


def prepare_path(home: Path, environ: MutableMapping[str, str]) -> None:
    """Puts the bundled tools first, so that "ffmpeg", "ffprobe" and "deno" are found wherever Melomancer is unpacked."""
    tools = home / "bin"
    if tools.is_dir():
        environ["PATH"] = str(tools) + os.pathsep + environ.get("PATH", "")


def read_version(home: Path, environ: MutableMapping[str, str]) -> None:
    marker = home / "VERSION"
    if "APP_VERSION" not in environ and marker.is_file():
        environ["APP_VERSION"] = marker.read_text(encoding="utf-8").strip()


def parse_port(value: Any) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise SystemExit(f"port must be a number, got {value!r}") from None
    if not 1 <= port <= 65535:
        raise SystemExit(f"port must be between 1 and 65535, got {port}")
    return port


def open_browser_when_ready(url: str, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "api/health", timeout=2):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="melomancer", description="Melomancer: music for tabletop RPG sessions.")
    parser.add_argument("--config", help="path of config.toml (default: next to the data folder)")
    parser.add_argument("--host", help=f"address to listen on (default {DEFAULT_HOST})")
    parser.add_argument("--port", help=f"port (default {DEFAULT_PORT})")
    parser.add_argument("--no-browser", action="store_true", help="do not open the panel in the browser")
    args = parser.parse_args(argv)

    home = Path(__file__).resolve().parents[1]
    prepare_path(home, os.environ)
    read_version(home, os.environ)

    config = Path(args.config or os.environ.get("MELOMANCER_CONFIG") or default_config_path())
    created = ensure_config(config)
    values = read_config(config)
    host = args.host or str(values.get("host") or DEFAULT_HOST)
    port = parse_port(args.port or values.get("port") or DEFAULT_PORT)
    apply_config(values, os.environ)

    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}/"
    print(f"Melomancer {os.environ.get('APP_VERSION', 'dev')}")
    print(f"Settings file: {config}" + ("  (created now, edit it to add your Discord bot token)" if created else ""))
    print(f"Panel: {url}   (Ctrl+C or closing this window stops it)")

    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()

    import uvicorn  # imported late: --help and the config handling work without the web stack
    uvicorn.run("app.main:app_factory", factory=True, host=host, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
