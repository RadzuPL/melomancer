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
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
try:
    import tomllib
except ImportError:   # Python before 3.11
    tomllib = None
import zipfile
from pathlib import Path

PORT = 18080
BASE = f"http://127.0.0.1:{PORT}"
PASSWORD = "smoke-test-password-1"
FAKE_TOKEN = ".".join(["MTIzNDU2Nzg5MDEyMzQ1Njc4OQ", "GabcDE", "abcdefghijklmnopqrstuvwxyz0123456789"])   # in parts: not a real token
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
    def __init__(self, base: str = "") -> None:
        self.base = base or BASE
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None) -> tuple[int, bytes]:
        request = urllib.request.Request(self.base + path, data=body, method=method,
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


def healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "api/health", timeout=3) as response:
            return response.status == 200
    except OSError:
        return False


def signatures(root: Path) -> None:
    """Information, not a check: is the bundled Python signed by its publisher? That decides how scary Windows looks."""
    for relative in ("runtime/pythonw.exe", "runtime/python.exe", "bin/deno.exe", "bin/ffmpeg.exe"):
        path = root / relative
        script = (f"$s = Get-AuthenticodeSignature -FilePath '{path}'; "
                  "Write-Output ('signature ' + '" + relative + "' + ': ' + $s.Status + ' | ' + $s.SignerCertificate.Subject)")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, encoding="utf-8",
                             errors="replace", timeout=60).stdout.strip()
        print(out or f"signature {relative}: could not be read", flush=True)


def background_mode(root: Path, work: Path) -> None:
    """The way a person starts it: pythonw, no console window, the icon next to the clock."""
    local = work / "lokalne dane Zażółć"
    config = local / "Melomancer" / "config.toml"
    env = {k: v for k, v in os.environ.items() if k not in ("APP_VERSION", "DATA_DIR", "AUTO_LOGIN", "MELOMANCER_CONFIG")}
    env.update(LOCALAPPDATA=str(local), ADMIN_PASSWORD=PASSWORD)
    url = "http://127.0.0.1:18082/"
    args = [str(root / "runtime" / "pythonw.exe"), "-m", "app.winmain", "--no-browser", "--port", "18082"]
    proc = subprocess.Popen(args, cwd=root, env=env)
    try:
        wait_for("the background mode to answer", lambda: healthy(url), 90)
        check(proc.poll() is None, "it runs in the background (pythonw, no console window)")
        logfile = local / "Melomancer" / "logs" / "melomancer.log"
        text = logfile.read_text(encoding="utf-8", errors="replace") if logfile.is_file() else ""
        check("Panel: " + url in text and "Log file:" in text, "the log file in the data folder says what it did")
        check(config.is_file(), "the settings file was created next to it (LOCALAPPDATA with Polish letters)")
        for _ in range(60):   # up to 30 s: the icon either appears or the log says why it could not
            seen = logfile.read_text(encoding="utf-8", errors="replace")
            if "Tray icon ready" in seen or "tray icon" in seen.lower() and ("not available" in seen or "failed" in seen):
                break
            time.sleep(0.5)
        text = logfile.read_text(encoding="utf-8", errors="replace")
        print("tray icon: " + ("shown" if "Tray icon ready" in text else "not available in this CI session (the server runs anyway)"), flush=True)
        again = subprocess.run(args, cwd=root, env=env, timeout=60)
        check(again.returncode == 0 and healthy(url), "a second start does not start a second copy, it opens the first")
        check("already running" in logfile.read_text(encoding="utf-8", errors="replace"), "the log says so")
    finally:
        proc.terminate()
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            proc.kill()
    check(not healthy(url), "after it is closed the panel does not answer any more")
    code = ("from app import tray; name = 'MelomancerSmokeTest'; tray.set_autostart(True, 'x', name); on = tray.autostart_enabled(name); "
            "tray.set_autostart(False, '', name); print('autostart', on, tray.autostart_enabled(name))")
    out = run([root / "runtime" / "python.exe", "-c", code], cwd=root).stdout
    check("autostart True False" in out, "start with Windows can be switched on and off in the user's own Run key")


