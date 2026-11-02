"""The last step of an update on Windows: swap the program folder for the new one, with a way back.

This file runs in a process of its own, started by the program that is being replaced and run by a private copy of the
Python runtime (see selfupdate.prepare_runner), because nothing inside the folder can be renamed while it is in use.
It therefore uses only the standard library and knows nothing about the rest of the application.

    1. wait until the old program has ended
    2. copy the database aside (a new version may change its layout)
    3. rename   Melomancer  ->  Melomancer.old
    4. rename   Melomancer.new  ->  Melomancer
    5. start the new version and wait until it answers with the expected version
    6. success: delete Melomancer.old.  failure: put the old folder back and start it again.

Renaming a folder is the one step that is all or nothing, so at any moment the person has a complete, working folder
under the name `Melomancer`: the old one until step 4, the new one after it.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DETACHED = 0
if sys.platform == "win32":
    DETACHED = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW

KEPT_BACKUPS = 2


def popen_detached(args: list[str], cwd: Path, env: dict[str, str] | None = None):
    """Starts a program that goes on when this one ends: no console, its own process group, and outside the job the
    caller may be in (a job that kills its children when it closes would take the new program with it)."""
    flags = DETACHED
    if sys.platform == "win32":
        flags |= getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    options = dict(cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    try:
        return subprocess.Popen(args, creationflags=flags, **options)
    except OSError:
        if sys.platform == "win32" and flags != DETACHED:   # a job that does not allow breaking away
            return subprocess.Popen(args, creationflags=DETACHED, **options)
        raise


@dataclass
class Job:
    root: Path            # the program folder that is running now, and the name the new one takes over
    new: Path             # the unpacked new version, next to `root`
    pid: int              # the running program, to wait for
    url: str              # where the program answers (http://127.0.0.1:8080/)
    version: str          # the version that must answer after the swap
    old_version: str
    data_dir: Path | None = None
    log: Path | None = None
    wait_seconds: float = 90.0
    rename_tries: int = 60
    health_seconds: float = 120.0


class Ops:
    """Everything that touches the system, in one place so that a test can replace it."""

    def __init__(self, log_path: Path | None) -> None:
        self.log_path = log_path

    def log(self, message: str) -> None:
        line = time.strftime("%Y-%m-%d %H:%M:%S") + " update: " + message
        if self.log_path:
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except OSError:
                pass
        if sys.stdout is not None:
            print(line, flush=True)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def wait_exit(self, pid: int, seconds: float) -> bool:
        """True when the process is gone (or never existed)."""
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x00100000, False, pid)   # SYNCHRONIZE
            if not handle:
                return True
            try:
                return kernel32.WaitForSingleObject(handle, int(seconds * 1000)) == 0
            finally:
                kernel32.CloseHandle(handle)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return True
            time.sleep(0.2)
        return False

    def start(self, root: Path):
        python = root / "runtime" / ("pythonw.exe" if sys.platform == "win32" else "python3")
        return popen_detached([str(python), "-m", "app.winmain"], root)

    def healthy(self, url: str, version: str) -> bool:
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/api/health", timeout=3) as response:
                return json.loads(response.read(4096)).get("version") == version
        except (OSError, ValueError):
            return False

    def kill(self, process) -> None:
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=30,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                process.kill()
        except (OSError, subprocess.SubprocessError):
            pass

    def notify(self, title: str, text: str) -> None:
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
                return
            except (AttributeError, OSError):
                pass
        print(f"{title}: {text}", file=sys.stderr)


def free_name(base: Path) -> Path:
    """`base` itself when nothing is there, else base-2, base-3 ... (a leftover folder that could not be deleted)."""
    candidate, number = base, 1
    while candidate.exists():
        number += 1
        candidate = base.with_name(f"{base.name}-{number}")
    return candidate


def rename_with_retries(source: Path, target: Path, tries: int, ops: Ops) -> bool:
    """Folders are briefly held by a program that is still closing, a virus scanner or an open Explorer window."""
    for attempt in range(tries):
        try:
            os.rename(source, target)
            return True
        except OSError as exc:
            if attempt == 0:
                ops.log(f"{source.name} is in use ({exc}), trying again")
            ops.sleep(0.5)
    return False


def backup_database(data_dir: Path | None, old_version: str, ops: Ops) -> None:
    """A copy of the database next to it, because a newer version may change its layout and an older one cannot read that."""
    if not data_dir or not (data_dir / "melomancer.db").is_file():
        return
    target = data_dir / "backups"
    try:
        target.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for suffix in ("", "-wal", "-shm"):
            source = data_dir / f"melomancer.db{suffix}"
            if source.is_file():
                shutil.copy2(source, target / f"melomancer-{old_version}-{stamp}.db{suffix}")
        copies = sorted({p.name.split(".db")[0] for p in target.glob("melomancer-*.db")})
        for stale in copies[:-KEPT_BACKUPS]:
            for leftover in target.glob(stale + ".db*"):
                leftover.unlink(missing_ok=True)
        ops.log(f"database copied to {target}")
    except OSError as exc:
        ops.log(f"the database copy failed ({exc}); going on without it")


def run_swap(job: Job, ops: Ops) -> int:
    """Returns 0 when the new version runs, otherwise a code that says where it stopped (1 and up). In every failure the
    old folder is back under its name and running."""
    root, new = job.root, job.new
    ops.log(f"updating {root} from {job.old_version} to {job.version}")
    if not ops.wait_exit(job.pid, job.wait_seconds):
        ops.log("the running program did not close in time; nothing was changed")
        ops.notify("Melomancer", "Melomancer nie zamknął się na czas, więc aktualizacja się nie odbyła. Nic nie zostało "
                   "zmienione. / Melomancer did not close in time, so the update did not happen. Nothing was changed.")
        return 2
    backup_database(job.data_dir, job.old_version, ops)

    for leftover in root.parent.glob(root.name + ".old*"):   # an earlier update that could not delete its old folder
        shutil.rmtree(leftover, ignore_errors=True)
    old = free_name(root.with_name(root.name + ".old"))
    if not rename_with_retries(root, old, job.rename_tries, ops):
        ops.log("the program folder could not be renamed; the old version stays")
        ops.start(root)
        ops.notify("Melomancer", "Nie udało się podmienić folderu programu (może jest otwarty w Eksploratorze albo "
                   "skanuje go antywirus). Zostaje poprzednia wersja. / The program folder could not be replaced (an "
                   "Explorer window or a virus scanner may hold it). The old version stays.")
        return 3
    try:
        os.rename(new, root)
    except OSError as exc:
        ops.log(f"the new folder could not take its place ({exc}); putting the old one back")
        os.rename(old, root)
        ops.start(root)
        ops.notify("Melomancer", "Aktualizacja się nie udała, wróciła poprzednia wersja. / The update failed, the old "
                   "version is back.")
        return 4

    process = ops.start(root)
    deadline = time.monotonic() + job.health_seconds
    while time.monotonic() < deadline:
        if ops.healthy(job.url, job.version):
            ops.log(f"the new version {job.version} answers")
            shutil.rmtree(old, ignore_errors=True)
            return 0
        if process.poll() is not None:
            break   # it already ended: no point in waiting
        ops.sleep(1.0)
    ops.log("the new version did not answer; going back to the old one")
    ops.kill(process)
    failed = free_name(root.with_name(root.name + ".failed"))
    ops.sleep(1.0)
    if rename_with_retries(root, failed, job.rename_tries, ops) and rename_with_retries(old, root, job.rename_tries, ops):
        shutil.rmtree(failed, ignore_errors=True)
        ops.start(root)
        ops.notify("Melomancer", "Nowa wersja nie wystartowała, wróciłem do poprzedniej. Szczegóły są w pliku update.log "
                   "w folderze z logami. / The new version did not start, the old one is back. Details are in update.log "
                   "in the logs folder.")
        return 5
    ops.log(f"could not go back automatically; the old version is in {old}")
    ops.notify("Melomancer", f"Aktualizacja się nie powiodła, a automatyczny powrót też. Poprzednia wersja jest w folderze {old}. "
               f"/ The update failed and so did the automatic way back. The old version is in {old}.")
    return 6


def parse(argv: list[str]) -> Job:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--old-version", default="")
    parser.add_argument("--data")
    parser.add_argument("--log")
    args = parser.parse_args(argv)
    return Job(root=Path(args.root), new=Path(args.new), pid=args.pid, url=args.url, version=args.version,
               old_version=args.old_version, data_dir=Path(args.data) if args.data else None,
               log=Path(args.log) if args.log else None)


def main(argv: list[str] | None = None) -> int:
    job = parse(sys.argv[1:] if argv is None else argv)
    return run_swap(job, Ops(job.log))


if __name__ == "__main__":
    sys.exit(main())
