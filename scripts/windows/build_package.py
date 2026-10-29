#!/usr/bin/env python3
"""Builds the Windows package of Melomancer: a folder you unpack and start, no installer and no Docker.

Run on Windows with the same Python 3.12 that the package will carry (CI does it in .github/workflows/windows.yml):

    python scripts/windows/build_package.py tools build/bin
    python scripts/windows/build_package.py package --version 0.7.0 --tools build/bin --out dist

`tools` downloads ffmpeg and ffprobe (the LGPL build of BtbN, with its DLLs) and deno (the JavaScript runtime yt-dlp
needs for YouTube). `package` downloads the official embeddable Python of the same version as the running one,
installs the requirements into it with the running interpreter's pip (wheels only), and zips the result.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DENO_URL = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"
FFMPEG_API = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/tags/latest"
FFMPEG_DOWNLOAD = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
FFMPEG_FALLBACK = "ffmpeg-master-latest-win64-lgpl-shared.zip"
FFMPEG_RELEASE_NAME = re.compile(r"^ffmpeg-n(\d+)\.(\d+)-latest-win64-lgpl-shared-\d+\.\d+\.zip$")

SETTINGS_CMD = r"""@echo off
setlocal
cd /d "%~dp0"
"runtime\python.exe" -m app.winmain --edit-config
"""

CMD_FILE = r"""@echo off
setlocal
cd /d "%~dp0"
"runtime\python.exe" -m app.winmain %*
if errorlevel 1 (
  echo.
  echo Melomancer stopped with an error. The messages above say why.
  pause
)
"""

READ_ME = """Melomancer dla Windows (wersja testowa)
=======================================

Pełna instrukcja ze zdjęciami i krokami:
https://github.com/RadzuPL/melomancer/blob/main/docs/pl/windows.md

W skrócie:

1. Rozpakuj ten folder w miejscu, w którym ma zostać, na przykład C:\\Melomancer (nie do "Program Files" i nie
   uruchamiaj programu z wnętrza zipa).
2. Kliknij dwukrotnie Melomancer.cmd. Windows zapyta "Nie można zweryfikować wydawcy": to normalne, bo program nie ma
   płatnego podpisu. Odznacz "Zawsze pytaj przed otwarciem tego pliku" i kliknij "Uruchom".
3. Otworzy się czarne okno (to działa Melomancer, nie zamykaj go, dopóki słuchasz) i przeglądarka ze stroną
   Melomancera. Logować się nie trzeba. Gdyby przeglądarka się nie otworzyła, wpisz: http://127.0.0.1:8080/
4. Dodaj muzykę w zakładce "Biblioteka" i zagraj ją w zakładce "Odtwarzacz" przyciskiem "Odtwarzaj tutaj".
5. Muzyka na Discordzie: kliknij dwukrotnie "Ustawienia - Settings.cmd", wpisz token i Application ID swojego bota
   (instrukcja w pełnym opisie) i uruchom Melomancera ponownie.

Twoje ustawienia i muzyka leżą w %LOCALAPPDATA%\\Melomancer, poza tym folderem, więc aktualizacja polega na
rozpakowaniu nowej wersji do nowego folderu. Zamknięcie czarnego okna wyłącza Melomancera. Licencje dołączonych
programów są w folderze "licenses" i w THIRD_PARTY.md.


Melomancer for Windows (test version)
=====================================

The full guide with pictures and steps:
https://github.com/RadzuPL/melomancer/blob/main/docs/en/windows.md

In short:

1. Unpack this folder where it should stay, for example C:\\Melomancer (not into "Program Files", and do not start
   the program from inside the zip).
2. Double-click Melomancer.cmd. Windows asks "Unable to verify the publisher": that is normal, because the program
   has no paid signature. Untick "Always ask before opening this file" and click "Run".
3. A black window opens (that is Melomancer running, do not close it while you listen) and your browser opens the
   Melomancer page. You do not have to sign in. If the browser does not open, type: http://127.0.0.1:8080/
4. Add music in the "Library" tab and play it in the "Player" tab with the "Play here" button.
5. Music on Discord: double-click "Ustawienia - Settings.cmd", enter the token and the Application ID of your bot
   (see the full guide) and start Melomancer again.

