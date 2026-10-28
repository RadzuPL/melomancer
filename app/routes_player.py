"""Player control: servers and channels, connecting, playing playlists, volume."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Literal

from pydantic import BaseModel, Field

from . import library
from .db import tx
from .deps import current_user, get_settings
from .player import PlayerError, QueueItem
from .routes_playlists import playlist_for, playlist_tracks

router = APIRouter(prefix="/api/player")


class ConnectIn(BaseModel):
    channel_id: str = Field(pattern=r"^\d{5,25}$")


class PlayIn(BaseModel):
    playlist_id: int | None = None
    track_id: str | None = None
    # Play whatever carries these tags right now, without a saved playlist.
    tags: list[str] | None = Field(default=None, max_length=10)
    mode: Literal["all", "any"] = "any"


class ChoiceIn(BaseModel):
    guild_id: str = Field(pattern=r"^\d{1,25}$")
    channel_id: str | None = Field(default=None, pattern=r"^\d{1,25}$")


class VolumeIn(BaseModel):
    volume: float = Field(ge=0, le=1.5)


class SeekIn(BaseModel):
    seconds: float = Field(ge=0, le=86400)


class JumpIn(BaseModel):
    index: int = Field(ge=0, le=100000)


class OptionsIn(BaseModel):
    loop: bool | None = None
    shuffle: bool | None = None


def _bot(request: Request):
    return request.app.state.bot


def _guild(guild_id: str) -> int:
    if not guild_id.isdigit():
        raise HTTPException(400, "bad_request")
    return int(guild_id)


def _allowed_guilds(request: Request, user: dict) -> set[str] | None:
    """None means every guild the bot is in (admins); otherwise the explicit allow-list."""
    if user["role"] == "admin":
        return None
    with tx(get_settings(request).db_path) as conn:
        return {r["guild_id"] for r in conn.execute("SELECT guild_id FROM guild_access WHERE user_id=?",
                                                    (user["id"],))}


def _check(request: Request, user: dict, guild_id: str) -> int:
    allowed = _allowed_guilds(request, user)
    if allowed is not None and guild_id not in allowed:
        raise HTTPException(404, "not_found")
    return _guild(guild_id)


def _check_lock(bot, gid: int, user: dict) -> None:
    """One server, one controller: another user's running session is not taken over by accident."""
    snap = bot.state(gid)
    holder = snap.get("controller_id")
    if holder and holder != user["id"] and user["role"] != "admin" and snap["state"] != "idle":
        raise PlayerError("busy", 409)


def _run(call):
    try:
        return call()
    except PlayerError as exc:
        raise HTTPException(exc.status, exc.code) from None


@router.get("/guilds")
def guilds(request: Request, user: dict = Depends(current_user)):
    allowed = _allowed_guilds(request, user)
    found = _bot(request).list_guilds()
    return [g for g in found if allowed is None or g["id"] in allowed]


@router.get("/{guild_id}/state")
def state(guild_id: str, request: Request, user: dict = Depends(current_user)):
    gid = _check(request, user, guild_id)
    return _run(lambda: _bot(request).state(gid))


@router.post("/{guild_id}/connect")
async def connect(guild_id: str, body: ConnectIn, request: Request, user: dict = Depends(current_user)):
    gid = _check(request, user, guild_id)
    bot = _bot(request)
    try:
        _check_lock(bot, gid, user)
        await bot.connect(gid, int(body.channel_id))
    except PlayerError as exc:
        raise HTTPException(exc.status, exc.code) from None
    return bot.state(gid)


@router.post("/{guild_id}/disconnect")
async def disconnect(guild_id: str, request: Request, user: dict = Depends(current_user)):
    gid = _check(request, user, guild_id)
    bot = _bot(request)
    try:
        _check_lock(bot, gid, user)
        await bot.disconnect(gid)
    except PlayerError as exc:
        raise HTTPException(exc.status, exc.code) from None
    return bot.state(gid)


def resolve_target(conn, user: dict, body: PlayIn):
    """What a play request means: (track rows in playing order, playlist info, the playlist's own options)."""
    if sum(bool(x) for x in (body.playlist_id, body.track_id, body.tags)) != 1:
        raise HTTPException(400, "bad_request")
    if body.playlist_id:
        row = playlist_for(conn, user, body.playlist_id)
        rows = playlist_tracks(conn, row)
        meta = {"id": row["id"], "name": row["name"], "set": row["set_name"]}
        opts = dict(loop=bool(row["loop"]), shuffle=bool(row["shuffle"]), fade=float(row["fade"]),
                    volume=row["volume"])
    elif body.tags:
        wanted = library.norm_tags(body.tags)
        rows = library.tracks_for_tags(conn, user["id"], wanted, body.mode)
        meta = {"id": None, "name": ("# " + (" + " if body.mode == "all" else " | ").join(wanted)), "set": None}
        opts = dict(loop=True, shuffle=True, fade=2.0, volume=None)
    else:
        single = conn.execute("SELECT id, title, ext, duration, loudness, peak, silence_lead, silence_trail, "
                              "trim_start, trim_end FROM tracks WHERE id=? AND deleted_at IS NULL",
                              (body.track_id,)).fetchone()
        if not single:
            raise HTTPException(404, "not_found")
        rows, meta = [single], {"id": None, "name": single["title"], "set": None}
        opts = dict(loop=False, shuffle=False, fade=0.0, volume=None)
    return rows, meta, opts


