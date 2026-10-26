"""Recovery commands, run inside the container:

    docker exec -it melomancer python -m app.cli reset-password <username>
"""
from __future__ import annotations

import getpass
import sys

from .config import Settings
from .db import init_db, tx
from .security import MIN_PASSWORD_LENGTH, hash_password


def reset_password(username: str) -> int:
    settings = Settings.from_env()
    init_db(settings.db_path)
    password = getpass.getpass(f"New password for {username} (min {MIN_PASSWORD_LENGTH} characters): ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must have at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1
    with tx(settings.db_path) as conn:
        row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            print(f"No such user: {username}", file=sys.stderr)
            return 1
        conn.execute("UPDATE users SET pw_hash=?, disabled=0 WHERE id=?", (hash_password(password), row["id"]))
        conn.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
    print("Password changed, user enabled, all sessions ended.")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "reset-password":
        return reset_password(argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
