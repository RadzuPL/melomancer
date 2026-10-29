# Configuration

Languages: **English** · [Polski](../pl/configuration.md)

Everything is configured with environment variables. Only `DISCORD_TOKEN` and the first administrator's password need your attention, the rest has sensible defaults.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `DISCORD_TOKEN` | (empty) | Bot token ([how to get it](discord-bot.md)). Without it the panel runs but the bot stays offline. |
| `DISCORD_CLIENT_ID` | (empty) | Optional. The Application ID of the bot ([where to find it](discord-bot.md)). With it the **Settings** tab shows a link that adds the bot to a server; empty means no link. |
| `ADMIN_USERNAME` | `admin` | Name of the first administrator. Used only when the database has no users. |
| `ADMIN_PASSWORD` | (empty) | Password of the first administrator, minimum 10 characters. Used only when the database has no users. If empty or too short, a random password is generated and written once to the container log. |
| `PUID` / `PGID` | `99` / `100` | Owner of the files in the data folder. The container starts as root only to fix ownership and then drops to this user. Use `1000` / `1000` on typical Linux hosts. |
| `TZ` | `UTC` | Time zone for log timestamps, for example `Europe/Warsaw`. |
| `DATA_DIR` | `/data` | Where the database and, by default, the music live. Mount a volume here. |
| `MUSIC_DIR` | `$DATA_DIR/music` | Optional separate folder for the audio files, for example to keep the library on a large array disk while the database stays on fast storage. It is a path **inside the container**: mount a host folder there (use `/music`) and set this variable to it. See [Music on another disk](#music-on-another-disk). |
| `MAX_UPLOAD_MB` | `300` | Largest single file accepted from an upload or a download. A Cloudflare Tunnel limits one request to 100 MB on the Free and Pro plans, see [Security](security.md). |
| `YTDLP_ENABLED` | `true` | `false` removes the download feature, uploads still work. |
| `YTDLP_DAILY_LIMIT` | `50` | Maximum downloads per rolling 24 hours (0 = no limit). Protects your IP address. |
| `YTDLP_MIN_GAP_SECONDS` | `20` | Pause between two downloads. |
| `YTDLP_ALLOWED_HOSTS` | `youtube.com,youtu.be,music.youtube.com,soundcloud.com,bandcamp.com` | Hosts that may be downloaded from (sub-domains included). Only `https://` addresses are accepted. |
| `YTDLP_COOKIES_FILE` | (empty) | Path inside the container to a cookies file for yt-dlp. Use only a throw-away account, never your main Google account. |
| `IDLE_LEAVE_MINUTES` | `30` | The bot leaves a voice channel after this many minutes with no human in it (0 = never). |
| `DEFAULT_VOLUME` | `0.4` | Starting volume, 0.0 to 1.5 (1.0 = 100 %). |
| `SESSION_HOURS` | `168` | How long a login lasts (7 days). |
| `COOKIE_SECURE` | `auto` | `auto` marks the login cookie as Secure when the panel is opened over https. `true` / `false` force it. |
| `LOGIN_MAX_FAILURES` | `5` | Failed logins per user name or address before a temporary block. |
| `LOGIN_WINDOW_SECONDS` | `300` | Length of that window and of the block. |
| `AUTO_LOGIN` | `false` | Lets the administrator in without a password, for requests from this very computer only (loopback address, a loopback `Host`, no proxy headers). The [Windows package](windows.md) switches it on by itself; leave it off in a container, where it could not apply anyway. See [Security](security.md). |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |

## Data folder

```
/data                         DATA_DIR: mount a fast disk here
├── melomancer.db             SQLite database: users, tracks, tags, sets, playlists, download jobs
├── melomancer.db.before-v2   automatic copy made before a database upgrade (kept, delete it when all is well)
├── tmp/                      uploads and downloads in progress (emptied at start)
└── music/                    audio files, named <track id>.<extension>   (only when MUSIC_DIR is not set)

/music                        MUSIC_DIR (optional): audio files, in a folder of their own, for example on a large disk
```

Without `MUSIC_DIR` the audio files are in `music/` inside the data folder, which is the simplest setup. With it they live in the folder you point it at, and the data folder keeps only the database and temporary files.

Audio files are stored under a generated name. The title you see in the panel lives in the database, so you cannot rename or move files by hand in these folders. Use the panel.

## Music on another disk

Use this when the library is big and the data folder sits on a small fast disk (an NVMe pool on Unraid, for example). `MUSIC_DIR` is a path inside the container, so two things have to match: a **mount** from a folder on the host to `/music`, and `MUSIC_DIR=/music`. A variable alone is not enough: without the mount the files would be written inside the container itself, and lost when it is recreated.

- **Docker:** add `-v /mnt/user/rpg/melomancer:/music -e MUSIC_DIR=/music` to the `docker run` command.
- **Compose:** add `- /mnt/user/rpg/melomancer:/music` under `volumes` and `MUSIC_DIR: /music` under `environment`.
- **Unraid:** the template has a **Music library** path (container path `/music`): set its host path, for example to `/mnt/user/rpg/melomancer`. Leave the variable **Music folder in the container** at `/music`.

To move an existing library, stop the container first, then copy the old folder, check the copy and only then delete the old one (on Unraid, from its terminal; adjust the two paths):

```
rsync -a --info=progress2 /mnt/user/appdata/melomancer/music/ /mnt/user/rpg/melomancer/
```

```
rsync -avnc /mnt/user/appdata/melomancer/music/ /mnt/user/rpg/melomancer/
```

The second command only compares the two folders and prints no file names when they are identical. Then remove the old folder and start the container with the new settings. Afterwards play a track and look for ⚠ marks in the playlists, which mean that a file was not found (usually the mount and `MUSIC_DIR` do not match).

Two things to remember: the backup has to cover this folder too, because it is no longer inside the data folder, and a disk that spins down needs a few seconds to wake up for the first track.

## Ports and network

| Port | Direction | Use |
|---|---|---|
| 8080/tcp | inbound | Web panel. Do not expose it directly to the internet. |
| 443/tcp and Discord voice UDP | outbound | Discord gateway and voice. Normal NAT is enough. |
| 443/tcp | outbound | yt-dlp downloads, only when downloads are enabled. |
| 443/tcp | outbound | `api.github.com`: the check for a newer release (Settings, can be switched off). |

## Reverse proxy and tunnel

The container starts uvicorn with proxy headers enabled, so the client address and `https` scheme from `X-Forwarded-*` headers are honoured. WebSockets are not used. See [Security](security.md) for a Cloudflare Tunnel with Access.
