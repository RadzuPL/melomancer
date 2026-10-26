from __future__ import annotations

from dataclasses import replace

import pytest

from app.config import Settings
from app.db import init_db, tx
from app.downloader import DownloadRejected, Downloader, enqueue, validate_url

from .conftest import login, make_user, make_wav


@pytest.fixture
def settings(tmp_path):
    cfg = replace(Settings.from_env(), data_dir=tmp_path / "data", ytdlp_enabled=True, ytdlp_daily_limit=2,
                  ytdlp_min_gap=0)
    cfg.ensure_dirs()
    init_db(cfg.db_path)
    with tx(cfg.db_path) as conn:
        conn.execute("INSERT INTO users(username, pw_hash, role) VALUES ('admin','x','admin')")
    return cfg


def test_url_validation(settings):
    assert validate_url(settings, "https://www.youtube.com/watch?v=abc") .startswith("https://")
    assert validate_url(settings, "https://youtu.be/abc")
    assert validate_url(settings, "https://artist.bandcamp.com/track/x")
    for bad in ("http://youtube.com/watch?v=abc", "https://evil.example/watch", "https://notyoutube.com/x",
                "ftp://youtube.com/x", "javascript:alert(1)", ""):
        with pytest.raises(DownloadRejected):
            validate_url(settings, bad)


def test_daily_limit_and_switch(settings):
    enqueue(settings, 1, "https://youtu.be/a", [])
    enqueue(settings, 1, "https://youtu.be/b", [])
    with pytest.raises(DownloadRejected) as limit:
        enqueue(settings, 1, "https://youtu.be/c", [])
    assert limit.value.code == "daily_limit"
    off = replace(settings, ytdlp_enabled=False)
    with pytest.raises(DownloadRejected) as disabled:
        enqueue(off, 1, "https://youtu.be/d", [])
    assert disabled.value.code == "downloads_disabled"


def test_worker_ingests_a_finished_download(settings, tmp_path):
    def fetch(url, workdir, cfg, report):
        report(stage="downloading", percent=42.0, speed=1_000_000, eta=3, title="Rain on the glass")
        seen.append(worker.progress()[job])
        return make_wav(workdir / "clip.wav", 500), "Rain on the glass", url

    seen = []
    job = enqueue(settings, 1, "https://youtu.be/rain", ["Rain"], ["Sesja 3"])
    worker = Downloader(settings, fetch=fetch)
    assert worker.process_one() is True
    assert worker.process_one() is False  # queue empty
    assert seen and seen[0]["percent"] == 42.0 and seen[0]["stage"] == "downloading"
    assert isinstance(seen[0]["elapsed"], int) and "started" not in seen[0]
    assert worker.progress() == {}  # nothing is reported for a finished job

    with tx(settings.db_path) as conn:
        row = conn.execute("SELECT * FROM downloads WHERE id=?", (job,)).fetchone()
        track = conn.execute("SELECT * FROM tracks WHERE id=?", (row["track_id"],)).fetchone()
        tags = [r["tag"] for r in conn.execute("SELECT tag FROM track_tags WHERE track_id=?", (track["id"],))]
        mine = [r["tag"] for r in conn.execute("SELECT tag FROM user_tags WHERE track_id=?", (track["id"],))]
    assert row["status"] == "done"
    assert track["title"] == "Rain on the glass" and track["source"] == "youtube"
    assert tags == ["rain"] and mine == ["sesja 3"]
    assert not list(settings.tmp_dir.glob("dl-*"))


def test_a_duplicate_download_still_gets_the_personal_tags(settings):
    def fetch(url, workdir, cfg, report):
        return make_wav(workdir / "clip.wav", 500), "Rain", url

    worker = Downloader(settings, fetch=fetch)
    enqueue(settings, 1, "https://youtu.be/one", [], ["Sesja 3"])
    enqueue(settings, 1, "https://youtu.be/two", [], ["Sesja 4"])
    assert worker.process_one() and worker.process_one()
    with tx(settings.db_path) as conn:
        statuses = [r["error"] for r in conn.execute("SELECT error FROM downloads ORDER BY id")]
        mine = sorted(r["tag"] for r in conn.execute("SELECT tag FROM user_tags"))
        tracks = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    assert statuses == [None, "duplicate"] and tracks == 1
    assert mine == ["sesja 3", "sesja 4"]


def test_worker_records_failures_and_keeps_going(settings):
    def fetch(url, workdir, cfg, report):
        raise RuntimeError("Sign in to confirm you're not a bot")

    job = enqueue(settings, 1, "https://youtu.be/blocked", [])
    worker = Downloader(settings, fetch=fetch)
    assert worker.process_one() is True
    with tx(settings.db_path) as conn:
        row = conn.execute("SELECT status, error FROM downloads WHERE id=?", (job,)).fetchone()
    assert row["status"] == "error" and "bot" in row["error"]


def test_download_api_validates_and_scopes_jobs(env):
    assert login(env, "admin").status_code == 200
    bad = env.client.post("/api/downloads", json={"url": "https://evil.example/x.mp3"})
    assert bad.status_code == 400 and bad.json()["detail"] == "host_not_allowed"
    ok = env.client.post("/api/downloads", json={"url": "https://youtu.be/abc", "tags": ["Ambient"], "my_tags": ["Sesja 3"]})
    assert ok.status_code == 201
    listing = env.client.get("/api/downloads").json()
    assert [d["status"] for d in listing["jobs"]] == ["queued"] and listing["pause_remaining"] == 0

    make_user(env, "mg1")
    login(env, "mg1")
    assert env.client.get("/api/downloads").json()["jobs"] == []  # other users' jobs are not listed
    assert env.client.delete(f"/api/downloads/{ok.json()['id']}").status_code == 404

    login(env, "admin")
    assert env.client.delete(f"/api/downloads/{ok.json()['id']}").status_code == 200
