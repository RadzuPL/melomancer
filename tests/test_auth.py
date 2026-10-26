from __future__ import annotations

from app.security import LoginThrottle, verify_password

from .conftest import PASSWORD, login, make_user


def test_bootstrap_admin_can_log_in(env):
    res = login(env, "admin")
    assert res.status_code == 200
    assert res.json()["role"] == "admin"
    assert env.client.get("/api/auth/me").json()["username"] == "admin"


def test_api_requires_login(env):
    env.client.cookies.clear()
    assert env.client.get("/api/tracks").status_code == 401


def test_state_changing_requests_need_the_custom_header(env):
    env.client.cookies.clear()
    res = env.client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD},
                          headers={"X-Melomancer": ""})
    assert res.status_code == 403


def test_wrong_password_is_rejected_and_throttled(env):
    for _ in range(5):
        assert login(env, "admin", "wrong-password-x").status_code == 401
    assert login(env, "admin", PASSWORD).status_code == 429  # blocked even with the right password


def test_unknown_user_gets_the_same_answer(env):
    assert login(env, "nobody", "whatever-password").status_code == 401


def test_admin_manages_users(env):
    uid = make_user(env, "mg1")
    assert login(env, "mg1").status_code == 200
    assert env.client.get("/api/users").status_code == 403

    login(env, "admin")
    assert env.client.patch(f"/api/users/{uid}", json={"disabled": True}).status_code == 200
    assert login(env, "mg1").status_code == 401


def test_duplicate_username_conflicts(env):
    make_user(env, "mg1")
    res = env.client.post("/api/users", json={"username": "MG1", "password": PASSWORD})
    assert res.status_code == 409


def test_last_admin_cannot_be_demoted_or_disabled(env):
    login(env, "admin")
    admin_id = env.client.get("/api/auth/me").json()["id"]
    assert env.client.patch(f"/api/users/{admin_id}", json={"role": "user"}).status_code == 409
    assert env.client.patch(f"/api/users/{admin_id}", json={"disabled": True}).status_code == 409


def test_change_password_ends_other_sessions(env):
    login(env, "admin")
    res = env.client.post("/api/auth/password", json={"current": PASSWORD, "new": "another-long-password"})
    assert res.status_code == 200
    env.client.cookies.clear()
    assert login(env, "admin", PASSWORD).status_code == 401
    assert login(env, "admin", "another-long-password").status_code == 200


def test_short_password_is_refused(env):
    login(env, "admin")
    res = env.client.post("/api/users", json={"username": "short", "password": "abc"})
    assert res.status_code == 422


def test_throttle_unit():
    throttle = LoginThrottle(max_failures=2, window_seconds=60)
    throttle.fail("a")
    assert not throttle.blocked("a")
    throttle.fail("a")
    assert throttle.blocked("a", "b")
    throttle.reset("a")
    assert not throttle.blocked("a")


def test_verify_password_with_no_stored_hash_is_false():
    assert verify_password(None, "melomancer-timing-equaliser") is False
