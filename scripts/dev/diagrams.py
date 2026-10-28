#!/usr/bin/env python3
"""Draws the diagrams of the documentation (docs/img/*.svg), in English and Polish, from one source.

    python3 scripts/dev/diagrams.py

Edit the drawing or the texts here and run it again; do not edit the SVG files by hand. Every diagram is written
twice, `name-lang.svg` for a light page and `name-lang-dark.svg` for a dark one, both on a transparent background;
the Markdown picks one with a `<picture>` element, which GitHub switches by its own theme. It also writes the
placeholder screenshots (docs/img/*.png) that stand in until a real screenshot is saved under the same name; an
existing screenshot is never overwritten.
"""
from __future__ import annotations

import pathlib
from xml.sax.saxutils import escape

OUT = pathlib.Path(__file__).resolve().parents[2] / "docs" / "img"

THEMES = {
    "light": dict(ink="#25222f", muted="#6c6779", line="#cfcbdb", page="#ffffff", grey="#f6f5f9",
                  accent="#6a43c2", accent_bg="#efe9fb", blue="#2b6cb0", blue_bg="#e8f1fa",
                  green="#2f855a", green_bg="#e6f4ec", disc="#5865f2", disc_bg="#eef0ff", disc_ink="#3a45c4"),
    # GitHub's dark theme: page #0d1117, boxes a little lighter, the same hues brighter
    "dark": dict(ink="#e6edf3", muted="#9198a1", line="#3d444d", page="#0d1117", grey="#151b23",
                 accent="#a78bfa", accent_bg="#241c3d", blue="#58a6ff", blue_bg="#0f2236",
                 green="#3fb950", green_bg="#0f2a1a", disc="#8b93ff", disc_bg="#1a1e3d", disc_ink="#aab0ff"),
}


class Svg:
    """Colours are given by name (a key of the theme) or as "none"."""

    def __init__(self, width: int, height: int, theme: str) -> None:
        self.w, self.h, self.c = width, height, THEMES[theme]
        self.parts: list[str] = []

    def col(self, name: str) -> str:
        return self.c.get(name, name)

    def box(self, x, y, w, h, title, sub=(), *, fill="grey", stroke="line", color="ink", dash=False):
        dashes = ' stroke-dasharray="6 4"' if dash else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{self.col(fill)}" '
                          f'stroke="{self.col(stroke)}" stroke-width="1.5"{dashes}/>')
        lines = [sub] if isinstance(sub, str) else list(sub)
        top = y + (h - 18 * len(lines) - (22 if title else 0)) / 2 + 16 if title else y + (h - 18 * len(lines)) / 2 + 13
        if title:
            self.parts.append(f'<text x="{x + w / 2}" y="{top:.0f}" text-anchor="middle" font-size="15" '
                              f'font-weight="700" fill="{self.col(color)}">{escape(title)}</text>')
            top += 22
        for i, line in enumerate(lines):
            self.parts.append(f'<text x="{x + w / 2}" y="{top + i * 18:.0f}" text-anchor="middle" font-size="12.5" '
                              f'fill="{self.col("muted")}">{escape(line)}</text>')

    def text(self, x, y, value, *, size=13, color="ink", weight=400, anchor="middle"):
        self.parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" '
                          f'fill="{self.col(color)}">{escape(value)}</text>')

    def arrow(self, points, label="", *, color="accent", both=False, at=None, anchor="middle"):
        path = "M" + " L".join(f"{px} {py}" for px, py in points)
        c = self.col(color)
        start = ' marker-start="url(#head-rev)"' if both else ""
        self.parts.append(f'<path d="{path}" fill="none" stroke="{c}" stroke-width="2" marker-end="url(#head)"{start}/>')
        if label:
            lx, ly = at if at else ((points[0][0] + points[-1][0]) / 2, (points[0][1] + points[-1][1]) / 2 - 7)
            # the halo has the colour of the page, so that a label crossing a line stays readable
            self.parts.append(f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="12" fill="{c}" font-weight="600" '
                              f'paint-order="stroke" stroke="{self.col("page")}" stroke-width="4">{escape(label)}</text>')

    def render(self) -> str:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                'font-family="Inter, \'Segoe UI\', \'DejaVu Sans\', Arial, sans-serif">'
                '<defs>'
                '<marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
                '<path d="M0 0 L10 5 L0 10 z" fill="context-stroke"/></marker>'
                '<marker id="head-rev" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
                '<path d="M0 0 L10 5 L0 10 z" fill="context-stroke"/></marker>'
                '</defs>' + "".join(self.parts) + "</svg>\n")


