"""The sampler: a board of big pads, each playing one track as a sound effect. Pads are private to their owner.

Playing is not here: on Discord it goes through `/api/player/{guild}/fx/...` (the bot mixes the effect into the voice
stream) and in the browser the page plays it itself from the `item` that every pad carries, like the local player.
"""
from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .db import tx
from .deps import current_user, get_settings
from .playback import entry
from .sampler import TRACK_COLUMNS, pad_for

router = APIRouter(prefix="/api/sampler")

STARTING_PADS = 8
MAX_PADS = 48
COLORS = 6


class PadPatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)   # the length of the rename box in the panel
    track_id: str | None = None          # read with model_fields_set: an explicit null empties the pad
    mode: Literal["once", "loop"] | None = None
    volume: float | None = Field(default=None, ge=0, le=1.5)
    color: int | None = Field(default=None, ge=0, le=COLORS - 1)


class OrderIn(BaseModel):
    ids: list[int] = Field(max_length=MAX_PADS)


def _pad_out(conn: sqlite3.Connection, runtime, row: sqlite3.Row) -> dict:
    track = item = None
    if row["track_id"]:
        found = conn.execute(f"SELECT {TRACK_COLUMNS} FROM tracks WHERE id=?", (row["track_id"],)).fetchone()
        if found:
            gone = found["deleted_at"] is not None
            track = {"title": found["title"], "duration": found["duration"], "deleted": gone}
            item = None if gone else entry(found, runtime)
    return {"id": row["id"], "position": row["position"], "name": row["name"], "track_id": row["track_id"], "track": track,
            "mode": row["mode"], "volume": row["volume"], "color": row["color"], "item": item}


def _pads(conn: sqlite3.Connection, runtime, user: dict) -> list[dict]:
    rows = conn.execute("SELECT * FROM sampler_pads WHERE user_id=? ORDER BY position, id", (user["id"],)).fetchall()
    return [_pad_out(conn, runtime, r) for r in rows]


@router.get("")
def board(request: Request, user: dict = Depends(current_user)):
    """The person's pads; the first visit finds a board of empty ones to fill."""
    with tx(get_settings(request).db_path) as conn:
        if not conn.execute("SELECT 1 FROM sampler_pads WHERE user_id=? LIMIT 1", (user["id"],)).fetchone():
            conn.executemany("INSERT INTO sampler_pads(user_id, position) VALUES (?, ?)",
                             [(user["id"], n) for n in range(STARTING_PADS)])
        return {"pads": _pads(conn, request.app.state.runtime, user)}


@router.post("/pads", status_code=201)
def add_pad(request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        count, last = conn.execute("SELECT COUNT(*), COALESCE(MAX(position), -1) FROM sampler_pads WHERE user_id=?",
                                   (user["id"],)).fetchone()
        if count >= MAX_PADS:
            raise HTTPException(409, "too_many_pads")
        conn.execute("INSERT INTO sampler_pads(user_id, position) VALUES (?, ?)", (user["id"], last + 1))
        return {"pads": _pads(conn, request.app.state.runtime, user)}


@router.patch("/pads/{pad_id}")
def patch_pad(pad_id: int, body: PadPatchIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        pad_for(conn, user, pad_id)
        changes: dict[str, object] = {}
        if body.name is not None:
            changes["name"] = " ".join(body.name.split())
        if "track_id" in body.model_fields_set:
            if body.track_id is not None and not conn.execute(
                    "SELECT 1 FROM tracks WHERE id=? AND deleted_at IS NULL", (body.track_id,)).fetchone():
                raise HTTPException(404, "not_found")
            changes["track_id"] = body.track_id
        for field in ("mode", "volume", "color"):
            if getattr(body, field) is not None:
                changes[field] = getattr(body, field)
        if changes:
            conn.execute(f"UPDATE sampler_pads SET {', '.join(f'{k}=?' for k in changes)} WHERE id=?",
                         (*changes.values(), pad_id))
        return {"pads": _pads(conn, request.app.state.runtime, user)}


@router.delete("/pads/{pad_id}")
def delete_pad(pad_id: int, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        pad_for(conn, user, pad_id)
        conn.execute("DELETE FROM sampler_pads WHERE id=?", (pad_id,))
        return {"pads": _pads(conn, request.app.state.runtime, user)}


@router.put("/order")
def reorder(body: OrderIn, request: Request, user: dict = Depends(current_user)):
    """The new order of all of the person's pads."""
    with tx(get_settings(request).db_path) as conn:
        mine = {r["id"] for r in conn.execute("SELECT id FROM sampler_pads WHERE user_id=?", (user["id"],))}
        if set(body.ids) != mine or len(body.ids) != len(mine):
            raise HTTPException(400, "bad_request")
        conn.executemany("UPDATE sampler_pads SET position=? WHERE id=?", [(n, pad_id) for n, pad_id in enumerate(body.ids)])
        return {"pads": _pads(conn, request.app.state.runtime, user)}
