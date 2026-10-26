from __future__ import annotations

from .conftest import login, make_user, upload


def _library(env, wavs):
    """tone0: ambient+rain, tone1: ambient, tone2: combat (+ personal tag 'sesja 3')."""
    ids = [upload(env, w).json()["id"] for w in wavs[:3]]
    for track_id, tags in zip(ids, (["ambient", "rain"], ["ambient"], ["combat"])):
        assert env.client.patch(f"/api/tracks/{track_id}", json={"tags": tags}).status_code == 200
    assert env.client.put(f"/api/tracks/{ids[2]}/my-tags", json={"tags": ["sesja 3"]}).status_code == 200
    return ids


def _new_set(env):
    return env.client.post("/api/sets", json={"name": "Druga"}).json()["id"]


def _tag_playlist(env, set_id, name, tags, mode="any"):
    res = env.client.post(f"/api/sets/{set_id}/playlists", json={"name": name, "kind": "tags", "tags": tags, "mode": mode})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _titles(env, playlist_id):
    return [i["title"] for i in env.client.get(f"/api/playlists/{playlist_id}").json()["items"]]


def test_any_and_all_modes(env, wavs):
    login(env, "admin")
    _library(env, wavs)
    set_id = _new_set(env)
    assert _titles(env, _tag_playlist(env, set_id, "Spokoj", ["Ambient"])) == ["tone0", "tone1"]
    assert _titles(env, _tag_playlist(env, set_id, "Deszcz", ["ambient", "rain"], "all")) == ["tone0"]
    assert _titles(env, _tag_playlist(env, set_id, "Dowolny", ["rain", "combat"], "any")) == ["tone0", "tone2"]
    assert _titles(env, _tag_playlist(env, set_id, "Pusta", [])) == []


def test_personal_tags_count_only_for_their_owner(env, wavs):
    make_user(env, "mg2")
    login(env, "admin")
    _library(env, wavs)
    mine = _tag_playlist(env, _new_set(env), "Sesja", ["sesja 3"])
    assert _titles(env, mine) == ["tone2"]

    login(env, "mg2")
    other = _tag_playlist(env, _new_set(env), "Sesja", ["sesja 3"])
    assert _titles(env, other) == []  # the tag is admin's private one


def test_the_playlist_follows_the_library(env, wavs):
    login(env, "admin")
    ids = _library(env, wavs)
    playlist = _tag_playlist(env, _new_set(env), "Spokoj", ["ambient"])
    assert env.client.get("/api/sets").json()[0]["playlists"][0]["count"] == 2

    env.client.patch(f"/api/tracks/{ids[2]}", json={"tags": ["combat", "ambient"]})  # tagged later: appears by itself
    assert _titles(env, playlist) == ["tone0", "tone1", "tone2"]
    env.client.delete(f"/api/tracks/{ids[0]}")  # deleted: disappears, no grey entry
    assert _titles(env, playlist) == ["tone1", "tone2"]
    entry = env.client.get("/api/sets").json()[0]["playlists"][0]
    assert entry["count"] == 2 and entry["missing"] == 0 and entry["kind"] == "tags"
    assert entry["rule"] == {"tags": ["ambient"], "mode": "any"}


def test_rule_can_be_edited_and_hand_editing_is_refused(env, wavs):
    login(env, "admin")
    ids = _library(env, wavs)
    set_id = _new_set(env)
    playlist = _tag_playlist(env, set_id, "Spokoj", ["ambient"])
    assert env.client.patch(f"/api/playlists/{playlist}", json={"tags": ["combat"], "mode": "all"}).status_code == 200
    detail = env.client.get(f"/api/playlists/{playlist}").json()
    assert detail["rule"] == {"tags": ["combat"], "mode": "all"} and [i["title"] for i in detail["items"]] == ["tone2"]

    assert env.client.post(f"/api/playlists/{playlist}/items", json={"track_ids": [ids[0]]}).status_code == 400
    assert env.client.put(f"/api/playlists/{playlist}/order", json={"ids": []}).status_code == 400
    assert env.client.put(f"/api/playlists/{playlist}/items/1", json={"track_id": ids[0]}).status_code == 400
    assert env.client.delete(f"/api/playlists/{playlist}/items/1").status_code == 400

    manual = env.client.post(f"/api/sets/{set_id}/playlists", json={"name": "Reczna"}).json()["id"]
    assert env.client.patch(f"/api/playlists/{manual}", json={"tags": ["x"]}).status_code == 400


def test_a_tag_playlist_plays_in_title_order(env, wavs):
    login(env, "admin")
    _library(env, wavs)
    playlist = _tag_playlist(env, _new_set(env), "Spokoj", ["ambient"])
    env.client.post("/api/player/111/connect", json={"channel_id": "100100"})
    assert env.client.post("/api/player/111/play", json={"playlist_id": playlist}).status_code == 200
    played = env.bot.played[-1]
    assert played["titles"] == ["tone0", "tone1"] and played["playlist"]["name"] == "Spokoj"


def test_play_by_tags_without_a_saved_playlist(env, wavs):
    login(env, "admin")
    _library(env, wavs)
    env.client.post("/api/player/111/connect", json={"channel_id": "100100"})
    res = env.client.post("/api/player/111/play", json={"tags": ["Ambient", "sesja 3"], "mode": "any"})
    assert res.status_code == 200
    played = env.bot.played[-1]
    assert played["titles"] == ["tone0", "tone1", "tone2"]
    assert played["playlist"] == {"id": None, "name": "# ambient | sesja 3", "set": None}
    assert played["opts"]["shuffle"] is True and played["opts"]["loop"] is True

    res = env.client.post("/api/player/111/play", json={"tags": ["ambient", "combat"], "mode": "all"})
    assert res.status_code == 400 and res.json()["detail"] == "empty_playlist"
    assert env.client.post("/api/player/111/play", json={"tags": ["ambient"], "playlist_id": 1}).status_code == 400
    assert env.client.post("/api/player/111/play", json={"tags": []}).status_code == 400


def test_tag_playlists_are_private_like_the_others(env, wavs):
    make_user(env, "mg2")
    login(env, "admin")
    _library(env, wavs)
    playlist = _tag_playlist(env, _new_set(env), "Spokoj", ["ambient"])
    login(env, "mg2")
    assert env.client.get(f"/api/playlists/{playlist}").status_code == 404
    assert env.client.patch(f"/api/playlists/{playlist}", json={"tags": ["x"]}).status_code == 404
