"""Windows background mode: no console window, an icon next to the clock instead.

The web server runs in a thread of the same process; the main thread belongs to the tray icon (pystray). Around that:
one copy at a time (a second start only opens the panel), the log goes to a file, a start that fails says so in a
message box (there is no console to print to), and "Start with Windows" is a value in the person's own Run key
(no administrator rights, nothing outside their profile).

Everything that needs Windows or the GUI libraries is imported where it is used, so that the logic around it can be
tested anywhere.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

from . import hostenv

log = logging.getLogger("melomancer.tray")
LAUNCHER_LOGGER = "melomancer.launcher"

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "Melomancer"
MUTEX_NAME = "Local\\Melomancer-single-instance"
ERROR_ALREADY_EXISTS = 183

TEXTS = {
    "pl": {
        "open": "Otwórz Melomancera", "settings": "Otwórz plik ustawień", "logs": "Pokaż pliki z logami",
        "autostart": "Uruchamiaj z Windows", "quit": "Zamknij Melomancera",
        "running": "Melomancer działa. Kliknij ikonę przy zegarze, żeby otworzyć panel.",
        "stopped": "Melomancer się zatrzymał. Szczegóły są w plikach z logami (menu ikony nie jest już dostępne).",
        "no_start": ("Melomancer nie mógł wystartować.\n\nNajczęstsza przyczyna: inny program używa adresu {url}. "
                     "Zmień port w pliku ustawień (port = 8081) i uruchom ponownie.\n\nSzczegóły: {log}"),
        "no_tray": ("Melomancer działa w tle, ale nie udało się pokazać ikony przy zegarze, więc nie da się go zamknąć "
                    "z jej menu. Zamknij go w Menedżerze zadań (proces pythonw.exe) albo uruchom tryb diagnostyczny.\n\n"
                    "Szczegóły: {log}"),
    },
    "en": {
        "open": "Open Melomancer", "settings": "Open the settings file", "logs": "Show the log files",
        "autostart": "Start with Windows", "quit": "Quit Melomancer",
        "running": "Melomancer is running. Click the icon next to the clock to open the panel.",
        "stopped": "Melomancer has stopped. The log files say why (the icon menu is no longer available).",
        "no_start": ("Melomancer could not start.\n\nThe most likely reason: another program uses the address {url}. "
                     "Change the port in the settings file (port = 8081) and start again.\n\nDetails: {log}"),
        "no_tray": ("Melomancer is running in the background, but the icon next to the clock could not be shown, so it "
                    "cannot be closed from its menu. Close it in the Task Manager (the process pythonw.exe) or use the "
                    "diagnostic mode.\n\nDetails: {log}"),
    },
}


def start_failed_text(url: str, log_path: Path, lang: str | None = None) -> str:
    return TEXTS[lang or ui_language()]["no_start"].format(url=url, log=log_path)


def ui_language(lang_id: int | None = None) -> str:
    """"pl" when Windows is set to Polish, otherwise "en". The primary language id of Polish is 0x15."""
    if lang_id is None:
        try:
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        except (AttributeError, OSError):
            return "en"
    return "pl" if (lang_id & 0x3FF) == 0x15 else "en"


# ---- start with Windows --------------------------------------------------------------------------------------------

def autostart_command(home: Path) -> str:
    """What Windows runs at sign-in: the bundled pythonw (no console), without opening the browser."""
    return f'"{home / "runtime" / "pythonw.exe"}" -m app.winmain --no-browser'


def autostart_enabled(name: str = AUTOSTART_NAME) -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, name)
            return True
    except FileNotFoundError:
        return False


def autostart_registered(name: str = AUTOSTART_NAME) -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return str(winreg.QueryValueEx(key, name)[0])
    except FileNotFoundError:
        return None


def set_autostart(enabled: bool, command: str, name: str = AUTOSTART_NAME) -> None:
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass


def refresh_autostart(command: str, name: str = AUTOSTART_NAME) -> bool:
    """If "start with Windows" is on but points somewhere else (the folder was moved or a newer package unpacked
    elsewhere), point it here. Returns True when it was changed."""
    current = autostart_registered(name)
    if current is not None and current != command:
        set_autostart(True, command, name)
        return True
    return False


# ---- one copy at a time ----------------------------------------------------------------------------------------------

class SingleInstance:
    """A named mutex of the person's session. `already_running` is true when another Melomancer holds it."""

    def __init__(self, name: str = MUTEX_NAME) -> None:
        self.already_running = False
        self._handle = None
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            self._handle = kernel32.CreateMutexW(None, False, name)
            self.already_running = kernel32.GetLastError() == ERROR_ALREADY_EXISTS
        except (AttributeError, OSError):
            pass   # not Windows: no protection, which is fine


