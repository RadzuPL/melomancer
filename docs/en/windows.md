# Melomancer on Windows (experimental)

Languages: **English** · [Polski](../pl/windows.md)

Melomancer runs on a Windows 10 or 11 computer without Docker: the same application as in the container, started from a folder you unpack. This page is for someone who wants to try it.

**Status: experimental.** Tried so far on Windows 11 with a real Discord bot: music over Discord voice, playing in the browser, downloading from YouTube, playlists, the settings file. There is no installer, no tray icon and no built-in self-update yet, and the program is not digitally signed, so Windows asks for confirmation when you start it (see step 3).

## What you need

- Windows 10 or 11, 64-bit. No administrator rights, no Docker, no WSL, nothing to install.
- About 140 MB to download; unpacked it takes a few hundred MB (a Python, ffmpeg and a JavaScript runtime are inside). Your music comes on top.
- Internet access (Discord, downloads, the check for a newer version).
- For music in a Discord voice channel: a Discord bot of your own and its token, see step 5. Without a bot the panel and **Play here** (the sound comes out of the speakers of this computer) work anyway.

## 1. Download

Every release of Melomancer carries the Windows package as an attachment, `Melomancer-win64-<version>.zip` (about 140 MB). It appears a few minutes after the release itself, and its link is in the release notes ("Windows package"). Releases: https://github.com/RadzuPL/melomancer/releases

If the newest release has no such file yet, wait a few minutes. If it still does not, that build failed: take the previous release.

## 2. Unpack

Right-click the zip and choose **Extract all**, or use any unpacking program. Pick a plain folder you can write to, for example `C:\Melomancer`; avoid Program Files. The folder you get contains `Melomancer.cmd`, `Ustawienia - Settings.cmd`, `config.example.toml`, `README-WINDOWS.txt` and the program itself (`runtime`, `app`, `bin`).

## 3. First start

Double-click `Melomancer.cmd`. Because the program is not signed, Windows shows the window **Open File - Security Warning** (in a Polish Windows: "Otwieranie pliku - ostrzeżenie o zabezpieczeniach") with "Unable to verify the publisher" and the publisher "Unknown publisher". That is expected.

1. Untick **Always ask before opening this file**, so that Windows does not ask again.
2. Click **Run**.

If Windows shows the blue SmartScreen page "Windows protected your PC" instead, click **More info** and then **Run anyway**. On a fresh Windows 11 with **Smart App Control** switched on, unsigned programs can be blocked outright; that is a known limit of this experiment (it can be switched off in Windows Security, but that is a decision about your whole computer).

A black window opens and prints something like this:

```
Melomancer 0.6.39
Settings file: C:\Users\YourName\AppData\Local\Melomancer\config.toml  (created now, edit it to add your Discord bot token)
Panel: http://127.0.0.1:8080/   (Ctrl+C or closing this window stops it)
```

After a few seconds your browser opens the panel. You are already signed in as the administrator (see "Signing in" below). **Keep the black window open while you use Melomancer**; closing it, or pressing Ctrl+C in it, stops the program.

## 4. Music without Discord

You can already use everything except the bot:

- **Library** tab: upload files, or paste a YouTube, SoundCloud or Bandcamp address in the **Downloads** tab (the tools it needs are in the package).
- **Playlists** tab: make a set and a playlist.
- **Player** tab: press **Play here** and then a playlist. The sound comes from the speakers of this computer and switching tabs of the panel does not stop it.

How the panel works in detail: [Using the panel](usage.md).

## 5. Connect the Discord bot

You need two values from the Discord Developer Portal: the **bot token** and the **Application ID**. How to create the bot, what to switch off and how to invite it: [Creating the Discord bot](discord-bot.md), steps 1 to 4. In short: https://discord.com/developers/applications, your application, **General Information** (copy **APPLICATION ID**) and **Bot** then **Reset Token** (copy the token, Discord shows it once).

1. Double-click `Ustawienia - Settings.cmd` in the Melomancer folder. The settings file opens in Notepad. (Without the shortcut: press Win+R, type the command below and press Enter.)

   ```
   notepad %LOCALAPPDATA%\Melomancer\config.toml
   ```

2. Find the two lines `# discord_token = ''` and `# discord_client_id = ''`. Remove the `#` and the space after it, and put the values between the single quotes:

   ```
   discord_token = 'the-token-you-copied'
   discord_client_id = '123456789012345678'
   ```

3. Save (Ctrl+S) and close Notepad. The file must stay saved as UTF-8 (the default of Notepad in Windows 11).
4. Close the black Melomancer window and start `Melomancer.cmd` again. The window now says that the bot logged in: `Logged in as <name of your bot>`.
5. In the panel open **Settings**: the bot tile shows **Running**, and, thanks to the Application ID, a link **Add the bot to a server**. Use it to invite the bot (you need the "Manage Server" permission on that Discord server).
6. In the **Player** tab choose the server and the voice channel, click **Connect**, then press a playlist.

The token is a password: never paste it in a message, an issue or a screenshot. If it ever leaks, press **Reset Token** again in the Developer Portal and put the new one in the file.

## The settings file

`%LOCALAPPDATA%\Melomancer\config.toml` lists every setting with an explanation in Polish and English; the package folder holds the same list as `config.example.toml`. Remove the `#` in front of a line to use it, save the file, then close and start Melomancer again. Put paths in single quotes: `music_dir = 'D:\Music\Melomancer'`. When a newer version has settings your file does not mention yet, Melomancer appends them at the end as commented lines under a heading with the version, and says so in the window; it never changes a line you wrote.

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

