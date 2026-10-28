# Troubleshooting

Languages: **English** · [Polski](../pl/troubleshooting.md)

Start with the log, it usually says what is wrong:

```
docker logs --tail 100 melomancer
```

For more detail set `LOG_LEVEL=DEBUG` and restart the container.

## The bot

**"The Discord bot is off: DISCORD_TOKEN is not set."**
The variable is empty or missing in the container settings. Set it and restart.

**"Discord rejected the bot token."**
The token is wrong or was reset. Copy a new one: Developer Portal, your application, **Bot**, **Reset Token** (see [Creating the Discord bot](discord-bot.md)). Paste it without spaces or quotes.

**The bot is online but my server is not in the Player tab.**
- The bot was not invited to that server. Use the invite link from [Creating the Discord bot](discord-bot.md).
- You are not an administrator and nobody ticked the server for you (Users tab, **Servers**).
- Only voice channels where the bot may **Connect** are listed. Check the channel's permissions.

**"The bot lacks permissions in that channel."**
Allow View Channel, Connect and Speak for the bot's role in that voice channel (a permission override on the channel can deny what the server allows).

**"The previous voice session has only just ended. Try again in N s."**
This is the deliberate 35 second wait after the voice session dropped. Wait and press again. If it keeps dropping, look for `Voice session in guild ... ended unexpectedly` in the log and check the network between the server and Discord.

**Connected, but no sound.**
- Is something actually playing (the player shows the track and a moving bar)?
- Volume slider at 0 %, or the bot muted by you in Discord. Right-click the bot in the channel to see its user volume.
- The log shows `File missing for ...`: the audio file was lost from the data folder. Replace or re-upload it.
- Check that the first lines of the log say `discord.py 2.7.x, davey ...` and not `davey MISSING`. Voice needs both since Discord's end-to-end encryption requirement (https://docs.discord.com/developers/topics/voice-connections). Pull the newest image if it is missing.

**Another user says "Someone else is controlling this server right now."**
Another user's playlist is playing on that server. They (or an administrator) press **Stop**.

## Uploads

**"The file is too large for the server or tunnel."** (HTTP 413)
Cloudflare allows 100 MB per request on the Free and Pro plans. Upload that file from inside your network, for example `http://<server address>:8080`, or split it. See [Security](security.md).

**"That is not an audio file."** / **"Unsupported file type."**
Only mp3, ogg, opus, flac, wav, m4a, aac and webm files that contain an audio stream are accepted.

## Downloads

Open the Downloads tab, the error text is shown next to the job.

**A download seems stuck.**
Look at the stage text under the title. "Preparing" can last 10 to 30 seconds (the site is contacted and a JavaScript challenge is solved), "Downloading" shows a percentage, and a queued job shows "starts in N s": that is the deliberate pause between downloads (`YTDLP_MIN_GAP_SECONDS`). The log has a line for the start and the end of every download with its duration, and every step yt-dlp reports in between with a time stamp (for example `yt-dlp: [youtube] Extracting URL`, downloading the page, solving the JavaScript challenge), so you can see which step takes the time:

```
docker logs --tail 50 melomancer
```

**"Sign in to confirm you're not a bot".**
YouTube is refusing requests from your IP address for now. Stop downloading for a few days, lower `YTDLP_DAILY_LIMIT`, raise `YTDLP_MIN_GAP_SECONDS`. Playing music that is already in the library is not affected. Do not feed it the cookies of your main account.

**"Requested format is not available", errors about a JavaScript runtime or a "challenge".**
yt-dlp is out of date or cannot run its JavaScript helper. Pull the newest image (a new one is built every Monday) and check the runtime inside:

```
docker exec melomancer deno --version
```

**"The daily download limit has been reached."**
`YTDLP_DAILY_LIMIT` in the last 24 hours. Raise it or wait.

## Containers, files and the database

**`PermissionError` for `/data`.**
Set `PUID` and `PGID` to the owner of the data folder on the host (Unraid: 99 and 100). The container fixes ownership of the data folder at start when it runs as root.

**"database is locked", or a corrupted database on Unraid.**
Move the data folder from `/mnt/user/...` to a direct pool path such as `/mnt/nvme/appdata/melomancer`. SQLite does not like the FUSE user share.

**Unraid cannot pull the image: "unauthorized".**
The official image is public, so this only happens with a private package, for example the image of your own fork, when the registry login is gone (it does not survive a reboot on Unraid). See the first section of [Installation](installation.md): log in again, script the login, or make the package public.

**The panel looks old after an update.**
Reload the page with Ctrl+F5. The page and its scripts carry the version number, so this normally happens by itself.

**I forgot the administrator password.**

```
docker exec -it melomancer python -m app.cli reset-password admin
```

**I locked myself out with too many wrong passwords.**
The block lasts 5 minutes (`LOGIN_WINDOW_SECONDS`) and is reset by restarting the container.
