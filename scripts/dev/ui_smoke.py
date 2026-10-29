"""Browser smoke test of the panel against a mocked API (no Python server, no Discord, no database).

It serves app/static with the same Content-Security-Policy as the real app, intercepts every /api call in Playwright
and drives the panel like a person would. Screenshots land in $SHOTS (a temporary folder by default).

    pip install playwright && playwright install chromium
    python3 scripts/dev/ui_smoke.py

Exit code 0 means no assertion failed and the page logged no errors or warnings. Keep the mock data in step with the API.
"""
import json
import os
import pathlib
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
PORT = 8099
SHOTS = os.environ.get("SHOTS") or tempfile.mkdtemp(prefix="melomancer-shots-")
from static_site import start_server  # noqa: E402


TRACKS = [
    {"id": "t1", "title": "Storm over the harbour", "original_title": "Storm over the harbour", "duration": 184.2, "size": 1000,
     "source": "upload", "source_url": None, "owner_id": 1, "owner": "admin", "created_at": "2026-10-26 10:00:00",
     "tags": ["ambient", "rain"], "my_tags": ["innsmouth"], "can_edit": True},
    {"id": "t2", "title": "<img src=x onerror=alert(1)> Tavern", "original_title": "Tavern", "duration": 95, "size": 1000,
     "source": "youtube", "source_url": "https://youtu.be/x", "owner_id": 2, "owner": "mg1", "created_at": "2026-10-26 09:00:00",
     "tags": ["tavern"], "my_tags": [], "can_edit": False},
]
PLAYLIST = {"id": 11, "name": "Dwor", "kind": "manual", "rule": None, "loop": True, "shuffle": False, "volume": None, "fade": 2, "count": 2, "missing": 1,
            "set_id": 1, "group_id": 5,
            "items": [{"id": 1, "track_id": "t1", "title": "Storm over the harbour", "duration": 184.2, "deleted": False},
                      {"id": 2, "track_id": "gone", "title": "Old theme", "duration": 60, "deleted": True}]}
SETS = [{"id": 1, "name": "Zew Cthulhu: Druga", "owner_id": 1, "owner": "admin",
         "playlists": [{"id": 12, "name": "Walka", "loop": True, "shuffle": False, "volume": None, "fade": 2, "count": 1, "missing": 0,
                        "kind": "tags", "rule": {"tags": ["ambient"], "mode": "any"}}],
         "groups": [
    {"id": 5, "name": "Lokacje", "playlists": [{"id": 11, "name": "Dwor", "loop": True, "shuffle": False, "volume": None,
                                                "fade": 2, "count": 2, "missing": 1, "kind": "manual", "rule": None}]},
    {"id": 6, "name": "Walka", "playlists": []}]}]
STATE = {"guild_id": "111", "connected": True, "channel_id": "1001", "channel_name": "Voice A", "state": "playing",
         "volume": 0.4, "loop": True, "shuffle": False, "playlist": {"id": 11, "name": "Dwor", "set": "Zew Cthulhu: Druga"},
         "now": {"track_id": "t1", "title": "Storm over the harbour", "duration": 184.2, "elapsed": 30.0, "index": 0}, "position": 1,
         "queue": [{"track_id": "t1", "title": "Storm over the harbour", "duration": 184.2},
                   {"track_id": "t3", "title": "Second song", "duration": 120}, {"track_id": "t4", "title": "Third song", "duration": 99}],
         "queue_length": 2, "controller_id": 1, "controller": "admin"}
GUILDS = [{"id": "111", "name": "Guild A", "channels": [{"id": "1001", "name": "Voice A"}, {"id": "1002", "name": "Voice B"}], "state": STATE}]

