"""When a request counts as coming from this computer (app/localaccess.py). Standard library only."""
from __future__ import annotations

import os

from app import localaccess, winmain
from app.localaccess import host_name, is_local_request


def test_host_names_are_read_without_the_port():
    assert host_name("localhost:8080") == "localhost" and host_name("LOCALHOST") == "localhost"
    assert host_name("127.0.0.1:8080") == "127.0.0.1" and host_name("[::1]:8080") == "::1"
    assert host_name("example.com:80") == "example.com"
    assert host_name("") == "" and host_name(None) == "" and host_name("[bad") == ""


def test_only_a_loopback_peer_with_a_loopback_host_and_no_proxy_counts():
    ok = {"host": "127.0.0.1:8080"}
    assert is_local_request("127.0.0.1", ok) and is_local_request("::1", {"host": "[::1]:8080"})
    assert is_local_request("::ffff:127.0.0.1", {"Host": "localhost:8080"})       # header names in any case
    assert not is_local_request("192.168.1.20", ok) and not is_local_request(None, ok) and not is_local_request("", ok)
    assert not is_local_request("127.0.0.1", {})                                  # no Host at all


def test_a_page_that_points_its_name_at_this_computer_is_refused():
    # DNS rebinding: the browser connects to 127.0.0.1 but sends the attacker's name
    for host in ("evil.example", "evil.example:8080", "127.0.0.1.evil.example", "localhost.evil.example:8080",
                 "foo.localhost:8080", "192.168.1.5:8080", "0.0.0.0:8080"):
        assert not is_local_request("127.0.0.1", {"host": host}), host


def test_a_proxy_or_a_tunnel_on_the_same_computer_is_refused():
    base = {"host": "127.0.0.1:8080"}
    for header in ("X-Forwarded-For", "X-Forwarded-Host", "x-forwarded-proto", "Forwarded", "X-Real-IP",
                   "CF-Connecting-IP", "Cf-Ray", "True-Client-IP"):
        assert not is_local_request("127.0.0.1", {**base, header: "1.2.3.4"}), header
    # a tunnel connects from 127.0.0.1 with the public name
    assert not is_local_request("127.0.0.1", {"host": "muzyka.example.com", "cf-ray": "abc"})
    assert not is_local_request("127.0.0.1", {"host": "muzyka.example.com"})


def test_the_launcher_turns_it_on_for_loopback_only():
    env = {}
    assert winmain.decide_auto_login("127.0.0.1", env) == "" and env["AUTO_LOGIN"] == "true"
    env = {}
    assert winmain.decide_auto_login("0.0.0.0", env) == "" and env["AUTO_LOGIN"] == "false"
    env = {"AUTO_LOGIN": "false"}
    assert winmain.decide_auto_login("127.0.0.1", env) == "" and env["AUTO_LOGIN"] == "false"   # a person's choice stays
    env = {"AUTO_LOGIN": "true"}
    note = winmain.decide_auto_login("0.0.0.0", env)
    assert env["AUTO_LOGIN"] == "false" and "0.0.0.0" in note                    # refused, and said so
    env = {"AUTO_LOGIN": "TRUE"}
    assert winmain.decide_auto_login("localhost", env) == "" and env["AUTO_LOGIN"] == "TRUE"


def test_the_template_explains_auto_login_in_both_languages():
    assert "# auto_login = true" in winmain.TEMPLATE and "Logowanie bez hasła" in winmain.TEMPLATE
    assert "Signing in without a password" in winmain.TEMPLATE
