#!/usr/bin/env python3
"""Adds the link to the Windows package to the text of a release (used by .github/workflows/windows-release.yml).

    python3 scripts/windows/release_link.py release-body.md 0.6.37 https://github.com/RadzuPL/melomancer/releases/download/v0.6.37/Melomancer-win64-0.6.37.zip

The line goes into the "Get it" list, above the changelog line; without such a list it is appended. It is not added
twice: "already there" means the exact download address is in the text, not just the name of the file (a release may
well talk about that file).
"""
from __future__ import annotations

import sys
from pathlib import Path

DOCS = "https://github.com/RadzuPL/melomancer/blob/main/docs/en/windows.md"


def add_link(body: str, version: str, url: str) -> str:
    if url in body:
        return body
    line = (f"- **Windows package:** [Melomancer-win64-{version}.zip]({url}) "
            f"(experimental, not signed: unpack it and run Melomancer.cmd, see [docs/en/windows.md]({DOCS}))")
    lines = body.rstrip("\n").split("\n") if body.strip() else []
    at = next((i for i, text in enumerate(lines) if text.startswith("- **Full changelog:**")), None)
    if at is not None:
        lines.insert(at, line)
    else:
        lines += (["", line] if lines else [line])
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    path, version, url = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    body = path.read_text(encoding="utf-8")
    new = add_link(body, version, url)
    path.write_text(new, encoding="utf-8")
    print("The notes already link the package." if new == body else "Added the link to the notes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
