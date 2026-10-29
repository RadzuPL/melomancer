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


def test_the_build_marker_is_read_when_there_is_one(tmp_path):
    assert winmain.read_build(tmp_path) == ""
    (tmp_path / "BUILD").write_text("build 12, 3f2a1c9\n", encoding="utf-8")
    assert winmain.read_build(tmp_path) == "build 12, 3f2a1c9"


def test_the_template_has_the_client_id_and_both_languages():
    text = winmain.TEMPLATE
    assert "# discord_client_id = ''" in text and "# discord_token = ''" in text
    assert "Ustawienia Melomancera" in text and "Melomancer settings" in text


def test_the_template_is_cut_into_paragraphs_with_their_setting_names():
    blocks = winmain.template_blocks()
    names = [n for block in blocks for n in block[0]]
    for wanted in ("discord_token", "discord_client_id", "admin_password", "host", "port", "data_dir", "music_dir",
                   "auto_login", "ytdlp_enabled", "log_level"):
        assert wanted in names, wanted
    assert len(names) == len(set(names)), "a setting is shown once"
    assert all(text.startswith("#") for _, text in blocks)


def test_an_older_settings_file_gets_the_missing_settings_as_comments(tmp_path):
    path = tmp_path / "config.toml"
    old = "# my own notes\n# discord_token = ''\ndiscord_client_id = '123456789012345678'\nport = 9000\n"
    path.write_text(old, encoding="utf-8")
    added = winmain.sync_config(path, "0.7.0")
    text = path.read_text(encoding="utf-8")
    assert text.startswith(old.rstrip("\n"))                                  # what the person wrote is untouched
    assert "auto_login" in added and "ytdlp_enabled" in added and "log_level" in added
    assert "discord_token" not in added and "discord_client_id" not in added and "port" not in added  # already there
    assert text.count("# discord_token = ''") == 1 and text.count("discord_client_id") == 1
    assert "Added by Melomancer 0.7.0" in text and "# auto_login = true" in text
    assert winmain.read_config(path) == {"discord_client_id": "123456789012345678", "port": 9000}   # still valid TOML
    assert winmain.sync_config(path, "0.7.0") == []                           # a second start adds nothing


def test_a_fresh_template_and_a_missing_file_need_no_sync(tmp_path):
    path = tmp_path / "config.toml"
    assert winmain.sync_config(path) == []
    winmain.ensure_config(path)
    assert winmain.sync_config(path) == [] and path.read_text(encoding="utf-8") == winmain.TEMPLATE


def test_a_bom_is_ignored_and_a_wrong_encoding_gives_a_message(tmp_path):
    path = tmp_path / "config.toml"
    path.write_bytes(b"\xef\xbb\xbfport = 9001\n")                          # Notepad's "UTF-8 with BOM"
    assert winmain.read_config(path) == {"port": 9001}
    path.write_bytes("# zażółć\nport = 9002\n".encode("cp1250"))              # an old Notepad's "ANSI"
    try:
        winmain.read_config(path)
    except SystemExit as exc:
        assert "UTF-8" in str(exc)
    else:
        raise AssertionError("a file in the wrong encoding must give a message")


def test_the_line_endings_of_the_persons_file_are_kept(tmp_path):
    crlf = tmp_path / "crlf.toml"
    crlf.write_bytes(b"# my notes\r\nport = 9000\r\n")                     # what Notepad writes
    assert winmain.sync_config(crlf, "1.0")
    data = crlf.read_bytes()
    assert data.startswith(b"# my notes\r\nport = 9000\r\n\r\n# --- Dodane")
    assert b"\r\r" not in data and data.count(b"\n") == data.count(b"\r\n")   # every line ends the same way, none doubled
    assert winmain.read_config(crlf) == {"port": 9000} and winmain.sync_config(crlf, "1.0") == []
    lf = tmp_path / "lf.toml"
    lf.write_bytes(b"# my notes\nport = 9000\n")
    winmain.sync_config(lf, "1.0")
    assert b"\r" not in lf.read_bytes()
