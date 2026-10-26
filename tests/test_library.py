from __future__ import annotations

from .conftest import login, make_user, upload


def _first(env):
    return env.client.get("/api/tracks").json()[0]


def test_upload_lists_and_deduplicates(env, wavs):
    login(env, "admin")
    first = upload(env, wavs[0])
    assert first.status_code == 201 and first.json()["status"] == "created"
    again = upload(env, wavs[0], name="renamed.wav")
    assert again.json()["status"] == "duplicate"
    assert again.json()["id"] == first.json()["id"]

    tracks = env.client.get("/api/tracks").json()
    assert len(tracks) == 1
    assert tracks[0]["title"] == "tone0"
    assert tracks[0]["can_edit"] is True
    assert 0.5 < tracks[0]["duration"] < 1.5


def test_upload_rejects_wrong_types(env, tmp_path):
    login(env, "admin")
    text = tmp_path / "notes.txt"
    text.write_text("hello")
    assert upload(env, text).status_code == 415
    fake = tmp_path / "fake.mp3"
    fake.write_text("this is not audio")
    res = upload(env, fake)
    assert res.status_code == 422 and res.json()["detail"] == "not_audio"


def test_folder_names_can_become_shared_tags(env, wavs):
    login(env, "admin")
    upload(env, wavs[0], folder_tags='["Horror", "Ambient"]')
    assert _first(env)["tags"] == ["ambient", "horror"]


def test_only_owner_or_admin_edits(env, wavs):
    make_user(env, "owner")
    make_user(env, "other")
    login(env, "owner")
    track_id = upload(env, wavs[0]).json()["id"]

    login(env, "other")
    listed = _first(env)
    assert listed["can_edit"] is False
    assert env.client.patch(f"/api/tracks/{track_id}", json={"title": "Hijack"}).status_code == 403
    assert env.client.delete(f"/api/tracks/{track_id}").status_code == 403

    login(env, "owner")
    assert env.client.patch(f"/api/tracks/{track_id}", json={"title": "Storm", "tags": ["Rain"]}).status_code == 200
    login(env, "admin")
    assert env.client.patch(f"/api/tracks/{track_id}", json={"title": "Storm II"}).status_code == 200
    assert _first(env)["title"] == "Storm II"


def test_personal_tags_are_private(env, wavs):
    make_user(env, "a")
    make_user(env, "b")
    login(env, "a")
    track_id = upload(env, wavs[0]).json()["id"]
    assert env.client.put(f"/api/tracks/{track_id}/my-tags", json={"tags": ["Innsmouth"]}).status_code == 200
    assert _first(env)["my_tags"] == ["innsmouth"]

    login(env, "b")
    assert _first(env)["my_tags"] == []
    assert env.client.get("/api/tags").json()["mine"] == []


def test_delete_leaves_a_tombstone_and_reupload_revives_it(env, wavs):
    login(env, "admin")
    track_id = upload(env, wavs[0]).json()["id"]
    set_id = env.client.post("/api/sets", json={"name": "Druga"}).json()["id"]
    group_id = env.client.post(f"/api/sets/{set_id}/groups", json={"name": "Dwor"}).json()["id"]
    playlist_id = env.client.post(f"/api/groups/{group_id}/playlists", json={"name": "Walka"}).json()["id"]
    env.client.post(f"/api/playlists/{playlist_id}/items", json={"track_ids": [track_id]})

    usage = env.client.get(f"/api/tracks/{track_id}/usage").json()
    assert usage == {"playlists": 1}
    refused = env.client.delete(f"/api/tracks/{track_id}")
    assert refused.status_code == 409 and refused.json()["detail"] == "in_use"
    assert env.client.delete(f"/api/tracks/{track_id}?force=true").status_code == 200

    assert env.client.get("/api/tracks").json() == []
    assert env.client.get(f"/api/tracks/{track_id}/stream").status_code == 404
    item = env.client.get(f"/api/playlists/{playlist_id}").json()["items"][0]
    assert item["deleted"] is True and item["title"] == "tone0"
    assert not any(env.settings.music_dir.iterdir())  # the audio file itself is gone

    revived = upload(env, wavs[0])
    assert revived.json()["status"] == "revived" and revived.json()["id"] == track_id
    assert env.client.get(f"/api/playlists/{playlist_id}").json()["items"][0]["deleted"] is False


def test_stream_serves_audio(env, wavs):
    login(env, "admin")
    track_id = upload(env, wavs[0]).json()["id"]
    res = env.client.get(f"/api/tracks/{track_id}/stream")
    assert res.status_code == 200 and len(res.content) > 1000
