"""Track storage: probing, de-duplication, tags and soft deletion."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import uuid
from pathlib import Path
from typing import Iterable

from .config import Settings
from .db import tx

ALLOWED_EXT = {".mp3", ".ogg", ".oga", ".opus", ".flac", ".wav", ".m4a", ".aac", ".webm"}
MAX_TAGS_PER_TRACK = 30
MAX_TAG_LENGTH = 40


class IngestError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def clean_title(value: str, fallback: str = "Untitled") -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[:200] or fallback


def norm_tag(value: str) -> str | None:
    tag = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    tag = tag[:MAX_TAG_LENGTH].strip()
    return tag or None


def norm_tags(values: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        tag = norm_tag(value)
        if tag:
            seen[tag] = None
    return list(seen)[:MAX_TAGS_PER_TRACK]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict:
    """Run ffprobe; raise IngestError('not_audio') if the file has no audio stream."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "format=duration:format_tags=title,artist:stream=codec_type",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise IngestError("probe_failed") from None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        raise IngestError("not_audio") from None
    if not data.get("streams"):
        raise IngestError("not_audio")
    fmt = data.get("format", {})
    try:
        duration = float(fmt.get("duration"))
    except (TypeError, ValueError):
        duration = None
    tags = {str(k).lower(): str(v) for k, v in (fmt.get("tags") or {}).items()}
    return {"duration": duration, "title": tags.get("title", ""), "artist": tags.get("artist", "")}


def track_path(settings: Settings, track_id: str, ext: str) -> Path:
    return settings.music_dir / f"{track_id}{ext}"


def set_shared_tags(conn: sqlite3.Connection, track_id: str, tags: Iterable[str]) -> None:
    conn.execute("DELETE FROM track_tags WHERE track_id=?", (track_id,))
    conn.executemany(
        "INSERT OR IGNORE INTO track_tags(track_id, tag) VALUES (?, ?)",
        [(track_id, tag) for tag in norm_tags(tags)],
    )


def add_shared_tags(conn: sqlite3.Connection, track_id: str, tags: Iterable[str]) -> None:
    existing = [r["tag"] for r in conn.execute("SELECT tag FROM track_tags WHERE track_id=?", (track_id,))]
    set_shared_tags(conn, track_id, [*existing, *tags])


def add_my_tags(conn: sqlite3.Connection, user_id: int, track_id: str, tags: Iterable[str]) -> None:
    """Personal tags are only added, never replaced: whatever the user tagged before stays."""
    conn.executemany("INSERT OR IGNORE INTO user_tags(user_id, track_id, tag) VALUES (?, ?, ?)",
                     [(user_id, track_id, tag) for tag in norm_tags(tags)])


def ingest(
    settings: Settings,
    src: Path,
    *,
    owner_id: int,
    original_name: str,
    source: str,
    source_url: str | None = None,
    title: str | None = None,
    tags: Iterable[str] = (),
    my_tags: Iterable[str] = (),
) -> tuple[dict, str]:
    """Move a finished file into the library.

    Returns (track row as dict, status) where status is 'created', 'duplicate' or 'revived'.
    A file whose content matches a soft-deleted track revives that track (same id),
    so playlists that kept a greyed-out entry for it link up again.
    """
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise IngestError("unsupported_type")
    digest = sha256_file(src)
    info = probe(src)
    size = src.stat().st_size
    stem = Path(original_name).stem
    if title:
        shown = title
    elif info["title"]:
        shown = f'{info["artist"]} - {info["title"]}' if info["artist"] else info["title"]
    else:
        shown = stem
    shown = clean_title(shown, fallback=clean_title(stem))
    tag_list = norm_tags(tags)
    my_list = norm_tags(my_tags)

    with tx(settings.db_path) as conn:
        live = conn.execute(
            "SELECT * FROM tracks WHERE sha256=? AND deleted_at IS NULL", (digest,)
        ).fetchone()
        if live:
            src.unlink(missing_ok=True)
            # The file is already there, but the person adding it still wants it tagged for their session.
            add_my_tags(conn, owner_id, live["id"], my_list)
            if tag_list and live["owner_id"] == owner_id:
                add_shared_tags(conn, live["id"], tag_list)
            return dict(live), "duplicate"

        tomb = conn.execute(
            "SELECT * FROM tracks WHERE sha256=? AND deleted_at IS NOT NULL ORDER BY deleted_at DESC LIMIT 1",
            (digest,),
        ).fetchone()
        track_id = tomb["id"] if tomb else uuid.uuid4().hex
        dest = track_path(settings, track_id, ext)
        settings.music_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), dest)
        try:
            if tomb:
                conn.execute(
                    "UPDATE tracks SET deleted_at=NULL, owner_id=?, ext=?, duration=?, size=?, "
                    "source=?, source_url=? WHERE id=?",
                    (owner_id, ext, info["duration"], size, source, source_url, track_id),
                )
                status = "revived"
            else:
                conn.execute(
                    "INSERT INTO tracks(id, owner_id, title, original_title, ext, sha256, duration, size, "
                    "source, source_url) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (track_id, owner_id, shown, shown, ext, digest, info["duration"], size, source, source_url),
                )
                status = "created"
            if tag_list:
                add_shared_tags(conn, track_id, tag_list)
            add_my_tags(conn, owner_id, track_id, my_list)
        except sqlite3.IntegrityError:
            dest.unlink(missing_ok=True)
            raise IngestError("duplicate_race") from None
        row = conn.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
    return dict(row), status


