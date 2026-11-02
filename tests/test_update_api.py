"""The update check over HTTP: who may ask, the switch, and what the panel gets."""
from __future__ import annotations

from dataclasses import replace

from app.loudness import RuntimeSettings
from app.updates import FetchError, UpdateChecker

from .conftest import login, make_user


def use_checker(env, answers: list, version: str = "0.6.28"):
    """Puts a checker with a made-up GitHub in the running app; the real thread never runs in tests."""
    calls = []

    def fetch(current, etag):
        calls.append(etag)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer, None

    checker = UpdateChecker(replace(env.settings, version=version), env.app.state.runtime, fetch=fetch)
    env.app.state.updates = checker
    return calls


def test_only_an_administrator_may_look_at_updates(env):
    make_user(env, "olga")
    assert login(env, "olga").status_code == 200
    assert env.client.get("/api/system/update").status_code == 403
    assert env.client.post("/api/system/update/check").status_code == 403
    env.client.cookies.clear()
    assert env.client.get("/api/system/update").status_code == 401


def test_checking_now_reports_the_newest_release(env):
    use_checker(env, [{"tag_name": "v0.6.30", "draft": False, "prerelease": False}])
    assert login(env, "admin").status_code == 200
    before = env.client.get("/api/system/update").json()
    assert before["available"] is False and before["latest"] is None and before["checked_at"] is None
    after = env.client.post("/api/system/update/check").json()
    assert after["available"] is True and after["latest"] == "0.6.30" and after["current"] == "0.6.28"
    assert env.client.get("/api/system/update").json() == after  # kept for the next visit to Settings


def test_a_failed_look_is_an_answer_not_an_error(env):
    use_checker(env, [FetchError("unreachable")])
    assert login(env, "admin").status_code == 200
    res = env.client.post("/api/system/update/check")
    assert res.status_code == 200 and res.json()["error"] == "unreachable"


def test_the_switch_is_a_setting_and_survives_a_restart(env):
    assert login(env, "admin").status_code == 200
    assert env.client.get("/api/system").json()["update_check"] is True  # on by default
    res = env.client.patch("/api/system", json={"update_check": False})
    assert res.status_code == 200 and res.json()["update_check"] is False
    assert env.client.get("/api/system/update").json()["enabled"] is False
    runtime = RuntimeSettings(env.settings)
    runtime.load()
    assert runtime.update_check is False
    assert env.client.patch("/api/system", json={"update_check": "maybe"}).status_code == 422


# ---- installing from the panel (the Windows package) -----------------------------------------------------------------

def use_installer(env, tmp_path, **options):
    """A made-up Windows package folder and GitHub, so that the installer runs here."""
    from .test_selfupdate import installer, package_zip
    data = package_zip("0.6.30")
    inst = installer(tmp_path, data, rel={**release_of(data), "tag_name": "v0.6.30"}, current="0.6.28", **options)
    env.app.state.installer = inst
    return inst


def release_of(data):
    from .test_selfupdate import release
    return release(data, tag="v0.6.30", url="https://github.com/RadzuPL/melomancer/releases/download/v0.6.30/Melomancer-win64-0.6.30.zip")


def test_in_a_container_nothing_can_be_installed(env):
    use_checker(env, [{"tag_name": "v0.6.30", "draft": False, "prerelease": False}])
    assert login(env, "admin").status_code == 200
    status = env.client.post("/api/system/update/check").json()
    assert status["available"] is True and status["installable"] is False and status["install"]["available"] is False
    res = env.client.post("/api/system/update/install")
    assert res.status_code == 409 and res.json()["detail"] == "update_unavailable"
    res = env.client.post("/api/system/update/apply")
    assert res.status_code == 409 and res.json()["detail"] == "not_ready"


def test_the_update_is_downloaded_from_the_panel_and_then_applied(env, tmp_path):
    import threading
    ended = threading.Event()
    inst = use_installer(env, tmp_path, quit_event=ended, spawned=[])
    use_checker(env, [{"tag_name": "v0.6.30", "draft": False, "prerelease": False}])
    assert login(env, "admin").status_code == 200
    status = env.client.post("/api/system/update/check").json()
    assert status["installable"] is True and status["install"]["state"] == "idle"
    assert env.client.post("/api/system/update/apply").json()["detail"] == "not_ready"

    started = env.client.post("/api/system/update/install")
    assert started.status_code == 200
    inst._thread.join(20)
    ready = env.client.get("/api/system/update").json()
    assert ready["install"]["state"] == "ready" and ready["install"]["version"] == "0.6.30"

    assert env.client.post("/api/system/update/apply").status_code == 200
    assert ended.wait(5), "applying ends the program"
    assert env.client.get("/api/system/update").json()["install"]["state"] == "applying"
    assert env.client.post("/api/system/update/install").json()["detail"] == "update_busy"


def test_only_an_administrator_may_install_and_only_with_the_header(env, tmp_path):
    use_installer(env, tmp_path, spawned=[])
    make_user(env, "olga")
    assert login(env, "olga").status_code == 200
    assert env.client.post("/api/system/update/install").status_code == 403
    assert env.client.post("/api/system/update/apply").status_code == 403
    assert login(env, "admin").status_code == 200
    assert env.client.post("/api/system/update/install", headers={"X-Melomancer": ""}).status_code == 403
    env.client.cookies.clear()
    assert env.client.post("/api/system/update/install").status_code == 401
