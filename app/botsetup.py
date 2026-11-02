"""Setting up the Discord bot from the panel on a desktop run: checking what was pasted and editing config.toml.

On Windows the settings file is where the bot token lives (the launcher turns it into the environment variables the
rest of the program reads). The panel writes the two values there, so that a person never has to open Notepad, and
changes them in the running program, so that no restart is needed. In a container the token stays a deployment
variable and none of this is offered.
"""
from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

# Three parts separated by dots: the bot's id, a timestamp and a signature. Only the shape is checked here; whether
# Discord accepts the token is learned by logging in.
_TOKEN_SHAPE = re.compile(r"^[A-Za-z0-9_\-]{18,}\.[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{20,}$")
_CLIENT_ID_SHAPE = re.compile(r"^[0-9]{5,25}$")


class SetupError(ValueError):
    """A short code for the panel (`err.<code>` in i18n.js)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def check_token(raw: str) -> str:
    """The token without the quotes or the "Bot " prefix people paste with it; "" means "remove the token"."""
    value = raw.strip().strip("'\"").strip()
    if value.lower().startswith("bot "):
        value = value[4:].strip()
    if not value:
        return ""
    if _CLIENT_ID_SHAPE.match(value):
        raise SetupError("token_is_app_id")   # the most common mix-up: the Application ID in the token field
    if not _TOKEN_SHAPE.match(value):
        raise SetupError("bad_token")
    return value


def check_client_id(raw: str) -> str:
    value = raw.strip().strip("'\"").strip()
    if value and not _CLIENT_ID_SHAPE.match(value):
        raise SetupError("bad_client_id")
    return value


def set_config_values(path: Path, values: dict[str, str]) -> None:
    """Writes `name = 'value'` lines into the settings file and touches nothing else.

    A line that already sets the name is replaced; failing that the commented example from the template is turned
    into the setting; failing that the line is appended. The file keeps its line endings and its BOM. The result is
    parsed again before it replaces the old file, so a mistake here can never leave a settings file that does not load.
    """
    try:
        raw = path.read_bytes() if path.is_file() else b""
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.replace("\r\n", "\n").split("\n")
        for name, value in values.items():
            if "'" in value or "\n" in value:
                raise SetupError("config_write_failed")   # never happens for checked values; the literal string has no escapes
            line = f"{name} = '{value}'"
            active = next((i for i, l in enumerate(lines) if re.match(rf"^\s*{name}\s*=", l)), None)
            commented = next((i for i, l in enumerate(lines) if re.match(rf"^\s*#\s*{name}\s*=", l)), None)
            target = active if active is not None else commented
            if target is not None:
                lines[target] = line
            else:
                while lines and lines[-1] == "":
                    lines.pop()
                lines += ["", line, ""]
        new_text = "\n".join(lines)
        if not new_text.endswith("\n"):
            new_text += "\n"
        parsed = tomllib.loads(new_text)
        if any(parsed.get(name) != value for name, value in values.items()):
            raise SetupError("config_write_failed")
        data = (b"\xef\xbb\xbf" if bom else b"") + new_text.replace("\n", newline).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, path)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        raise SetupError("config_write_failed") from None
