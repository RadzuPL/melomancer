from __future__ import annotations

from .conftest import login, make_user, make_wav, upload


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
    make_user(env, "alpha")
    make_user(env, "bravo")
    login(env, "alpha")
    track_id = upload(env, wavs[0]).json()["id"]
    assert env.client.put(f"/api/tracks/{track_id}/my-tags", json={"tags": ["Innsmouth"]}).status_code == 200
    assert _first(env)["my_tags"] == ["innsmouth"]

    login(env, "bravo")
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


def test_tags_given_at_upload_are_applied_and_personal_ones_stay_private(env, wavs):
    make_user(env, "mg1")
    make_user(env, "mg2")
    login(env, "mg1")
    assert upload(env, wavs[0], tags='["Ambient"]', my_tags='["Sesja 3", "Innsmouth"]').status_code == 201
    track = env.client.get("/api/tracks").json()[0]
    assert track["tags"] == ["ambient"] and track["my_tags"] == ["innsmouth", "sesja 3"]

    login(env, "mg2")
    assert env.client.get("/api/tracks").json()[0]["my_tags"] == []
    again = upload(env, wavs[0], tags='["Hack"]', my_tags='["Sesja 5"]')  # same file: a duplicate
    assert again.json()["status"] == "duplicate"
    track = env.client.get("/api/tracks").json()[0]
    assert track["my_tags"] == ["sesja 5"]  # still tagged for this person's session
    assert track["tags"] == ["ambient"]  # but shared tags are not theirs to change


def test_manual_start_and_end_are_stored_validated_clamped_and_cleared(env, tmp_path):
    login(env, "admin")
    track_id = upload(env, make_wav(tmp_path / "long.wav", seconds=10)).json()["id"]

    def trims():
        row = _first(env)
        return row["trim_start"], row["trim_end"], row["lead"], row["trail"]

    assert trims() == (None, None, None, None)
    assert env.client.patch(f"/api/tracks/{track_id}", json={"trim_start": 2, "trim_end": 8}).status_code == 200
    assert trims()[:2] == (2.0, 8.0)
    # one side on its own keeps the other
    assert env.client.patch(f"/api/tracks/{track_id}", json={"trim_start": 3}).status_code == 200
    assert trims()[:2] == (3.0, 8.0)
    # an end typed slightly past the file means "to the end"
    assert env.client.patch(f"/api/tracks/{track_id}", json={"trim_end": 12}).status_code == 200
    assert 9.7 < trims()[1] <= 10.0                       # clamped to the length of the file
    # nothing sensible is refused and changes nothing
    assert env.client.patch(f"/api/tracks/{track_id}", json={"trim_start": 9.5}).status_code == 400   # leaves < 1 s
    assert env.client.patch(f"/api/tracks/{track_id}", json={"trim_end": 3.5}).status_code == 400     # 3.0 to 3.5
    assert env.client.patch(f"/api/tracks/{track_id}", json={"trim_start": -1}).status_code == 422
    assert trims()[0] == 3.0
    # an explicit null goes back to automatic, for that side only
    assert env.client.patch(f"/api/tracks/{track_id}", json={"trim_start": None}).status_code == 200
    assert trims()[0] is None and trims()[1] is not None
    assert env.client.patch(f"/api/tracks/{track_id}", json={"trim_end": None}).status_code == 200
    assert trims()[:2] == (None, None)
    # the other fields of a patch do not touch the trim
    env.client.patch(f"/api/tracks/{track_id}", json={"trim_start": 1})
    env.client.patch(f"/api/tracks/{track_id}", json={"title": "Renamed"})
    assert trims()[0] == 1.0


def test_only_the_owner_or_an_administrator_sets_the_trim(env, tmp_path):
    make_user(env, "bob")
    login(env, "admin")
    track_id = upload(env, make_wav(tmp_path / "long.wav", seconds=10)).json()["id"]
    login(env, "bob")
    assert env.client.patch(f"/api/tracks/{track_id}", json={"trim_start": 2}).status_code == 403
