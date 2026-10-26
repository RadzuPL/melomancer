"""FastAPI dependencies: settings access, authentication and the CSRF header check."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from .config import Settings
from .db import tx
from .security import utc_string, sha256_hex

SESSION_COOKIE = "melomancer_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def csrf_guard(request: Request) -> None:
    """State-changing requests must carry a custom header, which a cross-site form cannot set."""
    if request.method not in SAFE_METHODS and request.headers.get("x-melomancer") != "1":
        raise HTTPException(403, "csrf")


def current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "not_authenticated")
    settings = get_settings(request)
    with tx(settings.db_path) as conn:
        row = conn.execute(
            "SELECT u.id, u.username, u.role, u.lang FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash=? AND s.expires_at > ? AND u.disabled=0",
            (sha256_hex(token), utc_string()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "not_authenticated")
    return dict(row)


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "forbidden")
    return user