Your settings and music live in %LOCALAPPDATA%\\Melomancer, outside this folder, so updating means unpacking the new
version into a new folder. Closing the black window switches Melomancer off. Licences of the bundled programs are in
the folder "licenses" and in THIRD_PARTY.md.
"""


def download(url: str, dest: Path, attempts: int = 3) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "melomancer-build"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as response, \
                    open(dest, "wb") as out:
                shutil.copyfileobj(response, out)
            print(f"downloaded {url} ({dest.stat().st_size // 1024} KB)")
            return
        except OSError as exc:
            print(f"download failed ({attempt}/{attempts}): {url}: {exc}")
            if attempt == attempts:
                raise
            time.sleep(3 * attempt)


def pick_ffmpeg_asset(names: list[str]) -> str:
    """The newest release-branch LGPL build (ffmpeg-n8.0-latest-win64-lgpl-shared-8.0.zip) rather than master."""
    releases = [(int(m[1]), int(m[2]), name) for name in names if (m := FFMPEG_RELEASE_NAME.match(name))]
    return max(releases)[2] if releases else FFMPEG_FALLBACK


def ffmpeg_url() -> str:
    try:
        tmp = ROOT / "build" / "ffmpeg-release.json"
        download(FFMPEG_API, tmp)
        names = [asset["name"] for asset in json.loads(tmp.read_text(encoding="utf-8"))["assets"]]
    except (OSError, ValueError, KeyError) as exc:
        print(f"could not list the ffmpeg builds ({exc}); using the master build")
        names = []
    chosen = pick_ffmpeg_asset(names)
    print("ffmpeg build:", chosen)
    return FFMPEG_DOWNLOAD + chosen


def fetch_tools(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    work = ROOT / "build" / "downloads"
    ffmpeg_zip = work / "ffmpeg.zip"
    download(ffmpeg_url(), ffmpeg_zip)
    with zipfile.ZipFile(ffmpeg_zip) as archive:
        for member in archive.namelist():
            parts = member.split("/")
            if len(parts) == 3 and parts[1] == "bin" and parts[2] and parts[2] != "ffplay.exe":
                (out / parts[2]).write_bytes(archive.read(member))
            elif len(parts) == 2 and parts[1].upper().startswith("LICENSE"):
                (out / "FFMPEG-LICENSE.txt").write_bytes(archive.read(member))
    deno_zip = work / "deno.zip"
    download(DENO_URL, deno_zip)
    with zipfile.ZipFile(deno_zip) as archive:
        (out / "deno.exe").write_bytes(archive.read("deno.exe"))
    for needed in ("ffmpeg.exe", "ffprobe.exe", "deno.exe"):
        if not (out / needed).is_file():
            raise SystemExit(f"{needed} is missing from {out}")
    print("tools ready in", out)


def pth_text(major: int, minor: int) -> str:
    """The embeddable Python ignores PYTHONPATH and the current folder; this file is what it reads instead."""
    return f"python{major}{minor}.zip\n.\n..\nLib\\site-packages\nimport site\n"


def package(version: str, tools: Path, out: Path, build: str = "", commit: str = "") -> Path:
    import subprocess
    major, minor, micro = sys.version_info[:3]
    full = f"{major}.{minor}.{micro}"
    root = ROOT / "build" / "Melomancer"
    if root.exists():
        shutil.rmtree(root)
    runtime = root / "runtime"
    embed_zip = ROOT / "build" / "downloads" / f"python-{full}-embed-amd64.zip"
    download(f"https://www.python.org/ftp/python/{full}/python-{full}-embed-amd64.zip", embed_zip)
    with zipfile.ZipFile(embed_zip) as archive:
        archive.extractall(runtime)
    (runtime / f"python{major}{minor}._pth").write_text(pth_text(major, minor), encoding="utf-8")

    site = runtime / "Lib" / "site-packages"
    site.mkdir(parents=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--target", str(site), "--only-binary=:all:",
                    "--no-warn-script-location", "-r", str(ROOT / "requirements.txt")], check=True)

    shutil.copytree(ROOT / "app", root / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(tools, root / "bin")
    licenses = root / "licenses"
    licenses.mkdir()
    for name in ("FFMPEG-LICENSE.txt",):
        if (root / "bin" / name).is_file():
            shutil.move(str(root / "bin" / name), licenses / name)
    shutil.copy(ROOT / "LICENSE", licenses / "Melomancer-LICENSE.txt")
    shutil.copy(ROOT / "THIRD_PARTY.md", root / "THIRD_PARTY.md")
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    if build:   # which build of the same version this is, shown in the console window (the version itself stays X.Y.Z)
        (root / "BUILD").write_text(f"build {build}" + (f", {commit}" if commit else "") + "\n", encoding="utf-8")
    (root / "Melomancer.cmd").write_text(CMD_FILE.replace("\n", "\r\n"), encoding="utf-8")
    (root / "Ustawienia - Settings.cmd").write_text(SETTINGS_CMD.replace("\n", "\r\n"), encoding="utf-8")
    sys.path.insert(0, str(ROOT))
    from app import winmain   # the template that the program itself writes on the first start
    (root / "config.example.toml").write_text(winmain.TEMPLATE, encoding="utf-8")
    (root / "README-WINDOWS.txt").write_text(READ_ME.replace("\n", "\r\n"), encoding="utf-8")

    out.mkdir(parents=True, exist_ok=True)
    target = out / f"Melomancer-win64-{version}{f'-build{build}' if build else ''}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, Path("Melomancer") / path.relative_to(root))
    print(f"package: {target} ({target.stat().st_size // 1048576} MB, Python {full})")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    tools = sub.add_parser("tools", help="download ffmpeg, ffprobe and deno")
    tools.add_argument("out", type=Path)
    pack = sub.add_parser("package", help="assemble and zip the package")
    pack.add_argument("--version", required=True)
    pack.add_argument("--tools", type=Path, required=True)
    pack.add_argument("--out", type=Path, default=ROOT / "dist")
    pack.add_argument("--build", default="", help="build number (CI run number): two builds of one version differ by it")
    pack.add_argument("--commit", default="", help="short commit id, shown next to the build number")
    args = parser.parse_args()
    if args.command == "tools":
        fetch_tools(args.out)
    else:
        package(args.version, args.tools, args.out, args.build, args.commit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
