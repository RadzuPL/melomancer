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
import logging
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
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
DEFAULT_PORT = 8080
LAUNCHER_KEYS = ("host", "port")   # read by the launcher itself, not passed on as environment variables

TEMPLATE = """\
# Ustawienia Melomancera. Usuń # sprzed linii, żeby jej użyć, i uruchom Melomancera ponownie.
# Melomancer settings. Remove the # in front of a line to use it, then start Melomancer again.
# Nazwy to zmienne środowiskowe małymi literami / the names are environment variables in lower case:
# docs/pl/configuration.md, docs/en/configuration.md
# Ścieżki Windows w pojedynczych cudzysłowach / use single quotes for Windows paths: 'D:\\Music\\Melomancer'

# Token bota z https://discord.com/developers/applications (jak go zdobyć: docs/pl/discord-bot.md).
# Bez tokena panel działa, a bot zostaje offline.
# Bot token from https://discord.com/developers/applications (how to get it: docs/en/discord-bot.md).
# Without it the panel works and the bot stays offline.
# discord_token = ''

# Application ID bota (Developer Portal, General Information). Dzięki niemu Ustawienia pokazują link "Dodaj bota do serwera".
# The bot's Application ID (Developer Portal, General Information). With it Settings shows an "Add the bot to a server" link.
# discord_client_id = ''

# Pierwszy administrator, tworzony tylko przy pustej bazie (hasło min. 10 znaków). Bez hasła powstaje losowe,
# pokazane raz w oknie. / The first administrator, created only while the database is empty (password at least 10
# characters). Without a password a random one is generated and shown once in the window.
# admin_username = 'admin'
# admin_password = ''

# Gdzie nasłuchuje panel. 127.0.0.1 to tylko ten komputer. 0.0.0.0 otwiera panel dla sieci (Windows zapyta o zaporę).
# Where the panel listens. 127.0.0.1 is this computer only. 0.0.0.0 opens it to your network (Windows will ask about the firewall).
# host = '127.0.0.1'
# port = 8080

# Logowanie bez hasła: panel wpuszcza ten komputer jako administratora (tylko przy host 127.0.0.1, nigdy przez tunel ani
# proxy). Wpisz false, żeby wymagać hasła. / Signing in without a password: the panel lets this computer in as the
# administrator (only with host 127.0.0.1, never through a tunnel or a proxy). Set false to require the password.
# auto_login = true

# Foldery. Domyślny folder danych to %LOCALAPPDATA%\\Melomancer\\data (baza i, o ile nie ustawiono music_dir, muzyka).
# Folders. The default data folder is %LOCALAPPDATA%\\Melomancer\\data (database and, unless music_dir is set, the music).
# data_dir = 'D:\\Melomancer\\data'
# music_dir = 'D:\\Music\\Melomancer'

# Pobieranie z YouTube i innych serwisów (yt-dlp) / downloads from YouTube and other sites (yt-dlp).
# ytdlp_enabled = true
# ytdlp_daily_limit = 50
# ytdlp_min_gap_seconds = 20

# Inne / other: największy plik w MB, po ilu minutach bot opuszcza pusty kanał (0 oznacza nigdy), głośność startowa 0.0-1.5.
# Largest file in MB, minutes before the bot leaves an empty channel (0 means never), starting volume 0.0-1.5.
# max_upload_mb = 300
# idle_leave_minutes = 30
# default_volume = 0.4
# log_level = 'INFO'
"""


class QuietConnectionResets(logging.Filter):
    """Windows' event loop logs "WinError 10054" as an ERROR with a traceback whenever a browser drops a connection it
    had open (closing a tab, seeking in the audio it streams). Nothing is wrong, so that one message is not shown."""

    def filter(self, record: logging.LogRecord) -> bool:
        exc = record.exc_info[1] if record.exc_info else None
        reset = isinstance(exc, ConnectionResetError) and 10054 in (getattr(exc, "winerror", None), exc.errno)
        return not reset


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


def read_build(home: Path) -> str:
    """The text of the BUILD file ("build 12, 3f2a1c9") when the package has one, else an empty string."""
    marker = home / "BUILD"
    return marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""


def decide_auto_login(host: str, environ: MutableMapping[str, str]) -> str:
    """Sets AUTO_LOGIN for this run and returns what to tell the person ("" for nothing).

    On by default for a desktop run on the loopback address: the panel opens as the administrator without a password.
    Never when the panel listens for other computers, whatever the settings say.
    """
    loopback = host in LOOPBACK_HOSTS
    wanted = environ.get("AUTO_LOGIN", "").strip().lower()
    if wanted == "":
        environ["AUTO_LOGIN"] = "true" if loopback else "false"
    elif wanted in ("1", "true", "yes", "on") and not loopback:
        environ["AUTO_LOGIN"] = "false"
        return (f"auto_login is ignored because the panel listens on {host}, not only on this computer: "
                "everyone who can reach it must sign in with a password.")
    return ""


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

    # A path or a title with a letter the console's code page lacks must never stop the program, only print as "?".
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    logging.getLogger("asyncio").addFilter(QuietConnectionResets())

    home = Path(__file__).resolve().parents[1]
    prepare_path(home, os.environ)
    read_version(home, os.environ)

    config = Path(args.config or os.environ.get("MELOMANCER_CONFIG") or default_config_path())
    created = ensure_config(config)
    values = read_config(config)
    host = args.host or str(values.get("host") or DEFAULT_HOST)
    port = parse_port(args.port or values.get("port") or DEFAULT_PORT)
    apply_config(values, os.environ)
    auto_login_note = decide_auto_login(host, os.environ)

    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}/"
    build = read_build(home)
    print(f"Melomancer {os.environ.get('APP_VERSION', 'dev')}" + (f" ({build})" if build else ""))
    print(f"Settings file: {config}" + ("  (created now, edit it to add your Discord bot token)" if created else ""))
    print(f"Panel: {url}   (Ctrl+C or closing this window stops it)")
    if auto_login_note:
        print("Note: " + auto_login_note)
    elif os.environ.get("AUTO_LOGIN") == "true":
        print("The panel lets this computer in as the administrator without a password (auto_login = false in the "
              "settings file turns that off).")

    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()

    import uvicorn  # imported late: --help and the config handling work without the web stack
    uvicorn.run("app.main:app_factory", factory=True, host=host, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
