from __future__ import annotations

import sqlite3

from app.db import MIGRATIONS, init_db


def test_migration_2_keeps_playlists_and_allows_playlists_without_a_folder(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(MIGRATIONS[0])
    conn.execute("PRAGMA user_version=1")
    conn.execute("INSERT INTO users(id, username, pw_hash) VALUES (1, 'u', 'x')")
    conn.execute("INSERT INTO sets(id, owner_id, name) VALUES (1, 1, 'Druga')")
    conn.execute("INSERT INTO set_groups(id, set_id, name) VALUES (5, 1, 'Po co to?')")
    conn.execute("INSERT INTO playlists(id, group_id, name, position, loop, shuffle, volume, fade) "
                 "VALUES (11, 5, 'Walka', 0, 0, 1, 0.7, 4)")
    conn.execute("INSERT INTO tracks(id, owner_id, title, original_title, ext, sha256) "
                 "VALUES ('t', 1, 'T', 'T', '.wav', 'h')")
    conn.execute("INSERT INTO playlist_items(playlist_id, track_id, position) VALUES (11, 't', 0)")
    conn.commit()
    conn.close()

    init_db(path)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM playlists WHERE id=11").fetchone()
    assert (row["set_id"], row["group_id"], row["name"], row["loop"], row["shuffle"], row["volume"], row["fade"]) == \
        (1, 5, "Walka", 0, 1, 0.7, 4)
    assert conn.execute("SELECT COUNT(*) FROM playlist_items WHERE playlist_id=11").fetchone()[0] == 1
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)

    conn.execute("INSERT INTO playlists(set_id, group_id, name) VALUES (1, NULL, 'root')")
    next_id = conn.execute("SELECT id FROM playlists WHERE name='root'").fetchone()[0]
    assert next_id > 11  # the id sequence continued after the copied rows
    conn.execute("PRAGMA foreign_keys=ON")
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()

    assert (tmp_path / "old.db.before-v2").exists()  # copy of the database as it was before the change


def test_fresh_database_gets_every_migration_without_a_backup(tmp_path):
    path = tmp_path / "new.db"
    init_db(path)
    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
    assert "my_tags" in [r[1] for r in conn.execute("PRAGMA table_info(downloads)")]
    conn.close()
    assert not list(tmp_path.glob("*.before-*"))
    init_db(path)  # running again changes nothing
