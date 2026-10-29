"""scripts/release_notes.py on a throw-away git repository: what the text of a release contains."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_notes.py"
notes = None
if SCRIPT.is_file() and shutil.which("git"):   # the Linux test image carries neither the scripts nor git
    spec = importlib.util.spec_from_file_location("release_notes", SCRIPT)
    notes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(notes)

TRAILERS = ("\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_011DSiPKamxDHrC1eLrxxmmM\n")


def sh(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
                           "-c", "tag.gpgsign=false", *args], cwd=repo, capture_output=True, encoding="utf-8",
                          check=True).stdout


def commit(repo: Path, subject: str, body: str = "") -> None:
    (repo / "f.txt").write_text(subject + "\n", encoding="utf-8")
    sh(repo, "add", "-A")
    sh(repo, "commit", "-q", "-m", subject + ("\n\n" + body if body else "") + "\n" + TRAILERS)


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    sh(repo, "init", "-q", "-b", "main")
    commit(repo, "First release")
    sh(repo, "tag", "v0.1.0")
    return repo


def run(repo: Path, *args: str) -> str:
    out = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=repo, capture_output=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_trailers_and_signatures_are_not_part_of_the_notes():
    if notes is None:
        return
    text = ("What changed for the reader.\n\nMore detail.\n\nCo-Authored-By: Someone <a@b.c>\n"
            "Claude-Session: https://claude.ai/code/session_abc\nhttps://claude.ai/code/session_abc\n"
            "\U0001F916 Generated with [Claude Code](https://claude.com/claude-code)\n")
    assert notes.clean_body(text) == "What changed for the reader.\n\nMore detail."
    assert notes.clean_body("") == "" and notes.clean_body(TRAILERS) == ""


def test_a_push_shows_what_each_commit_says_and_where_to_get_it(tmp_path):
    if notes is None:
        return
    repo = make_repo(tmp_path)
    commit(repo, "Panel: a new button", "It does the thing.\n\nSecond paragraph, with Polish letters: zażółć gęślą jaźń.")
    commit(repo, "Fix: a typo")
    out = run(repo, "--mode", "commit", "--version", "0.1.1", "--prev", "v0.1.0")
    assert "## What's new" in out
    assert "### Panel: a new button\n\nIt does the thing." in out and "zażółć gęślą jaźń" in out
    assert "### Fix: a typo" in out and "First release" not in out       # only what is newer than the previous release
    assert "Co-Authored-By" not in out and "Claude-Session" not in out and "claude.ai" not in out
    assert out.index("Panel: a new button") < out.index("Fix: a typo")      # oldest first
    assert "docker pull ghcr.io/radzupl/melomancer:0.1.1" in out
    assert "https://github.com/RadzuPL/melomancer/compare/v0.1.0...v0.1.1" in out


def test_a_build_without_new_commits_says_so(tmp_path):
    if notes is None:
        return
    repo = make_repo(tmp_path)
    out = run(repo, "--mode", "commit", "--version", "0.1.1", "--prev", "v0.1.0")
    assert "No code changes in this build." in out and "docker pull" in out


def test_without_a_previous_release_the_latest_commits_are_listed(tmp_path):
    if notes is None:
        return
    repo = make_repo(tmp_path)
    out = run(repo, "--mode", "commit", "--version", "0.1.0")
    assert "### First release" in out and "compare/" not in out


def test_the_weekly_rebuild_lists_every_release_since_the_previous_one(tmp_path):
    if notes is None:
        return
    repo = make_repo(tmp_path)
    sh(repo, "tag", "v0.2.0")                       # the previous weekly rebuild: same commit, no new code
    commit(repo, "Monday work", "Details of Monday.")
    sh(repo, "tag", "v0.2.1")
    commit(repo, "Tuesday work")
    commit(repo, "Tuesday again", "More.")
    sh(repo, "tag", "v0.2.2")
    sh(repo, "tag", "v0.2.3")                       # a build without code changes of its own
    out = run(repo, "--mode", "weekly", "--version", "0.3.0", "--prev", "v0.2.3", "--since-tag", "v0.2.0")
    assert out.startswith("Weekly rebuild: a fresh base image, ffmpeg and the newest yt-dlp.")
    assert "Changes since the previous weekly rebuild (v0.2.0)." in out
    assert out.index("### v0.2.1 ·") < out.index("### v0.2.2 ·")
    assert "#### Monday work (`" in out and "Details of Monday." in out
    assert "#### Tuesday work" in out and "#### Tuesday again" in out
    assert "First release" not in out                # before the previous weekly rebuild
    assert "Builds without code changes: v0.2.3." in out
    assert "compare/v0.2.3...v0.3.0" in out and "Co-Authored-By" not in out


def test_a_quiet_week_says_so(tmp_path):
    if notes is None:
        return
    repo = make_repo(tmp_path)
    sh(repo, "tag", "v0.2.0")
    out = run(repo, "--mode", "weekly", "--version", "0.3.0", "--prev", "v0.2.0", "--since-tag", "v0.2.0")
    assert "No code changes in this period." in out


def test_without_a_previous_rebuild_the_last_seven_days_count(tmp_path):
    if notes is None:
        return
    repo = make_repo(tmp_path)
    commit(repo, "Recent work")
    sh(repo, "tag", "v0.1.1")
    out = run(repo, "--mode", "weekly", "--version", "0.2.0", "--prev", "v0.1.1")
    assert "Changes in the last seven days." in out and "#### Recent work" in out