ROUTES = {
    "/api/auth/me": {"id": 1, "username": "admin", "role": "admin", "lang": "pl"},
    "/api/system": {"version": "1.2.3", "bot_status": "ready", "downloads_enabled": True,
                    "download_hosts": ["youtube.com", "youtu.be"], "max_upload_mb": 300, "normalize": True, "normalize_target": -16.0, "normalize_max_boost": 6.0, "trim_silence": True, "silence_threshold": -50.0, "crossfade_seconds": 3.0, "scrub_seconds": 0.3, "volume_glide_seconds": 0.25, "update_check": True, "settings_rev": 1, "invite_url": "https://discord.com/oauth2/authorize?client_id=123456789012345678&scope=bot&permissions=3146752", "loudness": {"total": 12, "measured": 9, "waiting": 3}},
    "/api/player/guilds": GUILDS,
    "/api/player/111/state": STATE,
    "/api/player/choice": {"guild": "111", "channels": {"111": "1002"}},
    "/api/sets": SETS,
    "/api/tracks": TRACKS,
    "/api/tags": {"shared": [{"tag": "ambient", "count": 1}, {"tag": "rain", "count": 1}], "mine": [{"tag": "innsmouth", "count": 1}]},
    "/api/playlists/11": PLAYLIST,
    "/api/playlists/12": {**PLAYLIST, "id": 12, "name": "Walka", "group_id": None, "count": 1, "missing": 0, "kind": "tags",
                          "rule": {"tags": ["ambient"], "mode": "any"},
                          "items": [{"id": None, "track_id": "t1", "title": "Storm over the harbour", "duration": 184.2, "deleted": False}]},
    "/api/downloads": {"pause_remaining": 12, "jobs": [
        {"id": 3, "url": "https://youtu.be/c", "status": "queued", "error": None, "title": None, "track_id": None, "user": "admin", "created_at": "", "stage": None, "percent": None, "speed": None, "eta": None},
        {"id": 2, "url": "https://youtu.be/b", "status": "running", "error": None, "title": "Rain on a tin roof", "track_id": None, "user": "admin", "created_at": "", "stage": "downloading", "percent": 43.4, "speed": 1258291, "eta": 12, "elapsed": 20},
        {"id": 1, "url": "https://youtu.be/a", "status": "running", "error": None, "title": None, "track_id": None, "user": "admin", "created_at": "", "stage": "preparing", "percent": None, "speed": None, "eta": None, "elapsed": 37},
        {"id": 0, "url": "https://youtu.be/x", "status": "error", "error": "Sign in to confirm", "title": None, "track_id": None, "user": "admin", "created_at": "", "stage": None, "percent": None, "speed": None, "eta": None}]},
    "/api/system/update": {"enabled": True, "current": "1.2.3", "comparable": True, "latest": "1.3.0", "available": True,
                           "url": "https://github.com/RadzuPL/melomancer/releases/tag/v1.3.0", "checked_at": 1793000000, "error": None},
    "/api/system/load": {"source": "cgroup2", "cpu": 4.2, "cpu_average": 3.1, "cpu_peak": 17.8, "memory_mb": 187, "cores": 4,
                         "history": {"cpu": [round(2 + (i * 7) % 15 + (i % 5), 1) for i in range(90)], "memory_mb": [150 + i // 3 for i in range(90)]}},
    "/api/people": [{"id": 2, "username": "bravo"}, {"id": 3, "username": "alpha"}],
    "/api/users": [{"id": 1, "username": "admin", "role": "admin", "lang": "pl", "disabled": False, "created_at": "", "guild_ids": []},
                   {"id": 2, "username": "mg1", "role": "user", "lang": "pl", "disabled": False, "created_at": "", "guild_ids": ["111"]}],
}

# What the server answers for playing in the browser: a short piece (4 s) that soon fades into a long one (24 s).
LOCAL_ITEMS = [{"track_id": "t1", "title": "Storm over the harbour", "duration": 30.0, "start": 20.0, "end": 24.0, "cut": True, "gain": 0.5},
               {"track_id": "t3", "title": "Second song", "duration": 30.0, "start": 5.0, "end": 29.0, "cut": True, "gain": 0.5}]
LOCAL_QUEUE = {"playlist": {"id": 12, "name": "Walka", "set": "Zew Cthulhu: Druga"}, "settings_rev": 1,
               "options": {"loop": True, "shuffle": False, "fade": 2.0, "volume": None}, "items": LOCAL_ITEMS}


def until(page, expr, seconds=8.0):
    """Wait for a JavaScript condition by asking again (wait_for_function evaluates a string, which the page's CSP forbids)."""
    import time
    end = time.time() + seconds
    while time.time() < end:
        if page.evaluate(expr):
            return
        page.wait_for_timeout(100)
    raise AssertionError("timed out waiting for: " + expr)

errors, calls, bodies = [], [], {}
for _t in TRACKS:
    _t.update(lead=None, trail=None, trim_start=None, trim_end=None)

import io, wave
_buf = io.BytesIO()
with wave.open(_buf, "wb") as _w:
    _w.setnchannels(1); _w.setsampwidth(2); _w.setframerate(8000); _w.writeframes(b"\x00\x00" * 8000 * 30)
WAV = _buf.getvalue()

SERVER = start_server(PORT)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
    page.on("console", lambda m: errors.append("console." + m.type + ": " + m.text) if m.type in ("error", "warning") else None)
    page.on("dialog", lambda d: (errors.append("DIALOG: " + d.message), d.dismiss()))

    def handle(route):
        req = route.request
        path = req.url.split("127.0.0.1:8099")[1].split("?")[0]
        calls.append(req.method + " " + path)
        if req.method != "GET":
            bodies[path] = req.post_data
        if req.method == "GET" and path.endswith("/stream"):
            rng = req.headers.get("range")
            if rng:
                start = int(rng.split("=")[1].split("-")[0]); end = len(WAV) - 1
                return route.fulfill(status=206, content_type="audio/wav", body=WAV[start:], headers={
                    "Content-Range": f"bytes {start}-{end}/{len(WAV)}", "Accept-Ranges": "bytes"})
            return route.fulfill(status=200, content_type="audio/wav", body=WAV, headers={"Accept-Ranges": "bytes"})
        if req.method == "POST" and path == "/api/local/queue":
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(LOCAL_QUEUE))
        if req.method == "POST" and path == "/api/local/resolve":
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(
                {"settings_rev": ROUTES["/api/system"]["settings_rev"], "items": [{**i, "gain": 0.25} for i in LOCAL_ITEMS]}))
        if req.method != "GET" and path.endswith("/copy"):
            return route.fulfill(status=201, content_type="application/json", body=json.dumps(
                {"id": 99, "set_id": 7, "set_name": "Od admin", "user": "bravo", "copied": 1, "skipped": 2, "tags_copied": 1}))
        if req.method != "GET":
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(STATE if "/player/" in path else {"ok": True}))
        if path in ROUTES:
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(ROUTES[path]))
        return route.fulfill(status=404, content_type="application/json", body='{"detail":"not_found"}')

    page.route("**/api/**", handle)
    page.goto("http://127.0.0.1:8099/")
    page.wait_for_selector("header.top")
    shots = SHOTS + "/"
    for tab, label in [("player", "Odtwarzacz"), ("library", "Biblioteka"), ("playlists", "Playlisty"),
                       ("downloads", "Pobieranie"), ("users", "Użytkownicy"), ("settings", "Ustawienia")]:
        page.click(f"nav.tabs button:has-text('{label}')")
        page.wait_for_timeout(500)
        page.screenshot(path=f"{shots}{tab}.png", full_page=True)
        if tab == "users":
            text = page.inner_text("main")
            assert "mg1" in text and "Nowy użytkownik" in text and "Wyrównywanie" not in text, text
            assert page.locator("nav.tabs button").all_inner_texts()[-2:] == ["Użytkownicy", "Ustawienia"]
        if tab == "settings":
            box = page.locator("label:has-text('Wyrównywanie głośności') input")
            assert box.is_checked(), "evening-out is on in the mock"
            text = page.inner_text("main")
            assert "Zmierzono 9 z 12 utworów" in text and "czeka na pomiar: 3" in text, text
            text = page.inner_text("main")
            assert "4.2 %" in text and "szczyt z 10 min: 17.8 %" in text and "187 MB" in text and "średnio z 60 s: 3.1 %" in text, text
            assert page.locator(".tile").count() == 3 and page.locator(".tile .spark polyline").first.get_attribute("points"), "tiles with a chart"
            link = page.locator(".tile a.btn")
            assert link.get_attribute("href").endswith("client_id=123456789012345678&scope=bot&permissions=3146752")
            assert link.get_attribute("target") == "_blank" and "noopener" in link.get_attribute("rel") and "Dodaj bota do serwera" in link.inner_text()
            assert "Działa" in page.locator(".tile.ok").inner_text()
            assert "Dostępna aktualizacja: 1.3.0 (masz 1.2.3)" in text and "Co nowego" in text and "Sprawdzono:" in text, text
            link = page.locator(".notice a")
            assert link.get_attribute("href") == "https://github.com/RadzuPL/melomancer/releases/tag/v1.3.0"
            assert link.get_attribute("target") == "_blank" and "noopener" in link.get_attribute("rel")
            assert page.locator("label:has-text('Sprawdzaj, czy jest nowa wersja') input").is_checked()
            page.locator("button:has-text('Sprawdź teraz')").click()
            page.wait_for_timeout(300)
            assert calls.count("POST /api/system/update/check") == 1, calls
            page.locator("label:has-text('Sprawdzaj, czy jest nowa wersja') input").uncheck()
            page.wait_for_timeout(300)
            assert json.loads(bodies["/api/system"]) == {"update_check": False}, bodies.get("/api/system")
            trim = page.locator("label:has-text('Przycinanie ciszy') input")
            thr = page.locator("input[aria-label='Próg ciszy (dB)']")
            assert trim.is_checked() and thr.input_value() == "-50" and thr.is_enabled()
            thr.fill("-60")
            thr.dispatch_event("change")
            page.wait_for_timeout(300)
            assert json.loads(bodies["/api/system"]) == {"silence_threshold": -60}, bodies.get("/api/system")
            page.locator("label:has-text('Przycinanie ciszy') input").uncheck()
            page.wait_for_timeout(300)
            assert json.loads(bodies["/api/system"]) == {"trim_silence": False}, bodies.get("/api/system")
            fade = page.locator("input[aria-label='Płynne przejście między utworami (s)']")
            scrub = page.locator("input[aria-label='Płynne przewijanie (s)']")
            assert fade.input_value() == "3" and scrub.input_value() == "0.3"
            fade.fill("5")
            fade.dispatch_event("change")
            page.wait_for_timeout(300)
            assert json.loads(bodies["/api/system"]) == {"crossfade_seconds": 5}, bodies.get("/api/system")
            glide = page.locator("input[aria-label='Płynna zmiana głośności (s)']")
            assert glide.input_value() == "0.25"
            glide.fill("0.6"); glide.dispatch_event("change")
            page.wait_for_timeout(300)
            assert json.loads(bodies["/api/system"]) == {"volume_glide_seconds": 0.6}, bodies.get("/api/system")
            page.locator("input[aria-label='Płynne przewijanie (s)']").fill("0")
            page.locator("input[aria-label='Płynne przewijanie (s)']").dispatch_event("change")
            page.wait_for_timeout(300)
            assert json.loads(bodies["/api/system"]) == {"scrub_seconds": 0}, bodies.get("/api/system")
            target = page.locator("input[aria-label='Poziom docelowy (LUFS)']")
            boost = page.locator("input[aria-label='Maks. podbicie (dB)']")
            assert target.input_value() == "-16" and boost.input_value() == "6" and target.is_enabled()
            target.fill("-20")
            target.dispatch_event("change")
            page.wait_for_timeout(300)
            assert json.loads(bodies["/api/system"]) == {"normalize_target": -20}, bodies.get("/api/system")
            page.locator("label:has-text('Wyrównywanie głośności') input").uncheck()
            page.wait_for_timeout(300)
            assert json.loads(bodies["/api/system"]) == {"normalize": False}, bodies.get("/api/system")

    # interactions
    page.click("nav.tabs button:has-text('Pobieranie')")
    page.wait_for_timeout(600)
    body = page.inner_text("main")
    assert "43%" in body and "Pobieranie" in body and "1.2 MB/s" in body and "start za 12 s" in body, body
    assert page.locator(".progress.indeterminate").count() == 1, "indeterminate bar while preparing"
    assert "37 s" in body, "elapsed time while preparing"
    assert page.locator(".taginput").count() == 2, "two tag fields"
    shared, mine = page.locator(".taginput").nth(0), page.locator(".taginput").nth(1)
    shared.locator("input").fill("ra")
    assert "rain" in shared.locator(".suggest").inner_text(), "suggestion from existing tags"
    shared.locator(".suggest .chip", has_text="rain").click()
    shared.locator("input").fill("Nowy Tag")
    page.keyboard.press("Enter")
    mine.locator("input").fill("sesja 3")
    page.keyboard.press("Enter")
    assert shared.locator(".taglist .chip").count() == 2
    page.fill("input[type=url]", "https://youtu.be/zzz")
    page.click("button:has-text('Pobierz')")
    page.wait_for_timeout(400)
    import json as _j
    posted = _j.loads(bodies["/api/downloads"])
    assert posted == {"url": "https://youtu.be/zzz", "tags": ["rain", "nowy tag"], "my_tags": ["sesja 3"]}, posted
    page.screenshot(path=shots + "downloads_tags.png", full_page=True)
    page.screenshot(path=shots + "downloads_progress.png", full_page=True)
    page.click("nav.tabs button:has-text('Biblioteka')")
    page.wait_for_timeout(300)
    assert page.locator("table tbody tr").count() == 2, "library rows"
    assert page.locator("img").count() == 0, "title must not be rendered as HTML"
    # listening: one play button per row, the seek bar opens right under the playing row
    rows = page.locator("table tbody tr[data-preview-id]")
    first_play, second_play = rows.nth(0).locator("td.actions button").first, rows.nth(1).locator("td.actions button").first
    assert first_play.inner_text() == "▶" and page.locator(".previewslot").count() == 0
    first_play.click()
    page.wait_for_timeout(700)
    assert first_play.inner_text() == "⏸", "the button shows that it plays"
    assert page.locator(".previewslot").count() == 1 and page.locator("table tbody tr.previewing").count() == 1
    assert page.locator("tbody tr").nth(1).get_attribute("class") == "previewslot", "the bar is directly under the playing row"
    assert "0:" in page.inner_text(".previewslot") and page.locator(".previewslot input[type=range]").count() == 1
    first_play.click()
    page.wait_for_timeout(200)
    assert first_play.inner_text() == "▶" and page.locator(".previewslot").count() == 1, "paused: the bar stays"
    page.locator(".previewslot input[type=range]").evaluate("el => { el.value = 7; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
    page.wait_for_timeout(300)
    assert 6.5 <= page.evaluate("Preview.audio.currentTime") <= 8, page.evaluate("Preview.audio.currentTime")
    second_play = page.locator("table tbody tr[data-preview-id]").nth(1).locator("td.actions button").first
    second_play.click()
    page.wait_for_timeout(500)
    assert page.locator(".previewslot").count() == 1, "only the track being listened to has a bar"
    assert page.locator("table tbody tr[data-preview-id]").nth(0).locator("td.actions button").first.inner_text() == "▶"
    page.locator("table tbody tr input[type=checkbox]").nth(1).check()      # a repaint of the table keeps the bar
    page.wait_for_timeout(200)
    assert page.locator(".previewslot").count() == 1 and page.evaluate("!Preview.audio.paused")
    page.screenshot(path=shots + "library_preview.png", full_page=True)
    page.locator(".previewslot button").click()                              # the bar's own close button
    page.wait_for_timeout(200)
    assert page.locator(".previewslot").count() == 0 and page.evaluate("Preview.track === null")
    page.locator("table tbody tr input[type=checkbox]").nth(1).uncheck()

    page.fill("input[type=search]", "storm")
    page.wait_for_timeout(300)
    assert page.locator("table tbody tr").count() == 1, "search filter"
    page.locator("table tbody tr").nth(0).locator("button[title='Edytuj']").click()
    page.wait_for_selector(".dialog .taginput")
    assert page.locator(".dialog .taginput").count() == 2, "tag fields in the edit dialog"
    assert page.locator(".dialog .taglist .chip").count() == 3, "existing tags as chips (2 shared + 1 mine)"
    page.screenshot(path=shots + "edit_tags.png")
    # start and end of the track: listen, find the spot, "set here"
    assert page.locator(".dialog input.timefield").count() == 2
    page.locator(".dialog button[aria-label='Odsłuchaj']").click()
    page.wait_for_timeout(600)
    assert page.locator(".dialog .previewslot input[type=range]").count() == 1, "a seek bar inside the dialog"
    page.locator(".dialog .previewslot input[type=range]").evaluate("el => { el.value = 3; el.dispatchEvent(new Event('input', {bubbles: true})); }")
    page.locator(".dialog .row:has(input[aria-label='Początek']) button:has-text('Ustaw tutaj')").click()
    start_text = page.locator(".dialog input[aria-label='Początek']").input_value()
    assert start_text.startswith("0:03"), start_text
    page.locator(".dialog input[aria-label='Koniec']").fill("2:30.5")
    page.click(".dialog button:has-text('Zapisz')")
    page.wait_for_timeout(400)
    patch = json.loads(bodies["/api/tracks/t1"])
    assert patch["trim_start"] == 3 and patch["trim_end"] == 150.5 and patch["title"] == "Storm over the harbour", patch
    assert page.evaluate("Preview.track === null"), "closing the dialog stopped the sound"
    page.locator("table tbody tr").nth(0).locator("button[title='Edytuj']").click()
    page.wait_for_selector(".dialog .taginput")
    page.locator(".dialog input[aria-label='Koniec']").fill("abc")
    page.click(".dialog button:has-text('Zapisz')")
    page.wait_for_timeout(300)
    assert page.locator(".dialog").count() == 1, "a bad time keeps the dialog open"
    assert "co najmniej sekundę" in page.inner_text("#toasts")
    page.click(".dialog button:has-text('Anuluj')")
    page.locator("table tbody tr input[type=checkbox]").first.check()
    assert page.locator(".bulk:not(.hidden)").count() == 1, "bulk bar"
    page.click("nav.tabs button:has-text('Playlisty')")
    page.wait_for_selector(".tree .pl .name")
    assert page.locator(".tree .pl.root").count() == 1, "playlist directly under the set"
    assert page.locator(".tree .group .pl").count() == 1, "playlist inside the folder"
    page.locator(".tree .pl.root .name").click()
    page.wait_for_selector(".dialog, .taginput")
    assert page.locator("#app .taginput").count() == 1, "rule field of an automatic playlist"
    assert "Storm over the harbour" in page.inner_text(".split > .card:last-child"), "matching tracks listed"
    assert page.locator("button:has-text('Dodaj utwory')").count() == 0, "no manual adding for an automatic playlist"
    page.locator("#app .taginput input").fill("ra")
    page.locator("#app .taginput .suggest .chip", has_text="rain").click()
    page.wait_for_timeout(300)
    assert "PATCH /api/playlists/12" in calls
    import json as _k
    assert _k.loads(bodies["/api/playlists/12"]) == {"tags": ["ambient", "rain"], "mode": "any"}, bodies["/api/playlists/12"]
    page.screenshot(path=shots + "tag_playlist.png", full_page=True)

    # copy the playlist to another person
    page.click("button:has-text('Kopiuj do…')")
    page.wait_for_selector(".dialog select")
    assert page.locator(".dialog select[aria-label='Kopiuj do…'] option").all_inner_texts() == ["Do mojego zestawu lub folderu", "Do innej osoby"]
    page.locator(".dialog select[aria-label='Kopiuj do…']").select_option(label="Do innej osoby")
    assert page.locator(".dialog select[aria-label='Osoba'] option").all_inner_texts() == ["bravo", "alpha"]
    page.locator(".dialog select[aria-label='Osoba']").select_option(label="bravo")
    page.locator(".dialog input[type=checkbox]").check()
    page.click(".dialog button:has-text('Kopiuj')")
    page.wait_for_timeout(300)
    assert _k.loads(bodies["/api/playlists/12/copy"]) == {"user_id": 2, "with_my_tags": True}, bodies.get("/api/playlists/12/copy")
    toast_text = page.inner_text("#toasts")
    assert "bravo" in toast_text and "Od admin" in toast_text and "pominięto usunięte: 2" in toast_text, toast_text
    # copy it to a folder of my own: the first choice of the dialog, no other person involved
    page.click("button:has-text('Kopiuj do…')")
    page.wait_for_selector(".dialog select")
    assert page.locator(".dialog select[aria-label='Zestaw lub folder']").is_visible() and page.locator(".dialog select[aria-label='Osoba']").is_hidden()
    page.locator(".dialog select[aria-label='Zestaw lub folder']").select_option(label="Zew Cthulhu: Druga › 📁 Lokacje")
    page.click(".dialog button:has-text('Kopiuj')")
    page.wait_for_timeout(300)
    assert _k.loads(bodies["/api/playlists/12/copy"]) == {"group_id": 5}, bodies.get("/api/playlists/12/copy")
    page.locator(".tree .set .head button[title='Nowa playlista']").first.click()
    page.wait_for_selector(".dialog select")
    page.locator(".dialog input").first.fill("Karczma")
    page.locator(".dialog select").first.select_option("tags")
    assert page.locator(".dialog .taginput").count() == 1
    page.locator(".dialog .taginput input").fill("tav")
    page.locator(".dialog .taginput .suggest .chip", has_text="tavern").click()
    page.screenshot(path=shots + "new_tag_playlist.png")
    page.click(".dialog button:has-text('OK')")
    page.wait_for_timeout(300)
    created = _k.loads(bodies["/api/sets/1/playlists"])
    assert created == {"name": "Karczma", "kind": "tags", "tags": ["tavern"], "mode": "any"}, created
    page.click(".tree .group .pl .name")
    page.wait_for_selector(".items li.gone")
    assert page.locator(".items li").count() == 2
    page.click("button:has-text('Przenieś playlistę')")
    page.wait_for_selector(".dialog select")
    options = page.locator(".dialog select option").all_inner_texts()
    assert any("bez folderu" in o for o in options) and any("Lokacje" in o for o in options), options
    page.screenshot(path=shots + "move_dialog.png")
    page.click(".dialog button:has-text('Anuluj')")
    page.screenshot(path=shots + "playlist_detail.png", full_page=True)
    page.click("button:has-text('Dodaj utwory')")
    page.wait_for_selector(".picker-list label")
    assert page.locator(".picker-list label").count() == 1, "tracks already on the playlist are hidden"
    assert "Tavern" in page.inner_text(".picker-list")
    assert page.locator(".picker-list label .chip").all_inner_texts() == ["tavern"], "the tags are shown to tell tracks apart"
    page.locator(".picker-list label button").first.click()
    page.wait_for_timeout(600)
    assert page.locator(".picker-list .previewslot").count() == 1, "the picker has a seek bar too"
    assert page.locator(".picker-list input[type=checkbox]").first.is_checked() is False, "listening does not pick the track"
    page.screenshot(path=shots + "picker_preview.png")
    page.click(".dialog button:has-text('Anuluj')")
    page.wait_for_timeout(600)
    assert page.evaluate("Preview.track === null"), "closing the picker stopped the sound"
    first_item = page.locator("ul.items li[data-preview-id]").first
    first_item.locator("button").first.click()
    page.wait_for_timeout(600)
    assert page.locator("ul.items li.previewslot").count() == 1, "a seek bar under the track in the playlist"
    page.click("nav.tabs button:has-text('Odtwarzacz')")
    page.wait_for_timeout(600)
    assert page.evaluate("Preview.track === null"), "leaving the screen stopped the sound"
    page.click("nav.tabs button:has-text('Odtwarzacz')")
    page.wait_for_selector(".qrow")
    assert page.locator(".qrow").count() == 3, "queue rows"
    assert page.locator(".qrow.current").count() == 1 and "Storm" in page.inner_text(".qrow.current")
    # ticks under the volume slider: long at 0/50/100/150, short at 25/75/125, lined up with the slider's scale
    assert page.locator(".volume .voltick .tick").count() == 7 and page.locator(".volume .voltick .tick.major").count() == 4
    geo = page.evaluate("""() => {
      const input = document.querySelector('.volume input'), r = input.getBoundingClientRect();
      const ticks = [...document.querySelectorAll('.volume .tick')].map((t) => { const b = t.getBoundingClientRect(); return [b.left + b.width / 2, b.height]; });
      return { left: r.left, width: r.width, ticks };
    }""")
    for (x, height), pct in zip(geo["ticks"], (0, 25, 50, 75, 100, 125, 150)):
        want = geo["left"] + 7 + (geo["width"] - 14) * pct / 150
        assert abs(x - want) < 1.0, (pct, x, want)
        assert height == (9 if pct % 50 == 0 else 5), (pct, height)
    page.locator(".volume").screenshot(path=shots + "volume_ticks.png")
    # the slider keeps one width whatever the label says (5 %, 40 %, 100 %, 150 %)
    widths = set()
    for value in (5, 9, 10, 40, 99, 100, 101, 150):
        page.locator(".volume input").evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); }", value)
        widths.add(page.evaluate("document.querySelector('.volume input').getBoundingClientRect().width"))
    assert len(widths) == 1, widths
    page.locator(".volume input").evaluate("el => { el.value = 40; el.dispatchEvent(new Event('input', {bubbles: true})); }")
    # the volume slider: the bot follows while it is dragged, one request after another, the last value wins
    vol = page.locator("input[aria-label='Głośność']").first
    before = calls.count("POST /api/player/111/volume")
    for value in (100, 60, 25):
        vol.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); }", value)
        page.wait_for_timeout(120)
    vol.evaluate("el => el.dispatchEvent(new Event('change', {bubbles: true}))")
    page.wait_for_timeout(300)
    assert calls.count("POST /api/player/111/volume") - before >= 3, "updates while dragging, not only at the end"
    assert json.loads(bodies["/api/player/111/volume"]) == {"volume": 0.25}, bodies.get("/api/player/111/volume")
    page.click(".qrow >> nth=1")
    page.wait_for_timeout(300)
    assert "POST /api/player/111/jump" in calls, "jump request"
    page.screenshot(path=shots + "player_queue.png", full_page=True)

    # footer links
    links = {a.inner_text(): a.get_attribute("href") for a in page.locator("footer.foot a").all()}
    assert links["Melomancer"] == "https://github.com/RadzuPL/melomancer", links
    assert links["Radzu"] == "https://radzu.net/", links
    assert [h for t, h in links.items() if t not in ("Melomancer", "Radzu")] == ["https://github.com/RadzuPL/melomancer/releases"], links
    assert "by" in page.inner_text("footer.foot")

    # seek bar
    seek = page.locator("input.seek:not(.vol)")
    assert seek.is_enabled(), "seek enabled when the track has a duration"
    assert abs(float(seek.get_attribute("max")) - 184.2) < 0.5, seek.get_attribute("max")
    seek.evaluate("el => { el.value = 100; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
    page.wait_for_timeout(300)
    assert _k.loads(bodies["/api/player/111/seek"]) == {"seconds": 100}, bodies.get("/api/player/111/seek")

    # user menu: username in a frame, the rest hides in a drop-down
    assert page.locator("header.top button:has-text('Wyloguj')").count() == 0, "logout hidden until the menu is open"
    page.click("header.top button.btn.small")

    assert page.locator(".menu:not(.hidden) .menuitem").all_inner_texts() == ["Zmień hasło", "Wyloguj"]
    page.keyboard.press("Escape")
    assert page.locator(".menu:not(.hidden)").count() == 0, "Escape closes the menu"
    page.click("header.top button.btn.small")
    page.click(".menuitem:has-text('Zmień hasło')")
    page.wait_for_selector(".dialog")
    assert "Zmień hasło" in page.inner_text(".dialog h3")
    page.click(".dialog button:has-text('Zamknij')")

    # theme: one click goes to the next mode: auto -> light -> dark -> auto
    theme = page.locator("header.top button.icon-only")
    theme_attr = "document.documentElement.getAttribute('data-theme')"
    assert page.locator(".menu:not(.hidden)").count() == 0, "no drop-down for the theme"
    assert theme.get_attribute("aria-label") == "Motyw: Automatyczny", theme.get_attribute("aria-label")
    theme.click()
    assert theme.get_attribute("aria-label") == "Motyw: Jasny" and theme.inner_text() == "☀"
    assert page.evaluate(theme_attr) == "light"
    assert page.evaluate("localStorage.getItem('melomancer.theme')") == "light"
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg != "rgb(255, 255, 255)", "light theme must not be pure white: " + bg
    page.screenshot(path=shots + "player_light.png", full_page=True)
    for tab, label in [("library", "Biblioteka"), ("playlists", "Playlisty"), ("downloads", "Pobieranie"), ("users", "Użytkownicy"), ("settings", "Ustawienia")]:
        page.click(f"nav.tabs button:has-text('{label}')")
        page.wait_for_timeout(300)
        page.screenshot(path=shots + f"light_{tab}.png", full_page=True)
    page.click("nav.tabs button:has-text('Odtwarzacz')")
    theme.click()
    assert theme.get_attribute("aria-label") == "Motyw: Ciemny" and page.evaluate(theme_attr) == "dark"
    theme.click()
    assert theme.get_attribute("aria-label") == "Motyw: Automatyczny"
    assert page.evaluate("localStorage.getItem('melomancer.theme')") is None, "auto clears the stored choice"
    page.reload()
    page.wait_for_selector("header.top")
    theme.click()
    assert page.evaluate(theme_attr) == "light"
    page.reload()
    page.wait_for_selector("header.top")
    assert page.evaluate(theme_attr) == "light" and theme.get_attribute("aria-label") == "Motyw: Jasny", "choice survives a reload"
    theme.click(); theme.click()
    page.wait_for_selector(".pad")
    assert page.locator(".pad").count() == 2, "root pad + folder pad"
    assert "🏷" in page.locator(".pad").first.inner_text(), "automatic playlists are marked"
    assert page.locator(".quickchips .chip").count() >= 3, "tags to pick from"
    assert page.locator("button:has-text('Zagraj (0)')").is_disabled(), "nothing chosen yet"
    page.locator(".quickchips .chip", has_text="ambient").click()
    assert page.locator("button:has-text('Zagraj (1)')").is_enabled()
    page.locator(".quickchips .chip", has_text="innsmouth").click()
    page.locator("button:has-text('Zagraj (1)')").click()
    page.wait_for_timeout(300)
    posted = _k.loads(bodies["/api/player/111/play"])
    assert posted == {"tags": ["ambient", "innsmouth"], "mode": "any"}, posted
    page.screenshot(path=shots + "quick_pick.png", full_page=True)
    page.click(".pad")
    page.wait_for_timeout(300)
    # ---- playing in the browser: Discord is skipped, the page makes the sound ----
    STATE.update(connected=False, channel_id=None, channel_name=None, state="idle", now=None, playlist=None, queue=[],
                 controller_id=None, controller=None)
    page.reload()
    page.wait_for_selector(".pad")
    connect_btn = page.get_by_role("button", name="Połącz", exact=True)
    here_btn = page.get_by_role("button", name="Odtwarzaj tutaj")
    assert connect_btn.is_enabled() and here_btn.is_enabled(), "both ways are open while the bot is not connected"
    # the server and channel chosen last come from the server, and a new choice is sent back
    channel = page.locator("select[aria-label='Kanał głosowy']")
    assert channel.input_value() == "1002", "the remembered channel is selected, not the first one"
    channel.select_option("1001")
    page.wait_for_timeout(200)
    assert _k.loads(bodies["/api/player/choice"]) == {"guild_id": "111", "channel_id": "1001"}, bodies["/api/player/choice"]
    # a playlist pressed while the bot is not connected is only loaded: nothing connects, nothing plays
    assert "primary" in here_btn.get_attribute("class") and "primary" in connect_btn.get_attribute("class"), "both buttons look alike"
    mark = len(calls)
    page.locator(".pad", has_text="Walka").click()
    page.wait_for_timeout(300)
    assert not [c for c in calls[mark:] if c.startswith("POST")], calls[mark:]
    assert "Wybrana: Walka" in page.inner_text(".now .title") and page.locator(".pad.armed").count() == 1
    assert page.get_by_role("button", name="Pauza / wznów").is_disabled(), "cannot start before connecting"
    assert page.locator(".qrow").count() == 1 and page.locator(".qrow").first.is_disabled(), "the selected playlist shows its tracks, stopped"
    assert "Storm over the harbour" in page.inner_text(".queue")
    STATE.update(connected=True, channel_id="1001", channel_name="Voice A")
    connect_btn.click()
    page.wait_for_timeout(300)
    assert "POST /api/player/111/connect" in calls[mark:] and "POST /api/player/111/play" not in calls[mark:], "connecting does not start it"
    assert page.get_by_role("button", name="Pauza / wznów").is_enabled()
    page.get_by_role("button", name="Pauza / wznów").click()
    page.wait_for_timeout(300)
    assert _k.loads(bodies["/api/player/111/play"]) == {"playlist_id": 12}, bodies["/api/player/111/play"]
    assert page.locator(".pad.armed").count() == 0
    STATE.update(connected=False, channel_id=None, channel_name=None, state="idle")
    page.reload()
    page.wait_for_selector(".pad")
    # a selected playlist survives turning "Play here" on, and the play button then plays it in the browser
    page.locator(".pad", has_text="Walka").click()
    page.wait_for_timeout(300)
    here_btn.click()
    page.wait_for_timeout(300)
    assert "Wybrana: Walka" in page.inner_text(".now .title") and page.locator(".qrow").count() == 1, "still selected, with its list"
    assert page.get_by_role("button", name="Pauza / wznów").is_enabled()
    page.get_by_role("button", name="Pauza / wznów").click()
    until(page, "LocalPlayer.state === 'playing' && !!LocalPlayer.cur")
    assert _k.loads(bodies["/api/local/queue"]) == {"playlist_id": 12} and page.locator(".qrow:not([disabled])").count() == 2
    page.get_by_role("button", name="Stop", exact=True).click()
    page.wait_for_timeout(400)
    page.get_by_role("button", name="Wyłącz odtwarzanie tutaj").click()
    page.wait_for_timeout(300)
    here_btn.click()
    page.wait_for_timeout(300)
    assert page.get_by_role("button", name="Wyłącz odtwarzanie tutaj").count() == 1
    assert connect_btn.is_disabled(), "playing here blocks connecting to Discord"
    assert page.locator("select[aria-label='Serwer']").is_hidden() and "Gra w tej przeglądarce" in page.inner_text("main")
    page.screenshot(path=shots + "player_local.png", full_page=True)
    page.locator(".pad", has_text="Walka").click()
    until(page, "LocalPlayer.state === 'playing' && !!LocalPlayer.cur && LocalPlayer.cur.a.currentTime > 20.3")
    assert _k.loads(bodies["/api/local/queue"]) == {"playlist_id": 12}, bodies["/api/local/queue"]
    assert page.evaluate("LocalPlayer.ctx.state") == "running", "the audio context runs"
    assert abs(page.evaluate("LocalPlayer.cur.trackGain.gain.value") - 0.5) < 0.01, "loudness gain of the track"
    assert page.evaluate("LocalPlayer.cur.a.currentTime") >= 20, "plays from the start point the server gave"
    assert "Storm over the harbour" in page.inner_text(".now .title"), page.inner_text(".now .title")
    assert not any(c.startswith("POST /api/player/111/play") for c in calls[-6:]), "Discord is not touched"

    # switching panel tabs does not stop the sound
    before = page.evaluate("LocalPlayer.cur.a.currentTime")
    page.click("nav.tabs button:has-text('Biblioteka')")
    page.wait_for_timeout(600)
    assert page.evaluate("LocalPlayer.state") == "playing" and not page.evaluate("LocalPlayer.cur.a.paused"), "still playing"
    page.click("nav.tabs button:has-text('Odtwarzacz')")
    page.wait_for_selector(".pad")
    page.wait_for_timeout(300)
    assert "Gra w tej przeglądarce" in page.inner_text("main") and page.get_by_role("button", name="Wyłącz odtwarzanie tutaj").count() == 1
    shown = page.inner_text(".now .title")
    assert shown in ("Storm over the harbour", "Second song"), "the player screen picks the running music up again: " + shown

    # the long track fades in over the end of the short one (4 s long, 3 s cross-fade) and then plays on
    until(page, "LocalPlayer.pos === 1")
    assert page.evaluate("LocalPlayer.cur.item.track_id") == "t3"
    page.wait_for_timeout(3600)
    assert page.evaluate("LocalPlayer.dying.size") == 0 and page.evaluate("LocalPlayer.cur.env.gain.value") > 0.98, "the old layer is gone"
    assert page.evaluate("LocalPlayer.state") == "playing", "the playlist loops"

    # pause / resume, seek, volume, options
    page.get_by_role("button", name="Pauza / wznów").click()
    page.wait_for_timeout(300)
    assert page.evaluate("LocalPlayer.state") == "paused" and page.evaluate("LocalPlayer.cur.a.paused")
    page.get_by_role("button", name="Pauza / wznów").click()
    page.wait_for_timeout(300)
    assert page.evaluate("LocalPlayer.state") == "playing" and not page.evaluate("LocalPlayer.cur.a.paused")
    page.locator("input.seek[aria-label='Przewiń utwór']").evaluate("el => { el.value = 21.5; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
    page.wait_for_timeout(700)
    assert page.evaluate("LocalPlayer.cur.seeked") and page.evaluate("LocalPlayer.cur.a.currentTime") >= 21.4, "seek continues from there"
    page.locator("input[aria-label='Głośność']").evaluate("el => { el.value = 100; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
    page.wait_for_timeout(900)
    assert abs(page.evaluate("LocalPlayer.master.gain.value") - 1.0) < 0.05, page.evaluate("LocalPlayer.master.gain.value")
    page.get_by_role("button", name="Pętla").click()
    page.wait_for_timeout(200)
    assert page.evaluate("LocalPlayer.loop") is False

    # a change of the administrator's settings reaches what is playing
    ROUTES["/api/system"]["settings_rev"] = 2
    page.evaluate("LocalPlayer.refreshSettings()")
    page.wait_for_timeout(900)
    assert "POST /api/local/resolve" in calls and abs(page.evaluate("LocalPlayer.cur.trackGain.gain.value") - 0.25) < 0.02

    page.get_by_role("button", name="Stop", exact=True).click()
    page.wait_for_timeout(500)
    assert page.evaluate("LocalPlayer.state") == "idle" and page.evaluate("LocalPlayer.dying.size") == 0
    page.get_by_role("button", name="Wyłącz odtwarzanie tutaj").click()
    page.wait_for_timeout(300)
    assert connect_btn.is_enabled() and page.get_by_role("button", name="Odtwarzaj tutaj").count() == 1, "Discord is available again"

    # the other way round: with the bot connected the button for playing here is blocked
    STATE.update(connected=True, channel_id="1001", channel_name="Voice A", state="idle")
    page.reload()
    page.wait_for_selector(".pad")
    assert page.get_by_role("button", name="Odtwarzaj tutaj").is_disabled(), "connected to Discord blocks playing here"
    STATE.update(connected=False, channel_id=None, channel_name=None)
    ROUTES["/api/system"]["settings_rev"] = 1
    assert page.locator("header.top select").count() == 0, "no language drop-down any more"
    page.click("header.top button.ghost:has-text('PL')")
    page.wait_for_timeout(300)
    assert page.locator("nav.tabs button:has-text('Player')").count() == 1, "language switch"
    assert page.locator("header.top button.ghost:has-text('EN')").count() == 1, "marker shows the current language"
    page.screenshot(path=shots + "player_en.png", full_page=True)
    browser.close()

print("calls:", sorted(set(calls)))
print("ERRORS:", errors if errors else "none")
SERVER.shutdown()
print("Screenshots:", SHOTS)
sys.exit(1 if errors else 0)