TEXT = {
    "en": {
        "browser": "Browser", "panel": "Panel", "panel_sub": "plain JavaScript, PL / EN",
        "local": "LocalPlayer", "local_sub": "Web Audio, \"Play here\"", "speakers": "speakers of this computer",
        "cf": "Cloudflare", "cf_sub": ("Tunnel + Access", "(optional)"),
        "container": "One container: melomancer", "loop": "one Python process, one asyncio loop",
        "api": "FastAPI", "api_sub": "login · library · playlists · player · local playback",
        "bot": "BotManager", "bot_sub": ("one GuildPlayer per server", "Mixer: layers, cross-fades,", "loudness gain, volume glide"),
        "dl": "Downloader", "dl_sub": "yt-dlp + ffmpeg, rate limits",
        "ld": "Loudness worker", "ld_sub": "ffmpeg: loudness and silence",
        "db": "SQLite", "db_sub": ("/data/melomancer.db", "users, tracks, playlists, settings"),
        "files": "Music files", "files_sub": ("/data/music/<id>.<ext>", "one shared library"),
        "discord": "Discord", "discord_sub": ("gateway + voice (UDP)", "end-to-end encrypted (DAVE)"),
        "src": "Internet", "src_sub": ("YouTube, SoundCloud, Bandcamp", "added by URL, downloaded once"),
        "https": "HTTPS", "voice": "voice (Opus)", "state": "play, volume, ...", "queue": "job queue",
        "sql": "data", "measures": "measures", "writes": "saves", "fetch": "yt-dlp", "stream": "audio stream (Play here)",
        # playback
        "decides": "The server decides what plays",
        "decides_sub": "playlist, tag selection or one track  →  queue with where each track starts and ends and its loudness gain (app/playback.py)",
        "lane_discord": "On Discord (the bot)", "lane_here": "Here (the browser)", "either": "either / or",
        "d1": "Music files on the server", "d1s": "/data/music",
        "d2": "Layers: ffmpeg decodes ahead", "d2s": ("one thread per layer, so the 20 ms audio", "thread never waits for a pipe"),
        "d3": "Mixer", "d3s": ("equal-power cross-fade, loudness gain,", "volume that glides instead of jumping"),
        "d4": "Opus → Discord voice channel", "d4s": "heard by everyone in the channel",
        "h1": "Music files on the server", "h1s": "GET /api/tracks/{id}/stream",
        "h2": "<audio> elements", "h2s": ("the current track and the next one,", "prepared before the current ends"),
        "h3": "Web Audio graph", "h3s": ("track gain → fade envelope → master volume", "same curves and settings as the mixer"),
        "h4": "Speakers of this computer", "h4s": ("Discord is skipped; stays on while you", "switch tabs, stops on reload"),
        "settings": "Settings tab: cross-fade, volume glide, loudness, silence", "title_overview": "How Melomancer fits together",
        "title_playback": "Two ways to play the same playlist",
    },
    "pl": {
        "browser": "Przeglądarka", "panel": "Panel", "panel_sub": "czysty JavaScript, PL / EN",
        "local": "LocalPlayer", "local_sub": "Web Audio, „Odtwarzaj tutaj”", "speakers": "głośniki tego komputera",
        "cf": "Cloudflare", "cf_sub": ("Tunnel + Access", "(opcjonalnie)"),
        "container": "Jeden kontener: melomancer", "loop": "jeden proces Pythona, jedna pętla asyncio",
        "api": "FastAPI", "api_sub": "logowanie · biblioteka · playlisty · odtwarzacz · odtwarzanie lokalne",
        "bot": "BotManager", "bot_sub": ("jeden GuildPlayer na serwer", "Mikser: warstwy, przejścia,", "wzmocnienie głośności, glide"),
        "dl": "Downloader", "dl_sub": "yt-dlp + ffmpeg, limity",
        "ld": "Pomiar głośności", "ld_sub": "ffmpeg: głośność i cisza",
        "db": "SQLite", "db_sub": ("/data/melomancer.db", "użytkownicy, utwory, playlisty"),
        "files": "Pliki muzyczne", "files_sub": ("/data/music/<id>.<ext>", "jedna wspólna biblioteka"),
        "discord": "Discord", "discord_sub": ("gateway + głos (UDP)", "szyfrowanie end-to-end (DAVE)"),
        "src": "Internet", "src_sub": ("YouTube, SoundCloud, Bandcamp", "dodawane po URL, pobierane raz"),
        "https": "HTTPS", "voice": "głos (Opus)", "state": "graj, głośność, ...", "queue": "kolejka zadań",
        "sql": "dane", "measures": "mierzy", "writes": "zapisuje", "fetch": "yt-dlp", "stream": "strumień audio (Odtwarzaj tutaj)",
        "decides": "Serwer decyduje, co gra",
        "decides_sub": "playlista, wybór tagów albo jeden utwór  →  kolejka z miejscem startu i końca każdego utworu i jego wzmocnieniem głośności (app/playback.py)",
        "lane_discord": "Na Discordzie (bot)", "lane_here": "Tutaj (przeglądarka)", "either": "albo / albo",
        "d1": "Pliki muzyczne na serwerze", "d1s": "/data/music",
        "d2": "Warstwy: ffmpeg dekoduje z wyprzedzeniem", "d2s": ("jeden wątek na warstwę, więc wątek audio", "co 20 ms nigdy nie czeka na pipe"),
        "d3": "Mikser", "d3s": ("przejście equal-power, wzmocnienie głośności,", "głośność, która płynie zamiast skakać"),
        "d4": "Opus → kanał głosowy Discorda", "d4s": "słyszą wszyscy na kanale",
        "h1": "Pliki muzyczne na serwerze", "h1s": "GET /api/tracks/{id}/stream",
        "h2": "Elementy <audio>", "h2s": ("bieżący utwór i następny,", "przygotowany, zanim bieżący się skończy"),
        "h3": "Graf Web Audio", "h3s": ("wzmocnienie utworu → obwiednia przejścia → głośność", "te same krzywe i ustawienia co w mikserze"),
        "h4": "Głośniki tego komputera", "h4s": ("Discord jest pomijany; gra dalej przy zmianie", "kart, kończy się po odświeżeniu"),
        "settings": "Zakładka Ustawienia: przejście, płynność głośności, głośność, cisza", "title_overview": "Jak Melomancer jest zbudowany",
        "title_playback": "Dwa sposoby grania tej samej playlisty",
    },
}