def self_update(root: Path, work: Path) -> None:
    """The update from the panel, for real: this package pretends to be version 0.0.1, downloads the newest release from
    GitHub, swaps its own folder for it and the new version answers on the same port."""
    port = 18083
    url = f"http://127.0.0.1:{port}/"
    local = work / "lokalne dane aktualizacji"
    (root / "VERSION").write_text("0.0.1", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("APP_VERSION", "DATA_DIR", "AUTO_LOGIN", "MELOMANCER_CONFIG")}
    env.update(LOCALAPPDATA=str(local), ADMIN_PASSWORD=PASSWORD)
    proc = subprocess.Popen([str(root / "runtime" / "pythonw.exe"), "-m", "app.winmain", "--no-browser", "--port", str(port)],
                            cwd=root, env=env)
    client = Client(url.rstrip("/"))
    newest = None
    try:
        wait_for("the old version to answer", lambda: healthy(url), 90)
        status, _ = client.json("POST", "/api/auth/login", {"username": "admin", "password": PASSWORD})
        check(status == 200, "update test: signed in to the old version (0.0.1)")
        status, info = client.json("POST", "/api/system/update/check")
        if info.get("error") or not info.get("available"):
            print(f"update test skipped: GitHub did not give a newer release ({info.get('error')})", flush=True)
            return
        newest = info["latest"]
        check(info["installable"] is True and info["install"]["available"] is True, f"update test: {newest} is offered for installing from the panel")
        status, _ = client.json("POST", "/api/system/update/install")
        check(status == 200, "update test: the download was started")
        last = None
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            install = client.json("GET", "/api/system/update")[1]["install"]
            if install["phase"] != last:
                last = install["phase"]
                print(f"update: {install['state']} {install['phase']} {install['done'] // 1048576}/{install['total'] // 1048576} MB", flush=True)
            if install["state"] != "working":
                break
            time.sleep(2)
        if install["state"] == "failed" and install["error"] in ("unreachable", "rate_limited", "package_not_ready"):
            print(f"update test skipped: {install['error']}", flush=True)
            return
        check(install["state"] == "ready" and install["version"] == newest, f"update test: the new version is downloaded, checked and unpacked ({install})")
        check((root.with_name("Melomancer.new") / "VERSION").read_text(encoding="utf-8").strip() == newest, "update test: it waits next to the program as Melomancer.new")
        check((root / "VERSION").read_text(encoding="utf-8").strip() == "0.0.1", "update test: the running version is untouched so far")
        status, answer = client.json("POST", "/api/system/update/apply")
        if status != 200:
            print(f"apply answered {status}: {answer}", flush=True)
            dump_update_state(root, local)
            runner = local / "Melomancer" / "updates" / "runner"
            print("--- the helper by hand ---")
            for args in (["-c", "import sys; print(sys.path); import ctypes, urllib.request, argparse, json, subprocess; print('imports ok')"],
                         ["swap.py", "--help"]):
                result = subprocess.run([str(runner / "python.exe"), *args], cwd=runner, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
                print(result.returncode, result.stdout[-800:], result.stderr[-1500:])
            print(sorted(p.name for p in runner.iterdir()) if runner.is_dir() else "(no runner folder)")
        check(status == 200, "update test: the swap was started")
        try:
            code = proc.wait(90)
        except subprocess.TimeoutExpired:
            raise SystemExit("FAIL update test: the old version did not close")
        check(code == 0, f"update test: the old version closed by itself (exit code {code})")
        try:
            wait_for(f"version {newest} to answer on the same address", lambda: _version(url) == newest, 240)
        except SystemExit:
            dump_update_state(root, local)
            raise
        check(_version(url) == newest, f"update test: the new version {newest} answers on the same address")
        check((root / "VERSION").read_text(encoding="utf-8").strip() == newest, "update test: the program folder holds the new version")
        wait_for("the old folder to be deleted", lambda: not root.with_name("Melomancer.old").exists(), 60)
        check(not root.with_name("Melomancer.old").exists() and not root.with_name("Melomancer.new").exists(), "update test: nothing is left next to the program folder")
        backups = list((local / "Melomancer" / "data" / "backups").glob("melomancer-0.0.1-*.db"))
        check(len(backups) == 1, "update test: the database was copied before the swap")
        text = (local / "Melomancer" / "logs" / "update.log").read_text(encoding="utf-8", errors="replace")
        check("answers" in text, "update test: update.log tells the story")
        status, _ = Client(url.rstrip("/")).json("POST", "/api/auth/login", {"username": "admin", "password": PASSWORD})
        check(status == 200, "update test: the settings and the database survived (the same administrator signs in)")
    finally:
        if proc.poll() is None:
            proc.terminate()
        if newest:   # the new version was started by the helper: stop whatever listens on the port
            stop = ("import psutil; [psutil.Process(c.pid).terminate() for c in psutil.net_connections('tcp') "
                    f"if c.status == 'LISTEN' and c.laddr.port == {port} and c.pid]")
            subprocess.run([str(root / "runtime" / "python.exe"), "-c", stop], cwd=root, capture_output=True, timeout=60)


def dump_update_state(root: Path, local: Path) -> None:
    """Said before a failed update test ends: what the helper wrote and what is left on the disk."""
    print("--- update.log ---")
    log = local / "Melomancer" / "logs" / "update.log"
    print(log.read_text(encoding="utf-8", errors="replace") if log.is_file() else "(no update.log)")
    print("--- next to the program folder ---")
    print(sorted(p.name for p in root.parent.iterdir()))
    for name in ("VERSION",):
        for folder in sorted(root.parent.glob("Melomancer*")):
            marker = folder / name
            print(f"{folder.name}/{name}: " + (marker.read_text(encoding="utf-8").strip() if marker.is_file() else "-"))
    print("--- the updates folder ---")
    updates = local / "Melomancer" / "updates"
    print(sorted(str(p.relative_to(updates)) for p in updates.rglob("*") if p.is_file())[:20] if updates.is_dir() else "(none)")
    print("--- melomancer.log (tail) ---")
    main_log = local / "Melomancer" / "logs" / "melomancer.log"
    if main_log.is_file():
        print("\n".join(main_log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]))
    print("--- pythonw processes ---")
    print(subprocess.run(["tasklist", "/FI", "IMAGENAME eq pythonw.exe"], capture_output=True, encoding="utf-8", errors="replace").stdout)


