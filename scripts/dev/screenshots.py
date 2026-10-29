#!/usr/bin/env python3
"""Takes the screenshots of the documentation (docs/img/<name>-<lang>[-dark].png) from the real panel code.

    pip install playwright pillow && playwright install chromium
    python3 scripts/dev/screenshots.py

The panel runs in headless Chromium against a mocked API with demo data (a made-up library, sets and playlists), so no
real library, names or accounts end up in a picture. Every screen is taken in English and Polish, in the light and the
dark theme; the Markdown picks the right one with a <picture> element. Run it again after the look of the panel changes.
Change the demo data here.
"""
from __future__ import annotations

import io
import json
import pathlib
import random
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

from static_site import start_server

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "img"
PORT = 8098

# (id, title, seconds, shared tags, owner)
LIBRARY = [
    ("t01", "Storm over the harbour", 250, ["ambient", "rain", "harbour"], "admin"),
    ("t02", "Rain on a tin roof", 212, ["rain", "ambient"], "admin"),
    ("t03", "Tavern fire and chatter", 348, ["tavern", "ambient"], "admin"),
    ("t04", "Fiddle and stomping boots", 176, ["tavern", "music"], "anna"),
    ("t05", "Night market", 201, ["city", "ambient"], "admin"),
    ("t06", "Combat drums", 164, ["combat"], "admin"),
    ("t07", "Last stand at the gate", 185, ["combat", "epic"], "anna"),
    ("t08", "Whispers in the cellar", 372, ["horror", "ambient"], "admin"),
    ("t09", "Cold wind on the moor", 280, ["travel", "ambient"], "admin"),
    ("t10", "Forest at dawn", 302, ["forest", "ambient"], "anna"),
    ("t11", "Distant bells", 107, ["horror", "city"], "admin"),
    ("t12", "Rowing boat in fog", 238, ["harbour", "horror"], "admin"),
]
MINE = {"t01": 0, "t08": 0, "t12": 0}  # personal tag "session 3" on these

TEXT = {
    "en": {
        "set1": "Dark Coast", "set2": "Sunday Campaign", "combat": "Combat", "locations": "Locations", "scenes": "Scenes",
        "harbour": "Harbour at night", "tavern": "Old tavern", "forest": "Forest road", "investigation": "Investigation",
        "dread": "Dread", "guild": "Friday Table", "channels": ["Table voice", "Backstage"], "mine": "session 3",
    },
    "pl": {
        "set1": "Mroczne Wybrzeże", "set2": "Niedzielna kampania", "combat": "Walka", "locations": "Lokacje", "scenes": "Sceny",
        "harbour": "Port nocą", "tavern": "Stara karczma", "forest": "Leśny trakt", "investigation": "Śledztwo",
        "dread": "Groza", "guild": "Piątkowy stół", "channels": ["Głosowy przy stole", "Zaplecze"], "mine": "sesja 3",
    },
}