def overview(lang: str, theme: str) -> str:
    t = TEXT[lang]
    s = Svg(1200, 700, theme)
    # the browser, and what is outside the container on the left
    s.box(30, 70, 210, 380, "", fill="none", stroke="blue", dash=True)
    s.text(135, 95, t["browser"], size=15, weight=700, color="blue")
    s.box(45, 110, 180, 70, t["panel"], t["panel_sub"], fill="blue_bg", stroke="blue")
    s.box(45, 330, 180, 80, t["local"], t["local_sub"], fill="blue_bg", stroke="blue")
    s.text(135, 435, t["speakers"], size=12, color="muted")
    s.box(262, 110, 130, 70, t["cf"], t["cf_sub"], fill="none", dash=True)
    s.box(30, 470, 210, 80, t["src"], t["src_sub"], fill="none", dash=True)
    # the container
    s.box(410, 30, 490, 640, "", fill="none", stroke="accent")
    s.text(655, 55, t["container"], size=15, weight=700, color="accent")
    s.box(440, 70, 430, 150, t["api"], t["api_sub"], fill="accent_bg", stroke="accent")
    s.box(440, 260, 210, 75, t["dl"], t["dl_sub"])
    s.box(440, 355, 210, 75, t["ld"], t["ld_sub"])
    s.box(670, 260, 200, 170, t["bot"], t["bot_sub"], fill="accent_bg", stroke="accent")
    s.box(440, 480, 210, 90, t["db"], t["db_sub"], fill="green_bg", stroke="green")
    s.box(670, 480, 200, 90, t["files"], t["files_sub"], fill="green_bg", stroke="green")
    s.text(655, 652, t["loop"], size=12, color="muted")
    # Discord, on the right
    s.box(950, 260, 220, 170, t["discord"], t["discord_sub"], fill="disc_bg", stroke="disc", color="disc_ink")
    # the panel talks to the API
    s.arrow([(225, 145), (262, 145)], color="blue")
    s.arrow([(392, 145), (440, 145)], color="blue", both=True)
    s.text(327, 100, t["https"], size=12, color="blue", weight=600)
    # inside
    s.arrow([(770, 220), (770, 260)], t["state"], at=(780, 245), anchor="start")
    s.arrow([(660, 220), (660, 525), (650, 525)], color="green")
    s.arrow([(545, 430), (545, 480)], t["measures"], at=(553, 462), anchor="start", color="green")
    s.arrow([(870, 345), (950, 345)], t["voice"], at=(910, 336))
    # downloads come in from the Internet; the audio goes out to the browser
    s.arrow([(240, 510), (425, 510), (425, 298), (440, 298)], t["fetch"], at=(332, 502), color="blue")
    s.arrow([(770, 570), (770, 625), (330, 625), (330, 370), (225, 370)], t["stream"], at=(550, 617), color="blue")
    return s.render()


