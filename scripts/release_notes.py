#!/usr/bin/env python3
"""Writes the text of a GitHub release from the commit messages, and says where to get the build.

    python3 scripts/release_notes.py --mode commit --version 0.6.37 --prev v0.6.36
    python3 scripts/release_notes.py --mode weekly --version 0.7.0 --prev v0.6.40 --since-tag v0.6.35

`commit` (a push to main): the messages of the commits since the previous release. The body of a commit message is
what the reader of the release sees, so it is written for them. `weekly` (the Monday rebuild): the same, for every
release since the previous weekly rebuild, grouped by version. Trailers such as Co-Authored-By and Claude-Session are
left out. Only the standard library and git are needed.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time

REPO = "RadzuPL/melomancer"
IMAGE = "ghcr.io/radzupl/melomancer"
TAG_GLOB = "v[0-9]*.[0-9]*.[0-9]*"
TRAILER = re.compile(r"^(co-authored-by|claude-session|signed-off-by|reviewed-by)\s*:", re.IGNORECASE)
NOISE = re.compile(r"^(https://claude\.ai/code/session_\S+|.*generated with \[?claude code\]?.*)$", re.IGNORECASE)
MAX_FALLBACK_COMMITS = 30


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], capture_output=True, encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def clean_body(text: str) -> str:
    """The message body without trailers, session links and tool signatures, trimmed."""
    lines = [line.rstrip() for line in text.splitlines() if not TRAILER.match(line.strip()) and not NOISE.match(line.strip())]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def commits(*log_args: str) -> list[dict]:
    """Oldest first. Merge commits are skipped: their text is a repeat of what they merge."""
    out = git("log", "--reverse", "--no-merges", "--date=short", "--format=%H%x1f%h%x1f%ad%x1f%s%x1f%b%x1e", *log_args)
    found = []
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if not record.strip():
            continue
        full, short, date, subject, body = (record.split("\x1f", 4) + [""] * 5)[:5]
        found.append({"sha": full.strip(), "short": short.strip(), "date": date.strip(), "subject": subject.strip(),
                      "body": clean_body(body)})
    return found


def render(entries: list[dict], level: str, with_sha: bool = False) -> list[str]:
    parts = []
    for entry in entries:
        title = entry["subject"] + (f" (`{entry['short']}`)" if with_sha else "")
        parts.append(f"{level} {title}")
        if entry["body"]:
            parts.append(entry["body"])
    return parts


def footer(version: str, prev: str, since: str = "") -> list[str]:
    base = prev or since
    lines = ["## Get it", "",
             f"- **Container image:** `docker pull {IMAGE}:{version}` (also `:latest`)"]
    if base:
        lines.append(f"- **Full changelog:** https://github.com/{REPO}/compare/{base}...v{version}")
    return lines


def commit_notes(version: str, prev: str, head: str) -> str:
    entries = commits(f"{prev}..{head}") if prev else commits("-n", str(MAX_FALLBACK_COMMITS), head)
    out = ["## What's new", ""]
    if entries:
        out += ["\n\n".join(render(entries, "###"))]
    else:
        out += ["No code changes in this build."]
    return "\n".join(out) + "\n\n" + "\n".join(footer(version, prev)) + "\n"


def tags_in_order(head: str) -> list[str]:
    return [t for t in git("tag", "--list", TAG_GLOB, "--sort=version:refname", "--merged", head).split() if t]


def is_ancestor(older: str, newer: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", older, newer], capture_output=True).returncode == 0


def weekly_notes(version: str, prev: str, since_tag: str, head: str, now: float | None = None) -> str:
    tags = tags_in_order(head)
    if since_tag:
        window = [t for t in tags if t != since_tag and not is_ancestor(t, since_tag)]
        intro = f"Changes since the previous weekly rebuild ({since_tag})."
    else:   # no earlier weekly rebuild to measure from: the last seven days
        cutoff = (now or time.time()) - 7 * 86400
        window = [t for t in tags if float(git("log", "-1", "--format=%ct", t).strip() or 0) >= cutoff]
        intro = "Changes in the last seven days."
    sections, quiet = [], []
    for tag in window:
        before = tags[tags.index(tag) - 1] if tags.index(tag) > 0 else ""
        entries = commits(f"{before}..{tag}") if before else commits("-n", str(MAX_FALLBACK_COMMITS), tag)
        if not entries:
            quiet.append(tag)
            continue
        date = entries[-1]["date"]
        sections.append(f"### {tag} · {date}\n\n" + "\n\n".join(render(entries, "####", with_sha=True)))
    # commits after the newest tag belong to the build being made now
    newest = tags[-1] if tags else ""
    pending = commits(f"{newest}..{head}") if newest else []
    if pending:
        sections.append(f"### v{version}\n\n" + "\n\n".join(render(pending, "####", with_sha=True)))
    out = ["Weekly rebuild: a fresh base image, ffmpeg and the newest yt-dlp.", "", f"## {intro}", ""]
    if sections:
        out.append("\n\n".join(sections))
    else:
        out.append("No code changes in this period.")
    if quiet:
        out += ["", "Builds without code changes: " + ", ".join(quiet) + "."]
    return "\n".join(out) + "\n\n" + "\n".join(footer(version, prev, since_tag)) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["commit", "weekly"], required=True)
    parser.add_argument("--version", required=True, help="the version being released, without the v")
    parser.add_argument("--prev", default="", help="the previous release tag, for the changelog link and the commit range")
    parser.add_argument("--since-tag", default="", help="weekly: the previous weekly rebuild's tag (default: the last 7 days)")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.mode == "commit":
        text = commit_notes(args.version, args.prev, args.head)
    else:
        text = weekly_notes(args.version, args.prev, args.since_tag, args.head)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
