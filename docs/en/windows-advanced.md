# Windows: details for advanced users

Languages: **English** · [Polski](../pl/windows-advanced.md)

The step-by-step guide is [Melomancer on Windows](windows.md). This page holds what that guide leaves out: every setting, how signing in works, where things are, what is different from the container, the technical side of the problems, and how the package is built.

## The settings file

`%LOCALAPPDATA%\Melomancer\config.toml` lists every setting with an explanation in Polish and English; the package folder holds the same list as `config.example.toml`. The shortcut `Ustawienia - Settings.cmd` opens the file in Notepad. Remove the `#` in front of a line to use it, save the file, then close and start Melomancer again. Put paths in single quotes: `music_dir = 'D:\Music\Melomancer'`. The file must be saved as UTF-8 (the default of Notepad in Windows 11). When a newer version has settings your file does not mention yet, Melomancer appends them at the end as commented lines under a heading with the version, and says so in the window; it never changes a line you wrote.

| Setting | Default | Meaning |
|---|---|---|
| `discord_token` | (empty) | Bot token. Without it the bot stays offline. |
| `discord_client_id` | (empty) | Application ID of the bot, for the **Add the bot to a server** link in Settings. |
| `admin_username`, `admin_password` | `admin`, (empty) | The first administrator, created only while the database is empty. Without a password a random one is shown once in the window (needed only if you switch `auto_login` off or open the panel from another computer). |
| `host`, `port` | `127.0.0.1`, `8080` | Where the panel listens. `127.0.0.1` is this computer only (so Windows has no firewall question); `host = '0.0.0.0'` opens the panel to your network and Windows will ask about the firewall. |
| `auto_login` | `true` | Signs this computer in as the administrator without a password, see below. |
| `data_dir`, `music_dir` | `%LOCALAPPDATA%\Melomancer\data`, a `music` folder inside it | Where the database and the audio files live. |
| `ytdlp_enabled`, `ytdlp_daily_limit`, `ytdlp_min_gap_seconds` | `true`, `50`, `20` | Downloads from YouTube and similar sites: on or off, the limit per 24 hours, the pause between two. |
| `max_upload_mb` | `300` | The largest single file, in MB. |
| `idle_leave_minutes` | `30` | The bot leaves a voice channel with nobody in it after this many minutes (0 means never). |
| `default_volume` | `0.4` | Starting volume, 0.0 to 1.5. |
| `log_level` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |

Every other variable from [Configuration](configuration.md) works too, written in lower case. An environment variable that is already set wins over the file.

## Where things are

| What | Where |
|---|---|
| The program | The folder you unpacked (can be deleted and replaced) |
| Settings file | `%LOCALAPPDATA%\Melomancer\config.toml` |
| Database and, by default, the music | `%LOCALAPPDATA%\Melomancer\data` |

`%LOCALAPPDATA%` is `C:\Users\<you>\AppData\Local`. To keep the music elsewhere (a bigger disk), copy the contents of `data\music` to the new folder, set `music_dir` to it and start again.

## Signing in

By default the panel lets **this computer** in as the administrator without a password (`auto_login = true`): the browser that Melomancer opens is already signed in, there is no login page and no **Log out** item. Set `auto_login = false` in `config.toml` to ask for a password, as in the container.

It is refused, whatever the file says, unless all of this holds: the panel listens on `127.0.0.1` only (`host = '0.0.0.0'` switches it off and the window says so), the request comes from the loopback address, its `Host` header is `127.0.0.1` or `localhost` (a web page on another site that points its own name at your computer is refused), and there is no proxy or tunnel header on it. A Cloudflare Tunnel or a reverse proxy on the same computer therefore never gets in without a password. What it does not stop: any program, or any other Windows account, on this computer can open the panel as the administrator. On a computer that several people use, set `auto_login = false`. Details: [Security](security.md).

## Start with Windows

Melomancer has no autostart of its own yet. To start it when you sign in to Windows: press Win+R, type `shell:startup` and press Enter, then put a shortcut to `Melomancer.cmd` in the folder that opens (right-click `Melomancer.cmd`, **Show more options**, **Create shortcut**, then move the shortcut there). The black window opens at every sign-in.

## What is different from the container

- The panel listens on 127.0.0.1 by default and there is no tunnel. **Play here** works as before.
- A track that is being played or streamed at that moment cannot be deleted from disk on Windows: it disappears from the library, a note is logged and the file stays in the music folder.
- The load tiles in Settings show the Melomancer process and its ffmpeg programs (there is no container to measure), and "Update available" tells you to download the newer package instead of updating an image.
- The black window may show harmless messages from the web stack; the Windows "connection was reset" message that appears when a browser drops a connection is hidden.

## Problems

| What you see | What it means |
|---|---|
| `... is not valid TOML` | A line in `config.toml` is written wrongly (a missing quote, for example). Fix it, or delete the file to get a fresh one. |
| `... is not saved as UTF-8` | In Notepad use **Save As** and choose the encoding **UTF-8**. |
| The window talks about an address already in use | Another program uses port 8080. Set `port = 8081` in `config.toml` and open http://127.0.0.1:8081/. |
| `DISCORD_TOKEN is not set` | The token is missing from `config.toml`. |
| The bot logs in but is silent | See [Creating the Discord bot](discord-bot.md) and [Troubleshooting](troubleshooting.md). The window prints `Voice connection complete` when the connection works. |
| Downloads fail | Update to the newest release (a new one is made every Monday with the newest yt-dlp); mind `ytdlp_daily_limit` and `ytdlp_min_gap_seconds`. |
| The antivirus quarantines files | The package is unsigned and some antivirus programs flag unsigned programs. Allow the folder, or use the container. |
| Windows 11 blocks the program outright | Smart App Control blocks unsigned programs without a way to run anyway. It can be switched off in Windows Security, but that is a decision about the whole computer. |

## How the package is built

`scripts/windows/build_package.py` downloads the official embeddable Python of the same version as the runner, installs `requirements.txt` into it as wheels, adds the LGPL build of ffmpeg (https://github.com/BtbN/FFmpeg-Builds) and deno (the JavaScript runtime yt-dlp needs for YouTube), writes the launcher files and zips the folder. `scripts/windows/smoke_test.py` then starts the unpacked package from a folder with Polish letters in its name, logs in, uploads a file whose tag has Polish letters, waits for the loudness analysis and deletes the track. The workflow `windows.yml` runs the whole test suite on `windows-latest` for every pull request and keeps the package as an artifact of the run; `windows-release.yml` builds the package for each release and attaches it. More: [Development](development.md). What has not been tried: a Windows 10 computer, a computer with Smart App Control switched on, and Discord voice for longer than a short session.
