"""Giving someone a copy of a playlist: independent rows, shared tracks, personal tags only when asked."""
from __future__ import annotations

from .conftest import login, make_user, upload


def _scenario(env, wavs):
    """admin: playlist 'Walka' with tone0, tone1, tone2 (tone1 deleted afterwards); tone2 carries a private tag."""
    login(env, "admin")
    ids = [upload(env, w).json()["id"] for w in wavs[:3]]
    set_id = env.client.post("/api/sets", json={"name": "Druga"}).json()["id"]
    playlist = env.client.post(f"/api/sets/{set_id}/playlists", json={"name": "Walka"}).json()["id"]
    assert env.client.post(f"/api/playlists/{playlist}/items", json={"track_ids": ids}).status_code == 201
    env.client.patch(f"/api/playlists/{playlist}", json={"loop": False, "shuffle": True, "fade": 4, "volume": 0.7})
    env.client.put(f"/api/tracks/{ids[2]}/my-tags", json={"tags": ["sesja 3"]})
    assert env.client.delete(f"/api/tracks/{ids[1]}?force=true").status_code == 200
    return ids, playlist


def _only_playlist(env):
    sets = env.client.get("/api/sets").json()
    assert len(sets) == 1, sets
    return sets[0], sets[0]["playlists"][0]


def test_the_copy_is_an_independent_playlist_in_a_set_named_after_the_sender(env, wavs):
    bob = make_user(env, "bob")
    ids, playlist = _scenario(env, wavs)

    res = env.client.post(f"/api/playlists/{playlist}/copy", json={"user_id": bob})
    assert res.status_code == 201, res.text
    body = res.json()
    assert (body["set_name"], body["user"], body["copied"], body["skipped"], body["tags_copied"]) == ("Od admin", "bob", 2, 1, 0)

    login(env, "bob")
    shared_set, copy = _only_playlist(env)
    assert shared_set["name"] == "Od admin"
    assert (copy["name"], copy["loop"], copy["shuffle"], copy["fade"], copy["volume"]) == ("Walka", False, True, 4, 0.7)
    detail = env.client.get(f"/api/playlists/{copy['id']}").json()
    assert [i["track_id"] for i in detail["items"]] == [ids[0], ids[2]]  # the deleted track is left out

    # changing the copy does not touch the original
    assert env.client.delete(f"/api/playlists/{copy['id']}/items/{detail['items'][0]['id']}").status_code == 200
    login(env, "admin")
    original = env.client.get(f"/api/playlists/{playlist}").json()
    assert len(original["items"]) == 3 and original["items"][1]["deleted"] is True


def test_private_tags_travel_only_when_asked_for(env, wavs):
    bob = make_user(env, "bob")
    ids, playlist = _scenario(env, wavs)

    env.client.post(f"/api/playlists/{playlist}/copy", json={"user_id": bob})
    login(env, "bob")
    assert {t["id"]: t["my_tags"] for t in env.client.get("/api/tracks").json()}[ids[2]] == []

    login(env, "admin")
    res = env.client.post(f"/api/playlists/{playlist}/copy", json={"user_id": bob, "with_my_tags": True})
    assert res.json()["tags_copied"] == 1
    login(env, "bob")
    assert {t["id"]: t["my_tags"] for t in env.client.get("/api/tracks").json()}[ids[2]] == ["sesja 3"]
    login(env, "admin")
    assert {t["id"]: t["my_tags"] for t in env.client.get("/api/tracks").json()}[ids[2]] == ["sesja 3"]  # still his


def test_a_second_copy_lands_in_the_same_set(env, wavs):
    bob = make_user(env, "bob")
    _, playlist = _scenario(env, wavs)
    first = env.client.post(f"/api/playlists/{playlist}/copy", json={"user_id": bob}).json()
    second = env.client.post(f"/api/playlists/{playlist}/copy", json={"user_id": bob}).json()
    assert first["set_id"] == second["set_id"] and first["id"] != second["id"]
    login(env, "bob")
    shared_set, _ = _only_playlist(env)
    assert len(shared_set["playlists"]) == 2


def test_an_automatic_playlist_is_copied_as_a_rule_and_needs_the_tags_to_find_anything(env, wavs):
    bob = make_user(env, "bob")
    ids, _ = _scenario(env, wavs)
    set_id = env.client.get("/api/sets").json()[0]["id"]
    auto = env.client.post(f"/api/sets/{set_id}/playlists",
                           json={"name": "Sesja", "kind": "tags", "tags": ["sesja 3"]}).json()["id"]

    bare = env.client.post(f"/api/playlists/{auto}/copy", json={"user_id": bob}).json()
    assert bare["copied"] == 0  # the rule uses a private tag the recipient does not have
    full = env.client.post(f"/api/playlists/{auto}/copy", json={"user_id": bob, "with_my_tags": True}).json()
    assert full["copied"] == 1 and full["tags_copied"] == 1

    login(env, "bob")
    copy = env.client.get(f"/api/playlists/{full['id']}").json()
    assert copy["kind"] == "tags" and copy["rule"] == {"tags": ["sesja 3"], "mode": "any"}
    assert [i["track_id"] for i in copy["items"]] == [ids[2]]


def test_bad_recipients_and_other_peoples_playlists_are_refused(env, wavs):
    bob = make_user(env, "bob")
    carol = make_user(env, "carol")
    admin_id = env.client.get("/api/auth/me").json()["id"]
    _, playlist = _scenario(env, wavs)

    assert env.client.post(f"/api/playlists/{playlist}/copy", json={"user_id": admin_id}).status_code == 400  # the owner
    assert env.client.post(f"/api/playlists/{playlist}/copy", json={"user_id": 9999}).status_code == 400
    assert env.client.patch(f"/api/users/{carol}", json={"disabled": True}).status_code == 200
    assert env.client.post(f"/api/playlists/{playlist}/copy", json={"user_id": carol}).status_code == 400

    login(env, "bob")  # bob cannot copy a playlist he cannot see, and learns nothing about it
    assert env.client.post(f"/api/playlists/{playlist}/copy", json={"user_id": bob}).status_code == 404


def test_the_set_name_follows_the_language_of_the_recipient(env, wavs):
    bob = make_user(env, "bob")
    login(env, "bob")
    assert env.client.patch("/api/auth/me", json={"lang": "en"}).status_code == 200
    _, playlist = _scenario(env, wavs)
    assert env.client.post(f"/api/playlists/{playlist}/copy", json={"user_id": bob}).json()["set_name"] == "From admin"


def test_people_lists_active_accounts_without_yourself(env):
    make_user(env, "bob")
    carol = make_user(env, "carol")
    env.client.patch(f"/api/users/{carol}", json={"disabled": True})
    login(env, "bob")
    assert [p["username"] for p in env.client.get("/api/people").json()] == ["admin"]
    env.client.cookies.clear()
    assert env.client.get("/api/people").status_code == 401
