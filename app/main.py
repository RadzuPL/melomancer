"""Application factory: wires the API, the static panel, the Discord bot and the download worker."""
from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from . import routes_auth, routes_library, routes_player, routes_playlists
from .config import Settings
from .db import init_db, tx
from .deps import csrf_guard
from .downloader import Downloader
from .loudness import LoudnessWorker, RuntimeSettings
from .player import BotManager
from .sysload import LoadMonitor
from .security import LoginThrottle, MIN_PASSWORD_LENGTH, hash_password

log = logging.getLogger("melomancer")
STATIC_DIR = Path(__file__).parent / "static"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": ("default-src 'self'; img-src 'self' data:; media-src 'self'; "
                                "style-src 'self'; script-src 'self'; frame-ancestors 'none'"),
}


def bootstrap_admin(settings: Settings) -> None:
    """Create the first administrator when the database has no users yet."""
    with tx(settings.db_path) as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        password = settings.admin_password
        generated = False
        if len(password) < MIN_PASSWORD_LENGTH:
            if password:
                log.warning("ADMIN_PASSWORD is shorter than %d characters; generating one instead.",
                            MIN_PASSWORD_LENGTH)
            password, generated = secrets.token_urlsafe(16), True
        conn.execute("INSERT INTO users(username, pw_hash, role) VALUES (?,?,'admin')",
                     (settings.admin_username, hash_password(password)))
    if generated:
        log.warning("First start: created administrator %r with generated password %s - "
                    "log in and change it. This message is shown only once.", settings.admin_username, password)
    else:
        log.info("First start: created administrator %r from ADMIN_USERNAME / ADMIN_PASSWORD.",
                 settings.admin_username)


def create_app(settings: Settings | None = None, bot=None, downloader: Downloader | None = None,
               loudness: LoudnessWorker | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_dirs()
        init_db(settings.db_path)
        bootstrap_admin(settings)
        for leftover in settings.tmp_dir.glob("*"):  # unfinished uploads from a previous run
            if leftover.is_file():
                leftover.unlink(missing_ok=True)
        log.info("Melomancer %s starting", settings.version)
        app.state.runtime.load()
        await app.state.bot.start()
        app.state.downloader.start()
        app.state.loudness.start()
        app.state.load.start()
        try:
            yield
        finally:
            app.state.load.stop()
            app.state.loudness.stop()
            app.state.downloader.stop()
            await app.state.bot.stop()

    app = FastAPI(title="Melomancer", version=settings.version, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.runtime = RuntimeSettings(settings)
    app.state.bot = bot or BotManager(settings, app.state.runtime)
    app.state.loudness = loudness or LoudnessWorker(settings, app.state.runtime)
    app.state.load = LoadMonitor()
    app.state.downloader = downloader or Downloader(settings)
    app.state.throttle = LoginThrottle(settings.login_max_failures, settings.login_window_seconds)

    guard = [Depends(csrf_guard)]
    for module in (routes_auth, routes_library, routes_playlists, routes_player):
        app.include_router(module.router, dependencies=guard)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8").replace("__VERSION__", settings.version)

    @app.get("/", include_in_schema=False)
    def index():
        return HTMLResponse(index_html, headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def app_factory() -> FastAPI:
    """Entry point for `uvicorn app.main:app_factory --factory`."""
    return create_app()
