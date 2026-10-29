# Windows (experimental)

Languages: **English** · [Polski](../pl/windows.md)

Melomancer also runs on a Windows 10 or 11 computer without Docker: the same application, started from a folder you unpack. This is the first, experimental step. There is no installer, no tray icon and no self-update yet, and the package is not signed.

## Get it and start it

The package is built by the workflow **Windows package (experimental)** (`.github/workflows/windows.yml`) and is an artifact of its runs, not a release: open the run in the **Actions** tab of https://github.com/RadzuPL/melomancer/actions, download `Melomancer-win64-<version>` at the bottom of the page (a GitHub account is needed) and unpack it where you like, for example `C:\Melomancer` (not in Program Files).

Start `Melomancer.cmd`. A window opens and, when the server is up, the browser opens the panel at http://127.0.0.1:8080/. Closing the window stops Melomancer.

Because the file is not signed, Windows may show "Windows protected your PC": **More info**, then **Run anyway**. On a fresh Windows 11 with Smart App Control switched on, unsigned programs can be blocked outright; that is a known limit of this experiment.

## Settings

The first start creates `%LOCALAPPDATA%\Melomancer\config.toml`, full of commented examples, and prints where it is. Remove the `#` in front of a line, save, start Melomancer again. Put your bot token there (`discord_token`, see [Discord bot](discord-bot.md)); without it the panel works and the bot stays offline.

Every key is the lower-case name of an environment variable from [Configuration](configuration.md), plus `host` and `port` for the launcher. An environment variable that is already set wins over the file. Use single quotes for paths: `music_dir = 'D:\Music\Melomancer'`.

| What | Where |
|---|---|
| Settings file | `%LOCALAPPDATA%\Melomancer\config.toml` |
| Database (and the music, unless `music_dir` is set) | `%LOCALAPPDATA%\Melomancer\data` |
| First administrator | `admin_username` and `admin_password` in the file; without a password a random one is shown once in the window |
| Address | `127.0.0.1` (this computer only, so Windows has no firewall question); `host = '0.0.0.0'` opens it to your network |

## What is different from the container

- The panel listens on 127.0.0.1 by default and there is no tunnel. Playing in the browser ("Play here") works as before.
- A track that is being played or streamed cannot be deleted from disk on Windows: the track is removed from the library and a note is logged, the file stays in the music folder.
- The load tiles in Settings show the Melomancer process and its ffmpeg children (there is no container to measure).

## How the package is built

`scripts/windows/build_package.py` downloads the official embeddable Python of the same version as the runner, installs `requirements.txt` into it as wheels, adds the LGPL build of ffmpeg (https://github.com/BtbN/FFmpeg-Builds) and deno (the JavaScript runtime yt-dlp needs for YouTube), and zips the folder. `scripts/windows/smoke_test.py` then starts the unpacked package from a folder with Polish letters in its name, logs in, uploads a file whose tag has Polish letters, waits for the loudness analysis and deletes the track. The workflow runs the whole test suite on `windows-latest` first. Nothing here has been tried against a real Discord voice channel on Windows.
