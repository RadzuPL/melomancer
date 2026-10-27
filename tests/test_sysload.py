"""Container load from cgroup files: both cgroup generations and the fallback."""
from __future__ import annotations

import time

from app.sysload import LoadMonitor

from .conftest import login, make_user


def test_cgroup_v2_cpu_and_memory_without_the_droppable_cache(tmp_path):
    (tmp_path / "cpu.stat").write_text("usage_usec 10000000\nuser_usec 6000000\n")
    (tmp_path / "memory.current").write_text(str(300 * 1048576))
    (tmp_path / "memory.stat").write_text("anon 1\ninactive_file " + str(100 * 1048576) + "\n")
    monitor = LoadMonitor(tmp_path)
    assert monitor._source.kind == "cgroup2"
    monitor._last = (time.monotonic() - 2.0, 10.0)           # 10 s of CPU used two seconds ago ...
    (tmp_path / "cpu.stat").write_text("usage_usec 11000000\n")  # ... and one more second since: half a core
    monitor.sample()
    snap = monitor.snapshot()
    assert 45 <= snap["cpu"] <= 55 and snap["cpu_peak"] == snap["cpu"] and snap["memory_mb"] == 200
    assert snap["source"] == "cgroup2"


def test_cgroup_v1_layout(tmp_path):
    (tmp_path / "cpuacct").mkdir()
    (tmp_path / "cpuacct" / "cpuacct.usage").write_text("5000000000")
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "memory.usage_in_bytes").write_text(str(250 * 1048576))
    (tmp_path / "memory" / "memory.stat").write_text("total_inactive_file " + str(50 * 1048576) + "\n")
    monitor = LoadMonitor(tmp_path)
    assert monitor._source.kind == "cgroup1"
    monitor._last = (time.monotonic() - 4.0, 5.0)
    (tmp_path / "cpuacct" / "cpuacct.usage").write_text("9000000000")  # 4 s of CPU in 4 s: one full core
    monitor.sample()
    snap = monitor.snapshot()
    assert 95 <= snap["cpu"] <= 105 and snap["memory_mb"] == 200


def test_without_cgroup_files_the_process_itself_is_measured(tmp_path):
    monitor = LoadMonitor(tmp_path)
    assert monitor._source.kind == "process"
    assert monitor.snapshot()["cpu"] is None            # nothing sampled yet
    assert monitor.snapshot()["memory_mb"] > 0
    monitor.sample()
    assert monitor.snapshot()["cpu"] >= 0


def test_the_load_endpoint_is_for_administrators(env):
    make_user(env, "bob")
    login(env, "bob")
    assert env.client.get("/api/system/load").status_code == 403
    login(env, "admin")
    data = env.client.get("/api/system/load").json()
    assert {"source", "cpu", "cpu_average", "cpu_peak", "memory_mb", "cores"} <= set(data)
