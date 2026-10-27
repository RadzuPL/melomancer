"""Authentication, user management and system information."""
from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .config import Settings
from .db import tx
from .deps import SESSION_COOKIE, current_user, get_settings, require_admin
from .loudness import BOOST_RANGE, CROSSFADE_RANGE, SCRUB_RANGE, TARGET_RANGE, counts as loudness_counts
from .security import (MIN_PASSWORD_LENGTH, hash_password, new_session_token, sha256_hex, utc_string,
                       verify_password)

router = APIRouter(prefix="/api")


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class PasswordIn(BaseModel):
    current: str = Field(max_length=256)
    new: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)


class ProfileIn(BaseModel):
    lang: Literal["pl", "en"]


class UserCreateIn(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)
    role: Literal["admin", "user"] = "user"


class UserPatchIn(BaseModel):
    role: Literal["admin", "user"] | None = None
    disabled: bool | None = None
    password: str | None = Field(default=None, min_length=MIN_PASSWORD_LENGTH, max_length=256)


class GuildAccessIn(BaseModel):
    guild_ids: list[str] = Field(max_length=200)


def _public_user(row) -> dict:
    return {"id": row["id"], "username": row["username"], "role": row["role"], "lang": row["lang"]}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _secure_cookie(settings: Settings, request: Request) -> bool:
    if settings.cookie_secure == "auto":
        return request.url.scheme == "https"
    return settings.cookie_secure == "true"


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    settings = get_settings(request)
    throttle = request.app.state.throttle
    keys = (f"u:{body.username.lower()}", f"ip:{_client_ip(request)}")
    if throttle.blocked(*keys):
        raise HTTPException(429, "too_many_attempts")
    with tx(settings.db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
        ok = verify_password(row["pw_hash"] if row else None, body.password)
        if not ok or row["disabled"]:
            throttle.fail(*keys)
            raise HTTPException(401, "bad_credentials")
        token, token_hash = new_session_token()
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (utc_string(),))
        conn.execute("INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?,?,?)",
                     (token_hash, row["id"], utc_string(settings.session_hours)))
    throttle.reset(*keys)
    response.set_cookie(SESSION_COOKIE, token, max_age=settings.session_hours * 3600, httponly=True,
                        samesite="lax", secure=_secure_cookie(settings, request), path="/")
    return _public_user(row)


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with tx(get_settings(request).db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (sha256_hex(token),))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return user


@router.patch("/auth/me")
def update_me(body: ProfileIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        conn.execute("UPDATE users SET lang=? WHERE id=?", (body.lang, user["id"]))
    return {**user, "lang": body.lang}


@router.post("/auth/password")
def change_password(body: PasswordIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        row = conn.execute("SELECT pw_hash FROM users WHERE id=?", (user["id"],)).fetchone()
        if not verify_password(row["pw_hash"], body.current):
            raise HTTPException(403, "bad_credentials")
        conn.execute("UPDATE users SET pw_hash=? WHERE id=?", (hash_password(body.new), user["id"]))
        token = request.cookies.get(SESSION_COOKIE) or ""
        conn.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], sha256_hex(token)))
    return {"ok": True}


# ---- user administration ------------------------------------------------


def _admins_left(conn: sqlite3.Connection, excluding: int) -> int:
    return conn.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND disabled=0 AND id<>?",
                        (excluding,)).fetchone()[0]


@router.get("/users")
def list_users(request: Request, _: dict = Depends(require_admin)):
    with tx(get_settings(request).db_path) as conn:
        access: dict[int, list[str]] = {}
        for r in conn.execute("SELECT user_id, guild_id FROM guild_access"):
            access.setdefault(r["user_id"], []).append(r["guild_id"])
        return [
            {**_public_user(r), "disabled": bool(r["disabled"]), "created_at": r["created_at"],
             "guild_ids": access.get(r["id"], [])}
            for r in conn.execute("SELECT * FROM users ORDER BY username")
        ]


@router.get("/people")
def list_people(request: Request, user: dict = Depends(current_user)):
    """Active accounts other than your own, for choosing who to copy a playlist to. Names only."""
    with tx(get_settings(request).db_path) as conn:
        return [{"id": r["id"], "username": r["username"]}
                for r in conn.execute("SELECT id, username FROM users WHERE disabled=0 AND id != ? ORDER BY username",
                                      (user["id"],))]