def tracks_for_tags(conn: sqlite3.Connection, user_id: int, tags: Iterable[str], mode: str) -> list[sqlite3.Row]:
    """Live tracks carrying all (mode "all") or any (mode "any") of the tags.

    A tag counts when it is a shared tag of the track or one of this user's personal tags.
    No tags means no tracks, never "everything".
    """
    wanted = norm_tags(tags)[:10]
    if not wanted:
        return []
    clauses, params = [], []
    for tag in wanted:
        clauses.append("(EXISTS (SELECT 1 FROM track_tags tt WHERE tt.track_id = t.id AND tt.tag = ?) "
                       "OR EXISTS (SELECT 1 FROM user_tags ut WHERE ut.track_id = t.id AND ut.user_id = ? AND ut.tag = ?))")
        params += [tag, user_id, tag]
    joiner = " AND " if mode == "all" else " OR "
    rows = conn.execute("SELECT t.id, t.title, t.ext, t.duration, t.loudness, t.peak, t.silence_lead, t.silence_trail, "
                        "t.trim_start, t.trim_end FROM tracks t "
                        "WHERE t.deleted_at IS NULL AND ("
                        + joiner.join(clauses) + ")", params).fetchall()
    return sorted(rows, key=lambda r: r["title"].casefold())


def soft_delete(settings: Settings, conn: sqlite3.Connection, track: sqlite3.Row) -> None:
    """Keep the row (title survives as a tombstone) but remove the audio file."""
    conn.execute("UPDATE tracks SET deleted_at=datetime('now') WHERE id=?", (track["id"],))
    track_path(settings, track["id"], track["ext"]).unlink(missing_ok=True)


def list_tracks(conn: sqlite3.Connection, user: dict) -> list[dict]:
    rows = conn.execute(
        "SELECT t.*, u.username AS owner FROM tracks t JOIN users u ON u.id = t.owner_id "
        "WHERE t.deleted_at IS NULL ORDER BY t.created_at DESC, t.title"
    ).fetchall()
    shared: dict[str, list[str]] = {}
    for r in conn.execute("SELECT track_id, tag FROM track_tags ORDER BY tag"):
        shared.setdefault(r["track_id"], []).append(r["tag"])
    mine: dict[str, list[str]] = {}
    for r in conn.execute("SELECT track_id, tag FROM user_tags WHERE user_id=? ORDER BY tag", (user["id"],)):
        mine.setdefault(r["track_id"], []).append(r["tag"])
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "original_title": r["original_title"],
            "duration": r["duration"],
            "size": r["size"],
            "source": r["source"],
            "source_url": r["source_url"],
            "owner_id": r["owner_id"],
            "owner": r["owner"],
            "created_at": r["created_at"],
            "lead": r["silence_lead"],        # what the silence analysis found (seconds to skip / to cut off)
            "trail": r["silence_trail"],
            "trim_start": r["trim_start"],    # set by hand, None = automatic
            "trim_end": r["trim_end"],
            "tags": shared.get(r["id"], []),
            "my_tags": mine.get(r["id"], []),
            "can_edit": user["role"] == "admin" or r["owner_id"] == user["id"],
        }
        for r in rows
    ]
