from __future__ import annotations

from .conftest import login, make_user, upload


def _tree(env, name="Zew Cthulhu"):
    set_id = env.client.post("/api/sets", json={"name": name}).json()["id"]
    group_id = env.client.post(f"/api/sets/{set_id}/groups", json={"name": "Lokacje"}).json()["id"]
    playlist_id = env.client.post(f"/api/groups/{group_id}/playlists", json={"name": "Dwor"}).json()["id"]
    return set_id, group_id, playlist_id


def test_other_users_cannot_see_or_touch_a_set(env):
    make_user(env, "mg1")
    make_user(env, "mg2")
    login(env, "mg1")
    set_id, group_id, playlist_id = _tree(env)

    login(env, "mg2")
    assert env.client.get("/api/sets").json() == []
    assert env.client.patch(f"/api/sets/{set_id}", json={"name": "x"}).status_code == 404
    assert env.client.delete(f"/api/groups/{group_id}").status_code == 404
    assert env.client.get(f"/api/playlists/{playlist_id}").status_code == 404
    assert env.client.post(f"/api/playlists/{playlist_id}/items", json={"track_ids": ["x"]}).status_code == 404

    login(env, "admin")
    assert env.client.get("/api/sets").json() == []
    assert len(env.client.get("/api/sets?all=true").json()) == 1
    assert env.client.get(f"/api/playlists/{playlist_id}").status_code == 200


def test_items_can_be_added_reordered_replaced_and_removed(env, wavs):
    login(env, "admin")
    ids = [upload(env, w).json()["id"] for w in wavs[:3]]
    _, _, playlist_id = _tree(env)
    added = env.client.post(f"/api/playlists/{playlist_id}/items", json={"track_ids": ids})
    assert added.json() == {"added": 3}

    items = env.client.get(f"/api/playlists/{playlist_id}").json()["items"]
    assert [i["track_id"] for i in items] == ids

    reordered = [items[2]["id"], items[0]["id"], items[1]["id"]]
    assert env.client.put(f"/api/playlists/{playlist_id}/order", json={"ids": reordered}).status_code == 200
    after = env.client.get(f"/api/playlists/{playlist_id}").json()["items"]
    assert [i["id"] for i in after] == reordered
    assert env.client.put(f"/api/playlists/{playlist_id}/order", json={"ids": reordered[:2]}).status_code == 400

    new_id = upload(env, wavs[3]).json()["id"]
    first = after[0]["id"]
    assert env.client.put(f"/api/playlists/{playlist_id}/items/{first}", json={"track_id": new_id}).status_code == 200
    replaced = env.client.get(f"/api/playlists/{playlist_id}").json()["items"]
    assert replaced[0]["track_id"] == new_id  # same slot

    assert env.client.delete(f"/api/playlists/{playlist_id}/items/{first}").status_code == 200
    assert len(env.client.get(f"/api/playlists/{playlist_id}").json()["items"]) == 2


def test_playlist_settings_and_tree(env):
    login(env, "admin")
    _, group_id, playlist_id = _tree(env)
    res = env.client.patch(f"/api/playlists/{playlist_id}",
                           json={"name": "Walka", "loop": False, "shuffle": True, "fade": 4, "volume": 0.7})
    assert res.status_code == 200
    playlist = env.client.get("/api/sets").json()[0]["groups"][0]["playlists"][0]
    assert playlist["name"] == "Walka" and playlist["loop"] is False and playlist["shuffle"] is True
    assert playlist["fade"] == 4 and playlist["volume"] == 0.7

    env.client.patch(f"/api/playlists/{playlist_id}", json={"volume": None})
    assert env.client.get("/api/sets").json()[0]["groups"][0]["playlists"][0]["volume"] is None
    assert env.client.patch(f"/api/playlists/{playlist_id}", json={"fade": 99}).status_code == 422


def test_deleting_a_set_removes_its_contents(env):
    login(env, "admin")
    set_id, _, playlist_id = _tree(env)
    assert env.client.delete(f"/api/sets/{set_id}").status_code == 200
    assert env.client.get(f"/api/playlists/{playlist_id}").status_code == 404


