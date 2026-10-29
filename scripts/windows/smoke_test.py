#!/usr/bin/env python3
"""Starts the Windows package for real and checks that it works, in a folder with Polish letters in its name.

    python scripts/windows/smoke_test.py dist/Melomancer-win64-0.7.0.zip 0.7.0

What it proves: the bundled Python imports every dependency (including the native ones and Discord's libopus), the
bundled ffmpeg has what the app uses, the server starts from config.toml, answers, logs in, takes an upload whose tag
holds Polish letters (the title must come back intact, not in the wrong code page), measures it with ffmpeg at a low
priority, reports its own load and deletes the track.
"""
from __future__ import annotations

import http.cookiejar
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

PORT = 18080
BASE = f"http://127.0.0.1:{PORT}"
PASSWORD = "smoke-test-password-1"
POLISH = "Zażółć gęślą jaźń"


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    print("$", " ".join(str(part) for part in cmd), flush=True)
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=120, **kwargs)
    if result.returncode != 0:
        print(result.stdout, result.stderr, sep="\n")
        raise SystemExit(f"FAIL: exit code {result.returncode}")
    return result


def check(condition: bool, message: str) -> None:
    print(("ok   " if condition else "FAIL ") + message, flush=True)
    if not condition:
        raise SystemExit(1)


class Client:
    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None) -> tuple[int, bytes]:
        request = urllib.request.Request(BASE + path, data=body, method=method,
                                         headers={"X-Melomancer": "1", **(headers or {})})
        try:
            with self.opener.open(request, timeout=30) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def json(self, method: str, path: str, payload: dict | None = None) -> tuple[int, object]:
        body = json.dumps(payload).encode() if payload is not None else None
        status, raw = self.call(method, path, body, {"Content-Type": "application/json"} if body else None)
        return status, (json.loads(raw) if raw else None)


def multipart(field: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            "Content-Type: audio/wav\r\n\r\n").encode()
    return head + content + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def wait_for(what: str, probe, seconds: float):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = probe()
        if value:
            return value
        time.sleep(1)
    raise SystemExit(f"FAIL: {what} did not happen within {seconds:.0f} s")


def main(archive: Path, version: str) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the runner's code page (cp1252) has no ż
    work = Path(tempfile.mkdtemp()) / "Muzyka Zażółć"
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(work)
    root = work / "Melomancer"
    py, ffmpeg = root / "runtime" / "python.exe", root / "bin" / "ffmpeg.exe"
    check(py.is_file() and ffmpeg.is_file(), f"package unpacked under {work}")

    # ---- what a person finds in the folder ----
    for name in ("Melomancer.cmd", "Ustawienia - Settings.cmd", "README-WINDOWS.txt", "config.example.toml", "THIRD_PARTY.md"):
        check((root / name).is_file(), f"{name} is in the package")
    readme = (root / "README-WINDOWS.txt").read_text(encoding="utf-8")
    check("Zawsze pytaj przed otwarciem" in readme and "Odblokuj" not in readme and "Unblock" not in readme,
          "the README describes the security window of the .cmd file, in Polish and English")
    check("discord_client_id" in (root / "config.example.toml").read_text(encoding="utf-8"), "config.example.toml lists discord_client_id")

    # ---- an older settings file is brought up to date, in a folder with Polish letters ----
    older = work / "stary config Zażółć.toml"
    older.write_text("# discord_token = ''\nport = 9000\n", encoding="utf-8")
    code = ("import sys; from pathlib import Path; from app import winmain; "
            "print('added:' + ','.join(winmain.sync_config(Path(sys.argv[1]), '1.0')))")
    added = run([root / "runtime" / "python.exe", "-c", code, str(older)], cwd=root).stdout
    check("discord_client_id" in added and "auto_login" in added and "discord_token" not in added and "port" not in added.split("added:")[1].split(","),
          f"missing settings are appended, existing ones are not repeated ({added.strip()})")
    check("Dodane przez Melomancera 1.0" in older.read_text(encoding="utf-8"), "the appended part is readable UTF-8")

    # ---- the bundled Python and its libraries ----
    out = run([py, "-c", (
        "import discord, nacl, davey, argon2, uvicorn, fastapi, yt_dlp, psutil, sys; import discord.opus as o;"
        "print('python', sys.version.split()[0]); print('discord', discord.__version__);"
        "print('yt-dlp', yt_dlp.version.__version__); print('opus', bool(o._load_default()), o.is_loaded())")],
        cwd=root).stdout
    print(out)
    check("opus True True" in out, "libopus loads from discord.py's own folder")

    # ---- the bundled tools ----
    run([root / "bin" / "ffprobe.exe", "-version"])
    check("libopus" in run([ffmpeg, "-hide_banner", "-encoders"]).stdout, "ffmpeg can encode opus (yt-dlp needs it)")
    filters = run([ffmpeg, "-hide_banner", "-filters"]).stdout
    check("loudnorm" in filters and "silencedetect" in filters, "ffmpeg has loudnorm and silencedetect")
    print(run([root / "bin" / "deno.exe", "--version"]).stdout)

    # ---- the server ----
    config, data = work / "config Zażółć.toml", work / "dane Zażółć"
    env = {k: v for k, v in __import__("os").environ.items() if k not in ("APP_VERSION", "DATA_DIR")}
    env.update(DATA_DIR=str(data), ADMIN_PASSWORD=PASSWORD)
    log = open(work / "server.log", "w", encoding="utf-8")
    server = subprocess.Popen([py, "-m", "app.winmain", "--no-browser", "--port", str(PORT), "--config", str(config)],
                              cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
    client = Client()
    try:
        def health():
            try:
                status, raw = client.call("GET", "/api/health")
                return json.loads(raw) if status == 200 else None
            except OSError:
                return None
        info = wait_for("the server to answer", health, 90)
        check(info["version"] == version, f"version {info['version']} comes from the VERSION file")
        check(config.is_file(), "config.toml was created on the first start")
        status, _ = client.json("POST", "/api/auth/login", {"username": "admin", "password": PASSWORD})
        check(status == 200, "the administrator can log in")

        tone = work / "tone.wav"
        run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
             "-metadata", f"title={POLISH}", tone])
        body, content_type = multipart("file", "tone.wav", tone.read_bytes())
        status, raw = client.call("POST", "/api/tracks/upload", body, {"Content-Type": content_type})
        check(status == 201, f"upload accepted ({status} {raw[:200]!r})")
        track = json.loads(raw)
        check(track["title"] == POLISH, f"the title with Polish letters survives ffprobe: {track['title']!r}")

        measured = wait_for("the loudness measurement", lambda: client.json("GET", "/api/system")[1]["loudness"]["measured"] >= 1, 90)
        check(bool(measured), "ffmpeg measured the track in the background")
        time.sleep(5)
        status, load = client.json("GET", "/api/system/load")
        check(status == 200 and load["memory_mb"] > 0 and load["cpu"] is not None, f"load is reported: {load['source']}, "
              f"{load['memory_mb']} MB, {load['cpu']} %")

        status, _ = client.json("DELETE", f"/api/tracks/{track['id']}")
        check(status in (200, 204), f"the track can be deleted ({status})")
        check((data / "melomancer.db").is_file(), "the database is in the data folder")
    finally:
        server.terminate()
        try:
            server.wait(15)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()
        print("--- server log (tail) ---")
        print("\n".join((work / "server.log").read_text(encoding="utf-8", errors="replace").splitlines()[-40:]))
    print("smoke test passed")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    sys.exit(main(Path(sys.argv[1]), sys.argv[2]))
