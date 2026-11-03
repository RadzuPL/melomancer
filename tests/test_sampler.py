"""The sampler: pads are private, editable, and played on Discord through the effect endpoints."""
from __future__ import annotations

from .conftest import login, make_user, upload
from .test_player_api import _grant, _playlist_with_tracks


def first_track(env, wavs, n=0) -> str:
    return upload(env, wavs[n]).json()["id"]


def pads(env) -> list[dict]:
    return env.client.get("/api/sampler").json()["pads"]


# ---- the board ----------------------------------------------------------------------------------------------------------

def test_the_first_visit_finds_a_board_of_empty_pads_and_a_second_one_the_same(env):
    login(env, "admin")
    board = pads(env)
    assert len(board) == 8 and all(p["track_id"] is None and p["item"] is None and p["mode"] == "once" for p in board)
    assert [p["position"] for p in board] == list(range(8))
    assert [p["id"] for p in pads(env)] == [p["id"] for p in board]


def test_a_pad_gets_a_track_a_mode_a_volume_a_colour_and_a_name(env, wavs):
    login(env, "admin")
    track = first_track(env, wavs)
    pad = pads(env)[0]
    res = env.client.patch(f"/api/sampler/pads/{pad['id']}", json={"track_id": track, "mode": "loop", "volume": 0.7, "color": 3,
                                                                    "name": "  Burza   z piorunami "})
    assert res.status_code == 200
    changed = next(p for p in res.json()["pads"] if p["id"] == pad["id"])
    assert changed["track_id"] == track and changed["mode"] == "loop" and changed["volume"] == 0.7 and changed["color"] == 3
    assert changed["name"] == "Burza z piorunami", "spaces are tidied"
    assert changed["track"]["title"] and changed["item"]["track_id"] == track, "the browser gets what it needs to play it"
    assert {"start", "end", "gain", "duration"} <= set(changed["item"])


def test_a_pad_can_be_emptied_with_an_explicit_null_and_other_fields_stay_when_left_out(env, wavs):
    login(env, "admin")
    track = first_track(env, wavs)
    pad_id = pads(env)[0]["id"]
    env.client.patch(f"/api/sampler/pads/{pad_id}", json={"track_id": track, "mode": "loop"})
    res = env.client.patch(f"/api/sampler/pads/{pad_id}", json={"volume": 0.5})
    kept = next(p for p in res.json()["pads"] if p["id"] == pad_id)
    assert kept["track_id"] == track and kept["mode"] == "loop", "a field that is left out stays"
    res = env.client.patch(f"/api/sampler/pads/{pad_id}", json={"track_id": None})
    assert next(p for p in res.json()["pads"] if p["id"] == pad_id)["track_id"] is None


def test_wrong_values_are_refused(env, wavs):
    login(env, "admin")
    pad_id = pads(env)[0]["id"]
    assert env.client.patch(f"/api/sampler/pads/{pad_id}", json={"track_id": "no-such-track"}).status_code == 404
    assert env.client.patch(f"/api/sampler/pads/{pad_id}", json={"mode": "forever"}).status_code == 422
    assert env.client.patch(f"/api/sampler/pads/{pad_id}", json={"volume": 9}).status_code == 422
    assert env.client.patch(f"/api/sampler/pads/{pad_id}", json={"color": 12}).status_code == 422


def test_a_deleted_track_leaves_a_greyed_pad_that_cannot_play(env, wavs):
    login(env, "admin")
    track = first_track(env, wavs)
    pad_id = pads(env)[0]["id"]
    env.client.patch(f"/api/sampler/pads/{pad_id}", json={"track_id": track})
    assert env.client.delete(f"/api/tracks/{track}?force=true").status_code in (200, 204)
    pad = next(p for p in pads(env) if p["id"] == pad_id)
    assert pad["track"]["deleted"] is True and pad["item"] is None
    assert env.client.patch(f"/api/sampler/pads/{pad_id}", json={"track_id": track}).status_code == 404, "a deleted track cannot be chosen"


def test_pads_are_added_deleted_and_moved_and_there_is_a_limit(env):
    login(env, "admin")
    ids = [p["id"] for p in pads(env)]
    added = env.client.post("/api/sampler/pads")
    assert added.status_code == 201 and len(added.json()["pads"]) == 9
    reordered = env.client.put("/api/sampler/order", json={"ids": list(reversed([p["id"] for p in added.json()["pads"]]))})
    assert [p["id"] for p in reordered.json()["pads"]][-1] == ids[0]
    assert env.client.put("/api/sampler/order", json={"ids": ids[:3]}).status_code == 400, "all pads or none"
    assert len(env.client.delete(f"/api/sampler/pads/{ids[0]}").json()["pads"]) == 8
    while len(pads(env)) < 48:
        env.client.post("/api/sampler/pads")
    res = env.client.post("/api/sampler/pads")
    assert res.status_code == 409 and res.json()["detail"] == "too_many_pads"