def _version(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url + "api/health", timeout=3) as response:
            return json.loads(response.read()).get("version")
    except (OSError, ValueError):
        return None


def main(archive: Path, version: str) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the runner's code page (cp1252) has no ż
    work = Path(tempfile.mkdtemp()) / "Muzyka Zażółć"
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(work)
    root = work / "Melomancer"
    py, ffmpeg = root / "runtime" / "python.exe", root / "bin" / "ffmpeg.exe"
    check(py.is_file() and ffmpeg.is_file(), f"package unpacked under {work}")

    # ---- what a person finds in the folder ----
    for name in ("Melomancer.cmd", "Ustawienia - Settings.cmd", "Diagnostyka - Diagnostics.cmd", "README-WINDOWS.txt", "THIRD_PARTY.md"):
        check((root / name).is_file(), f"{name} is in the package")
    readme = (root / "README-WINDOWS.txt").read_text(encoding="utf-8")
    check("Zawsze pytaj przed otwarciem" in readme and "Always ask before opening" in readme
          and "Odblokuj" not in readme and "Unblock" not in readme and "docs/pl/windows.md" in readme and "docs/en/windows.md" in readme,
          "the README describes the security window of the .cmd file and links the full guide, in Polish and English")
    check(not (root / "config.example.toml").exists(), "there is no separate example of the settings: the program writes config.toml itself")

    # ---- an older settings file is brought up to date, in a folder with Polish letters ----
    older = work / "stary config Zażółć.toml"
    older.write_text("# discord_token = ''\nport = 9000\n", encoding="utf-8")
    code = ("import sys; from pathlib import Path; from app import winmain; "
            "print('added:' + ','.join(winmain.sync_config(Path(sys.argv[1]), '1.0')))")
    added = run([root / "runtime" / "python.exe", "-c", code, str(older)], cwd=root).stdout
    check("discord_client_id" in added and "auto_login" in added and "discord_token" not in added and "port" not in added.split("added:")[1].split(","),
          f"missing settings are appended, existing ones are not repeated ({added.strip()})")
    check("Dodane przez Melomancera 1.0" in older.read_text(encoding="utf-8"), "the appended part is readable UTF-8")

    signatures(root)

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

        # ---- the bot is set up from the panel: the token goes into config.toml and the bot logs in without a restart ----
        status, info = client.json("GET", "/api/system")
        check(info["bot_setup"] is True and info["bot_token_set"] is False, "the panel offers the bot setup (the launcher knows the settings file)")
        status, info = client.json("PUT", "/api/system/bot", {"token": FAKE_TOKEN, "client_id": "123456789012345678"})
        check(status == 200 and info["bot_token_set"] is True and FAKE_TOKEN not in json.dumps(info), f"the token is accepted and never sent back ({status})")
        raw = config.read_bytes()
        check(f"discord_token = '{FAKE_TOKEN}'".encode() in raw and b"discord_client_id = '123456789012345678'" in raw,
              "the token and the Application ID are in config.toml")
        check(b"\n" not in raw.replace(b"\r\n", b""), "the file kept its Windows line endings")
        if tomllib:
            check(tomllib.loads(raw.decode("utf-8-sig"))["discord_token"] == FAKE_TOKEN, "config.toml still parses")
        status, info = client.json("PUT", "/api/system/bot", {"token": "123456789012345678"})
        check(status == 422 and info["detail"] == "token_is_app_id", "the Application ID pasted as a token is named, not saved")
        answer = wait_for("the bot to answer Discord", lambda: (client.json("GET", "/api/system")[1]["bot_status"] != "starting") or None, 60)
        print("bot status after the fake token: " + client.json("GET", "/api/system")[1]["bot_status"] + " (login_failed with a network)", flush=True)
        status, info = client.json("PUT", "/api/system/bot", {"token": ""})
        check(status == 200 and info["bot_token_set"] is False and info["bot_status"] == "disabled", "removing the token switches the bot off")
        check(b"discord_token = ''" in config.read_bytes(), "the settings file keeps an empty token line")

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
        check(FAKE_TOKEN not in (work / "server.log").read_text(encoding="utf-8", errors="replace"), "the token is not in the log")
        print("--- server log (tail) ---")
        print("\n".join((work / "server.log").read_text(encoding="utf-8", errors="replace").splitlines()[-40:]))
    background_mode(root, work)
    self_update(root, work)
    print("smoke test passed")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    sys.exit(main(Path(sys.argv[1]), sys.argv[2]))
