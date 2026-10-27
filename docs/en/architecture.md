# Architecture

Languages: **English** · [Polski](../pl/architecture.md)

## Overview

One Python process, one container:

```
 browser ──HTTP──► FastAPI (app/main.py) ──► SQLite  /data/melomancer.db
                     │   ├─ routes_auth       login, users, system
                     │   ├─ routes_library    upload, tags, tracks, downloads
                     │   ├─ routes_playlists  sets, folders, playlists
                     │   └─ routes_player     connect, play, volume
                     │
                     ├─► BotManager (app/player.py) ──► discord.py ──► Discord gateway + voice (UDP)
                     │        └─ one GuildPlayer per server ──► ffmpeg ──► Opus
                     │
                     └─► Downloader thread (app/downloader.py) ──► yt-dlp + ffmpeg ──► library
 files: /data/music/<track id>.<ext>
```

The Discord client runs on the same asyncio loop as the web server. Database access is plain `sqlite3` with a short transaction per request. Playback decodes with `ffmpeg` and sends Opus to Discord through `discord.py` (with `davey` for the end-to-end encrypted voice protocol DAVE).

The browser side is a static page (`app/static`): plain JavaScript, no build step, Polish and English dictionaries in `i18n.js`.

## Modules

| File | Role |
|---|---|
| `app/main.py` | Application factory, security headers, first-run administrator, lifespan (starts and stops the bot and the downloader) |
| `app/config.py` | Settings from environment variables |
| `app/db.py` | Schema migrations (`PRAGMA user_version`) and the transaction helper |
| `app/security.py` | Argon2 hashing, session tokens, login throttle |
| `app/deps.py` | Authentication, administrator check, CSRF header check |
| `app/library.py` | Probing with ffprobe, de-duplication by SHA-256, tags, tombstones, track listing |
| `app/downloader.py` | URL validation, daily limit, queue worker around yt-dlp |
| `app/player.py` | `GuildPlayer` (queue, volume, fades, reconnect cool-down) and `BotManager` |
| `app/routes_*.py` | HTTP API |
| `app/cli.py` | `reset-password` recovery command |

## Data model

```
users ──< sessions
  │  └──< guild_access (user, guild id)
  │
  ├──< tracks (owner)  ──< track_tags (shared tags)
  │        │         └──< user_tags (user, track, personal tag)
  │        └──────────────┐
  └──< sets ──< playlists ──< playlist_items ─┘
         └──< set_groups (folder, optional) ──< playlists
downloads (user, url, status, track)
```

- **tracks** are never physically deleted. Deleting sets `deleted_at` and removes the file, so `playlist_items` keep pointing at a row with the old title (the greyed-out entry). A partial unique index keeps `sha256` unique among live tracks only, so re-uploading identical content revives the old row (same id).
- Sets, folders and playlists cascade on delete. Tracks are never touched by that.
- Positions are integers, rewritten when an order is saved.
- `tracks.loudness` (integrated LUFS) and `tracks.peak` (true peak, dBTP) are filled in by a background thread (`app/loudness.py`) that picks the newest unmeasured track, measures it with ffmpeg `loudnorm` (analysis only, run under `nice`) and sets `loudness_tried`. NULL means unknown: the track plays unchanged. At playback `BotManager.gain_for` turns the measurement into a gain (target minus loudness, limited by the maximum boost and by keeping the peak under -1 dBTP) that multiplies the volume of the `PCMVolumeTransformer`; nothing is re-encoded. The administrator's switch lives in the `app_settings` table and wins over `NORMALIZE_VOLUME`.
- `playlists.kind` is `manual` (rows in `playlist_items`) or `tags` (a JSON rule in `playlists.rule`: `{"tags": [...], "mode": "all"|"any"}`). A tag playlist stores no items, its tracks are computed with `library.tracks_for_tags` when it is shown or played, from shared tags and the owner's personal tags. `POST /player/{guild}/play` can also take `tags` and `mode` directly to play an unsaved selection.

## Permissions

