"""Is this request from this very computer, typed into its own browser? (For signing in without a password.)

The Windows package lets the administrator in without a password, but only for a request that cannot have come from
anywhere else. All of these must hold:

* the TCP peer is the loopback address (nobody on the network can be it),
* the `Host` header names the loopback address or `localhost` (a web page on another site that points its own name
  at 127.0.0.1, "DNS rebinding", sends its own name there and is refused),
* there is no sign of a proxy or a tunnel in front (a Cloudflare Tunnel or a reverse proxy on the same computer
  connects from 127.0.0.1 too, but adds forwarding headers and carries the public name in `Host`).

Standard library only.
"""
from __future__ import annotations

from typing import Mapping
from urllib.parse import urlsplit

LOOPBACK_PEERS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
LOOPBACK_NAMES = {"127.0.0.1", "localhost", "::1"}
PROXY_HEADERS = {"forwarded", "x-real-ip", "true-client-ip", "cf-connecting-ip", "cf-ray", "cf-visitor"}


def host_name(host_header: str | None) -> str:
    """The name in a Host header without the port ("localhost:8080" -> "localhost", "[::1]:8080" -> "::1")."""
    if not host_header:
        return ""
    try:
        return (urlsplit("//" + host_header.strip()).hostname or "").lower()
    except ValueError:
        return ""


def is_local_request(peer: str | None, headers: Mapping[str, str]) -> bool:
    if (peer or "") not in LOOPBACK_PEERS:
        return False
    names = {key.lower(): value for key, value in headers.items()}
    if any(key in PROXY_HEADERS or key.startswith("x-forwarded-") for key in names):
        return False
    return host_name(names.get("host")) in LOOPBACK_NAMES
