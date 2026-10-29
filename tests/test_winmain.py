"""The Windows launcher and the platform helpers. Only the standard library is needed, so these also run with
scripts/dev/run_tests.py, and they run on every platform."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from app import hostenv, winmain
from app.config import Settings


def test_data_folder_is_slash_data_in_the_container_and_local_app_data_on_windows():
    assert hostenv.default_data_dir("linux") == Path("/data")
    path = hostenv.default_data_dir("win32", {"LOCALAPPDATA": "/users/ola/local"})
    assert path.parts[-2:] == ("Melomancer", "data") and path.parts[-3] == "local"
    fallback = hostenv.default_data_dir("win32", {}, home=Path("/users/ola"))
    assert fallback.parts[-4:] == ("AppData", "Local", "Melomancer", "data")


def test_the_config_file_sits_next_to_the_data_folder():
    path = hostenv.default_config_path("win32", {"LOCALAPPDATA": "/users/ola/local"})
    assert path.name == "config.toml" and path.parent.name == "Melomancer"


def test_settings_use_the_platform_default_only_without_data_dir(monkeypatch):
    monkeypatch.setattr(os, "environ", {"DATA_DIR": ""})
    assert Settings.from_env().data_dir == hostenv.default_data_dir()
    monkeypatch.setattr(os, "environ", {"DATA_DIR": "/somewhere/else"})
    assert Settings.from_env().data_dir == Path("/somewhere/else")


def test_keys_become_environment_variables_and_the_environment_wins():
    environ = {"ADMIN_USERNAME": "from-env"}
    values = {"discord_token": "abc", "admin_username": "from-file", "ytdlp_enabled": False, "max_upload_mb": 50,
              "ytdlp_allowed_hosts": ["youtube.com", "bandcamp.com"], "host": "0.0.0.0", "port": 9000,
              "nested": {"ignored": 1}}
    applied = winmain.apply_config(values, environ)
    assert environ["DISCORD_TOKEN"] == "abc"
    assert environ["ADMIN_USERNAME"] == "from-env"            # already set: the file does not override it
    assert environ["YTDLP_ENABLED"] == "false" and environ["MAX_UPLOAD_MB"] == "50"
    assert environ["YTDLP_ALLOWED_HOSTS"] == "youtube.com,bandcamp.com"
    assert "HOST" not in environ and "PORT" not in environ and "NESTED" not in environ  # launcher keys, tables
    assert sorted(applied) == ["DISCORD_TOKEN", "MAX_UPLOAD_MB", "YTDLP_ALLOWED_HOSTS", "YTDLP_ENABLED"]


def test_the_template_is_valid_and_changes_nothing_until_a_line_is_uncommented(tmp_path):
    path = tmp_path / "sub" / "config.toml"
    assert winmain.ensure_config(path) is True
    assert winmain.ensure_config(path) is False                 # never overwrites what the person edited
    assert winmain.read_config(path) == {}
    # every example line, uncommented, is valid TOML with the value the comment promises
    lines = [l[2:] for l in winmain.TEMPLATE.splitlines() if l.startswith("# ") and " = " in l]
    assert lines, "the template shows its keys"
    parsed = winmain.tomllib.loads("\n".join(lines))
    assert parsed["port"] == 8080 and parsed["host"] == "127.0.0.1" and parsed["data_dir"].endswith("data")
    assert "\\" in parsed["music_dir"] and "\\\\" not in parsed["music_dir"]   # single quotes keep Windows paths as typed


def test_a_broken_file_gives_a_message_not_a_traceback(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("port = = 1", encoding="utf-8")
    try:
        winmain.read_config(path)
    except SystemExit as exc:
        assert "not valid TOML" in str(exc) and str(path) in str(exc)
    else:
        raise AssertionError("a broken file must stop the start")


def test_port_must_be_a_real_port():
    assert winmain.parse_port("8081") == 8081 and winmain.parse_port(9000) == 9000
    for bad in ("abc", 0, 70000, None):
        try:
            winmain.parse_port(bad)
        except SystemExit:
            continue
        raise AssertionError(f"{bad!r} must be refused")


def test_bundled_tools_come_first_on_the_path_and_the_version_is_read(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "VERSION").write_text("0.7.1\n", encoding="utf-8")
    environ = {"PATH": "/usr/bin"}
    winmain.prepare_path(tmp_path, environ)
    winmain.read_version(tmp_path, environ)
    assert environ["PATH"].split(os.pathsep)[0] == str(tmp_path / "bin") and environ["APP_VERSION"] == "0.7.1"
    other = {"APP_VERSION": "9.9.9"}
    winmain.read_version(tmp_path, other)
    assert other["APP_VERSION"] == "9.9.9"                      # an explicit setting is not replaced
    empty = {"PATH": "/usr/bin"}
    winmain.prepare_path(tmp_path / "nowhere", empty)
    assert empty["PATH"] == "/usr/bin"


def test_only_the_harmless_windows_connection_reset_is_hidden():
    def record(exc):
        info = (type(exc), exc, None) if exc else None
        return logging.LogRecord("asyncio", logging.ERROR, __file__, 1, "Exception in callback", None, info)

    quiet = winmain.QuietConnectionResets()
    reset = ConnectionResetError(10054, "forcibly closed by the remote host")
    assert quiet.filter(record(reset)) is False
    other = ConnectionResetError(104, "connection reset by peer")
    assert quiet.filter(record(other)) is True                    # a reset with another code is not this noise
    assert quiet.filter(record(RuntimeError("boom"))) is True
    assert quiet.filter(record(None)) is True
