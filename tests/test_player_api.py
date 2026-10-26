from __future__ import annotations

from .conftest import login, make_user, upload


def _playlist_with_tracks(env, wavs, count=2):
    ids = [upload(env, w).json()["id"] for w in wavs[:count]]
    set_id = env.client.post("/api/sets", json={"name": "S"}).json()["id"]
    group_id = env.client.post(f"/api/sets/{set_id}/groups", json={"name": "G"}).json()["id"]
    playlist_id = env.client.post(f"/api/groups/{group_id}/playlists", json={"name": "P"}).json()["id"]
    env.client.post(f"/api/playlists/{playlist_id}/items", json={"track_ids": ids})
    return playlist_id, ids


def _grant(env, user_id, guild_ids):
    login(env, "admin")
    res = env.client.put(f"/api/users/{user_id}/guilds", json={"guild_ids": guild_ids})
    assert res.status_code == 200


def test_users_only_see_servers_they_were_given(env):
    uid = make_user(env, "mg1")
    login(env, "mg1")
    assert env.client.get("/api/player/guilds").json() == []
    assert env.client.get("/api/player/111/state").status_code == 404

    _grant(env, uid, ["111"])
    login(env, "mg1")
    assert [g["id"] for g in env.client.get("/api/player/guilds").json()] == ["111"]
    assert env.client.get("/api/player/111/state").status_code == 200
    assert env.client.get("/api/player/222/state").status_code == 404

    login(env, "admin")
    assert len(env.client.get("/api/player/guilds").json()) == 2


def test_play_playlist_skips_deleted_tracks(env, wavs):
    login(env, "admin")
    playlist_id, ids = _playlist_with_tracks(env, wavs, 3)
    env.client.delete(f"/api/tracks/{ids[1]}?force=true")
    env.client.post("/api/player/111/connect", json={"channel_id": "100100"})
    res = env.client.post("/api/player/111/play", json={"playlist_id": playlist_id})
    assert res.status_code == 200 and res.json()["state"] == "playing"
    assert env.bot.played[-1]["titles"] == ["tone0", "tone2"]
    assert env.bot.played[-1]["opts"]["loop"] is True


def test_play_needs_exactly_one_target_and_a_connection(env, wavs):
    login(env, "admin")
    playlist_id, ids = _playlist_with_tracks(env, wavs, 1)
    assert env.client.post("/api/player/111/play", json={}).status_code == 400
    assert env.client.post("/api/player/111/play", json={"playlist_id": playlist_id, "track_id": ids[0]}).status_code == 400
    assert env.client.post("/api/player/111/play", json={"playlist_id": playlist_id}).status_code == 409


def test_playing_a_foreign_playlist_is_not_found(env, wavs):
    owner = make_user(env, "owner")
    other = make_user(env, "other")
    login(env, "owner")
    playlist_id, _ = _playlist_with_tracks(env, wavs, 1)
    _grant(env, other, ["111"])
    login(env, "other")
    env.client.post("/api/player/111/connect", json={"channel_id": "100100"})
    assert env.client.post("/api/player/111/play", json={"playlist_id": playlist_id}).status_code == 404
    assert owner != other


def test_only_one_controller_per_server(env, wavs):
    a = make_user(env, "alpha")
    b = make_user(env, "bravo")
    _grant(env, a, ["111"])
    _grant(env, b, ["111"])
    login(env, "alpha")
    playlist_id, _ = _playlist_with_tracks(env, wavs, 1)
    env.client.post("/api/player/111/connect", json={"channel_id": "100100"})
    assert env.client.post("/api/player/111/play", json={"playlist_id": playlist_id}).status_code == 200

    login(env, "bravo")
    busy = env.client.post("/api/player/111/pause")
    assert busy.status_code == 409 and busy.json()["detail"] == "busy"
    assert env.client.post("/api/player/111/volume", json={"volume": 0.2}).status_code == 409

    login(env, "admin")
    assert env.client.post("/api/player/111/pause").status_code == 200

    login(env, "alpha")
    assert env.client.post("/api/player/111/stop").json()["state"] == "idle"
    login(env, "bravo")
    assert env.client.post("/api/player/111/volume", json={"volume": 0.2}).status_code == 200


def test_volume_is_bounded(env):
    login(env, "admin")
    assert env.client.post("/api/player/111/volume", json={"volume": 2.5}).status_code == 422
    assert env.client.post("/api/player/111/volume", json={"volume": -0.1}).status_code == 422
    assert env.client.post("/api/player/111/volume", json={"volume": 0.5}).json()["volume"] == 0.5


def test_bad_channel_or_guild_ids_are_rejected(env):
    login(env, "admin")
    assert env.client.post("/api/player/111/connect", json={"channel_id": "abc"}).status_code == 422
    assert env.client.get("/api/player/not-a-number/state").status_code == 400