def test_playlists_can_live_directly_under_a_set(env):
    login(env, "admin")
    set_id = env.client.post("/api/sets", json={"name": "Druga"}).json()["id"]
    walka = env.client.post(f"/api/sets/{set_id}/playlists", json={"name": "Walka"}).json()["id"]
    spokoj = env.client.post(f"/api/sets/{set_id}/playlists", json={"name": "Spokoj"}).json()["id"]
    folder = env.client.post(f"/api/sets/{set_id}/groups", json={"name": "Specjalne"}).json()["id"]
    inner = env.client.post(f"/api/groups/{folder}/playlists", json={"name": "Wewnatrz"}).json()["id"]

    tree = env.client.get("/api/sets").json()[0]
    assert [p["name"] for p in tree["playlists"]] == ["Walka", "Spokoj"]
    assert [g["name"] for g in tree["groups"]] == ["Specjalne"]
    assert [p["name"] for p in tree["groups"][0]["playlists"]] == ["Wewnatrz"]

    assert env.client.put(f"/api/sets/{set_id}/playlists/order", json={"ids": [spokoj, walka]}).status_code == 200
    assert [p["name"] for p in env.client.get("/api/sets").json()[0]["playlists"]] == ["Spokoj", "Walka"]
    assert env.client.put(f"/api/sets/{set_id}/playlists/order", json={"ids": [spokoj, walka, inner]}).status_code == 400

    detail = env.client.get(f"/api/playlists/{walka}").json()
    assert detail["set_id"] == set_id and detail["group_id"] is None


def test_playlists_can_be_moved_between_folder_and_set_root(env):
    login(env, "admin")
    set_id = env.client.post("/api/sets", json={"name": "Druga"}).json()["id"]
    other_set = env.client.post("/api/sets", json={"name": "Inny"}).json()["id"]
    folder = env.client.post(f"/api/sets/{set_id}/groups", json={"name": "Specjalne"}).json()["id"]
    playlist = env.client.post(f"/api/groups/{folder}/playlists", json={"name": "Walka"}).json()["id"]

    assert env.client.patch(f"/api/playlists/{playlist}", json={"group_id": None}).status_code == 200
    tree = {s["name"]: s for s in env.client.get("/api/sets").json()}
    assert [p["name"] for p in tree["Druga"]["playlists"]] == ["Walka"]
    assert tree["Druga"]["groups"][0]["playlists"] == []

    assert env.client.patch(f"/api/playlists/{playlist}", json={"group_id": folder}).status_code == 200
    detail = env.client.get(f"/api/playlists/{playlist}").json()
    assert detail["group_id"] == folder and detail["set_id"] == set_id

    assert env.client.patch(f"/api/playlists/{playlist}", json={"set_id": other_set, "group_id": None}).status_code == 200
    detail = env.client.get(f"/api/playlists/{playlist}").json()
    assert detail["group_id"] is None and detail["set_id"] == other_set


def test_root_playlists_are_private_too(env):
    make_user(env, "mg1")
    make_user(env, "mg2")
    login(env, "mg1")
    set_id = env.client.post("/api/sets", json={"name": "Moj"}).json()["id"]
    playlist = env.client.post(f"/api/sets/{set_id}/playlists", json={"name": "Sekret"}).json()["id"]
    folder = env.client.post(f"/api/sets/{set_id}/groups", json={"name": "F"}).json()["id"]

    login(env, "mg2")
    assert env.client.post(f"/api/sets/{set_id}/playlists", json={"name": "x"}).status_code == 404
    assert env.client.put(f"/api/sets/{set_id}/playlists/order", json={"ids": [playlist]}).status_code == 404
    assert env.client.get(f"/api/playlists/{playlist}").status_code == 404
    own = env.client.post("/api/sets", json={"name": "Wlasny"}).json()["id"]
    mine = env.client.post(f"/api/sets/{own}/playlists", json={"name": "Moja"}).json()["id"]
    assert env.client.patch(f"/api/playlists/{mine}", json={"group_id": folder}).status_code == 404
    assert env.client.patch(f"/api/playlists/{mine}", json={"set_id": set_id, "group_id": None}).status_code == 404
