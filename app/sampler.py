"""The sampler's pads: reading them, and turning a pad into something the player can play."""
from __future__ import annotations

import sqlite3

from fastapi import HTTPException

from . import library
from .config import Settings
from .player import QueueItem

TRACK_COLUMNS = "id, title, ext, duration, loudness, peak, silence_lead, silence_trail, trim_start, trim_end, deleted_at"


def pad_for(conn: sqlite3.Connection, user: dict, pad_id: int) -> sqlite3.Row:
    """A pad of this person; someone else's pad answers 404 like everything else that is private (also for admins:
    a sampler is a personal board)."""
    row = conn.execute("SELECT * FROM sampler_pads WHERE id=? AND user_id=?", (pad_id, user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "not_found")
    return row


def queue_item(conn: sqlite3.Connection, settings: Settings, pad: sqlite3.Row) -> QueueItem:
    """The track of a pad as the player takes it. A pad without a track, or whose track was deleted, cannot play."""
    if not pad["track_id"]:
        raise HTTPException(409, "pad_empty")
    track = conn.execute(f"SELECT {TRACK_COLUMNS} FROM tracks WHERE id=?", (pad["track_id"],)).fetchone()
    if not track or track["deleted_at"] is not None:
        raise HTTPException(409, "pad_empty")
    return QueueItem(track["id"], track["title"], str(library.track_path(settings, track["id"], track["ext"])),
                     track["duration"], track["loudness"], track["peak"], track["silence_lead"] or 0.0,
                     track["silence_trail"] or 0.0, track["trim_start"], track["trim_end"])
