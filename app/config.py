"""Runtime configuration, read from environment variables only."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from .hostenv import default_data_dir

# View Channels + Connect + Speak: all that the bot needs in a server.
BOT_PERMISSIONS = 1024 + (1 << 20) + (1 << 21)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(int(raw), minimum)
    except ValueError:
        raise SystemExit(f"{name} must be an integer, got {raw!r}") from None


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return min(max(float(raw), minimum), maximum)
    except ValueError:
        raise SystemExit(f"{name} must be a number, got {raw!r}") from None


def _client_id(raw: str) -> str:
    value = raw.strip()
    if value and not (value.isdigit() and 5 <= len(value) <= 25):
        logging.getLogger("melomancer").warning("DISCORD_CLIENT_ID is not a number (the Application ID); no invite link is shown.")
        return ""
    return value


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    music_dir_override: str
    discord_token: str
    discord_client_id: str  # the Application ID; only used to show an invite link in the panel
    admin_username: str
    admin_password: str
    max_upload_mb: int
    session_hours: int
    cookie_secure: str  # "auto" | "true" | "false"
    auto_login: bool    # the administrator is let in without a password, for requests from this computer only
    ytdlp_enabled: bool
    ytdlp_allowed_hosts: tuple[str, ...]
    ytdlp_min_gap: int
    ytdlp_daily_limit: int
    ytdlp_cookies_file: str
    idle_leave_minutes: int
    default_volume: float
    login_max_failures: int
    login_window_seconds: int
    log_level: str
    version: str

    @property
    def invite_url(self) -> str | None:
        """The link that adds the bot to a server, or None when DISCORD_CLIENT_ID is not set."""
        if not self.discord_client_id:
            return None
        return (f"https://discord.com/oauth2/authorize?client_id={self.discord_client_id}"
                f"&scope=bot&permissions={BOT_PERMISSIONS}")

    @classmethod
    def from_env(cls) -> "Settings":
        hosts = os.getenv(
            "YTDLP_ALLOWED_HOSTS",
            "youtube.com,youtu.be,music.youtube.com,soundcloud.com,bandcamp.com",
        )
        cookie_secure = os.getenv("COOKIE_SECURE", "auto").strip().lower()
        if cookie_secure not in {"auto", "true", "false"}:
            raise SystemExit("COOKIE_SECURE must be auto, true or false.")
        return cls(
            data_dir=Path(os.getenv("DATA_DIR", "").strip() or default_data_dir()),
            music_dir_override=os.getenv("MUSIC_DIR", "").strip(),
            discord_token=os.getenv("DISCORD_TOKEN", "").strip(),
            discord_client_id=_client_id(os.getenv("DISCORD_CLIENT_ID", "")),
            admin_username=os.getenv("ADMIN_USERNAME", "admin").strip() or "admin",
            admin_password=os.getenv("ADMIN_PASSWORD", ""),
            max_upload_mb=_env_int("MAX_UPLOAD_MB", 300, 1),
            session_hours=_env_int("SESSION_HOURS", 168, 1),
            cookie_secure=cookie_secure,
            auto_login=_env_bool("AUTO_LOGIN", False),
            ytdlp_enabled=_env_bool("YTDLP_ENABLED", True),
            ytdlp_allowed_hosts=tuple(h.strip().lower() for h in hosts.split(",") if h.strip()),
            ytdlp_min_gap=_env_int("YTDLP_MIN_GAP_SECONDS", 20, 0),
            ytdlp_daily_limit=_env_int("YTDLP_DAILY_LIMIT", 50, 0),
            ytdlp_cookies_file=os.getenv("YTDLP_COOKIES_FILE", "").strip(),
            idle_leave_minutes=_env_int("IDLE_LEAVE_MINUTES", 30, 0),
            default_volume=_env_float("DEFAULT_VOLUME", 0.4, 0.0, 1.5),
            login_max_failures=_env_int("LOGIN_MAX_FAILURES", 5, 1),
            login_window_seconds=_env_int("LOGIN_WINDOW_SECONDS", 300, 10),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
            version=os.getenv("APP_VERSION", "dev").strip() or "dev",
        )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "melomancer.db"

    @property
    def music_dir(self) -> Path:
        return Path(self.music_dir_override) if self.music_dir_override else self.data_dir / "music"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.music_dir, self.tmp_dir):
            path.mkdir(parents=True, exist_ok=True)
