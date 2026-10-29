"""What differs between the places Melomancer runs: a Linux container and a Windows desktop.

Kept in one small module so that the rest of the code asks "where is the data folder" or "how do I start a quiet
subprocess" instead of testing the platform in many places.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

IS_WINDOWS = sys.platform == "win32"

# Flags for subprocess on Windows; 0 elsewhere (Popen accepts only 0 there).
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)            # no console flashing up for ffmpeg and ffprobe
BELOW_NORMAL = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)  # the Windows counterpart of `nice -n 10`


def default_data_dir(platform: str = sys.platform, environ: Mapping[str, str] = os.environ,
                     home: Path | None = None) -> Path:
    """/data in the container; %LOCALAPPDATA%\\Melomancer\\data on Windows (never the roaming profile or OneDrive)."""
    if platform == "win32":
        base = environ.get("LOCALAPPDATA") or str((home or Path.home()) / "AppData" / "Local")
        return Path(base) / "Melomancer" / "data"
    return Path("/data")


def default_config_path(platform: str = sys.platform, environ: Mapping[str, str] = os.environ,
                        home: Path | None = None) -> Path:
    """Where the Windows launcher keeps config.toml: next to the data folder, not inside it."""
    return default_data_dir(platform, environ, home).parent / "config.toml"