`%LOCALAPPDATA%` is `C:\Users\<you>\AppData\Local`. Everything you made lives there, not in the program folder, which is why updating is simple. To keep the music elsewhere (a bigger disk), copy the contents of `data\music` to the new folder, set `music_dir` to it and start again.

## Signing in

By default the panel lets **this computer** in as the administrator without a password (`auto_login = true`): the browser that Melomancer opens is already signed in, there is no login page and no **Log out** item. Set `auto_login = false` in `config.toml` to ask for a password, as in the container.

It is refused, whatever the file says, unless all of this holds: the panel listens on `127.0.0.1` only (`host = '0.0.0.0'` switches it off and the window says so), the request comes from the loopback address, its `Host` header is `127.0.0.1` or `localhost` (a web page on another site that points its own name at your computer is refused), and there is no proxy or tunnel header on it. A Cloudflare Tunnel or a reverse proxy on the same computer therefore never gets in without a password. What it does not stop: any program, or any other Windows account, on this computer can open the panel as the administrator. On a computer that several people use, set `auto_login = false`. Details: [Security](security.md).

## Updating

The **Settings** tab, group **Updates**, tells you when a newer release exists ("Update available"). There is no built-in updater yet, so:

1. Close the black Melomancer window.
2. Download the newer package and unpack it into a **new** folder (for example `C:\Melomancer-0.7.0`).
3. Start `Melomancer.cmd` from the new folder. Windows asks about the unsigned file once more, because it is a new location. Your settings and data are found where they were.
4. When all is well, delete the old folder.

Downloading from YouTube depends on the current yt-dlp, which changes often: a new release is made every Monday with the newest one, so when downloads stop working, update first.

## Start with Windows (optional)

Melomancer has no autostart of its own yet. To start it when you sign in to Windows: press Win+R, type `shell:startup` and press Enter, then put a shortcut to `Melomancer.cmd` in the folder that opens (right-click `Melomancer.cmd`, **Show more options**, **Create shortcut**, then move the shortcut there). The black window opens at every sign-in.

## Stop and remove

Close the black window (or press Ctrl+C in it). To remove Melomancer, delete the program folder. To remove your library and settings as well, delete `%LOCALAPPDATA%\Melomancer`: **that deletes the music you uploaded and the playlists**, so copy what you want to keep first.

## What is different from the container

- The panel listens on 127.0.0.1 by default and there is no tunnel. **Play here** works as before.
- A track that is being played or streamed at that moment cannot be deleted from disk on Windows: it disappears from the library, a note is logged and the file stays in the music folder.
- The load tiles in Settings show the Melomancer process and its ffmpeg programs (there is no container to measure), and "Update available" tells you to download the newer package instead of updating an image.
- The black window may show harmless messages from the web stack; the Windows "connection was reset" message that appears when a browser drops a connection is hidden.

## Problems

| What you see | What to do |
|---|---|
| Windows asks about the publisher every time | Untick **Always ask before opening this file** in that window before you click **Run**. |
| The blue "Windows protected your PC" page | **More info**, then **Run anyway**. |
| Nothing starts, Windows or the antivirus says it is blocked or quarantined | The program is unsigned, and unsigned programs are sometimes blocked or flagged by mistake. Allow the folder in your antivirus or in Windows Security, or use the container instead. |
| The window shows an error and waits | `Melomancer.cmd` waits so that you can read it. `... is not valid TOML` means a line in `config.toml` is written wrongly (a missing quote, for example): fix it, or delete the file to get a fresh one. `... is not saved as UTF-8`: in Notepad use **Save As** and choose **UTF-8**. |
| The panel does not open in the browser | Open http://127.0.0.1:8080/ yourself. If the window says that the address is already in use, another program uses port 8080: set `port = 8081` in `config.toml` and open http://127.0.0.1:8081/. |
| The bot tile says it is not running | The window and the tile say why: `DISCORD_TOKEN is not set` (put the token in the file), or the login failed (the token is wrong or was reset: copy a new one). |
| The Player tab lists no servers | The bot is not on any server yet: use **Add the bot to a server** in Settings (needs `discord_client_id`). |
| The bot is connected but there is no sound | Check its permissions in that voice channel, see [Creating the Discord bot](discord-bot.md) and [Troubleshooting](troubleshooting.md). The window prints `Voice connection complete` when the connection works. |
| Downloads from YouTube fail | Update to the newest release (see Updating); mind the limits `ytdlp_daily_limit` and `ytdlp_min_gap_seconds`. |
| Something else | Report it: https://github.com/RadzuPL/melomancer/issues. Say what you did, which version and build the first line of the window shows, and copy the last lines of the window. **Never include the bot token.** |

## For developers: how the package is built

`scripts/windows/build_package.py` downloads the official embeddable Python of the same version as the runner, installs `requirements.txt` into it as wheels, adds the LGPL build of ffmpeg (https://github.com/BtbN/FFmpeg-Builds) and deno (the JavaScript runtime yt-dlp needs for YouTube), writes the launcher files and zips the folder. `scripts/windows/smoke_test.py` then starts the unpacked package from a folder with Polish letters in its name, logs in, uploads a file whose tag has Polish letters, waits for the loudness analysis and deletes the track. The workflow `windows.yml` runs the whole test suite on `windows-latest` for every pull request and keeps the package as an artifact of the run; `windows-release.yml` builds the package for each release and attaches it. More: [Development](development.md). What has not been tried: a Windows 10 computer, a computer with Smart App Control switched on, and Discord voice for longer than a short session.
