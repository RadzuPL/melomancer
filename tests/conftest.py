from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.player import PlayerError

PASSWORD = "password-for-tests-1"


class StubDownloader:
    """Keeps the API tests from starting the real yt-dlp worker thread."""

    def start(self): ...
    def stop(self): ...
    def wake(self): ...
    def progress(self): return {}
    def pause_remaining(self): return 0


class StubLoudness:
    """Keeps the API tests from starting the measuring thread; tests call measure_all() themselves."""

    def start(self): ...
    def stop(self): ...
    def wake(self): ...


class FakeBot:
    """Stands in for BotManager: same interface, no Discord."""

    def __init__(self) -> None:
        self.status = "ready"
        self.guild_list = [
            {"id": "111", "name": "Guild A", "channels": [{"id": "100100", "name": "Voice A"}]},
            {"id": "222", "name": "Guild B", "channels": [{"id": "200100", "name": "Voice B"}]},
        ]
        self.states: dict[int, dict] = {}
        self.played: list[dict] = []

    async def start(self): ...
    async def stop(self): ...

    async def reconfigure(self, settings):
        self.applied = settings   # what the panel's bot setup handed over

    def refresh_settings(self):
        self.settings_refreshed = getattr(self, "settings_refreshed", 0) + 1

    def _st(self, gid: int) -> dict:
        return self.states.setdefault(gid, {
            "guild_id": str(gid), "connected": False, "channel_id": None, "channel_name": None,
            "state": "idle", "volume": 0.4, "loop": True, "shuffle": False, "playlist": None, "now": None,
            "position": 0, "queue_length": 0, "controller_id": None, "controller": None,
        })

    def list_guilds(self):
        return [{**g, "state": self._st(int(g["id"]))} for g in self.guild_list]

    def state(self, gid: int) -> dict:
        return dict(self._st(gid))

    async def connect(self, gid: int, channel_id: int):
        self._st(gid).update(connected=True, channel_id=str(channel_id))

    async def disconnect(self, gid: int):
        self.states.pop(gid, None)

    async def play(self, gid, items, playlist, controller, **opts):
        st = self._st(gid)
        if not st["connected"]:
            raise PlayerError("not_connected", 409)
        st.update(state="playing", controller_id=controller["id"], controller=controller["username"],
                  queue_length=len(items), playlist=playlist)
        self.played.append({"gid": gid, "titles": [i.title for i in items], "opts": opts, "playlist": playlist,
                            "items": items})

    # ---- sound effects: remembers what was asked, plays nothing ----

    def _fx_on(self, gid):
        return self._st(gid).setdefault("fx", [])

    def _need_voice(self, gid):
        if not self._st(gid)["connected"]:
            raise PlayerError("not_connected", 409)

    def fx_toggle(self, gid, key, item, *, loop, volume):
        self._need_voice(gid)
        on = self._fx_on(gid)
        self.fx_calls = getattr(self, "fx_calls", []) + [("toggle", gid, key, item.title, loop, volume)]
        if any(e["pad_id"] == key for e in on):
            on[:] = [e for e in on if e["pad_id"] != key]
            return False
        on.append({"pad_id": key, "loop": loop, "momentary": False})
        return True

    def fx_hold(self, gid, key, item, *, loop, volume):
        self._need_voice(gid)
        self.fx_calls = getattr(self, "fx_calls", []) + [("hold", gid, key, item.title, loop, volume)]
        self._fx_on(gid).append({"pad_id": key, "loop": loop, "momentary": True})

    def fx_release(self, gid, key):
        self.fx_calls = getattr(self, "fx_calls", []) + [("release", gid, key)]
        on = self._fx_on(gid)
        on[:] = [e for e in on if not (e["pad_id"] == key and e["momentary"])]

    def fx_stop(self, gid, key=None):
        self._fx_on(gid).clear()

    def fx_volume(self, gid, volume):
        self._st(gid)["fx_volume"] = volume

    def control(self, gid, action, value=None):
        st = self._st(gid)
        if action == "pause":
            st["state"] = "paused"
        elif action == "resume":
            st["state"] = "playing"
        elif action == "stop":
            st.update(state="idle", controller_id=None, controller=None)
        elif action == "seek":
            if st["state"] == "idle":
                raise PlayerError("not_playing", 409)
            st["seeked"] = value
        elif action == "jump":
            if st["state"] == "idle":
                raise PlayerError("not_playing", 409)
            st["position"] = value + 1
        elif action == "volume":
            st["volume"] = value
        elif action == "options":
            st.update({k: v for k, v in value.items() if v is not None})


def make_wav(path: Path, frequency: int = 440, seconds: int = 1) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         f"sine=frequency={frequency}:duration={seconds}", str(path)],
        check=True,
    )
    return path


@pytest.fixture
def env(tmp_path):
    settings = replace(
        Settings.from_env(), data_dir=tmp_path / "data", admin_username="admin", admin_password=PASSWORD,
        discord_token="", ytdlp_enabled=True, ytdlp_daily_limit=3, login_max_failures=5,
    )
    bot = FakeBot()
    app = create_app(settings, bot=bot, downloader=StubDownloader(), loudness=StubLoudness())
    with TestClient(app) as client:
        client.headers["X-Melomancer"] = "1"
        yield SimpleNamespace(client=client, settings=settings, bot=bot, app=app, tmp=tmp_path)


def login(env, username: str, password: str = PASSWORD):
    env.client.cookies.clear()
    return env.client.post("/api/auth/login", json={"username": username, "password": password})


def make_user(env, username: str, role: str = "user") -> int:
    assert login(env, "admin").status_code == 200
    res = env.client.post("/api/users", json={"username": username, "password": PASSWORD, "role": role})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def upload(env, path: Path, name: str | None = None, **form):
    with open(path, "rb") as handle:
        return env.client.post("/api/tracks/upload", files={"file": (name or path.name, handle, "audio/wav")},
                               data=form)


@pytest.fixture
def wavs(tmp_path):
    return [make_wav(tmp_path / f"tone{i}.wav", 300 + i * 100) for i in range(4)]
