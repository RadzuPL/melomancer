"""Library: upload, listing, tags, editing, soft deletion and download jobs."""
from __future__ import annotations

import json
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import downloader, library
from .db import tx
from .deps import current_user, get_settings

router = APIRouter(prefix="/api")


class TrackPatchIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    tags: list[str] | None = Field(default=None, max_length=60)


class TagsIn(BaseModel):
    tags: list[str] = Field(max_length=60)


class DownloadIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=30)
    my_tags: list[str] = Field(default_factory=list, max_length=30)


def _json_list(text: str) -> list[str]:
    try:
        value = json.loads(text) if text else []
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _editable_track(conn, user: dict, track_id: str):
    row = conn.execute("SELECT * FROM tracks WHERE id=? AND deleted_at IS NULL", (track_id,)).fetchone()
    if not row:
        raise HTTPException(404, "not_found")
    return row


def _require_edit(user: dict, row) -> None:
    if user["role"] != "admin" and row["owner_id"] != user["id"]:
        raise HTTPException(403, "forbidden")


def _usage(conn, track_id: str) -> int:
    return conn.execute("SELECT COUNT(DISTINCT playlist_id) FROM playlist_items WHERE track_id=?",
                        (track_id,)).fetchone()[0]


@router.get("/tracks")
def list_tracks(request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        return library.list_tracks(conn, user)


@router.post("/tracks/upload", status_code=201)
def upload(request: Request, file: UploadFile = File(...), folder_tags: str = Form(""), tags: str = Form(""),
           my_tags: str = Form(""), user: dict = Depends(current_user)):
    settings = get_settings(request)
    name = file.filename or "upload"
    ext = Path(name).suffix.lower()
    if ext not in library.ALLOWED_EXT:
        raise HTTPException(415, "unsupported_type")
    shared = [*_json_list(folder_tags), *_json_list(tags)]
    mine = _json_list(my_tags)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = settings.tmp_dir / f"up-{uuid.uuid4().hex}{ext}"
    limit = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with open(tmp, "wb") as out:
            while chunk := file.file.read(1024 * 1024):
                written += len(chunk)
                if written > limit:
                    raise HTTPException(413, "too_large")
                out.write(chunk)
        try:
            track, status = library.ingest(settings, tmp, owner_id=user["id"], original_name=name,
                                           source="upload", tags=shared, my_tags=mine)
        except library.IngestError as exc:
            raise HTTPException(422, exc.code) from None
    finally:
        tmp.unlink(missing_ok=True)
    return {"id": track["id"], "title": track["title"], "status": status}


@router.get("/tracks/{track_id}/stream")
def stream(track_id: str, request: Request, user: dict = Depends(current_user)):
    settings = get_settings(request)
    with tx(settings.db_path) as conn:
        row = _editable_track(conn, user, track_id)
    path = library.track_path(settings, row["id"], row["ext"])
    if not path.is_file():
        raise HTTPException(404, "not_found")
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream")


@router.patch("/tracks/{track_id}")
def patch_track(track_id: str, body: TrackPatchIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        row = _editable_track(conn, user, track_id)
        _require_edit(user, row)
        if body.title is not None:
            conn.execute("UPDATE tracks SET title=? WHERE id=?", (library.clean_title(body.title), track_id))
        if body.tags is not None:
            library.set_shared_tags(conn, track_id, body.tags)
    return {"ok": True}


@router.put("/tracks/{track_id}/my-tags")
def put_my_tags(track_id: str, body: TagsIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _editable_track(conn, user, track_id)
        conn.execute("DELETE FROM user_tags WHERE user_id=? AND track_id=?", (user["id"], track_id))
        conn.executemany("INSERT OR IGNORE INTO user_tags(user_id, track_id, tag) VALUES (?,?,?)",
                         [(user["id"], track_id, t) for t in library.norm_tags(body.tags)])
    return {"ok": True}


@router.get("/tracks/{track_id}/usage")
def track_usage(track_id: str, request: Request, user: dict = Depends(current_user)):
    """Only a count: playlist names and owners can give away scenario details."""
    with tx(get_settings(request).db_path) as conn:
        row = _editable_track(conn, user, track_id)
        _require_edit(user, row)
        return {"playlists": _usage(conn, track_id)}


@router.delete("/tracks/{track_id}")
def delete_track(track_id: str, request: Request, force: bool = False, user: dict = Depends(current_user)):
    settings = get_settings(request)
    with tx(settings.db_path) as conn:
        row = _editable_track(conn, user, track_id)
        _require_edit(user, row)
        used = _usage(conn, track_id)
        if used and not force:
            raise HTTPException(409, "in_use")
        library.soft_delete(settings, conn, row)
    return {"ok": True, "playlists": used}


@router.get("/tags")
def list_tags(request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        shared = conn.execute(
            "SELECT tt.tag AS tag, COUNT(*) AS n FROM track_tags tt JOIN tracks t ON t.id = tt.track_id "
            "WHERE t.deleted_at IS NULL GROUP BY tt.tag ORDER BY tt.tag").fetchall()
        mine = conn.execute(
            "SELECT ut.tag AS tag, COUNT(*) AS n FROM user_tags ut JOIN tracks t ON t.id = ut.track_id "
            "WHERE ut.user_id=? AND t.deleted_at IS NULL GROUP BY ut.tag ORDER BY ut.tag",
            (user["id"],)).fetchall()
    return {"shared": [{"tag": r["tag"], "count": r["n"]} for r in shared],
            "mine": [{"tag": r["tag"], "count": r["n"]} for r in mine]}


# ---- downloads ------------------------------------------------------------


@router.get("/downloads")
def list_downloads(request: Request, user: dict = Depends(current_user)):
    settings = get_settings(request)
    worker = request.app.state.downloader
    with tx(settings.db_path) as conn:
        if user["role"] == "admin":
            rows = conn.execute("SELECT d.*, u.username FROM downloads d JOIN users u ON u.id=d.user_id "
                                "ORDER BY d.id DESC LIMIT 100").fetchall()
        else:
            rows = conn.execute("SELECT d.*, u.username FROM downloads d JOIN users u ON u.id=d.user_id "
                                "WHERE d.user_id=? ORDER BY d.id DESC LIMIT 100", (user["id"],)).fetchall()
    live = worker.progress()
    jobs = []
    for r in rows:
        extra = live.get(r["id"], {}) if r["status"] == "running" else {}
        jobs.append({"id": r["id"], "url": r["url"], "status": r["status"], "error": r["error"],
                     "title": r["title"] or extra.get("title"), "track_id": r["track_id"], "user": r["username"],
                     "created_at": r["created_at"], "stage": extra.get("stage"), "percent": extra.get("percent"),
                     "speed": extra.get("speed"), "eta": extra.get("eta"), "elapsed": extra.get("elapsed")})
    return {"jobs": jobs, "pause_remaining": worker.pause_remaining()}


@router.post("/downloads", status_code=201)
def create_download(body: DownloadIn, request: Request, user: dict = Depends(current_user)):
    settings = get_settings(request)
    try:
        job = downloader.enqueue(settings, user["id"], body.url, library.norm_tags(body.tags),
                                 library.norm_tags(body.my_tags))
    except downloader.DownloadRejected as exc:
        status = 429 if exc.code == "daily_limit" else 400
        raise HTTPException(status, exc.code) from None
    request.app.state.downloader.wake()
    return {"id": job}


@router.delete("/downloads/{download_id}")
def delete_download(download_id: int, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        row = conn.execute("SELECT * FROM downloads WHERE id=?", (download_id,)).fetchone()
        if not row or (row["user_id"] != user["id"] and user["role"] != "admin"):
            raise HTTPException(404, "not_found")
        if row["status"] == "running":
            raise HTTPException(409, "running")
        conn.execute("DELETE FROM downloads WHERE id=?", (download_id,))
    return {"ok": True}