def playback(lang: str, theme: str) -> str:
    t = TEXT[lang]
    s = Svg(1200, 640, theme)
    first, second = t["decides_sub"].split("  →  ")
    s.box(250, 25, 700, 105, t["decides"], (first + "  →", second, t["settings"]), fill="accent_bg", stroke="accent", color="accent")
    s.arrow([(420, 130), (420, 170), (300, 170), (300, 195)], color="accent")
    s.arrow([(780, 130), (780, 170), (900, 170), (900, 195)], color="accent")
    s.box(40, 195, 520, 425, "", fill="none", stroke="disc", dash=True)
    s.text(300, 225, t["lane_discord"], size=16, weight=700, color="disc_ink")
    s.box(640, 195, 520, 425, "", fill="none", stroke="blue", dash=True)
    s.text(900, 225, t["lane_here"], size=16, weight=700, color="blue")
    s.text(600, 410, t["either"], size=13, weight=700, color="muted")
    ys, hs = (245, 335, 435, 540), (60, 70, 75, 60)
    for x, color, bg, keys in ((70, "disc", "disc_bg", ("d1", "d2", "d3", "d4")), (670, "blue", "blue_bg", ("h1", "h2", "h3", "h4"))):
        for i, (key, y, h) in enumerate(zip(keys, ys, hs)):
            s.box(x, y, 460, h, t[key], t[key + "s"], fill=bg if i in (1, 2) else "grey", stroke=color)
        for (y, h), nxt in zip(zip(ys, hs), ys[1:]):
            s.arrow([(x + 230, y + h), (x + 230, nxt)], color=color)
    return s.render()


def placeholder(name: str, what: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1280, 720), "#2a2733")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
        small = ImageFont.truetype("DejaVuSans.ttf", 24)
    except OSError:
        font = small = ImageFont.load_default()
    draw.rectangle((24, 24, 1255, 695), outline="#6a43c2", width=4)
    for text, y, f, fill in ((f"docs/img/{name}", 280, font, "#ffffff"),
                             ("placeholder, replace this file with a screenshot of", 345, small, "#c9c4d8"),
                             (what, 385, small, "#c9c4d8")):
        w = draw.textlength(text, font=f)
        draw.text(((1280 - w) / 2, y), text, font=f, fill=fill)
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for lang in ("en", "pl"):
        for theme, suffix in (("light", ""), ("dark", "-dark")):
            (OUT / f"overview-{lang}{suffix}.svg").write_text(overview(lang, theme), encoding="utf-8")
            (OUT / f"playback-{lang}{suffix}.svg").write_text(playback(lang, theme), encoding="utf-8")
    for name, what in (("player.png", "the Player tab, ideally while a playlist plays"),
                       ("library.png", "the Library tab"),
                       ("playlists.png", "the Playlists tab with a set open")):
        target = OUT / name
        if not target.exists():
            target.write_bytes(placeholder(name, what))
    print("written to", OUT)


if __name__ == "__main__":
    main()
