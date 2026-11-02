"""Installing an update from the panel, in the Windows package only.

The panel asks, the server does it in two steps that the person starts one after the other:

  1. download + unpack  (a thread): fetch the package of the newest release from GitHub, check its size and its
     SHA-256 against what the release says, and unpack it next to the program folder as `Melomancer.new`.
  2. apply: copy a small private Python into the updates folder and start `app/swap.py` with it, then end this program.
     That helper (see swap.py) renames the folders, starts the new version and goes back to the old one if the new
     one does not answer.

Nothing is installed without a click, nothing outside the program folder and the updates folder is touched, and the
settings, the music and the database live elsewhere (%LOCALAPPDATA%\\Melomancer) and are not part of the swap.
"""
from __future__ import annotations

import errno
import hashlib
import logging
import os
import shutil
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from . import hostenv, lifecycle
from .config import Settings
from .swap import popen_detached
from .updates import REPO, FetchError, _tls_context, fetch_latest, parse_version

log = logging.getLogger("melomancer.selfupdate")

DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
ASSET_NAME = "Melomancer-win64-{version}.zip"
SPARE_BYTES = 300 * 1024 * 1024       # room to spare on the disk besides the files themselves
CHUNK = 256 * 1024
READ_TIMEOUT_SECONDS = 30
# What a package folder holds. The running installation also needs swap.py (it does the swap); the NEW package need not
# have it: the helper is always the one of the version being replaced, and older packages do not carry it.
PACKAGE_FILES = ("VERSION", "app/winmain.py", "runtime/python.exe", "runtime/pythonw.exe")
INSTALLED_FILES = PACKAGE_FILES + ("app/swap.py",)


