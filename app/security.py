"""Password hashing, session tokens and the login throttle."""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 10

_hasher = PasswordHasher()
# Verified against when the user does not exist, so that response time does not reveal usernames.
_DUMMY_HASH = _hasher.hash("melomancer-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_session_token() -> tuple[str, str]:
    """Return (token for the cookie, hash to store in the database)."""
    token = secrets.token_urlsafe(32)
    return token, sha256_hex(token)


def utc_string(offset_hours: float = 0) -> str:
    moment = datetime.now(timezone.utc) + timedelta(hours=offset_hours)
    return moment.strftime("%Y-%m-%d %H:%M:%S")


class LoginThrottle:
    """Blocks a key (username or client address) after too many recent failures."""

    def __init__(self, max_failures: int, window_seconds: int) -> None:
        self._max = max_failures
        self._window = window_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _recent(self, key: str) -> list[float]:
        cutoff = time.monotonic() - self._window
        fresh = [t for t in self._failures[key] if t > cutoff]
        self._failures[key] = fresh
        return fresh

    def blocked(self, *keys: str) -> bool:
        with self._lock:
            return any(len(self._recent(k)) >= self._max for k in keys)

    def fail(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._recent(key).append(time.monotonic())

    def reset(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._failures.pop(key, None)