def demo(lang: str) -> dict:
    t = TEXT[lang]
    tracks = [{"id": i, "title": title, "original_title": title, "duration": secs, "size": secs * 20000, "source": "upload",
               "source_url": None, "owner_id": 1 if owner == "admin" else 2, "owner": owner, "created_at": "2026-10-2%d 20:00:00" % (n % 8),
               "tags": tags, "my_tags": [t["mine"]] if i in MINE else [], "can_edit": owner == "admin",
               "lead": None, "trail": None, "trim_start": None, "trim_end": None}
              for n, (i, title, secs, tags, owner) in enumerate(LIBRARY)]
    by_id = {x["id"]: x for x in tracks}

    def manual(pid, name, ids, group_id):
        return {"id": pid, "name": name, "kind": "manual", "rule": None, "loop": True, "shuffle": False, "volume": None, "fade": 2,
                "count": len(ids), "missing": 0, "set_id": 1, "group_id": group_id,
                "items": [{"id": 100 * pid + n, "track_id": i, "title": by_id[i]["title"], "duration": by_id[i]["duration"], "deleted": False}
                          for n, i in enumerate(ids)]}

    def by_tags(pid, name, tags):
        ids = [x["id"] for x in tracks if set(tags) & set(x["tags"])]
        return {"id": pid, "name": name, "kind": "tags", "rule": {"tags": tags, "mode": "any"}, "loop": True, "shuffle": True,
                "volume": None, "fade": 2, "count": len(ids), "missing": 0, "set_id": 1, "group_id": None,
                "items": [{"id": None, "track_id": i, "title": by_id[i]["title"], "duration": by_id[i]["duration"], "deleted": False} for i in ids]}

    playlists = {
        11: manual(11, t["harbour"], ["t01", "t12", "t05", "t11", "t09"], 5),
        12: manual(12, t["tavern"], ["t03", "t04", "t02", "t05"], 5),
        13: manual(13, t["forest"], ["t10", "t09", "t02"], 5),
        14: manual(14, t["investigation"], ["t08", "t11", "t05", "t12"], 6),
        15: by_tags(15, t["dread"], ["horror"]),
        16: by_tags(16, t["combat"], ["combat"]),
    }

    def entry(p):
        return {k: p[k] for k in ("id", "name", "loop", "shuffle", "volume", "fade", "count", "missing", "kind", "rule")}

    sets = [
        {"id": 1, "name": t["set1"], "owner_id": 1, "owner": "admin", "playlists": [entry(playlists[16])],
         "groups": [{"id": 5, "name": t["locations"], "playlists": [entry(playlists[n]) for n in (11, 12, 13)]},
                    {"id": 6, "name": t["scenes"], "playlists": [entry(playlists[n]) for n in (14, 15)]}]},
        {"id": 2, "name": t["set2"], "owner_id": 1, "owner": "admin", "playlists": [], "groups": []},
    ]
    queue_ids = ["t01", "t12", "t05", "t11", "t09"]
    queue = [{"track_id": i, "title": by_id[i]["title"], "duration": by_id[i]["duration"]} for i in queue_ids]
    state = {"guild_id": "111", "connected": True, "channel_id": "1001", "channel_name": t["channels"][0], "state": "playing",
             "volume": 0.55, "loop": True, "shuffle": False, "playlist": {"id": 11, "name": t["harbour"], "set": t["set1"]},
             "now": {"track_id": "t01", "title": by_id["t01"]["title"], "duration": 250, "elapsed": 96.0, "index": 0}, "position": 1,
             "queue": queue, "queue_length": len(queue), "controller_id": 1, "controller": "admin"}
    guilds = [{"id": "111", "name": t["guild"], "channels": [{"id": "1001", "name": t["channels"][0]}, {"id": "1002", "name": t["channels"][1]}],
               "state": state}]

    def tag_counts(key):
        counts: dict[str, int] = {}
        for x in tracks:
            for tag in x[key]:
                counts[tag] = counts.get(tag, 0) + 1
        return [{"tag": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    rng = random.Random(7)
    cpu = []
    level = 2.0
    for _ in range(90):
        level = max(0.4, min(14.0, level + rng.uniform(-1.2, 1.3) + (rng.random() < 0.06) * rng.uniform(3, 6)))
        cpu.append(round(level, 1))
    memory = [176 + i // 9 + rng.randint(0, 2) for i in range(90)]
    routes = {
        "/api/auth/me": {"id": 1, "username": "admin", "role": "admin", "lang": lang},
        "/api/system": {"version": "", "bot_status": "ready", "invite_url": "https://discord.com/oauth2/authorize?client_id=1&scope=bot&permissions=3146752",
                        "downloads_enabled": True, "download_hosts": ["youtube.com"], "max_upload_mb": 300, "normalize": True,
                        "normalize_target": -16.0, "normalize_max_boost": 6.0, "trim_silence": True, "silence_threshold": -50.0,
                        "crossfade_seconds": 3.0, "scrub_seconds": 0.3, "volume_glide_seconds": 0.25, "update_check": True, "settings_rev": 1,
                        "loudness": {"total": len(tracks), "measured": len(tracks), "waiting": 0}},
        "/api/system/update": {"enabled": True, "current": "0.8.0", "comparable": True, "host": "container", "latest": "0.8.1", "available": True,
                               "url": "https://github.com/RadzuPL/melomancer/releases/tag/v0.8.1", "checked_at": 1793000000, "error": None},
        "/api/system/load": {"source": "cgroup2", "cpu": cpu[-1], "cpu_average": round(sum(cpu[-30:]) / 30, 1), "cpu_peak": max(cpu),
                             "memory_mb": memory[-1], "cores": 4, "history": {"cpu": cpu, "memory_mb": memory}},
        "/api/player/guilds": guilds,
        "/api/player/choice": {"guild": "111", "channels": {"111": "1001"}},
        "/api/player/111/state": state,
        "/api/sets": sets,
        "/api/tracks": tracks,
        "/api/tags": {"shared": tag_counts("tags"), "mine": tag_counts("my_tags")},
        "/api/people": [],
    }
    for pid, p in playlists.items():
        routes[f"/api/playlists/{pid}"] = p
    return routes


def shoot(page, name: str, lang: str, dark: bool) -> None:
    """A picture of what is on screen, cut under the last card (the footer carries the version)."""
    box = page.locator("main").bounding_box()
    height = int(min(box["y"] + box["height"] + 24, 1400))
    png = page.screenshot(full_page=True, clip={"x": 0, "y": 0, "width": 1200, "height": height})
    image = Image.open(io.BytesIO(png)).convert("RGB")
    target = OUT / f"{name}-{lang}{'-dark' if dark else ''}.png"
    image.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(target, optimize=True)
    print("wrote", target.relative_to(ROOT), target.stat().st_size // 1024, "kB")


def answer(routes: dict):
    """The route handler that serves the demo data of one language."""
    def handle(route):
        path = route.request.url.split(f"127.0.0.1:{PORT}")[1].split("?")[0]
        if route.request.method == "GET" and path in routes:
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(routes[path]))
        return route.fulfill(status=404, content_type="application/json", body='{"detail":"not_found"}')
    return handle


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    server = start_server(PORT)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for lang in ("en", "pl"):
                routes = demo(lang)
                for dark in (False, True):
                    context = browser.new_context(viewport={"width": 1200, "height": 800})
                    context.add_init_script(f"localStorage.setItem('melomancer.theme', '{'dark' if dark else 'light'}')")
                    page = context.new_page()

                    page.route("**/api/**", answer(routes))
                    page.goto(f"http://127.0.0.1:{PORT}/")
                    page.wait_for_selector("header.top")
                    tabs = page.locator("nav.tabs button")
                    page.wait_for_selector(".pad")
                    page.wait_for_timeout(700)
                    shoot(page, "player", lang, dark)
                    tabs.nth(1).click()
                    page.wait_for_selector("table tbody tr")
                    page.wait_for_timeout(400)
                    shoot(page, "library", lang, dark)
                    tabs.nth(2).click()
                    page.wait_for_selector(".tree .pl")
                    page.locator(".tree .pl .name", has_text=TEXT[lang]["harbour"]).click()
                    page.wait_for_selector("ul.items li")
                    page.wait_for_timeout(400)
                    shoot(page, "playlists", lang, dark)
                    tabs.nth(5).click()
                    page.wait_for_selector(".tile .spark polyline")
                    page.wait_for_timeout(400)
                    shoot(page, "settings", lang, dark)
                    context.close()
            browser.close()
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
