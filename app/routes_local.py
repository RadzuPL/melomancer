"""Playing in the browser: the server decides what plays and where it starts and ends; the page does the playing."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .db import tx
from .deps import current_user, get_settings
from .playback import entry
from .routes_player import PlayIn, resolve_target

router = APIRouter(prefix="/api/local")

COLUMNS = ("id, title, ext, duration, loudness, peak, silence_lead, silence_trail, trim_start, trim_end")


class ResolveIn(BaseModel):
    track_ids: list[str] = Field(min_length=1, max_length=2000)


@router.post("/queue")
def queue(body: PlayIn, request: Request, user: dict = Depends(current_user)):
    """The tracks of a playlist, a tag selection or a single track, in playing order, ready for the browser."""
    runtime = request.app.state.runtime
    with tx(get_settings(request).db_path) as conn:
        rows, meta, opts = resolve_target(conn, user, body)
    if not rows:
        raise HTTPException(400, "empty_playlist")
    return {"playlist": meta, "options": opts, "settings_rev": runtime.rev,
            "items": [entry(r, runtime) for r in rows]}


@router.post("/resolve")
def resolve(body: ResolveIn, request: Request, _: dict = Depends(current_user)):
    """Fresh start, end and gain for tracks already queued, after the settings changed or a track was edited."""
    runtime = request.app.state.runtime
    ids = list(dict.fromkeys(body.track_ids))
    with tx(get_settings(request).db_path) as conn:
        marks = ",".join("?" * len(ids))
        rows = conn.execute(f"SELECT {COLUMNS} FROM tracks WHERE id IN ({marks}) AND deleted_at IS NULL",
                            ids).fetchall()
    return {"settings_rev": runtime.rev, "items": [entry(r, runtime) for r in rows]}