| Resource | Read | Write |
|---|---|---|
| Library listing, preview | any user | n/a |
| Track title, shared tags, deletion | any user | owner, administrator |
| Personal tags | author only | author |
| Sets, folders, playlists | owner, administrator | owner, administrator |
| Download jobs | owner, administrator | owner, administrator |
| Users, server access | administrator | administrator |
| Player of a Discord server | users granted that server, administrators | same, one controller at a time |

## Playback

- One `GuildPlayer` per Discord server holds the queue (track ids, titles, paths), the order (shuffled or not), loop and shuffle flags, volume and the controlling user.
- Each track is played through `FFmpegPCMAudio` wrapped in `PCMVolumeTransformer`. Changing the volume sets the transformer's volume, so it applies within a frame (20 ms).
- **Fades.** When a playlist has a fade time, the ffmpeg filter `afade` fades each track in and out. Tracks follow one another, they do not overlap.
- **Generation counter.** Every started or stopped source bumps a counter. The `after` callback of a source that was replaced or stopped sees an old number and does nothing, which makes skip, stop and replace race-free.
- **Failures.** A track that ends within 1.5 s or errors counts as a failure. If every track of a queue fails in a row, playback stops instead of looping forever. Missing files are skipped.
- **Reconnects.** If the voice session ends unexpectedly, the player resets and refuses new connections for 35 seconds. `discord.py` keeps a timer for the old session for about 30 seconds, and joining again inside that window can get every new session killed. The same lesson is built into the `discord-stream-bot` project.
- **Idle leave.** A background task checks every 30 seconds; a channel without any human for `IDLE_LEAVE_MINUTES` is left.
- Discord ids are always strings in the API (JavaScript cannot hold 64-bit integers).

## Downloads

1. `POST /api/downloads` validates the address (https, allowed host), checks the daily limit and inserts a `queued` row.
2. The worker thread picks the oldest queued job, runs yt-dlp (audio only, one video, size limit) into a temporary folder, extracts Opus with ffmpeg and hands the file to the same ingest function as uploads (probe, hash, de-duplicate, store).
3. The row becomes `done` or `error` with a short reason. After a job the worker pauses `YTDLP_MIN_GAP_SECONDS`.
4. Jobs interrupted by a restart go back to the queue.

## HTTP API

All paths are under `/api`; state-changing requests need the header `X-Melomancer: 1`; every path except `/auth/login` and `/health` needs a session cookie.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET/PATCH /auth/me`, `POST /auth/password` |
| Users | `GET/POST /users`, `PATCH /users/{id}`, `PUT /users/{id}/guilds` |
| Library | `GET /tracks`, `POST /tracks/upload`, `PATCH/DELETE /tracks/{id}`, `GET /tracks/{id}/usage`, `GET /tracks/{id}/stream`, `PUT /tracks/{id}/my-tags`, `GET /tags` |
| Downloads | `GET/POST /downloads` (the list also carries live progress, elapsed seconds and the remaining pause; `POST` takes `tags` and `my_tags`), `DELETE /downloads/{id}` |
| Playlists | `GET/POST /sets`, `PATCH/DELETE /sets/{id}`, `POST /sets/{id}/playlists`, `PUT /sets/{id}/playlists/order`, `POST /sets/{id}/groups`, `PUT /sets/{id}/groups/order`, `PATCH/DELETE /groups/{id}`, `POST /groups/{id}/playlists`, `PUT /groups/{id}/playlists/order`, `GET/PATCH/DELETE /playlists/{id}`, `POST /playlists/{id}/copy`, `POST /playlists/{id}/items`, `PUT /playlists/{id}/order`, `PUT/DELETE /playlists/{id}/items/{item}` |
| Player | `GET /player/guilds`, `GET /player/{guild}/state`, `POST /player/{guild}/connect`, `disconnect`, `play`, `pause`, `resume`, `next`, `prev`, `jump`, `seek`, `stop`, `volume`, `PATCH /player/{guild}/options` |
| People | `GET /people` (active accounts other than yours, names only, for choosing who to copy to) |
| System | `GET /system`, `PATCH /system` (administrator: loudness switch), `GET /health` |

## Not built yet

Overlapping cross-fade between tracks, ambient layers under the music, a sound-effects board. The data model does not stand in the way of any of them.
