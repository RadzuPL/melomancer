"""Setting up the Discord bot from the panel on a desktop run: the checks, the settings file and the API."""
from __future__ import annotations

import asyncio
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

import app.player as player_mod
from app.botsetup import SetupError, check_client_id, check_token, set_config_values
from app.config import Settings
from app.player import BotManager
from app.winmain import TEMPLATE

from .conftest import login, make_user

TOKEN = ".".join(["MTIzNDU2Nzg5MDEyMzQ1Njc4OQ", "GabcDE", "abcdefghijklmnopqrstuvwxyz0123456789"])   # made of parts: the shape of a token, but no secret scanner should take it for one
OTHER = ".".join(["MTk4NzY1NDMyMTA5ODc2NTQzMg", "GxyzAB", "ZYXWVUTSRQPONMLKJIHGFEDCBA9876543210"])


# ---- what was pasted ----------------------------------------------------------------------------------------

def test_a_token_is_cleaned_of_quotes_and_the_bot_prefix():
    assert check_token(f"  {TOKEN}  ") == TOKEN
    assert check_token(f'"{TOKEN}"') == TOKEN
    assert check_token(f"Bot {TOKEN}") == TOKEN
    assert check_token("   ") == ""   # empty means "remove"


@pytest.mark.parametrize("pasted, code", [
    ("123456789012345678", "token_is_app_id"),   # the Application ID in the token field
    ("0a1b2c3d4e5f60718293a4b5c6d7e8f9", "bad_token"),   # a Client Secret / Public Key looks like this
    ("not a token", "bad_token"),
    ("abc.def.ghi", "bad_token"),
    (TOKEN + " " + TOKEN, "bad_token"),
])
def test_things_that_are_not_a_token_are_named(pasted, code):
    with pytest.raises(SetupError) as caught:
        check_token(pasted)
    assert caught.value.code == code


def test_the_application_id_is_digits_or_empty():
    assert check_client_id(" 123456789012345678 ") == "123456789012345678"
    assert check_client_id("") == ""
    with pytest.raises(SetupError) as caught:
        check_client_id("my-bot")
    assert caught.value.code == "bad_client_id"


# ---- the settings file --------------------------------------------------------------------------------------

