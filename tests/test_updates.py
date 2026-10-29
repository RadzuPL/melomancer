"""The look at the newest GitHub release: version parsing, the comparison, the cache and the error codes.

Only the standard library is needed, so these also run with scripts/dev/run_tests.py.
"""
from __future__ import annotations

import threading
from dataclasses import replace
from types import SimpleNamespace

from app import hostenv, updates
from app.config import Settings
from app.updates import FetchError, NotModified, UpdateChecker, parse_version


class Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def release(tag: str = "v0.7.0", **extra) -> dict:
    return {"tag_name": tag, "draft": False, "prerelease": False,
            "html_url": "https://example.invalid/should-not-be-used", **extra}


def make(version: str, answers: list, clock: Clock | None = None, enabled: bool = True):
    """A checker whose 'GitHub' answers from `answers` in turn: a release dict, or an exception to raise."""
    calls: list[str | None] = []

    def fetch(current: str, etag: str | None):
        calls.append(etag)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer, "etag-%d" % len(calls)

    settings = replace(Settings.from_env(), version=version)
    runtime = SimpleNamespace(update_check=enabled)
    return UpdateChecker(settings, runtime, fetch=fetch, clock=clock or Clock()), calls


def test_parse_version():
    assert parse_version("0.6.28") == (0, 6, 28)
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version(" v10.0.1 ") == (10, 0, 1)
    for bad in ("dev", "", None, "1.2", "1.2.3.4", "v1.2.x", "1.2.3-rc1"):
        assert parse_version(bad) is None, bad


def test_numbers_are_compared_as_numbers_not_as_text():
    checker, _ = make("0.6.9", [release("v0.6.10")])
    status = checker.check()
    assert status["latest"] == "0.6.10" and status["available"] is True


def test_newer_release_is_an_update_and_the_link_is_built_from_the_tag():
    checker, _ = make("0.6.28", [release("v0.6.30")])
    status = checker.check()
    assert status["available"] is True and status["latest"] == "0.6.30" and status["current"] == "0.6.28"
    assert status["url"] == "https://github.com/RadzuPL/melomancer/releases/tag/v0.6.30"  # never GitHub's html_url
    assert status["error"] is None and status["checked_at"] == 1_000_000


def test_same_or_older_release_is_not_an_update():
    for current in ("0.6.30", "0.7.0"):
        checker, _ = make(current, [release("v0.6.30")])
        status = checker.check()
        assert status["available"] is False and status["latest"] == "0.6.30"


def test_a_build_without_a_version_number_compares_nothing():
    checker, _ = make("dev", [release("v0.6.30")])
    status = checker.check()
    assert status["comparable"] is False and status["available"] is False and status["latest"] == "0.6.30"


def test_drafts_prereleases_and_odd_tags_are_ignored():
    for bad in (release(draft=True), release(prerelease=True), release("latest"), {"nothing": 1}):
        checker, _ = make("0.6.28", [bad])
        status = checker.check()
        assert status["error"] == "bad_response" and status["latest"] is None and status["available"] is False


def test_errors_are_short_codes_and_keep_the_last_good_answer():
    clock = Clock()
    checker, _ = make("0.6.28", [release("v0.6.30"), FetchError("unreachable"), FetchError("rate_limited")], clock)
    assert checker.check()["available"] is True
    clock.now += updates.CHECK_EVERY_SECONDS + 1
    status = checker.check()
    assert status["error"] == "unreachable" and status["latest"] == "0.6.30" and status["available"] is True
    clock.now += updates.CHECK_EVERY_SECONDS + 1
    assert checker.check()["error"] == "rate_limited"


def test_automatic_checks_are_cached_and_the_etag_is_sent_back():
    clock = Clock()
    checker, calls = make("0.6.28", [release("v0.6.30"), NotModified()], clock)
    checker.check()
    clock.now += 3600
    checker.check()                       # within the cache time: no request
    assert calls == [None]
    clock.now += updates.CHECK_EVERY_SECONDS
    status = checker.check()              # the cache has run out: asks again, with the ETag of the first answer
    assert calls == [None, "etag-1"]
    assert status["latest"] == "0.6.30" and status["error"] is None  # 304 keeps what we knew


def test_checking_by_hand_is_not_cached_but_not_a_hammer_either():
    clock = Clock()
    checker, calls = make("0.6.28", [release("v0.6.30"), release("v0.6.31")], clock)
    checker.check(force=True)
    clock.now += updates.MIN_MANUAL_GAP_SECONDS - 1
    checker.check(force=True)             # pressed again at once: answered from memory
    assert len(calls) == 1
    clock.now += 2
    status = checker.check(force=True)
    assert len(calls) == 2 and status["latest"] == "0.6.31"


def test_the_background_thread_is_not_held_back_by_the_long_cache_window():
    """After a rate limit the thread tries again an hour later, and turning the switch on checks soon (wake)."""
    clock = Clock()
    checker, calls = make("0.6.28", [FetchError("rate_limited"), release("v0.6.30")], clock)
    assert checker.check(force=True)["error"] == "rate_limited"
    clock.now += updates.RATE_LIMIT_PAUSE_SECONDS           # an hour: inside the 6 h window of an ordinary check
    assert updates.RATE_LIMIT_PAUSE_SECONDS < updates.CHECK_EVERY_SECONDS
    status = checker.check(force=True)
    assert len(calls) == 2 and status["error"] is None and status["latest"] == "0.6.30"


def test_the_thread_asks_with_force(monkeypatch):
    checker, _ = make("0.6.28", [])
    seen = []
    monkeypatch.setattr(checker, "check", lambda force=False: seen.append(force) or {"error": None})
    checker._wake.set()                    # as when the switch is turned on: no waiting for the first delay
    thread = threading.Thread(target=checker._run, daemon=True)
    thread.start()
    for _ in range(100):
        if seen:
            break
        threading.Event().wait(0.05)
    checker.stop()
    thread.join(2)
    assert seen and seen[0] is True


def test_the_status_says_how_an_update_is_installed(monkeypatch):
    checker, _ = make("0.6.28", [])
    assert checker.status()["host"] == ("desktop" if hostenv.IS_WINDOWS else "container")
    monkeypatch.setattr(hostenv, "IS_WINDOWS", True)
    assert checker.status()["host"] == "desktop"
    monkeypatch.setattr(hostenv, "IS_WINDOWS", False)
    assert checker.status()["host"] == "container"


def test_status_shows_the_switch():
    checker, _ = make("0.6.28", [], enabled=False)
    status = checker.status()
    assert status["enabled"] is False and status["latest"] is None and status["checked_at"] is None


def test_a_dev_build_never_starts_the_background_thread():
    checker, calls = make("dev", [])
    checker.start()
    checker.stop()
    assert checker._thread is None and calls == []
