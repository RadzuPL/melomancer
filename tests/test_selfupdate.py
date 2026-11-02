"""Installing an update in the Windows package: the download and unpacking, and the swap of the folders.

Nothing here needs Windows or the network: the release, the download and the processes are made up, the folders are real.
"""
from __future__ import annotations

import hashlib
import io
import json
import threading
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import selfupdate, swap
from app.selfupdate import InstallError, Installer, find_package
from app.updates import FetchError

URL = "https://github.com/RadzuPL/melomancer/releases/download/v0.8.0/Melomancer-win64-0.8.0.zip"


def package_zip(version: str = "0.8.0", extra: dict | None = None, skip: tuple = ()) -> bytes:
    files = {"VERSION": version, "app/winmain.py": "print('new')", "app/swap.py": "# swap", "runtime/python.exe": "py",
             "runtime/pythonw.exe": "pyw", "bin/ffmpeg.exe": "x" * 5000}
    files.update(extra or {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            if name not in skip:
                archive.writestr("Melomancer/" + name, content)
    return buffer.getvalue()


def release(data: bytes | None, tag: str = "v0.8.0", url: str = URL, state: str = "uploaded", digest: str | None = "auto"):
    assets = []
    if data is not None:
        asset = {"name": f"Melomancer-win64-{tag[1:]}.zip", "browser_download_url": url, "size": len(data), "state": state}
        if digest == "auto":
            asset["digest"] = "sha256:" + hashlib.sha256(data).hexdigest()
        elif digest:
            asset["digest"] = digest
        assets.append(asset)
    return {"tag_name": tag, "assets": assets}


def make_root(tmp_path: Path, version: str = "0.7.0") -> Path:
    root = tmp_path / "apps" / "Melomancer"
    for name, content in {"VERSION": version, "app/winmain.py": "print('old')", "app/swap.py": Path(swap.__file__).read_text(),
                          "runtime/python.exe": "py", "runtime/pythonw.exe": "pyw", "runtime/python312.dll": "dll",
                          "runtime/python312.zip": "stdlib", "runtime/python312._pth": "python312.zip\n..\nLib\\site-packages\n",
                          "runtime/Lib/site-packages/big.py": "x", "bin/ffmpeg.exe": "ff"}.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def installer(tmp_path: Path, data: bytes | None, *, rel: dict | None = None, cut: bool = False, spawned: list | None = None,
              quit_event: threading.Event | None = None, current: str = "0.7.0", error: str | None = None) -> Installer:
    root = make_root(tmp_path, current)

    def fetch(_current, _etag):
        if error:
            raise FetchError(error)
        return (rel if rel is not None else release(data)), None

    def opener(_url):
        body = data[: len(data) // 2] if cut else data
        return io.BytesIO(body)

    def quit_hook():
        if quit_event:
            quit_event.set()
        return True

    return Installer(root, tmp_path / "updates", tmp_path / "data", current, "http://127.0.0.1:8080/", tmp_path / "update.log",
                     fetch=fetch, opener=opener, spawn=lambda args, cwd, env=None: spawned.append((args, cwd, env)) if spawned is not None else None,
                     quit_hook=quit_hook)


def run(inst: Installer) -> dict:
    inst.start()
    inst._thread.join(20)
    return inst.status()


# ---- the release ------------------------------------------------------------------------------------------------

def test_the_windows_package_is_found_among_the_files_of_the_release():
    data = package_zip()
    found = find_package(release(data), "0.8.0")
    assert found["url"] == URL and found["size"] == len(data) and found["sha256"] == hashlib.sha256(data).hexdigest()
    assert find_package(release(None), "0.8.0") is None                                  # not attached yet
    assert find_package(release(data, state="starter"), "0.8.0") is None                  # still uploading
    assert find_package(release(data, url="https://evil.example/Melomancer-win64-0.8.0.zip"), "0.8.0") is None
    assert find_package(release(data, tag="v0.9.0"), "0.8.0") is None                    # a package of another version
    assert find_package(release(data, digest=None), "0.8.0")["sha256"] == ""             # an older release without a digest


@pytest.mark.parametrize("name", ["Other/app.py", "app.py", "Melomancer/../x", "Melomancer//x", "/Melomancer/x",
                                  "Melomancer/C:/x", "Melomancer\\..\\x"])
def test_names_that_could_leave_the_folder_are_refused(name):
    assert selfupdate._inside(name) is None


def test_the_top_folder_of_the_package_is_dropped():
    assert selfupdate._inside("Melomancer/app/x.py") == "app/x.py"
    assert selfupdate._inside("Melomancer\\app\\x.py") == "app/x.py"


# ---- step 1: download and unpack -------------------------------------------------------------------------------------

def test_the_new_version_is_downloaded_checked_and_unpacked_next_to_the_program(tmp_path):
    data = package_zip()
    inst = installer(tmp_path, data)
    status = run(inst)
    assert status["state"] == "ready" and status["version"] == "0.8.0" and status["error"] is None
    new = inst.root.with_name("Melomancer.new")
    assert (new / "VERSION").read_text() == "0.8.0" and (new / "bin" / "ffmpeg.exe").stat().st_size == 5000
    assert not list((tmp_path / "updates").glob("*.zip*")), "the downloaded file is removed once it is unpacked"
    assert (inst.root / "VERSION").read_text() == "0.7.0", "the running version is untouched"


@pytest.mark.parametrize("make, code", [
    (lambda: dict(data=package_zip(), digest="sha256:" + "0" * 64), "checksum"),
    (lambda: dict(data=package_zip(), cut=True), "bad_package"),            # the connection was cut: size is short
    (lambda: dict(data=package_zip("0.9.9")), "bad_package"),               # a package that says another version
    (lambda: dict(data=package_zip(skip=("app/winmain.py",))), "bad_package"),
    (lambda: dict(data=package_zip(extra={"../evil.txt": "x"})), "bad_package"),
    (lambda: dict(data=None), "package_not_ready"),
    (lambda: dict(data=package_zip(), current="0.8.0"), "no_update"),
    (lambda: dict(data=package_zip(), error="unreachable"), "unreachable"),
    (lambda: dict(data=package_zip(), error="rate_limited"), "rate_limited"),
])
def test_a_package_that_cannot_be_trusted_is_dropped_and_nothing_is_left_behind(tmp_path, make, code):
    options = make()
    digest = options.pop("digest", "auto")
    data = options["data"]
    rel = release(data, digest=digest) if data is not None else release(None)
    inst = installer(tmp_path, data, rel=rel, **{k: v for k, v in options.items() if k != "data"})
    status = run(inst)
    assert status["state"] == "failed" and status["error"] == code, status
    assert not inst.root.with_name("Melomancer.new").exists()
    assert not list((tmp_path / "updates").glob("*.zip*"))
    assert (inst.root / "VERSION").read_text() == inst.current


def test_a_second_start_while_one_runs_is_refused_and_a_failed_one_may_be_repeated(tmp_path):
    gate = threading.Event()
    data = package_zip()
    inst = installer(tmp_path, data)

    class Slow(io.BytesIO):
        def read(self, size=-1):
            gate.wait(5)
            return super().read(size)

    inst._open = lambda _url: Slow(data)
    inst.start()
    with pytest.raises(InstallError) as caught:
        inst.start()
    assert caught.value.code == "busy"
    gate.set()
    inst._thread.join(20)
    assert inst.status()["state"] == "ready"


def test_progress_is_reported_while_downloading(tmp_path):
    seen = []
    data = package_zip(extra={"big.bin": "y" * 700_000})
    inst = installer(tmp_path, data)

    class Watching(io.BytesIO):
        def read(self, size=-1):
            seen.append(inst.status())
            return super().read(size)

    inst._open = lambda _url: Watching(data)
    run(inst)
    downloading = [s for s in seen if s["phase"] == "downloading"]
    assert downloading and downloading[0]["total"] == len(data) and downloading[-1]["done"] > downloading[0]["done"]


def test_not_enough_room_is_reported_before_anything_is_written(tmp_path, monkeypatch):
    monkeypatch.setattr(selfupdate.shutil, "disk_usage", lambda path: SimpleNamespace(total=10, used=10, free=1000))
    inst = installer(tmp_path, package_zip())
    status = run(inst)
    assert status["state"] == "failed" and status["error"] == "no_space"
    assert not inst.root.with_name("Melomancer.new").exists()


def test_an_installer_without_a_package_folder_is_not_available(tmp_path):
    inst = Installer(None, tmp_path, None, "0.7.0", "")
    assert inst.available is False and inst.status()["available"] is False
    with pytest.raises(InstallError) as caught:
        inst.start()
    assert caught.value.code == "update_unavailable"


# ---- step 2: apply -------------------------------------------------------------------------------------------------------

def test_apply_starts_the_helper_from_a_private_copy_of_python_and_then_ends_the_program(tmp_path):
    spawned, ended = [], threading.Event()
    inst = installer(tmp_path, package_zip(), spawned=spawned, quit_event=ended)
    with pytest.raises(InstallError) as caught:
        inst.apply()
    assert caught.value.code == "not_ready" and not spawned
    run(inst)
    inst.apply()
    assert ended.wait(5), "the program is asked to end"
    (args, cwd, env), = spawned
    runner = tmp_path / "updates" / "runner"
    assert args[0] == str(runner / "pythonw.exe") and Path(args[1]) == runner / "swap.py" and cwd == runner
    assert all(f"{flag}" in args for flag in ("--root", "--new", "--pid", "--url", "--version", "--old-version", "--data", "--log"))
    assert args[args.index("--version") + 1] == "0.8.0" and args[args.index("--root") + 1] == str(inst.root)
    assert {p.name for p in runner.iterdir()} == {"python.exe", "pythonw.exe", "python312.dll", "python312.zip", "python312._pth", "swap.py"}
    assert (runner / "python312._pth").read_text() == "python312.zip\n.\n", "the copy reads its standard library, not the program folder"
    assert (runner / "swap.py").read_text() == (inst.root / "app" / "swap.py").read_text()
    assert inst.status()["state"] == "applying"


def test_the_new_version_is_started_with_the_environment_the_program_had_before_the_launcher_changed_it(tmp_path):
    from app import lifecycle
    lifecycle.set_original_env({"PATH": "C:\\Windows", "ADMIN_PASSWORD": "kept"})
    try:
        spawned = []
        inst = installer(tmp_path, package_zip(), spawned=spawned, quit_event=threading.Event())
        run(inst)
        inst.apply()
        (_, _, env), = spawned
        assert env == {"PATH": "C:\\Windows", "ADMIN_PASSWORD": "kept"}, "no APP_VERSION, DISCORD_TOKEN or MELOMANCER_* of the old run"
    finally:
        lifecycle._original_env = None


def test_a_helper_that_cannot_start_leaves_everything_as_it_was(tmp_path):
    inst = installer(tmp_path, package_zip())
    inst._spawn = lambda args, cwd, env=None: (_ for _ in ()).throw(OSError("blocked"))
    run(inst)
    with pytest.raises(InstallError) as caught:
        inst.apply()
    assert caught.value.code == "failed" and inst.status()["state"] == "ready"
    assert inst.root.with_name("Melomancer.new").is_dir() and (inst.root / "VERSION").read_text() == "0.7.0"


# ---- the swap --------------------------------------------------------------------------------------------------------------

class FakeProcess:
    pid = 4242

    def __init__(self, alive: bool = True) -> None:
        self.alive, self.killed = alive, False

    def poll(self):
        return None if self.alive else 1


class FakeOps(swap.Ops):
    def __init__(self, healthy=True, exits=True, new_dies=False) -> None:
        super().__init__(None)
        self._healthy, self._exits, self._new_dies = healthy, exits, new_dies
        self.started: list[str] = []
        self.messages: list[str] = []
        self.logged: list[str] = []
        self.killed = 0

    def log(self, message): self.logged.append(message)
    def sleep(self, seconds): time.sleep(0.001)
    def wait_exit(self, pid, seconds): return self._exits
    def start(self, root):
        self.started.append((root / "VERSION").read_text())
        return FakeProcess(alive=not (self._new_dies and len(self.started) == 1))
    def healthy(self, url, version): return self._healthy and self.started and self.started[-1] == version
    def kill(self, process): self.killed += 1
    def notify(self, title, text): self.messages.append(text)


def swap_job(tmp_path: Path, **overrides) -> swap.Job:
    root = tmp_path / "apps" / "Melomancer"
    new = tmp_path / "apps" / "Melomancer.new"
    for folder, version in ((root, "0.7.0"), (new, "0.8.0")):
        (folder / "app").mkdir(parents=True)
        (folder / "VERSION").write_text(version)
        (folder / "app" / "winmain.py").write_text(version)
    data = tmp_path / "data"
    data.mkdir()
    (data / "melomancer.db").write_text("database 0.7.0")
    options = dict(root=root, new=new, pid=4242, url="http://127.0.0.1:8080/", version="0.8.0", old_version="0.7.0",
                   data_dir=data, wait_seconds=1, rename_tries=3, health_seconds=0.3)
    options.update(overrides)
    return swap.Job(**options)


def test_the_new_folder_takes_the_place_of_the_old_one_and_the_old_one_is_deleted(tmp_path):
    job, ops = swap_job(tmp_path), FakeOps()
    assert swap.run_swap(job, ops) == 0
    assert (job.root / "VERSION").read_text() == "0.8.0" and not job.new.exists()
    assert not list(job.root.parent.glob("Melomancer.old*")) and ops.started == ["0.8.0"] and not ops.messages
    backups = list((job.data_dir / "backups").glob("melomancer-0.7.0-*.db"))
    assert len(backups) == 1 and backups[0].read_text() == "database 0.7.0", "the database was copied before the swap"


def test_if_the_old_program_does_not_close_nothing_is_changed(tmp_path):
    job, ops = swap_job(tmp_path), FakeOps(exits=False)
    assert swap.run_swap(job, ops) == 2
    assert (job.root / "VERSION").read_text() == "0.7.0" and job.new.is_dir() and not ops.started and ops.messages


def test_a_folder_that_stays_in_use_keeps_the_old_version_running(tmp_path, monkeypatch):
    job, ops = swap_job(tmp_path), FakeOps()
    real = swap.os.rename

    def locked(source, target):
        if Path(source) == job.root:
            raise PermissionError("in use")
        return real(source, target)

    monkeypatch.setattr(swap.os, "rename", locked)
    assert swap.run_swap(job, ops) == 3
    assert (job.root / "VERSION").read_text() == "0.7.0" and ops.started == ["0.7.0"] and ops.messages


def test_a_new_version_that_does_not_answer_is_replaced_by_the_old_one_again(tmp_path):
    job, ops = swap_job(tmp_path), FakeOps(healthy=False)
    assert swap.run_swap(job, ops) == 5
    assert (job.root / "VERSION").read_text() == "0.7.0", "the old folder is back under its name"
    assert ops.started == ["0.8.0", "0.7.0"] and ops.killed == 1 and ops.messages
    assert not list(job.root.parent.glob("Melomancer.failed*")) and not list(job.root.parent.glob("Melomancer.old*"))


def test_a_new_version_that_ends_at_once_does_not_make_anyone_wait_for_the_whole_time(tmp_path):
    job, ops = swap_job(tmp_path, health_seconds=60), FakeOps(healthy=False, new_dies=True)
    started = time.monotonic()
    assert swap.run_swap(job, ops) == 5
    assert time.monotonic() - started < 5 and (job.root / "VERSION").read_text() == "0.7.0"


def test_a_leftover_old_folder_of_an_earlier_update_is_cleared_first(tmp_path):
    job, ops = swap_job(tmp_path), FakeOps()
    leftover = job.root.with_name("Melomancer.old")
    (leftover / "app").mkdir(parents=True)
    (leftover / "app" / "x").write_text("x")
    assert swap.run_swap(job, ops) == 0 and not leftover.exists()


def test_only_the_latest_database_copies_are_kept(tmp_path):
    job = swap_job(tmp_path)
    backups = job.data_dir / "backups"
    backups.mkdir()
    for stamp in ("20260101-000001", "20260101-000002", "20260101-000003"):
        (backups / f"melomancer-0.6.0-{stamp}.db").write_text(stamp)
    swap.run_swap(job, FakeOps())
    names = sorted(p.name for p in backups.glob("*.db"))
    assert len(names) == 2 and names[0].endswith("000003.db"), names


def test_the_helper_reads_its_arguments(tmp_path):
    job = swap.parse(["--root", "R", "--new", "N", "--pid", "7", "--url", "http://x/", "--version", "1.2.3",
                      "--old-version", "1.2.2", "--data", "D", "--log", "L"])
    assert (job.root, job.new, job.pid, job.version, job.old_version, job.data_dir, job.log) == (
        Path("R"), Path("N"), 7, "1.2.3", "1.2.2", Path("D"), Path("L"))
