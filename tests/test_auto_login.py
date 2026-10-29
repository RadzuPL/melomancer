"""Signing in without a password: POST /api/auth/local. Off unless AUTO_LOGIN is on, and then only for a request that
provably comes from this computer."""
from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from .conftest import login


def local_client(env, host="127.0.0.1:8080", peer="127.0.0.1", extra=None):
    """A client that looks like a browser on this computer (or not, depending on the arguments)."""
    client = TestClient(env.app, base_url=f"http://{host}", client=(peer, 50000))
    client.headers["X-Melomancer"] = "1"
    client.headers.update(extra or {})
    return client


def turn_on(env):
    env.app.state.settings = replace(env.settings, auto_login=True)


def test_it_is_off_by_default(env):
    with local_client(env) as client:
        res = client.post("/api/auth/local")
        assert res.status_code == 403 and res.json()["detail"] == "local_login_off"
        assert client.get("/api/auth/me").status_code == 401


def test_it_signs_this_computer_in_as_the_first_administrator(env):
    turn_on(env)
    with local_client(env) as client:
        res = client.post("/api/auth/local")
        assert res.status_code == 200 and res.json()["username"] == "admin" and res.json()["role"] == "admin"
        assert client.get("/api/auth/me").json()["username"] == "admin"          # the cookie works
        info = client.get("/api/system").json()
        assert info["auto_login"] is True and client.get("/api/system/update").status_code == 200  # an administrator


def test_localhost_by_name_works_too(env):
    turn_on(env)
    with local_client(env, host="localhost:8080") as client:
        assert client.post("/api/auth/local").status_code == 200


def test_a_request_from_another_computer_is_refused(env):
    turn_on(env)
    with local_client(env, peer="192.168.1.20") as client:
        assert client.post("/api/auth/local").status_code == 403
        assert client.get("/api/auth/me").status_code == 401


def test_a_page_on_another_site_cannot_use_it(env):
    turn_on(env)   # DNS rebinding: the connection is to 127.0.0.1, the Host is the attacker's name
    with local_client(env, host="evil.example:8080") as client:
        assert client.post("/api/auth/local").status_code == 403


def test_a_proxy_or_a_tunnel_on_the_same_computer_cannot_use_it(env):
    turn_on(env)
    for header in ({"X-Forwarded-For": "203.0.113.9"}, {"Forwarded": "for=203.0.113.9"}, {"CF-Connecting-IP": "203.0.113.9"}):
        with local_client(env, extra=header) as client:
            assert client.post("/api/auth/local").status_code == 403, header
    with local_client(env, host="muzyka.example.com") as client:
        assert client.post("/api/auth/local").status_code == 403


def test_the_system_info_does_not_claim_it_for_a_request_that_could_not_use_it(env):
    turn_on(env)
    assert login(env, "admin").status_code == 200       # the ordinary client of the fixture: not from a loopback address
    assert env.client.get("/api/system").json()["auto_login"] is False


def test_it_needs_the_csrf_header_like_every_state_changing_request(env):
    turn_on(env)
    with local_client(env) as client:
        del client.headers["X-Melomancer"]
        assert client.post("/api/auth/local").status_code == 403


def test_the_first_active_administrator_is_the_one_let_in(env):
    turn_on(env)
    assert login(env, "admin").status_code == 200
    boss = env.client.post("/api/users", json={"username": "boss", "password": "password-for-tests-1", "role": "admin"})
    assert boss.status_code == 201
    env.client.post("/api/users", json={"username": "olga", "password": "password-for-tests-1", "role": "user"})
    admin_id = next(u["id"] for u in env.client.get("/api/users").json() if u["username"] == "admin")
    assert env.client.patch(f"/api/users/{admin_id}", json={"disabled": True}).status_code == 200
    with local_client(env) as client:     # "admin" is disabled now, "olga" is not an administrator: "boss" it is
        assert client.post("/api/auth/local").json()["username"] == "boss"
