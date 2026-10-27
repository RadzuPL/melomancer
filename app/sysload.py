"""CPU and memory use of the container, read from its cgroup, so that the panel can show it.

Docker's own numbers come from the same files. CPU is given in percent of one core (as `docker stats` does, so 100 %
is one full core and a busy two-core container can show 200 %). Outside a container, or when the cgroup files are not
readable, the process's own CPU time and memory are used instead: that leaves out child processes such as ffmpeg.
"""
from __future__ import annotations

import logging
import os
import resource
import threading
import time
from collections import deque
from pathlib import Path

log = logging.getLogger("melomancer.sysload")

INTERVAL_SECONDS = 2.0
WINDOW_SECONDS = 600       # how far back the peak looks
AVERAGE_SECONDS = 60


def _read(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def _stat_value(text: str | None, key: str) -> int | None:
    for line in (text or "").splitlines():
        name, _, value = line.partition(" ")
        if name == key and value.strip().isdigit():
            return int(value)
    return None


class _Source:
    """Where the numbers come from: 'cgroup2', 'cgroup1' or 'process'."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.kind = "process"
        if _stat_value(_read(root / "cpu.stat"), "usage_usec") is not None:
            self.kind = "cgroup2"
        elif any((root / sub / "cpuacct.usage").is_file() for sub in ("cpuacct", "cpu,cpuacct", "cpu/cpuacct")):
            self.kind = "cgroup1"

    def cpu_seconds(self) -> float:
        if self.kind == "cgroup2":
            return (_stat_value(_read(self.root / "cpu.stat"), "usage_usec") or 0) / 1e6
        if self.kind == "cgroup1":
            for sub in ("cpuacct", "cpu,cpuacct", "cpu/cpuacct"):
                text = _read(self.root / sub / "cpuacct.usage")
                if text and text.strip().isdigit():
                    return int(text) / 1e9
        own, kids = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        return own.ru_utime + own.ru_stime + kids.ru_utime + kids.ru_stime

    def memory_bytes(self) -> int:
        """Memory in use without the page cache that Linux can drop at any time (what `docker stats` shows)."""
        if self.kind == "cgroup2":
            text = _read(self.root / "memory.current")
            used = int(text) if text and text.strip().isdigit() else None
            if used is not None:
                return max(0, used - (_stat_value(_read(self.root / "memory.stat"), "inactive_file") or 0))
        if self.kind == "cgroup1":
            text = _read(self.root / "memory" / "memory.usage_in_bytes")
            if text and text.strip().isdigit():
                cache = _stat_value(_read(self.root / "memory" / "memory.stat"), "total_inactive_file") or 0
                return max(0, int(text) - cache)
        for line in (_read(Path("/proc/self/status")) or "").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
        return 0


class LoadMonitor:
    """Samples the CPU every couple of seconds and remembers the last ten minutes."""

    def __init__(self, root: Path = Path("/sys/fs/cgroup"), interval: float = INTERVAL_SECONDS) -> None:
        self._source = _Source(root)
        self._interval = interval
        self._samples: deque[tuple[float, float]] = deque()  # (monotonic time, percent of one core)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last = (time.monotonic(), self._source.cpu_seconds())

    def sample(self) -> None:
        now, cpu = time.monotonic(), self._source.cpu_seconds()
        then, before = self._last
        self._last = (now, cpu)
        if now - then <= 0:
            return
        percent = max(0.0, (cpu - before) / (now - then) * 100)
        with self._lock:
            self._samples.append((now, percent))
            while self._samples and now - self._samples[0][0] > WINDOW_SECONDS:
                self._samples.popleft()

    def snapshot(self) -> dict:
        now = time.monotonic()
        with self._lock:
            samples = list(self._samples)
        recent = [p for t, p in samples if now - t <= AVERAGE_SECONDS]
        return {
            "source": self._source.kind,
            "cpu": round(samples[-1][1], 1) if samples else None,
            "cpu_average": round(sum(recent) / len(recent), 1) if recent else None,
            "cpu_peak": round(max(p for _, p in samples), 1) if samples else None,
            "memory_mb": round(self._source.memory_bytes() / 1048576),
            "cores": os.cpu_count(),
        }

    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._run, name="sysload", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self.sample()
            except Exception:  # noqa: BLE001
                log.debug("Sampling the load failed", exc_info=True)
