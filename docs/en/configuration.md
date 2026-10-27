# Configuration

Languages: **English** · [Polski](../pl/configuration.md)

Everything is configured with environment variables. Only `DISCORD_TOKEN` and the first administrator's password need your attention, the rest has sensible defaults.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `DISCORD_TOKEN` | (empty) | Bot token ([how to get it](discord-bot.md)). Without it the panel runs but the bot stays offline. |
| `ADMIN_USERNAME` | `admin` | Name of the first administrator. Used only when the database has no users. |
| `ADMIN_PASSWORD` | (empty) | Password of the first administrator, minimum 10 characters. Used only when the database has no users. If empty or too short, a random password is generated and written once to the container log. |
| `PUID` / `PGID` | `99` / `100` | Owner of the files in the data folder. The container starts as root only to fix ownership and then drops to this user. Use `1000` / `1000` on typical Linux hosts. |
| `TZ` | `UTC` | Time zone for log timestamps, for example `Europe/Warsaw`. |
| `DATA_DIR` | `/data` | Where the database and, by default, the music live. Mount a volume here. |
| `MUSIC_DIR` | `$DATA_DIR/music` | Optional separate folder for the audio files, for example to keep the library on a large array disk while the database stays on fast storage. Mount it and point this variable at it. |
| `MAX_UPLOAD_MB` | `300` | Largest single file accepted from an upload or a download. A Cloudflare Tunnel limits one request to 100 MB on the Free and Pro plans, see [Security](security.md). |
| `YTDLP_ENABLED` | `true` | `false` removes the download feature, uploads still work. |
| `YTDLP_DAILY_LIMIT` | `50` | Maximum downloads per rolling 24 hours (0 = no limit). Protects your IP address. |
| `YTDLP_MIN_GAP_SECONDS` | `20` | Pause between two downloads. |
| `YTDLP_ALLOWED_HOSTS` | `youtube.com,youtu.be,music.youtube.com,soundcloud.com,bandcamp.com` | Hosts that may be downloaded from (sub-domains included). Only `https://` addresses are accepted. |
| `YTDLP_COOKIES_FILE` | (empty) | Path inside the container to a cookies file for yt-dlp. Use only a throw-away account, never your main Google account. |
| `IDLE_LEAVE_MINUTES` | `30` | The bot leaves a voice channel after this many minutes with no human in it (0 = never). |
| `DEFAULT_VOLUME` | `0.4` | Starting volume, 0.0 to 1.5 (1.0 = 100 %). |
| `NORMALIZE_VOLUME` | `true` | Even out loudness while playing (see [Usage](usage.md)). This is only the starting value: an administrator can switch it in the panel, and the choice made there is stored and wins over this variable. |
| `NORMALIZE_TARGET_LUFS` | `-16` | The level tracks are brought to, from -30 to -8. |
| `NORMALIZE_MAX_BOOST_DB` | `6` | The most a quiet track is raised, from 0 to 12 dB. A track is never boosted into clipping, whatever this says. |
| `SESSION_HOURS` | `168` | How long a login lasts (7 days). |
| `COOKIE_SECURE` | `auto` | `auto` marks the login cookie as Secure when the panel is opened over https. `true` / `false` force it. |
| `LOGIN_MAX_FAILURES` | `5` | Failed logins per user name or address before a temporary block. |
| `LOGIN_WINDOW_SECONDS` | `300` | Length of that window and of the block. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |

## Data folder

```
/data
├── melomancer.db        SQLite database: users, tracks, tags, sets, playlists, download jobs
├── melomancer.db.before-v2   automatic copy made before a database upgrade (kept, delete it when all is well)
├── music/               audio files, named <track id>.<extension>
└── tmp/                 uploads and downloads in progress (emptied at start)
```

Audio files are stored under a generated name. The title you see in the panel lives in the database, so you cannot rename or move files by hand in this folder. Use the panel.

## Ports and network

| Port | Direction | Use |
|---|---|---|
| 8080/tcp | inbound | Web panel. Do not expose it directly to the internet. |
| 443/tcp and Discord voice UDP | outbound | Discord gateway and voice. Normal NAT is enough. |
| 443/tcp | outbound | yt-dlp downloads, only when downloads are enabled. |

## Reverse proxy and tunnel

The container starts uvicorn with proxy headers enabled, so the client address and `https` scheme from `X-Forwarded-*` headers are honoured. WebSockets are not used. See [Security](security.md) for a Cloudflare Tunnel with Access.
