"""Playing in the browser: the server resolves the queue and the part of each track to play."""
from __future__ import annotations

import pytest

from app.db import tx
from app.loudness import linear_gain
from app.playback import span

from .conftest import login, make_user, upload


def _playlist(env, ids, name="P"):
    set_id = env.client.post("/api/sets", json={"name": "S" + name}).json()["id"]
    playlist = env.client.post(f"/api/sets/{set_id}/playlists", json={"name": name}).json()["id"]
    env.client.post(f"/api/playlists/{playlist}/items", json={"track_ids": ids})
    return playlist


def _long(env, track_id, **columns):
    sets = ", ".join(f"{k}=?" for k in ("duration", *columns))
    with tx(env.settings.db_path) as conn:
        conn.execute(f"UPDATE tracks SET {sets} WHERE id=?", (100.0, *columns.values(), track_id))


def test_span_rules():
    assert span(100, 2, 3, None, None, True) == (2, 97, True)
    assert span(100, 2, 3, None, None, False) == (0.0, 100, False)
    # a hand-set side wins, whatever the switch says, and only for its own side
    assert span(100, 2, 3, 5, None, False) == (5, 100, False)
    assert span(100, 2, 3, None, 90, True) == (2, 90, True)
    # a seek replaces the start; a trim that leaves under a second is ignored
    assert span(100, 2, 3, None, None, True, offset=40) == (40, 97, True)
    assert span(100, 0, 0, 99.5, None, True) == (0.0, 100, False)


def test_queue_of_a_playlist_has_spans_gains_and_options(env, wavs):
    login(env, "admin")
    ids = [upload(env, w).json()["id"] for w in wavs[:2]]
    _long(env, ids[0], silence_lead=1.5, silence_trail=2.0, loudness=-24.0, peak=-6.0)
    _long(env, ids[1], trim_start=10.0, trim_end=60.0)
    playlist = _playlist(env, ids)
    res = env.client.post("/api/local/queue", json={"playlist_id": playlist})
    assert res.status_code == 200
    data = res.json()
    assert data["playlist"]["name"] == "P" and data["options"]["loop"] is True
    first, second = data["items"]
    assert (first["start"], first["end"], first["cut"]) == (1.5, 98.0, True)
    # the same rule as the bot's: -24 LUFS lifted towards the target, as far as the peak and the boost limit allow
    assert first["gain"] == pytest.approx(linear_gain(-24.0, -6.0, -16.0, 6.0)) and first["gain"] > 1.5
    assert (second["start"], second["end"]) == (10.0, 60.0) and second["gain"] == 1.0


def test_queue_follows_the_switches_and_the_settings_revision(env, wavs):
    login(env, "admin")
    track = upload(env, wavs[0]).json()["id"]
    _long(env, track, silence_lead=1.5, silence_trail=2.0, loudness=-24.0, peak=-6.0)
    before = env.client.get("/api/system").json()["settings_rev"]
    res = env.client.patch("/api/system", json={"trim_silence": False, "normalize": False})
    assert res.json()["settings_rev"] > before
    item = env.client.post("/api/local/queue", json={"track_id": track}).json()["items"][0]
    assert (item["start"], item["end"], item["gain"]) == (0.0, 100.0, 1.0)
    fresh = env.client.post("/api/local/resolve", json={"track_ids": [track, track]}).json()
    assert fresh["settings_rev"] == res.json()["settings_rev"] and len(fresh["items"]) == 1


def test_queue_by_tags_and_single_track(env, wavs):
    login(env, "admin")
    track = upload(env, wavs[0]).json()["id"]
    assert env.client.patch(f"/api/tracks/{track}", json={"tags": ["bitwa"]}).status_code == 200
    one = env.client.post("/api/local/queue", json={"track_id": track}).json()
    assert one["options"]["loop"] is False and one["items"][0]["track_id"] == track
    tagged = env.client.post("/api/local/queue", json={"tags": ["bitwa"]}).json()
    assert [i["track_id"] for i in tagged["items"]] == [track] and tagged["options"]["shuffle"] is True
    assert env.client.post("/api/local/queue", json={"tags": ["nic"]}).status_code == 400
    assert env.client.post("/api/local/queue", json={}).status_code == 400
    assert env.client.post("/api/local/queue", json={"track_id": "nope"}).status_code == 404


def test_someone_elses_playlist_is_not_found_and_login_is_required(env, wavs):
    make_user(env, "owner")
    make_user(env, "other")
    login(env, "owner")
    playlist = _playlist(env, [upload(env, wavs[0]).json()["id"]])
    login(env, "other")
    assert env.client.post("/api/local/queue", json={"playlist_id": playlist}).status_code == 404
    env.client.post("/api/auth/logout")
    assert env.client.post("/api/local/queue", json={"playlist_id": playlist}).status_code == 401
    assert env.client.post("/api/local/resolve", json={"track_ids": ["x"]}).status_code == 401