def test_the_commented_example_of_the_template_becomes_the_setting(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(TEMPLATE, encoding="utf-8")
    set_config_values(path, {"discord_token": TOKEN, "discord_client_id": "123456789012345678"})
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data == {"discord_token": TOKEN, "discord_client_id": "123456789012345678"}
    after = path.read_text(encoding="utf-8").splitlines()
    before = TEMPLATE.splitlines()
    assert len(after) == len(before)   # lines were replaced in place, none added
    assert sum(1 for a, b in zip(after, before) if a != b) == 2   # ... and only these two differ


def test_a_value_that_is_already_set_is_replaced_and_the_rest_is_untouched(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("# my note\nport = 9000\ndiscord_token = 'old'  # the old one\nlog_level = \"DEBUG\"\n", encoding="utf-8")
    set_config_values(path, {"discord_token": OTHER})
    assert path.read_text(encoding="utf-8") == f"# my note\nport = 9000\ndiscord_token = '{OTHER}'\nlog_level = \"DEBUG\"\n"


def test_a_missing_setting_is_appended(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("port = 9000\n", encoding="utf-8")
    set_config_values(path, {"discord_client_id": "123456789012345678"})
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"port": 9000, "discord_client_id": "123456789012345678"}


def test_there_may_be_no_file_yet(tmp_path):
    path = tmp_path / "new" / "config.toml"
    set_config_values(path, {"discord_token": TOKEN})
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"discord_token": TOKEN}


def test_removing_a_value_leaves_an_empty_setting(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(f"discord_token = '{TOKEN}'\n", encoding="utf-8")
    set_config_values(path, {"discord_token": ""})
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"discord_token": ""}


def test_line_endings_and_the_bom_of_the_persons_file_stay(tmp_path):
    path = tmp_path / "config.toml"
    path.write_bytes(b"\xef\xbb\xbf# note\r\n# discord_token = ''\r\nport = 9000\r\n")
    set_config_values(path, {"discord_token": TOKEN})
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    assert tomllib.loads(raw.decode("utf-8-sig")) == {"discord_token": TOKEN, "port": 9000}


def test_a_failed_write_changes_nothing(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("port = 9000\n", encoding="utf-8")
    with pytest.raises(SetupError) as caught:
        set_config_values(path, {"discord_token": "it's quoted"})   # never reaches the file
    assert caught.value.code == "config_write_failed"
    assert path.read_text(encoding="utf-8") == "port = 9000\n"
    assert not list(tmp_path.glob("*.tmp"))


def test_a_file_that_is_not_utf8_is_reported_and_left_alone(tmp_path):
    path = tmp_path / "config.toml"
    path.write_bytes(b"# z\xbf\xf3\xb3\n")   # cp1250 bytes of a Polish word: not UTF-8
    with pytest.raises(SetupError) as caught:
        set_config_values(path, {"discord_token": TOKEN})
    assert caught.value.code == "config_write_failed"
    assert path.read_bytes() == b"# z\xbf\xf3\xb3\n"


# ---- the API --------------------------------------------------------------------------------------------------

def desktop(env, tmp_path: Path | None = None) -> Path:
    """Makes the running app look like a desktop run: it knows where its settings file is."""
    path = (tmp_path or env.tmp) / "config.toml"
    path.write_text(TEMPLATE, encoding="utf-8")
    env.app.state.settings = replace(env.app.state.settings, config_file=str(path))
    return path


def test_in_a_container_the_panel_cannot_set_the_token(env):
    login(env, "admin")
    assert env.client.get("/api/system").json()["bot_setup"] is False
    res = env.client.put("/api/system/bot", json={"token": TOKEN})
    assert res.status_code == 409 and res.json()["detail"] == "bot_setup_unavailable"


def test_the_administrator_sets_the_token_and_it_is_applied_at_once(env):
    path = desktop(env)
    login(env, "admin")
    before = env.client.get("/api/system").json()
    assert before["bot_setup"] is True and before["bot_token_set"] is False and before["bot_client_id"] == ""

    res = env.client.put("/api/system/bot", json={"token": TOKEN, "client_id": "123456789012345678"})
    assert res.status_code == 200
    info = res.json()
    assert info["bot_token_set"] is True and info["bot_client_id"] == "123456789012345678"
    assert "client_id=123456789012345678" in info["invite_url"]
    assert TOKEN not in res.text and TOKEN not in env.client.get("/api/system").text   # the token is write-only
    assert tomllib.loads(path.read_text(encoding="utf-8"))["discord_token"] == TOKEN
    assert env.bot.applied.discord_token == TOKEN   # the bot was handed the new settings


def test_a_field_that_is_left_out_stays_and_an_empty_one_removes(env):
    path = desktop(env)
    login(env, "admin")
    assert env.client.put("/api/system/bot", json={"token": TOKEN, "client_id": "123456789012345678"}).status_code == 200
    info = env.client.put("/api/system/bot", json={"client_id": ""}).json()
    assert info["bot_token_set"] is True and info["bot_client_id"] == "" and info["invite_url"] is None
    info = env.client.put("/api/system/bot", json={"token": ""}).json()
    assert info["bot_token_set"] is False
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"discord_token": "", "discord_client_id": ""}


def test_a_wrong_value_gets_a_short_code_and_is_never_echoed_or_saved(env):
    path = desktop(env)
    before = path.read_text(encoding="utf-8")
    login(env, "admin")
    for body, code in (({"token": "123456789012345678"}, "token_is_app_id"),
                       ({"token": "this-is-a-secret-looking-but-wrong-value"}, "bad_token"),
                       ({"client_id": "my bot"}, "bad_client_id")):
        res = env.client.put("/api/system/bot", json=body)
        assert res.status_code == 422 and res.json()["detail"] == code
        assert next(iter(body.values())) not in res.text
    assert env.client.put("/api/system/bot", json={}).json()["detail"] == "nothing_to_change"
    assert path.read_text(encoding="utf-8") == before


def test_only_the_administrator_and_only_with_the_header(env):
    desktop(env)
    make_user(env, "mg")
    login(env, "mg")
    assert env.client.put("/api/system/bot", json={"token": TOKEN}).status_code == 403
    login(env, "admin")
    assert env.client.put("/api/system/bot", json={"token": TOKEN}, headers={"X-Melomancer": ""}).status_code == 403
    env.client.cookies.clear()
    assert env.client.put("/api/system/bot", json={"token": TOKEN}).status_code == 401


def test_an_unwritable_settings_file_is_reported_and_the_bot_keeps_what_it_had(env):
    path = desktop(env)
    env.app.state.settings = replace(env.app.state.settings, config_file=str(path.parent))   # a folder, not a file
    login(env, "admin")
    res = env.client.put("/api/system/bot", json={"token": TOKEN})
    assert res.status_code == 500 and res.json()["detail"] == "config_write_failed"
    assert not hasattr(env.bot, "applied") and env.client.get("/api/system").json()["bot_token_set"] is False


# ---- the bot itself ---------------------------------------------------------------------------------------------

class FakeClient:
    """Stands in for the Discord client: logs in at once, or is rejected, depending on the token."""
    created: list = []

    def __init__(self, manager):
        self.manager, self.user, self.closed, self.token = manager, None, False, None
        FakeClient.created.append(self)

    async def start(self, token):
        self.token = token
        if token == "rejected":
            raise player_mod.discord.LoginFailure("no")
        self.user = type("User", (), {"name": "Melo"})()
        self.manager.status = "ready"
        await asyncio.Event().wait()   # stays logged in until cancelled

    async def close(self):
        self.closed = True


def manager_with(token: str, monkeypatch):
    FakeClient.created.clear()
    monkeypatch.setattr(player_mod, "MelomancerClient", FakeClient)
    return BotManager(replace(Settings.from_env(), discord_token=token))


async def settle(manager):
    for _ in range(5):
        await asyncio.sleep(0)


def test_a_new_token_logs_the_bot_in_without_a_restart(monkeypatch):
    async def scenario():
        manager = manager_with("", monkeypatch)
        await manager.start()
        assert manager.status == "disabled" and not FakeClient.created   # no token: offline, nothing running
        await manager.reconfigure(replace(manager.settings, discord_token=TOKEN))
        await settle(manager)
        assert manager.status == "ready" and manager.name == "Melo" and FakeClient.created[0].token == TOKEN
        await manager.stop()
    asyncio.run(scenario())


def test_changing_the_token_closes_the_old_connection_first(monkeypatch):
    async def scenario():
        manager = manager_with(TOKEN, monkeypatch)
        await manager.start()
        await settle(manager)
        old = manager.client
        await manager.reconfigure(replace(manager.settings, discord_token=OTHER))
        await settle(manager)
        assert old.closed and manager.client is not old and manager.client.token == OTHER and manager.status == "ready"
        await manager.stop()
    asyncio.run(scenario())


def test_a_rejected_token_is_shown_and_removing_it_switches_the_bot_off(monkeypatch):
    async def scenario():
        manager = manager_with(TOKEN, monkeypatch)
        await manager.start()
        await settle(manager)
        await manager.reconfigure(replace(manager.settings, discord_token="rejected"))
        await settle(manager)
        assert manager.status == "login_failed" and manager.name is None
        await manager.reconfigure(replace(manager.settings, discord_token=""))
        assert manager.status == "disabled" and manager.client is None
        await manager.stop()
    asyncio.run(scenario())


def test_a_new_application_id_alone_does_not_touch_the_connection(monkeypatch):
    async def scenario():
        manager = manager_with(TOKEN, monkeypatch)
        await manager.start()
        await settle(manager)
        client = manager.client
        await manager.reconfigure(replace(manager.settings, discord_client_id="123456789012345678"))
        assert manager.client is client and not client.closed and manager.status == "ready"
        assert "123456789012345678" in manager.settings.invite_url
        await manager.stop()
    asyncio.run(scenario())