@router.get("/choice")
def get_choice(request: Request, user: dict = Depends(current_user)):
    """The server and voice channel this person chose last, to be selected again in the player."""
    with tx(get_settings(request).db_path) as conn:
        rows = conn.execute("SELECT key, value FROM user_prefs WHERE user_id=? AND key LIKE 'player.%'",
                            (user["id"],)).fetchall()
    stored = {r["key"]: r["value"] for r in rows}
    prefix = "player.channel."
    return {"guild": stored.get("player.guild"),
            "channels": {k[len(prefix):]: v for k, v in stored.items() if k.startswith(prefix)}}


@router.put("/choice")
def put_choice(body: ChoiceIn, request: Request, user: dict = Depends(current_user)):
    """Remember the chosen server and, when given, the channel chosen on it. Choosing is not connecting."""
    entries = {"player.guild": body.guild_id}
    if body.channel_id:
        entries["player.channel." + body.guild_id] = body.channel_id
    with tx(get_settings(request).db_path) as conn:
        for key, value in entries.items():
            conn.execute("INSERT INTO user_prefs(user_id, key, value) VALUES (?, ?, ?) "
                         "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value", (user["id"], key, value))
    return {"ok": True}


@router.post("/{guild_id}/play")
async def play(guild_id: str, body: PlayIn, request: Request, user: dict = Depends(current_user)):
    gid = _check(request, user, guild_id)
    settings = get_settings(request)
    bot = _bot(request)
    with tx(settings.db_path) as conn:
        rows, meta, opts = resolve_target(conn, user, body)
    items = [QueueItem(r["id"], r["title"], str(library.track_path(settings, r["id"], r["ext"])), r["duration"],
                       r["loudness"], r["peak"], r["silence_lead"] or 0.0, r["silence_trail"] or 0.0,
                       r["trim_start"], r["trim_end"])
             for r in rows]
    if not items:
        raise HTTPException(400, "empty_playlist")
    try:
        _check_lock(bot, gid, user)
        await bot.play(gid, items, meta, {"id": user["id"], "username": user["username"]}, **opts)
    except PlayerError as exc:
        raise HTTPException(exc.status, exc.code) from None
    return bot.state(gid)


def _control(action: str):
    def handler(guild_id: str, request: Request, user: dict = Depends(current_user)):
        gid = _check(request, user, guild_id)
        bot = _bot(request)

        def call():
            _check_lock(bot, gid, user)
            bot.control(gid, action)
            return bot.state(gid)

        return _run(call)

    return handler


for _action in ("pause", "resume", "next", "prev", "stop"):
    router.add_api_route(f"/{{guild_id}}/{_action}", _control(_action), methods=["POST"], name=f"player_{_action}")


@router.post("/{guild_id}/volume")
def volume(guild_id: str, body: VolumeIn, request: Request, user: dict = Depends(current_user)):
    gid = _check(request, user, guild_id)
    bot = _bot(request)

    def call():
        _check_lock(bot, gid, user)
        bot.control(gid, "volume", body.volume)
        return bot.state(gid)

    return _run(call)


@router.post("/{guild_id}/seek")
def seek(guild_id: str, body: SeekIn, request: Request, user: dict = Depends(current_user)):
    gid = _check(request, user, guild_id)
    bot = _bot(request)

    def call():
        _check_lock(bot, gid, user)
        bot.control(gid, "seek", body.seconds)
        return bot.state(gid)

    return _run(call)


@router.post("/{guild_id}/jump")
def jump(guild_id: str, body: JumpIn, request: Request, user: dict = Depends(current_user)):
    gid = _check(request, user, guild_id)
    bot = _bot(request)

    def call():
        _check_lock(bot, gid, user)
        bot.control(gid, "jump", body.index)
        return bot.state(gid)

    return _run(call)


@router.patch("/{guild_id}/options")
def options(guild_id: str, body: OptionsIn, request: Request, user: dict = Depends(current_user)):
    gid = _check(request, user, guild_id)
    bot = _bot(request)

    def call():
        _check_lock(bot, gid, user)
        bot.control(gid, "options", body.model_dump())
        return bot.state(gid)

    return _run(call)