class InstallError(Exception):
    """A short code for the panel (`upd_err_<code>` while installing, `err.<code>` for a refused request)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def package_root() -> Path | None:
    """The folder of the Windows package this program runs from, or None (a container, a development checkout)."""
    if not hostenv.IS_WINDOWS:
        return None
    home = Path(__file__).resolve().parents[1]
    return home if all((home / name).is_file() for name in INSTALLED_FILES) else None


def find_package(release: dict, version: str) -> dict | None:
    """The Windows package among the files of a release: {name, url, size, sha256}; None while it is not attached yet
    (the release is created first, the package follows a few minutes later) or when it does not look right."""
    wanted = ASSET_NAME.format(version=version)
    for asset in release.get("assets") or []:
        if not isinstance(asset, dict) or asset.get("name") != wanted:
            continue
        url = str(asset.get("browser_download_url") or "")
        if not url.startswith(DOWNLOAD_PREFIX) or asset.get("state") not in (None, "uploaded"):
            return None
        digest = str(asset.get("digest") or "")
        size = asset.get("size")
        return {"name": wanted, "url": url, "size": size if isinstance(size, int) and size > 0 else 0,
                "sha256": digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else ""}
    return None


def open_url(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "melomancer-updater"})
    return urllib.request.urlopen(request, timeout=READ_TIMEOUT_SECONDS, context=_tls_context())


def prepare_runner(root: Path, work_dir: Path) -> Path:
    """A private copy of the bundled Python (only the interpreter and its libraries, not the installed packages) and of
    swap.py, outside the program folder: the folder cannot be renamed while its own python.exe is running. Returns the
    path of the copied pythonw.exe."""
    runner = work_dir / "runner"
    shutil.rmtree(runner, ignore_errors=True)
    runner.mkdir(parents=True)
    source = root / "runtime"
    zip_name = ""
    for item in source.iterdir():
        if item.is_file() and item.suffix.lower() in (".exe", ".dll", ".pyd", ".zip"):
            shutil.copy2(item, runner / item.name)
            if item.suffix.lower() == ".zip" and item.name.lower().startswith("python"):
                zip_name = item.name
    for pth in source.glob("python*._pth"):
        # the embeddable Python reads this file instead of the environment: the standard library and this folder
        (runner / pth.name).write_text(f"{zip_name}\n.\n", encoding="utf-8")
    shutil.copy2(root / "app" / "swap.py", runner / "swap.py")
    return runner / "pythonw.exe"


class Installer:
    def __init__(self, root: Path | None, work_dir: Path, data_dir: Path | None, current: str, url: str,
                 log_path: Path | None = None, *, fetch: Callable = fetch_latest, opener: Callable = open_url,
                 spawn: Callable = popen_detached, quit_hook: Callable[[], bool] = lifecycle.request_quit) -> None:
        self.root, self.work_dir, self.data_dir = root, work_dir, data_dir
        self.current, self.url, self.log_path = current, url, log_path
        self._fetch, self._open, self._spawn, self._quit = fetch, opener, spawn, quit_hook
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._state, self._phase, self._version, self._error = "idle", None, None, None
        self._done = self._total = 0

    # ---- what the panel sees -------------------------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self.root is not None

    @property
    def new_dir(self) -> Path:
        assert self.root is not None
        return self.root.with_name(self.root.name + ".new")

    def status(self) -> dict:
        with self._lock:
            return {"available": self.available, "state": self._state, "phase": self._phase, "done": self._done,
                    "total": self._total, "version": self._version, "error": self._error}

    def _set(self, **values) -> None:
        with self._lock:
            for key, value in values.items():
                setattr(self, "_" + key, value)

    # ---- step 1: download and unpack ---------------------------------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self.root is None:
                raise InstallError("update_unavailable")
            if self._state in ("working", "applying"):
                raise InstallError("busy")
            self._state, self._phase, self._error, self._done, self._total = "working", "checking", None, 0, 0
        self._thread = threading.Thread(target=self._work, name="self-update", daemon=True)
        self._thread.start()

    def _work(self) -> None:
        try:
            self._download_and_unpack()
        except InstallError as exc:
            log.warning("The update could not be prepared: %s", exc.code)
            self._fail(exc.code)
        except Exception:  # noqa: BLE001
            log.exception("The update could not be prepared")
            self._fail("failed")

    def _fail(self, code: str) -> None:
        self._set(state="failed", error=code, phase=None)
        shutil.rmtree(self.new_dir, ignore_errors=True)
        for leftover in self.work_dir.glob("Melomancer-win64-*.zip*"):
            leftover.unlink(missing_ok=True)

    def _download_and_unpack(self) -> None:
        try:
            release, _ = self._fetch(self.current, None)   # fresh: the package may have been attached since the last look
        except FetchError as exc:
            raise InstallError(exc.code) from None
        version = parse_version(str(release.get("tag_name") or ""))
        current = parse_version(self.current)
        if version is None or current is None or version <= current:
            raise InstallError("no_update")
        text = ".".join(map(str, version))
        package = find_package(release, text)
        if package is None:
            raise InstallError("package_not_ready")
        self._set(version=text)
        archive = self._download(package)
        self._set(phase="unpacking", done=0, total=0)
        self._unpack(archive, text)
        archive.unlink(missing_ok=True)
        self._set(state="ready", phase=None)
        log.info("Version %s is unpacked and waits for the restart", text)

    def _download(self, package: dict) -> Path:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        for leftover in self.work_dir.glob("Melomancer-win64-*.zip*"):
            leftover.unlink(missing_ok=True)
        if package["size"] and shutil.disk_usage(self.work_dir).free < package["size"] * 1.1:
            raise InstallError("no_space")
        part, final = self.work_dir / (package["name"] + ".part"), self.work_dir / package["name"]
        digest, done = hashlib.sha256(), 0
        self._set(phase="downloading", done=0, total=package["size"])
        try:
            with self._open(package["url"]) as response, open(part, "wb") as out:
                if not package["size"]:
                    self._set(total=int(getattr(response, "headers", {}).get("Content-Length") or 0))
                while chunk := response.read(CHUNK):
                    out.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    self._set(done=done)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            raise InstallError("unreachable") from None
        except OSError as exc:
            raise InstallError("no_space" if exc.errno == errno.ENOSPC else "no_write_access") from None
        self._set(phase="verifying")
        if package["size"] and done != package["size"]:
            raise InstallError("bad_package")
        if package["sha256"] and digest.hexdigest() != package["sha256"]:
            raise InstallError("checksum")
        os.replace(part, final)
        return final

    def _unpack(self, archive: Path, version: str) -> None:
        target = self.new_dir
        shutil.rmtree(target, ignore_errors=True)
        try:
            with zipfile.ZipFile(archive) as package:
                files = [(info, _inside(info.filename)) for info in package.infolist() if not info.is_dir()]
                if not files or any(name is None for _, name in files):
                    raise InstallError("bad_package")
                total = sum(info.file_size for info, _ in files)
                if shutil.disk_usage(target.parent).free < total + SPARE_BYTES:
                    raise InstallError("no_space")
                try:
                    target.mkdir()
                except OSError:
                    raise InstallError("no_write_access") from None
                self._set(total=total)
                done = 0
                for info, name in files:
                    destination = target / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(info) as source, open(destination, "wb") as out:
                        while chunk := source.read(CHUNK):
                            out.write(chunk)
                            done += len(chunk)
                            self._set(done=done)
        except zipfile.BadZipFile:
            raise InstallError("bad_package") from None
        except OSError as exc:
            raise InstallError("no_space" if exc.errno == errno.ENOSPC else "no_write_access") from None
        if any(not (target / name).is_file() for name in PACKAGE_FILES):
            raise InstallError("bad_package")
        if (target / "VERSION").read_text(encoding="utf-8").strip() != version:
            raise InstallError("bad_package")

    # ---- step 2: apply -------------------------------------------------------------------------------------------------

    def apply(self) -> None:
        """Starts the helper that swaps the folders and ends this program. The helper waits for this one to end."""
        with self._lock:
            if self._state != "ready" or self.root is None:
                raise InstallError("not_ready")
            self._state = "applying"
            version = self._version
        try:
            python = prepare_runner(self.root, self.work_dir)
            args = [str(python), str(python.with_name("swap.py")), "--root", str(self.root), "--new", str(self.new_dir),
                    "--pid", str(os.getpid()), "--url", self.url, "--version", str(version), "--old-version", self.current]
            if self.data_dir:
                args += ["--data", str(self.data_dir)]
            if self.log_path:
                args += ["--log", str(self.log_path)]
            self._spawn(args, python.parent, lifecycle.original_env())
        except (OSError, shutil.Error):
            log.exception("The update helper could not be started")
            self._set(state="ready")   # nothing was changed: the person may try again
            raise InstallError("failed") from None
        log.info("The update helper is running, closing for the swap")
        threading.Timer(1.0, self._quit).start()   # after the answer to the request has gone out


def _inside(name: str) -> str | None:
    """The path of a file of the package without its top folder ("Melomancer/app/x.py" -> "app/x.py"), or None when the
    name could lead outside the folder it is unpacked into."""
    parts = name.replace("\\", "/").split("/")
    if len(parts) < 2 or parts[0] != "Melomancer" or any(p in ("", ".", "..") or ":" in p for p in parts):
        return None
    return "/".join(parts[1:])


def create(settings: Settings) -> Installer:
    """The installer of this program: available only for a Windows package started by its launcher."""
    if not settings.config_file:
        return Installer(None, Path("."), None, settings.version, "")
    config = Path(settings.config_file)
    return Installer(package_root(), config.parent / "updates", settings.data_dir, settings.version,
                     os.environ.get("MELOMANCER_URL", "http://127.0.0.1:8080/"), config.parent / "logs" / "update.log")