def test_pads_are_private_even_from_an_administrator(env, wavs):
    make_user(env, "mg")
    login(env, "mg")
    theirs = pads(env)[0]["id"]
    login(env, "admin")
    assert pads(env)[0]["id"] != theirs, "everyone has a board of their own"
    assert env.client.patch(f"/api/sampler/pads/{theirs}", json={"name": "x"}).status_code == 404
    assert env.client.delete(f"/api/sampler/pads/{theirs}").status_code == 404
    login(env, "mg")
    assert pads(env)[0]["name"] == "", "untouched"


def test_the_sampler_needs_a_login_and_the_header(env):
    env.client.cookies.clear()
    assert env.client.get("/api/sampler").status_code == 401
    login(env, "admin")
    assert env.client.post("/api/sampler/pads", headers={"X-Melomancer": ""}).status_code == 403


# ---- playing on Discord ---------------------------------------------------------------------------------------------------

def connected(env, wavs, mode="once"):
    login(env, "admin")
    track = first_track(env, wavs)
    pad_id = pads(env)[0]["id"]
    env.client.patch(f"/api/sampler/pads/{pad_id}", json={"track_id": track, "mode": mode, "volume": 0.8})
    env.client.post("/api/player/111/connect", json={"channel_id": "100100"})
    return pad_id


def test_a_press_starts_the_effect_and_the_next_one_stops_it(env, wavs):
    pad_id = connected(env, wavs, mode="loop")
    state = env.client.post(f"/api/player/111/fx/{pad_id}/toggle").json()
    assert state["fx"] == [{"pad_id": pad_id, "loop": True, "momentary": False}]
    assert env.bot.fx_calls[-1][:3] == ("toggle", 111, pad_id) and env.bot.fx_calls[-1][4:] == (True, 0.8)
    assert env.client.post(f"/api/player/111/fx/{pad_id}/toggle").json()["fx"] == []


def test_holding_a_pad_plays_it_only_until_it_is_released(env, wavs):
    pad_id = connected(env, wavs)
    held = env.client.post(f"/api/player/111/fx/{pad_id}/hold").json()
    assert held["fx"][0]["momentary"] is True and env.bot.fx_calls[-1][0] == "hold"
    assert env.client.post(f"/api/player/111/fx/{pad_id}/release").json()["fx"] == []


def test_everything_stops_at_once_and_the_effect_volume_is_bounded(env, wavs):
    pad_id = connected(env, wavs)
    env.client.post(f"/api/player/111/fx/{pad_id}/toggle")
    assert env.client.post("/api/player/111/fx/stop").json()["fx"] == []
    assert env.client.post("/api/player/111/fx/volume", json={"volume": 0.3}).json()["fx_volume"] == 0.3
    assert env.client.post("/api/player/111/fx/volume", json={"volume": 3}).status_code == 422


def test_an_empty_pad_a_missing_bot_connection_and_someone_elses_pad_are_refused(env, wavs):
    login(env, "admin")
    empty = pads(env)[1]["id"]
    env.client.post("/api/player/111/connect", json={"channel_id": "100100"})
    res = env.client.post(f"/api/player/111/fx/{empty}/toggle")
    assert res.status_code == 409 and res.json()["detail"] == "pad_empty"
    track = first_track(env, wavs)
    mine = pads(env)[0]["id"]
    env.client.patch(f"/api/sampler/pads/{mine}", json={"track_id": track})
    make_user(env, "mg")
    login(env, "mg")
    assert env.client.post(f"/api/player/111/fx/{mine}/toggle").status_code == 404, "not allowed on that server, and not their pad"


def test_a_pad_cannot_be_pressed_on_a_server_that_is_not_connected(env, wavs):
    login(env, "admin")
    track = first_track(env, wavs)
    pad_id = pads(env)[0]["id"]
    env.client.patch(f"/api/sampler/pads/{pad_id}", json={"track_id": track})
    res = env.client.post(f"/api/player/111/fx/{pad_id}/toggle")
    assert res.status_code == 409 and res.json()["detail"] == "not_connected"


def test_effects_respect_the_one_controller_rule_of_a_server(env, wavs):
    a = make_user(env, "alpha")
    b = make_user(env, "bravo")
    _grant(env, a, ["111"])
    _grant(env, b, ["111"])
    login(env, "alpha")
    playlist_id, _ = _playlist_with_tracks(env, wavs, 1)
    env.client.post("/api/player/111/connect", json={"channel_id": "100100"})
    assert env.client.post("/api/player/111/play", json={"playlist_id": playlist_id}).status_code == 200
    login(env, "bravo")
    pad_id = pads(env)[0]["id"]
    env.client.patch(f"/api/sampler/pads/{pad_id}", json={"track_id": first_track(env, wavs, 1)})
    res = env.client.post(f"/api/player/111/fx/{pad_id}/toggle")
    assert res.status_code == 409 and res.json()["detail"] == "busy"