@router.post("/users", status_code=201)
def create_user(body: UserCreateIn, request: Request, _: dict = Depends(require_admin)):
    with tx(get_settings(request).db_path) as conn:
        try:
            cur = conn.execute("INSERT INTO users(username, pw_hash, role) VALUES (?,?,?)",
                               (body.username, hash_password(body.password), body.role))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "username_taken") from None
        return {"id": cur.lastrowid, "username": body.username, "role": body.role}


@router.patch("/users/{user_id}")
def patch_user(user_id: int, body: UserPatchIn, request: Request, admin: dict = Depends(require_admin)):
    with tx(get_settings(request).db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, "not_found")
        demoting = (body.role == "user" and row["role"] == "admin") or (body.disabled and row["role"] == "admin")
        if demoting and _admins_left(conn, user_id) == 0:
            raise HTTPException(409, "last_admin")
        if body.role is not None:
            conn.execute("UPDATE users SET role=? WHERE id=?", (body.role, user_id))
        if body.disabled is not None:
            conn.execute("UPDATE users SET disabled=? WHERE id=?", (int(body.disabled), user_id))
            if body.disabled:
                conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        if body.password:
            conn.execute("UPDATE users SET pw_hash=? WHERE id=?", (hash_password(body.password), user_id))
            conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    return {"ok": True}


@router.put("/users/{user_id}/guilds")
def set_guild_access(user_id: int, body: GuildAccessIn, request: Request, _: dict = Depends(require_admin)):
    ids = sorted({g for g in body.guild_ids if g.isdigit()})
    with tx(get_settings(request).db_path) as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
            raise HTTPException(404, "not_found")
        conn.execute("DELETE FROM guild_access WHERE user_id=?", (user_id,))
        conn.executemany("INSERT INTO guild_access(user_id, guild_id) VALUES (?,?)", [(user_id, g) for g in ids])
    return {"guild_ids": ids}


# ---- system -------------------------------------------------------------


@router.get("/health", include_in_schema=False)
def health(request: Request):
    return {"status": "ok", "version": get_settings(request).version}


def _system_info(request: Request) -> dict:
    settings = get_settings(request)
    return {
        "version": settings.version,
        "bot_status": request.app.state.bot.status,
        "downloads_enabled": settings.ytdlp_enabled,
        "download_hosts": list(settings.ytdlp_allowed_hosts),
        "max_upload_mb": settings.max_upload_mb,
        "normalize": request.app.state.runtime.normalize,
        "normalize_target": request.app.state.runtime.target,
        "normalize_max_boost": request.app.state.runtime.max_boost,
        "crossfade_seconds": request.app.state.runtime.crossfade,
        "scrub_seconds": request.app.state.runtime.scrub,
        "loudness": loudness_counts(settings),
    }


@router.get("/system")
def system(request: Request, _: dict = Depends(current_user)):
    return _system_info(request)


class SystemPatch(BaseModel):
    normalize: bool | None = None
    normalize_target: float | None = Field(default=None, ge=TARGET_RANGE[0], le=TARGET_RANGE[1])
    normalize_max_boost: float | None = Field(default=None, ge=BOOST_RANGE[0], le=BOOST_RANGE[1])
    crossfade_seconds: float | None = Field(default=None, ge=CROSSFADE_RANGE[0], le=CROSSFADE_RANGE[1])
    scrub_seconds: float | None = Field(default=None, ge=SCRUB_RANGE[0], le=SCRUB_RANGE[1])


@router.patch("/system")
def patch_system(body: SystemPatch, request: Request, _: dict = Depends(require_admin)):
    """Change the loudness and fade settings while the bot runs; what is playing now follows at once."""
    request.app.state.runtime.update(normalize=body.normalize, target=body.normalize_target,
                                     max_boost=body.normalize_max_boost, crossfade=body.crossfade_seconds,
                                     scrub=body.scrub_seconds)
    request.app.state.bot.refresh_settings()
    return _system_info(request)
