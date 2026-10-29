"""scripts/windows/release_link.py: where the Windows package link goes in the text of a release."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "release_link.py"
release_link = None
if SCRIPT.is_file():   # the Linux test image carries the tests and the app, not the scripts
    spec = importlib.util.spec_from_file_location("release_link", SCRIPT)
    release_link = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release_link)

URL = "https://github.com/RadzuPL/melomancer/releases/download/v1.0.0/Melomancer-win64-1.0.0.zip"
NOTES = ("## What's new\n\nText.\n\n## Get it\n\n- **Container image:** `docker pull x:1.0.0` (also `:latest`)\n"
         "- **Full changelog:** https://example.invalid/compare/a...b\n")


def test_the_line_goes_above_the_changelog_line():
    if release_link is None:
        return
    out = release_link.add_link(NOTES, "1.0.0", URL)
    lines = out.split("\n")
    at = next(i for i, l in enumerate(lines) if l.startswith("- **Windows package:**"))
    assert lines[at - 1].startswith("- **Container image:**") and lines[at + 1].startswith("- **Full changelog:**")
    assert f"]({URL})" in out


def test_it_is_not_added_twice():
    if release_link is None:
        return
    once = release_link.add_link(NOTES, "1.0.0", URL)
    assert release_link.add_link(once, "1.0.0", URL) == once


def test_a_release_that_only_talks_about_the_file_still_gets_the_link():
    if release_link is None:
        return
    # the notes of the release that introduced the package name the file in plain words
    notes = NOTES.replace("Text.", "A workflow attaches Melomancer-win64-<version>.zip to the release.")
    out = release_link.add_link(notes, "1.0.0", URL)
    assert out != notes and f"]({URL})" in out


def test_without_a_get_it_list_or_without_text_it_is_appended():
    if release_link is None:
        return
    old = "## What's Changed\n* something\n\n**Full Changelog**: https://example.invalid/compare/a...b\n"
    out = release_link.add_link(old, "1.0.0", URL)
    assert out.startswith(old.rstrip("\n")) and out.rstrip("\n").endswith("windows.md))") and f"]({URL})" in out
    assert release_link.add_link("", "1.0.0", URL).startswith("- **Windows package:**")


def test_the_command_line_rewrites_the_file(tmp_path):
    if release_link is None:
        return
    import subprocess, sys
    path = tmp_path / "body.md"
    path.write_text(NOTES, encoding="utf-8")
    run = subprocess.run([sys.executable, str(SCRIPT), str(path), "1.0.0", URL], capture_output=True, encoding="utf-8")
    assert run.returncode == 0 and "Added the link" in run.stdout
    assert URL in path.read_text(encoding="utf-8")
    again = subprocess.run([sys.executable, str(SCRIPT), str(path), "1.0.0", URL], capture_output=True, encoding="utf-8")
    assert "already link" in again.stdout
