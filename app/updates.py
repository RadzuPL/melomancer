"""Looks up the newest release on GitHub so that the panel can say "an update is available".

The server asks, not the browser (the panel's content security policy allows no outside requests). The question is one
anonymous GET of the public releases API, repeated at most every few hours and answered from a cache in between; it
carries no data about the installation. Nothing is downloaded or installed: in a container the update is a new image,
pulled on the host.
"""
from __future__ import annotations

import json
import logging
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Callable

from .config import Settings

log = logging.getLogger("melomancer.updates")

REPO = "RadzuPL/melomancer"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_URL = f"https://github.com/{REPO}/releases/tag/"
CHECK_EVERY_SECONDS = 6 * 3600
FIRST_CHECK_DELAY_SECONDS = 30
RATE_LIMIT_PAUSE_SECONDS = 3600
REQUEST_TIMEOUT_SECONDS = 8
MIN_MANUAL_GAP_SECONDS = 10      # "Check now" pressed repeatedly does not hammer the API

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

Version = tuple[int, int, int]


def parse_version(text: str | None) -> Version | None:
    """'v0.6.28' or '0.6.28' -> (0, 6, 28); anything else (such as the 'dev' of a local build) -> None."""
    match = _VERSION.match((text or "").strip())
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


class FetchError(Exception):
    """A short error code (see `err` below), never a message with details."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class NotModified(Exception):
    """The release is the same as at the last check (HTTP 304)."""


def _tls_context() -> ssl.SSLContext | None:
    """The CA bundle that ships with yt-dlp's `certifi` when there is one, so that the check does not depend on the
    certificates the base image happens to carry; otherwise the system store (None = Python's default)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return None


def fetch_latest(current: str, etag: str | None) -> tuple[dict, str | None]:
    """Returns (release json, etag). Raises NotModified or FetchError."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"melomancer/{current}",
               "X-GitHub-Api-Version": "2022-11-28"}
    if etag:
        headers["If-None-Match"] = etag
    request = urllib.request.Request(API_URL, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS, context=_tls_context()) as response:
            body = response.read(256 * 1024)
            new_etag = response.headers.get("ETag")
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            raise NotModified from None
        if exc.code in (403, 429):
            raise FetchError("rate_limited") from None
        raise FetchError("unreachable") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise FetchError("unreachable") from None
    try:
        data = json.loads(body)
    except ValueError:
        raise FetchError("bad_response") from None
    if not isinstance(data, dict):
        raise FetchError("bad_response")
    return data, new_etag


class UpdateChecker:
    """Keeps the newest known release and refreshes it in the background while the switch in Settings is on."""

    def __init__(self, settings: Settings, runtime, fetch: Callable[[str, str | None], tuple[dict, str | None]] = fetch_latest,
                 clock: Callable[[], float] = time.time) -> None:
        self._settings = settings
        self._runtime = runtime
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._latest: Version | None = None
        self._tag = ""
        self._etag: str | None = None
        self._checked_at: float | None = None
        self._error: str | None = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ---- state ------------------------------------------------------------

    @property
    def current(self) -> Version | None:
        return parse_version(self._settings.version)

    def status(self) -> dict:
        """What the panel shows. `available` is true only when the newest release is above the running version."""
        with self._lock:
            latest, tag, checked_at, error = self._latest, self._tag, self._checked_at, self._error
        current = self.current
        return {
            "enabled": self._runtime.update_check,
            "current": self._settings.version,
            "comparable": current is not None,
            "latest": ".".join(map(str, latest)) if latest else None,
            "available": bool(latest and current and latest > current),
            "url": RELEASE_URL + tag if latest else None,
            "checked_at": int(checked_at) if checked_at else None,
            "error": error,
        }

    # ---- checking ---------------------------------------------------------

    def check(self, force: bool = False) -> dict:
        """Asks GitHub (blocking, so call it from a thread or a plain `def` route) and returns the new status."""
        now = self._clock()
        with self._lock:
            recent = self._checked_at is not None and now - self._checked_at < (MIN_MANUAL_GAP_SECONDS if force else CHECK_EVERY_SECONDS)
            etag = self._etag
        if recent:
            return self.status()
        try:
            data, new_etag = self._fetch(self._settings.version, etag)
        except NotModified:
            self._record(error=None)
        except FetchError as exc:
            log.info("Update check failed: %s", exc.code)
            self._record(error=exc.code)
        else:
            tag = str(data.get("tag_name") or "")
            version = parse_version(tag)
            if version is None or data.get("draft") or data.get("prerelease"):
                self._record(error="bad_response")
            else:
                self._record(error=None, latest=version, tag=tag if tag.startswith("v") else "v" + tag, etag=new_etag)
        return self.status()

    def _record(self, *, error: str | None, latest: Version | None = None, tag: str = "", etag: str | None = None) -> None:
        with self._lock:
            self._checked_at = self._clock()
            self._error = error
            if latest is not None:
                self._latest, self._tag, self._etag = latest, tag, etag

    # ---- background thread --------------------------------------------------

    def start(self) -> None:
        # A build without a version number ("dev") has nothing to compare, so it never goes out to the network by itself.
        if self._thread or self.current is None:
            return
        self._thread = threading.Thread(target=self._run, name="updates", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def wake(self) -> None:
        """Called when the switch in Settings changes, so that turning it on checks soon."""
        self._wake.set()

    def _run(self) -> None:
        delay = FIRST_CHECK_DELAY_SECONDS
        while not self._stop.is_set():
            self._wake.wait(delay)
            self._wake.clear()
            if self._stop.is_set():
                return
            delay = CHECK_EVERY_SECONDS
            if not self._runtime.update_check:
                continue
            try:
                if self.check()["error"] == "rate_limited":
                    delay = RATE_LIMIT_PAUSE_SECONDS
            except Exception:  # noqa: BLE001
                log.debug("Update check crashed", exc_info=True)
