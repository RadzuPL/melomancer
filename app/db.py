"""SQLite access: schema migrations and a small transaction helper."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Each entry is applied once, in order; PRAGMA user_version records how many ran.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        pw_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
        disabled INTEGER NOT NULL DEFAULT 0,
        lang TEXT NOT NULL DEFAULT 'pl',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE guild_access (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        guild_id TEXT NOT NULL,
        PRIMARY KEY (user_id, guild_id)
    );

    CREATE TABLE tracks (
        id TEXT PRIMARY KEY,
        owner_id INTEGER NOT NULL REFERENCES users(id),
        title TEXT NOT NULL,
        original_title TEXT NOT NULL,
        ext TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        duration REAL,
        size INTEGER NOT NULL DEFAULT 0,
        source TEXT NOT NULL DEFAULT 'upload',
        source_url TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        deleted_at TEXT
    );
    CREATE UNIQUE INDEX idx_tracks_sha_live ON tracks(sha256) WHERE deleted_at IS NULL;
    CREATE INDEX idx_tracks_sha ON tracks(sha256);

    CREATE TABLE track_tags (
        track_id TEXT NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
        tag TEXT NOT NULL,
        PRIMARY KEY (track_id, tag)
    );

    CREATE TABLE user_tags (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        track_id TEXT NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
        tag TEXT NOT NULL,
        PRIMARY KEY (user_id, track_id, tag)
    );

    CREATE TABLE sets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL REFERENCES users(id),
        name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE set_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_id INTEGER NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        position INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL REFERENCES set_groups(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        position INTEGER NOT NULL DEFAULT 0,
        loop INTEGER NOT NULL DEFAULT 1,
        shuffle INTEGER NOT NULL DEFAULT 0,
        volume REAL,
        fade REAL NOT NULL DEFAULT 2
    );

    CREATE TABLE playlist_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
        track_id TEXT NOT NULL REFERENCES tracks(id),
        position INTEGER NOT NULL
    );
    CREATE INDEX idx_items_playlist ON playlist_items(playlist_id, position);

    CREATE TABLE downloads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        url TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',
        error TEXT,
        track_id TEXT,
        title TEXT,
        tags TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    # 2: playlists belong to a set directly; the folder (set_groups row) became optional.
    # SQLite cannot drop NOT NULL in place, so the table is rebuilt (foreign keys are off while migrating).
    """
    CREATE TABLE playlists_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_id INTEGER NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
        group_id INTEGER REFERENCES set_groups(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        position INTEGER NOT NULL DEFAULT 0,
        loop INTEGER NOT NULL DEFAULT 1,
        shuffle INTEGER NOT NULL DEFAULT 0,
        volume REAL,
        fade REAL NOT NULL DEFAULT 2
    );
    INSERT INTO playlists_new(id, set_id, group_id, name, position, loop, shuffle, volume, fade)
        SELECT p.id, g.set_id, p.group_id, p.name, p.position, p.loop, p.shuffle, p.volume, p.fade
        FROM playlists p JOIN set_groups g ON g.id = p.group_id;
    DROP TABLE playlists;
    ALTER TABLE playlists_new RENAME TO playlists;
    CREATE INDEX idx_playlists_set ON playlists(set_id, group_id, position);
    """,
    # 3: personal tags chosen when a download is queued.
    "ALTER TABLE downloads ADD COLUMN my_tags TEXT NOT NULL DEFAULT '[]';",
    # 4: playlists built automatically from tags: kind 'tags' with a rule {"tags": [...], "mode": "all"|"any"}.
    """
    ALTER TABLE playlists ADD COLUMN kind TEXT NOT NULL DEFAULT 'manual';
    ALTER TABLE playlists ADD COLUMN rule TEXT;
    """,
    # 5: loudness measured in the background (integrated LUFS and true peak in dBTP; NULL = unknown), plus a small
    # key/value table for settings an administrator changes in the panel.
    """
    ALTER TABLE tracks ADD COLUMN loudness REAL;
    ALTER TABLE tracks ADD COLUMN peak REAL;
    ALTER TABLE tracks ADD COLUMN loudness_tried INTEGER NOT NULL DEFAULT 0;
    CREATE TABLE app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # 6: silence at the start and end of a track (seconds to skip / to cut), measured with the threshold in silence_db;
    # a changed threshold makes the worker measure again.
    """
    ALTER TABLE tracks ADD COLUMN silence_lead REAL;
    ALTER TABLE tracks ADD COLUMN silence_trail REAL;
    ALTER TABLE tracks ADD COLUMN silence_db REAL;
    """,
]


def _backup_before_migration(path: Path, version: int) -> None:
    """Keep a copy of the database as it was before a schema change."""
    target = path.with_name(f"{path.name}.before-v{version + 1}")
    if target.exists():
        return
    source = sqlite3.connect(path)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if 0 < version < len(MIGRATIONS):
            _backup_before_migration(path, version)
        for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
            conn.executescript(script)
            conn.execute(f"PRAGMA user_version={number}")
        conn.commit()
    finally:
        conn.close()


@contextmanager
def tx(path: Path) -> Iterator[sqlite3.Connection]:
    """One connection, one transaction: commit on success, roll back on error."""
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
