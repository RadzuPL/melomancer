"""Sets, folders (groups) and playlists. Everything here is private to the owner (admins see all).

Other users get 404 instead of 403 so that the existence of someone else's scenario is not revealed.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import library
from .db import tx
from .deps import current_user, get_settings

router = APIRouter(prefix="/api")


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PlaylistCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["manual", "tags"] = "manual"
    tags: list[str] = Field(default_factory=list, max_length=10)  # the rule of a "tags" playlist
    mode: Literal["all", "any"] = "any"


class PlaylistPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    loop: bool | None = None
    shuffle: bool | None = None
    volume: float | None = Field(default=None, ge=0, le=1.5)
    fade: float | None = Field(default=None, ge=0, le=10)
    # Moving: group_id = target folder; group_id null (+ optional set_id) = directly under a set.
    group_id: int | None = None
    set_id: int | None = None
    # Rule of an automatic playlist.
    tags: list[str] | None = Field(default=None, max_length=10)
    mode: Literal["all", "any"] | None = None


class CopyIn(BaseModel):
    user_id: int
    with_my_tags: bool = False  # also give the recipient the personal tags the owner put on these tracks


class TrackIdsIn(BaseModel):
    track_ids: list[str] = Field(min_length=1, max_length=500)


class OrderIn(BaseModel):
    ids: list[int] = Field(max_length=2000)


class ReplaceIn(BaseModel):
    track_id: str


def _name(value: str) -> str:
    return " ".join(value.split())[:100] or "?"


def _set_for(conn: sqlite3.Connection, user: dict, set_id: int):
    row = conn.execute("SELECT * FROM sets WHERE id=?", (set_id,)).fetchone()
    if not row or (row["owner_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "not_found")
    return row


def _group_for(conn: sqlite3.Connection, user: dict, group_id: int):
    row = conn.execute("SELECT g.*, s.owner_id FROM set_groups g JOIN sets s ON s.id = g.set_id WHERE g.id=?",
                       (group_id,)).fetchone()
    if not row or (row["owner_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "not_found")
    return row


def playlist_for(conn: sqlite3.Connection, user: dict, playlist_id: int):
    row = conn.execute(
        "SELECT p.*, s.owner_id, s.name AS set_name FROM playlists p JOIN sets s ON s.id = p.set_id WHERE p.id=?",
        (playlist_id,)).fetchone()
    if not row or (row["owner_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "not_found")
    return row


def _next_position(conn: sqlite3.Connection, table: str, column: str, value: int) -> int:
    row = conn.execute(f"SELECT COALESCE(MAX(position), -1) + 1 FROM {table} WHERE {column}=?", (value,)).fetchone()
    return int(row[0])


def _next_playlist_position(conn: sqlite3.Connection, set_id: int, group_id: int | None) -> int:
    if group_id is None:
        row = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM playlists WHERE set_id=? AND group_id IS NULL",
                           (set_id,)).fetchone()
    else:
        row = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM playlists WHERE group_id=?",
                           (group_id,)).fetchone()
    return int(row[0])


def _rule(row) -> dict:
    try:
        rule = json.loads(row["rule"]) if row["rule"] else {}
    except json.JSONDecodeError:
        rule = {}
    return {"tags": library.norm_tags(rule.get("tags", [])), "mode": "all" if rule.get("mode") == "all" else "any"}


def playlist_tracks(conn: sqlite3.Connection, row) -> list:
    """The playable tracks of a playlist, in playing order. `row` comes from playlist_for (it has owner_id)."""
    if row["kind"] == "tags":
        rule = _rule(row)
        return library.tracks_for_tags(conn, row["owner_id"], rule["tags"], rule["mode"])
    return conn.execute(
        "SELECT t.id, t.title, t.ext, t.duration, t.loudness, t.peak, t.silence_lead, t.silence_trail "
        "FROM playlist_items i JOIN tracks t ON t.id = i.track_id "
        "WHERE i.playlist_id=? AND t.deleted_at IS NULL ORDER BY i.position, i.id", (row["id"],)).fetchall()


def _require_manual(row) -> None:
    if row["kind"] == "tags":
        raise HTTPException(400, "tag_playlist")


def _insert_playlist(conn: sqlite3.Connection, set_id: int, group_id: int | None, body: PlaylistCreateIn) -> int:
    rule = json.dumps({"tags": library.norm_tags(body.tags), "mode": body.mode}) if body.kind == "tags" else None
    cur = conn.execute("INSERT INTO playlists(set_id, group_id, name, position, kind, rule) VALUES (?,?,?,?,?,?)",
                       (set_id, group_id, _name(body.name), _next_playlist_position(conn, set_id, group_id),
                        body.kind, rule))
    return int(cur.lastrowid)


def _playlist_with_stats(conn: sqlite3.Connection, row, owner_id: int) -> dict:
    if row["kind"] == "tags":
        rule = _rule(row)
        return _playlist_json(row, len(library.tracks_for_tags(conn, owner_id, rule["tags"], rule["mode"])), 0)
    stats = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(t.deleted_at IS NOT NULL), 0) AS gone "
        "FROM playlist_items i JOIN tracks t ON t.id = i.track_id WHERE i.playlist_id=?", (row["id"],)).fetchone()
    return _playlist_json(row, stats["n"], stats["gone"])


def playlist_items(conn: sqlite3.Connection, playlist_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT i.id, i.track_id, t.title, t.duration, t.deleted_at FROM playlist_items i "
        "JOIN tracks t ON t.id = i.track_id WHERE i.playlist_id=? ORDER BY i.position, i.id", (playlist_id,))
    return [{"id": r["id"], "track_id": r["track_id"], "title": r["title"], "duration": r["duration"],
             "deleted": r["deleted_at"] is not None} for r in rows]


def _playlist_json(row, count: int, missing: int) -> dict:
    return {"id": row["id"], "name": row["name"], "loop": bool(row["loop"]), "shuffle": bool(row["shuffle"]),
            "volume": row["volume"], "fade": row["fade"], "count": count, "missing": missing,
            "kind": row["kind"], "rule": _rule(row) if row["kind"] == "tags" else None}


@router.get("/sets")
def list_sets(request: Request, all: bool = False, user: dict = Depends(current_user)):
    show_all = all and user["role"] == "admin"
    with tx(get_settings(request).db_path) as conn:
        sets = conn.execute(
            "SELECT s.*, u.username AS owner FROM sets s JOIN users u ON u.id = s.owner_id "
            + ("" if show_all else "WHERE s.owner_id=? ") + "ORDER BY s.name COLLATE NOCASE",
            () if show_all else (user["id"],)).fetchall()
        result = []
        for s in sets:
            direct = [_playlist_with_stats(conn, p, s["owner_id"]) for p in conn.execute(
                "SELECT * FROM playlists WHERE set_id=? AND group_id IS NULL ORDER BY position, id", (s["id"],))]
            folders = []
            for g in conn.execute("SELECT * FROM set_groups WHERE set_id=? ORDER BY position, id", (s["id"],)):
                inside = [_playlist_with_stats(conn, p, s["owner_id"]) for p in conn.execute(
                    "SELECT * FROM playlists WHERE group_id=? ORDER BY position, id", (g["id"],))]
                folders.append({"id": g["id"], "name": g["name"], "playlists": inside})
            result.append({"id": s["id"], "name": s["name"], "owner_id": s["owner_id"], "owner": s["owner"],
                           "playlists": direct, "groups": folders})
        return result


@router.post("/sets", status_code=201)
def create_set(body: NameIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        cur = conn.execute("INSERT INTO sets(owner_id, name) VALUES (?,?)", (user["id"], _name(body.name)))
        return {"id": cur.lastrowid}


@router.patch("/sets/{set_id}")
def rename_set(set_id: int, body: NameIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _set_for(conn, user, set_id)
        conn.execute("UPDATE sets SET name=? WHERE id=?", (_name(body.name), set_id))
    return {"ok": True}


@router.delete("/sets/{set_id}")
def delete_set(set_id: int, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _set_for(conn, user, set_id)
        conn.execute("DELETE FROM sets WHERE id=?", (set_id,))
    return {"ok": True}


@router.post("/sets/{set_id}/groups", status_code=201)
def create_group(set_id: int, body: NameIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _set_for(conn, user, set_id)
        cur = conn.execute("INSERT INTO set_groups(set_id, name, position) VALUES (?,?,?)",
                           (set_id, _name(body.name), _next_position(conn, "set_groups", "set_id", set_id)))
        return {"id": cur.lastrowid}


@router.post("/sets/{set_id}/playlists", status_code=201)
def create_root_playlist(set_id: int, body: PlaylistCreateIn, request: Request, user: dict = Depends(current_user)):
    """A playlist directly under a set, without a folder."""
    with tx(get_settings(request).db_path) as conn:
        _set_for(conn, user, set_id)
        return {"id": _insert_playlist(conn, set_id, None, body)}


@router.put("/sets/{set_id}/playlists/order")
def order_root_playlists(set_id: int, body: OrderIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _set_for(conn, user, set_id)
        _apply_order(conn, "playlists", "set_id", set_id, body.ids, "AND group_id IS NULL")
    return {"ok": True}


@router.put("/sets/{set_id}/groups/order")
def order_groups(set_id: int, body: OrderIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _set_for(conn, user, set_id)
        _apply_order(conn, "set_groups", "set_id", set_id, body.ids)
    return {"ok": True}


@router.patch("/groups/{group_id}")
def rename_group(group_id: int, body: NameIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _group_for(conn, user, group_id)
        conn.execute("UPDATE set_groups SET name=? WHERE id=?", (_name(body.name), group_id))
    return {"ok": True}


@router.delete("/groups/{group_id}")
def delete_group(group_id: int, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _group_for(conn, user, group_id)
        conn.execute("DELETE FROM set_groups WHERE id=?", (group_id,))
    return {"ok": True}


@router.post("/groups/{group_id}/playlists", status_code=201)
def create_playlist(group_id: int, body: PlaylistCreateIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        group = _group_for(conn, user, group_id)
        return {"id": _insert_playlist(conn, group["set_id"], group_id, body)}


@router.put("/groups/{group_id}/playlists/order")
def order_playlists(group_id: int, body: OrderIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _group_for(conn, user, group_id)
        _apply_order(conn, "playlists", "group_id", group_id, body.ids)
    return {"ok": True}


def _apply_order(conn: sqlite3.Connection, table: str, column: str, value: int, ids: list[int],
                 extra: str = "") -> None:
    current = {r[0] for r in conn.execute(f"SELECT id FROM {table} WHERE {column}=? {extra}", (value,))}
    if set(ids) != current or len(ids) != len(current):
        raise HTTPException(400, "bad_order")
    conn.executemany(f"UPDATE {table} SET position=? WHERE id=?", [(pos, item) for pos, item in enumerate(ids)])


@router.get("/playlists/{playlist_id}")
def get_playlist(playlist_id: int, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        row = playlist_for(conn, user, playlist_id)
        if row["kind"] == "tags":  # the matches are the content: computed now, nothing to edit by hand
            items = [{"id": None, "track_id": r["id"], "title": r["title"], "duration": r["duration"], "deleted": False}
                     for r in playlist_tracks(conn, row)]
        else:
            items = playlist_items(conn, playlist_id)
        return {**_playlist_json(row, len(items), sum(i["deleted"] for i in items)), "set_id": row["set_id"],
                "group_id": row["group_id"], "items": items}


@router.patch("/playlists/{playlist_id}")
def patch_playlist(playlist_id: int, body: PlaylistPatchIn, request: Request, user: dict = Depends(current_user)):
    changes = body.model_dump(exclude_unset=True)
    with tx(get_settings(request).db_path) as conn:
        current = playlist_for(conn, user, playlist_id)
        if ("tags" in changes and changes["tags"] is not None) or changes.get("mode"):
            if current["kind"] != "tags":
                raise HTTPException(400, "not_a_tag_playlist")
            rule = _rule(current)
            if changes.get("tags") is not None:
                rule["tags"] = library.norm_tags(changes["tags"])
            if changes.get("mode"):
                rule["mode"] = changes["mode"]
            conn.execute("UPDATE playlists SET rule=? WHERE id=?", (json.dumps(rule), playlist_id))
        if "group_id" in changes or "set_id" in changes:
            if changes.get("group_id") is not None:
                group = _group_for(conn, user, changes["group_id"])
                target_set, target_group = group["set_id"], group["id"]
            else:
                target_set = changes.get("set_id") or current["set_id"]
                _set_for(conn, user, target_set)
                target_group = None
            if (target_set, target_group) != (current["set_id"], current["group_id"]):
                conn.execute("UPDATE playlists SET set_id=?, group_id=?, position=? WHERE id=?",
                             (target_set, target_group, _next_playlist_position(conn, target_set, target_group),
                              playlist_id))
        for field in ("loop", "shuffle"):
            if changes.get(field) is not None:
                conn.execute(f"UPDATE playlists SET {field}=? WHERE id=?", (int(changes[field]), playlist_id))
        if "volume" in changes:  # None clears the per-playlist volume
            conn.execute("UPDATE playlists SET volume=? WHERE id=?", (changes["volume"], playlist_id))
        if changes.get("fade") is not None:
            conn.execute("UPDATE playlists SET fade=? WHERE id=?", (changes["fade"], playlist_id))
        if changes.get("name"):
            conn.execute("UPDATE playlists SET name=? WHERE id=?", (_name(changes["name"]), playlist_id))
    return {"ok": True}


@router.post("/playlists/{playlist_id}/copy", status_code=201)
def copy_playlist(playlist_id: int, body: CopyIn, request: Request, user: dict = Depends(current_user)):
    """Give another user their own copy of a playlist. The tracks themselves are shared by everyone, so a copy is
    only a new playlist row (and its items) in a set of the recipient's; from then on the two lists are independent.
    """
    with tx(get_settings(request).db_path) as conn:
        source = playlist_for(conn, user, playlist_id)
        recipient = conn.execute("SELECT id, username, lang FROM users WHERE id=? AND disabled=0",
                                 (body.user_id,)).fetchone()
        if not recipient or recipient["id"] == source["owner_id"]:
            raise HTTPException(400, "bad_recipient")

        # One set per sender in the recipient's account, so copies do not mix with their own scenarios.
        set_name = _name(("Od " if recipient["lang"] == "pl" else "From ") + user["username"])
        target = conn.execute("SELECT id FROM sets WHERE owner_id=? AND name=?", (recipient["id"], set_name)).fetchone()
        target_set = target["id"] if target else conn.execute(
            "INSERT INTO sets(owner_id, name) VALUES (?,?)", (recipient["id"], set_name)).lastrowid

        live = playlist_tracks(conn, source)  # tracks that still exist, in playing order
        cur = conn.execute(
            "INSERT INTO playlists(set_id, group_id, name, position, loop, shuffle, volume, fade, kind, rule) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (target_set, None, source["name"], _next_playlist_position(conn, target_set, None), source["loop"],
             source["shuffle"], source["volume"], source["fade"], source["kind"], source["rule"]))
        new_id = int(cur.lastrowid)
        skipped = 0
        if source["kind"] == "manual":
            conn.executemany("INSERT INTO playlist_items(playlist_id, track_id, position) VALUES (?,?,?)",
                             [(new_id, t["id"], pos) for pos, t in enumerate(live)])
            skipped = conn.execute("SELECT COUNT(*) FROM playlist_items WHERE playlist_id=?",
                                   (playlist_id,)).fetchone()[0] - len(live)
        tags_copied = 0
        if body.with_my_tags:
            ids = [t["id"] for t in live]
            for start in range(0, len(ids), 400):  # stay well under SQLite's limit on bound parameters
                chunk = ids[start:start + 400]
                tags_copied += conn.execute(
                    "INSERT OR IGNORE INTO user_tags(user_id, track_id, tag) SELECT ?, track_id, tag FROM user_tags "
                    f"WHERE user_id=? AND track_id IN ({','.join('?' * len(chunk))})",
                    (recipient["id"], source["owner_id"], *chunk)).rowcount
        copy = playlist_for(conn, {"id": recipient["id"], "role": "user"}, new_id)
        matches = len(playlist_tracks(conn, copy))
    return {"id": new_id, "set_id": target_set, "set_name": set_name, "user": recipient["username"],
            "copied": matches, "skipped": skipped, "tags_copied": tags_copied}


@router.delete("/playlists/{playlist_id}")
def delete_playlist(playlist_id: int, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        playlist_for(conn, user, playlist_id)
        conn.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
    return {"ok": True}


@router.post("/playlists/{playlist_id}/items", status_code=201)
def add_items(playlist_id: int, body: TrackIdsIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _require_manual(playlist_for(conn, user, playlist_id))
        position = _next_position(conn, "playlist_items", "playlist_id", playlist_id)
        added = 0
        for track_id in body.track_ids:
            if conn.execute("SELECT 1 FROM tracks WHERE id=? AND deleted_at IS NULL", (track_id,)).fetchone():
                conn.execute("INSERT INTO playlist_items(playlist_id, track_id, position) VALUES (?,?,?)",
                             (playlist_id, track_id, position))
                position += 1
                added += 1
    return {"added": added}


@router.put("/playlists/{playlist_id}/order")
def order_items(playlist_id: int, body: OrderIn, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _require_manual(playlist_for(conn, user, playlist_id))
        _apply_order(conn, "playlist_items", "playlist_id", playlist_id, body.ids)
    return {"ok": True}


@router.put("/playlists/{playlist_id}/items/{item_id}")
def replace_item(playlist_id: int, item_id: int, body: ReplaceIn, request: Request,
                 user: dict = Depends(current_user)):
    """Swap the track in a slot, keeping its place (used to replace a deleted, greyed-out entry)."""
    with tx(get_settings(request).db_path) as conn:
        _require_manual(playlist_for(conn, user, playlist_id))
        if not conn.execute("SELECT 1 FROM tracks WHERE id=? AND deleted_at IS NULL", (body.track_id,)).fetchone():
            raise HTTPException(404, "not_found")
        cur = conn.execute("UPDATE playlist_items SET track_id=? WHERE id=? AND playlist_id=?",
                           (body.track_id, item_id, playlist_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "not_found")
    return {"ok": True}


@router.delete("/playlists/{playlist_id}/items/{item_id}")
def remove_item(playlist_id: int, item_id: int, request: Request, user: dict = Depends(current_user)):
    with tx(get_settings(request).db_path) as conn:
        _require_manual(playlist_for(conn, user, playlist_id))
        conn.execute("DELETE FROM playlist_items WHERE id=? AND playlist_id=?", (item_id, playlist_id))
    return {"ok": True}
