"""The background mode (app/tray.py): everything that does not need a screen. Windows-only parts run only on Windows."""
from __future__ import annotations

import logging
import socket
import urllib.request
from pathlib import Path

from app import hostenv, tray


def test_polish_windows_gets_polish_texts_and_every_other_language_english():
    assert tray.ui_language(0x0415) == "pl"       # Polish (Poland)
    assert tray.ui_language(0x0809) == "en" and tray.ui_language(0x0407) == "en"
    assert set(tray.TEXTS["pl"]) == set(tray.TEXTS["en"]), "every text exists in both languages"


def test_the_icon_knows_about_a_newer_version_only_when_the_checker_says_so():
    from app import lifecycle
    try:
        lifecycle.set_update_info(None)
        assert lifecycle.pending_update() is None, "nobody registered"
        lifecycle.set_update_info(lambda: {"available": True, "latest": "0.9.1"})
        assert lifecycle.pending_update() == "0.9.1"
        lifecycle.set_update_info(lambda: {"available": False, "latest": "0.9.1"})
        assert lifecycle.pending_update() is None, "the newest release is not above the running version"
        lifecycle.set_update_info(lambda: {"available": True, "latest": None})
        assert lifecycle.pending_update() is None

        def broken():
            raise RuntimeError("the checker failed")
        lifecycle.set_update_info(broken)
        assert lifecycle.pending_update() is None, "a failing checker never takes the icon down"
    finally:
        lifecycle.set_update_info(None)


def test_the_autostart_command_uses_the_bundled_pythonw_and_does_not_open_the_browser():
    command = tray.autostart_command(Path("C:/Programy/Melomancer"))
    assert command.startswith('"') and command.endswith("-m app.winmain --no-browser")
    assert "pythonw.exe" in command and "runtime" in command


def test_the_start_failed_message_names_the_address_and_the_log():
    text = tray.start_failed_text("http://127.0.0.1:8080/", Path("C:/logs/melomancer.log"), "pl")
    assert "http://127.0.0.1:8080/" in text and "melomancer.log" in text and "port = 8081" in text


def test_logging_goes_to_a_file_and_replaces_whatever_handlers_were_there(tmp_path):
    root = logging.getLogger()
    before = list(root.handlers), root.level
    try:
        path = tray.setup_logging(tmp_path / "logs", "INFO", console=False)
        assert path == tmp_path / "logs" / "melomancer.log" and path.parent.is_dir()
        logging.getLogger("melomancer.test").info("Zażółć gęślą jaźń")
        for handler in root.handlers:
            handler.flush()
        assert "Zażółć gęślą jaźń" in path.read_text(encoding="utf-8")
        assert len(root.handlers) == 1
        tray.setup_logging(tmp_path / "logs", "WARNING", console=False)
        assert root.level == logging.WARNING and len(root.handlers) == 1   # a second call does not pile handlers up
    finally:
        for handler in list(root.handlers):
            handler.close()
            root.removeHandler(handler)
        for handler in before[0]:
            root.addHandler(handler)
        root.setLevel(before[1])


def test_the_icon_is_an_image_of_the_asked_size():
    try:
        image = tray.make_icon_image(32)
    except ImportError:    # Pillow is a dependency of the Windows package only
        return
    assert image.size == (32, 32) and image.mode == "RGBA"
    assert image.getpixel((16, 2))[3] == 255 and image.getpixel((0, 0))[3] == 0   # opaque body, transparent corner


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_the_server_runs_in_a_thread_and_stops_when_asked(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ADMIN_PASSWORD", "password-for-tests-1")
    monkeypatch.setenv("DISCORD_TOKEN", "")
    port = free_port()
    server = tray.ServerThread("127.0.0.1", port)
    server.start()
    try:
        assert server.wait_started(60), server.error
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=10) as response:
            assert response.status == 200
    finally:
        server.stop()
    assert not server.is_alive() and server.error is None


def test_a_port_that_is_taken_ends_the_thread_instead_of_hanging(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DISCORD_TOKEN", "")
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        server = tray.ServerThread("127.0.0.1", taken.getsockname()[1])
        server.start()
        assert server.wait_started(30) is False
        server.join(10)
        assert not server.is_alive() and server.error is not None


def test_start_with_windows_is_a_value_in_the_users_own_run_key():
    if not hostenv.IS_WINDOWS:
        return
    name = "MelomancerTestEntry"
    try:
        assert tray.autostart_enabled(name) is False
        tray.set_autostart(True, '"C:\\a\\pythonw.exe" -m app.winmain', name)
        assert tray.autostart_enabled(name) is True
        assert tray.refresh_autostart('"C:\\b\\pythonw.exe" -m app.winmain', name) is True     # the folder moved
        assert tray.autostart_registered(name) == '"C:\\b\\pythonw.exe" -m app.winmain'
        assert tray.refresh_autostart('"C:\\b\\pythonw.exe" -m app.winmain', name) is False    # nothing to do
    finally:
        tray.set_autostart(False, "", name)
    assert tray.autostart_enabled(name) is False
    tray.set_autostart(False, "", name)                                                     # removing twice is fine
    assert tray.refresh_autostart("anything", name) is False                                 # switched off: stays off


def test_only_one_instance_holds_the_mutex():
    if not hostenv.IS_WINDOWS:
        return
    name = "Local\\Melomancer-test-single-instance"
    first = tray.SingleInstance(name)
    second = tray.SingleInstance(name)
    assert first.already_running is False and second.already_running is True
