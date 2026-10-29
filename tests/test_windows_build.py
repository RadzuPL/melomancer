"""The pure parts of scripts/windows/build_package.py (the rest needs Windows and the network)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "build_package.py"
build_package = None
if SCRIPT.is_file():   # the Linux test image carries the tests and the app, not the scripts; the Windows job has both
    spec = importlib.util.spec_from_file_location("build_package", SCRIPT)
    build_package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_package)


def test_the_newest_release_branch_build_of_ffmpeg_is_chosen_over_master():
    if build_package is None:
        return
    names = ["ffmpeg-master-latest-win64-gpl.zip", "ffmpeg-master-latest-win64-lgpl-shared.zip",
             "ffmpeg-n7.1-latest-win64-lgpl-shared-7.1.zip", "ffmpeg-n8.0-latest-win64-lgpl-shared-8.0.zip",
             "ffmpeg-n8.0-latest-win64-lgpl-8.0.zip", "ffmpeg-n10.1-latest-win64-lgpl-shared-10.1.zip",
             "ffmpeg-n9.0-latest-win64-gpl-shared-9.0.zip"]
    assert build_package.pick_ffmpeg_asset(names) == "ffmpeg-n10.1-latest-win64-lgpl-shared-10.1.zip"  # LGPL, shared, 10 > 8
    assert build_package.pick_ffmpeg_asset(["unrelated.zip"]) == build_package.FFMPEG_FALLBACK
    assert build_package.pick_ffmpeg_asset([]) == build_package.FFMPEG_FALLBACK


def test_the_embeddable_python_reads_its_search_path_from_the_pth_file():
    if build_package is None:
        return
    lines = build_package.pth_text(3, 12).splitlines()
    assert lines[0] == "python312.zip" and ".." in lines          # ".." is the folder that holds the app package
    assert "Lib\\site-packages" in lines and lines[-1] == "import site"