def message_box(title: str, text: str, error: bool = True) -> None:
    """A window with the message: with no console there is nowhere else to say it."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10 if error else 0x40)   # MB_ICONERROR / MB_ICONINFORMATION
    except (AttributeError, OSError):
        print(f"{title}: {text}", file=sys.stderr)


# ---- the server in a thread --------------------------------------------------------------------------------------------

class ServerThread(threading.Thread):
    """Runs uvicorn (the web server, with the bot and the workers in its lifespan) beside the tray icon."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__(name="melomancer-server", daemon=True)
        import uvicorn
        # log_config=None: uvicorn's own handlers write to the console, which does not exist here; its messages reach
        # the root logger (the log file) instead.
        config = uvicorn.Config("app.main:app_factory", factory=True, host=host, port=port, log_config=None,
                                log_level="warning")
        self.server = uvicorn.Server(config)
        self.error: BaseException | None = None

    def run(self) -> None:
        try:
            self.server.run()
        except BaseException as exc:   # noqa: BLE001 - uvicorn leaves a failed start with SystemExit
            self.error = exc
            log.error("The server stopped: %r", exc)

    def wait_started(self, timeout: float = 60.0) -> bool:
        """True once it listens; False when the thread ended first (a port in use) or the time ran out."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.server.started:
                return True
            if not self.is_alive():
                return False
            time.sleep(0.1)
        return False

    def stop(self, timeout: float = 20.0) -> None:
        self.server.should_exit = True
        self.join(timeout)


# ---- the icon ----------------------------------------------------------------------------------------------------------

def make_icon_image(size: int = 64):
    """A blue rounded square with a white eighth note, drawn here so that there is no image file to ship.

    Drawn four times larger and scaled down, so that the small tray size has smooth edges."""
    from PIL import Image, ImageDraw
    big = size * 4
    scale = big / 64
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2 * scale, 2 * scale, 62 * scale, 62 * scale), radius=14 * scale, fill=(22, 104, 220, 255))
    draw.ellipse((15 * scale, 37 * scale, 32 * scale, 50 * scale), fill="white")
    draw.rectangle((28 * scale, 13 * scale, 33 * scale, 44 * scale), fill="white")
    draw.polygon([(33 * scale, 13 * scale), (47 * scale, 22 * scale), (47 * scale, 31 * scale), (33 * scale, 24 * scale)],
                 fill="white")
    return image.resize((size, size), Image.LANCZOS)


def open_path(path: Path) -> None:
    if hasattr(os, "startfile"):
        os.startfile(str(path))   # noqa: S606 - Explorer / Notepad, as the person would


def run_tray(*, url: str, version: str, home: Path, config: Path, logs_dir: Path, server: ServerThread,
             open_browser: bool, lang: str | None = None) -> int:
    """Shows the icon and blocks until the person quits (or the server dies). Returns the exit code."""
    text = TEXTS[lang or ui_language()]
    command = autostart_command(home)
    try:
        refresh_autostart(command)
    except OSError:
        log.debug("Could not refresh the autostart entry", exc_info=True)

    try:
        import pystray
        image = make_icon_image()
    except Exception:   # noqa: BLE001 - missing GUI libraries must not take the program down
        log.exception("The tray icon is not available")
        message_box("Melomancer", text["no_tray"].format(log=logs_dir / "melomancer.log"), error=False)
        if open_browser:
            webbrowser.open(url)
        server.join()
        return 0 if server.error is None else 1

    def toggle_autostart(icon, item) -> None:
        try:
            set_autostart(not autostart_enabled(), command)
        except OSError:
            log.exception("Could not change the autostart entry")

    stopping = threading.Event()

    def quit_program(icon, item) -> None:
        stopping.set()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(text["open"], lambda icon, item: webbrowser.open(url), default=True),
        pystray.MenuItem(text["settings"], lambda icon, item: open_path(config)),
        pystray.MenuItem(text["logs"], lambda icon, item: open_path(logs_dir)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(text["autostart"], toggle_autostart, checked=lambda item: autostart_enabled()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"Melomancer {version}", lambda icon, item: None, enabled=False),
        pystray.MenuItem(text["quit"], quit_program),
    )
    icon = pystray.Icon("Melomancer", image, f"Melomancer {version}", menu)

    def watch(_icon) -> None:
        _icon.visible = True
        log.info("Tray icon ready")
        try:
            _icon.notify(text["running"], "Melomancer")
        except Exception:   # noqa: BLE001 - a notification is a courtesy
            log.debug("The notification could not be shown", exc_info=True)
        if open_browser:
            webbrowser.open(url)
        while server.is_alive() and not stopping.is_set():
            time.sleep(1)
        if not stopping.is_set():   # the server ended by itself
            log.error("The server is gone, closing the icon")
            message_box("Melomancer", text["stopped"])
            _icon.stop()

    try:
        icon.run(setup=watch)   # pystray runs the setup callback in a thread of its own
    except Exception:   # noqa: BLE001
        log.exception("The tray icon failed")
        message_box("Melomancer", text["no_tray"].format(log=logs_dir / "melomancer.log"), error=False)
        server.join()
    stopping.set()
    return 0 if server.error is None else 1


def setup_logging(logs_dir: Path, level: str = "INFO", console: bool = False) -> Path:
    """The log file (rotated, UTF-8) next to the settings; the console too when there is one."""
    from logging.handlers import RotatingFileHandler
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / "melomancer.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    for old in list(root.handlers):
        root.removeHandler(old)
    handlers: list[logging.Handler] = [RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")]
    if console and sys.stderr is not None:
        stream = logging.StreamHandler()
        stream.addFilter(lambda record: record.name != LAUNCHER_LOGGER)   # the banner is printed, not logged twice
        handlers.append(stream)
    for handler in handlers:
        handler.setFormatter(fmt)
        root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    return path
