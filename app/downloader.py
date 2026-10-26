"""Background yt-dlp worker: one download at a time, with a pause between them and a daily cap.

The limits exist to keep the server's (fixed) IP address out of trouble with YouTube.
Playlists are never expanded; one URL means one video.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from .config import Settings
from .db import tx
from .library import IngestError, ingest

log = logging.getLogger("melomancer.downloads")

# report(stage=..., percent=..., speed=..., eta=..., title=...) tells the panel how far a download is.
ReportFunc = Callable[..., None]
# fetch(url, workdir, settings, report) -> (downloaded file, display title, final source url)
FetchFunc = Callable[[str, Path, Settings, ReportFunc], "tuple[Path, str, str]"]


class DownloadRejected(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def validate_url(settings: Settings, url: str) -> str:
    url = (url or "").strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise DownloadRejected("bad_url")
    host = parts.hostname.lower()
    allowed = any(host == h or host.endswith("." + h) for h in settings.ytdlp_allowed_hosts)
    if not allowed:
        raise DownloadRejected("host_not_allowed")
    return url


def count_recent(settings: Settings) -> int:
    with tx(settings.db_path) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM downloads WHERE status IN ('queued','running','done') "
            "AND created_at > datetime('now','-1 day')"
        ).fetchone()[0]


def enqueue(settings: Settings, user_id: int, url: str, tags: list[str]) -> int:
    if not settings.ytdlp_enabled:
        raise DownloadRejected("downloads_disabled")
    url = validate_url(settings, url)
    if settings.ytdlp_daily_limit and count_recent(settings) >= settings.ytdlp_daily_limit:
        raise DownloadRejected("daily_limit")
    with tx(settings.db_path) as conn:
        cur = conn.execute(
            "INSERT INTO downloads(user_id, url, tags) VALUES (?,?,?)",
            (user_id, url, json.dumps(tags)),
        )
        return int(cur.lastrowid)


def ytdlp_fetch(url: str, workdir: Path, settings: Settings, report: ReportFunc) -> tuple[Path, str, str]:
    import yt_dlp  # imported lazily so the panel still starts if the package is broken

    class _Log:
        def debug(self, msg: str) -> None: ...
        def info(self, msg: str) -> None: ...
        def warning(self, msg: str) -> None:
            log.debug("yt-dlp: %s", msg)

        def error(self, msg: str) -> None:
            log.warning("yt-dlp: %s", msg)

    def on_progress(data: dict) -> None:
        title = (data.get("info_dict") or {}).get("title")
        if title:
            report(title=str(title))
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            done = data.get("downloaded_bytes") or 0
            report(stage="downloading", percent=round(done / total * 100, 1) if total else None,
                   speed=data.get("speed"), eta=data.get("eta"))
        elif data.get("status") == "finished":
            report(stage="converting", percent=None, speed=None, eta=None)

    def on_postprocess(data: dict) -> None:
        if data.get("status") == "started":
            report(stage="converting", percent=None, speed=None, eta=None)

    options = {
        "progress_hooks": [on_progress],
        "postprocessor_hooks": [on_postprocess],
        "format": "bestaudio/best",
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "restrictfilenames": True,
        "retries": 3,
        "socket_timeout": 30,
        "max_filesize": settings.max_upload_mb * 1024 * 1024,
        "logger": _Log(),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "opus"}],
    }
    if settings.ytdlp_cookies_file and Path(settings.ytdlp_cookies_file).is_file():
        options["cookiefile"] = settings.ytdlp_cookies_file
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            raise RuntimeError("no_result")
        if info.get("_type") == "playlist" and info.get("entries"):
            info = next(e for e in info["entries"] if e)
        downloads = info.get("requested_downloads") or []
        path = Path(downloads[0]["filepath"]) if downloads else None
        if path is None or not path.is_file():
            matches = sorted(workdir.glob(f"{info.get('id', '*')}.*"))
            if not matches:
                raise RuntimeError("no_file")
            path = matches[0]
        return path, str(info.get("title") or path.stem), str(info.get("webpage_url") or url)


class Downloader:
    def __init__(self, settings: Settings, fetch: FetchFunc = ytdlp_fetch) -> None:
        self.settings = settings
        self._fetch = fetch
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._progress: dict[int, dict] = {}
        self._lock = threading.Lock()
        self._pause_until = 0.0

    # ---- progress, read by the API ---------------------------------------

    def _report(self, job_id: int, **fields) -> None:
        with self._lock:
            self._progress.setdefault(job_id, {}).update(fields)

    def progress(self) -> dict[int, dict]:
        with self._lock:
            return {job: dict(values) for job, values in self._progress.items()}

    def pause_remaining(self) -> int:
        """Seconds until the next queued download may start (the deliberate pause between downloads)."""
        return max(0, math.ceil(self._pause_until - time.monotonic()))

    def start(self) -> None:
        if not self.settings.ytdlp_enabled or self._thread:
            return
        with tx(self.settings.db_path) as conn:  # jobs interrupted by a restart go back to the queue
            conn.execute("UPDATE downloads SET status='queued' WHERE status='running'")
        self._thread = threading.Thread(target=self._run, name="downloader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def wake(self) -> None:
        self._wake.set()

    def _next_job(self):
        with tx(self.settings.db_path) as conn:
            row = conn.execute("SELECT * FROM downloads WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
            if row:
                conn.execute(
                    "UPDATE downloads SET status='running', updated_at=datetime('now') WHERE id=?", (row["id"],)
                )
            return row

    def _finish(self, job_id: int, status: str, error: str | None = None, track_id: str | None = None,
                title: str | None = None) -> None:
        with tx(self.settings.db_path) as conn:
            conn.execute(
                "UPDATE downloads SET status=?, error=?, track_id=?, title=COALESCE(?, title), "
                "updated_at=datetime('now') WHERE id=?",
                (status, error, track_id, title, job_id),
            )

    def process_one(self) -> bool:
        """Handle the next queued job. Returns False when the queue is empty."""
        job = self._next_job()
        if job is None:
            return False
        job_id = job["id"]
        workdir = self.settings.tmp_dir / f"dl-{job_id}"
        workdir.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        self._report(job_id, stage="preparing", percent=None, speed=None, eta=None)
        log.info("Download %s started (%s)", job_id, urlsplit(job["url"]).hostname)
        try:
            path, title, final_url = self._fetch(job["url"], workdir, self.settings,
                                                 lambda **fields: self._report(job_id, **fields))
            self._report(job_id, stage="importing", percent=None, speed=None, eta=None, title=title)
            track, status = ingest(
                self.settings, path, owner_id=job["user_id"], original_name=path.name,
                source="youtube", source_url=final_url, title=title, tags=json.loads(job["tags"] or "[]"),
            )
            self._finish(job["id"], "done", None if status != "duplicate" else "duplicate",
                         track["id"], track["title"])
        except IngestError as exc:
            self._finish(job["id"], "error", exc.code)
        except Exception as exc:  # noqa: BLE001 - one bad URL must not kill the worker
            log.warning("Download %s failed: %s", job["id"], exc)
            self._finish(job["id"], "error", str(exc)[:300] or "failed")
        finally:
            for leftover in workdir.glob("*"):
                leftover.unlink(missing_ok=True)
            workdir.rmdir()
            with self._lock:
                self._progress.pop(job_id, None)
            log.info("Download %s finished after %.0f s", job_id, time.monotonic() - started)
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            if self.process_one():
                # Pause between downloads, interruptible by shutdown. The panel shows the remaining seconds.
                self._pause_until = time.monotonic() + self.settings.ytdlp_min_gap
                self._stop.wait(self.settings.ytdlp_min_gap)
            else:
                self._wake.wait(timeout=30)
                self._wake.clear()
