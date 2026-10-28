# Installation

Languages: **English** · [Polski](../pl/installation.md)

Melomancer is one container, and a container is currently the only way to run it that this documentation describes (a plain Windows computer, or a desktop wrapper, are not ruled out for later). It needs outbound internet access only (Discord over HTTPS/WebSocket and UDP for voice), no inbound ports for the bot. The web panel listens on port **8080**.

Before you start you need a **Discord bot token**. Create the bot first: [Creating the Discord bot](discord-bot.md).

## 1. Get the image

The image is built by GitHub Actions and published to the GitHub Container Registry:

```
ghcr.io/radzupl/melomancer:latest
```

The package is public, so no registry login is needed: `docker pull` and the Unraid template work as they are.

If you fork the repository and build your own image, GitHub makes the new package private by default. Then either make it public (package page, Package settings, Danger Zone, Change package visibility), or log in on the machine that runs Docker. For the login create a classic personal access token with only the `read:packages` scope at https://github.com/settings/tokens, then run:

```
docker login ghcr.io -u YOUR_GITHUB_NAME
```

Paste the token when asked for the password.

> Unraid: the root file system lives in RAM, so a `docker login` typed in the terminal is usually forgotten after a reboot and later updates fail with "unauthorized". A public package, or a User Scripts job that runs `docker login` at array start, avoids that.

## 2. Docker run

Replace the token, the password and the host folder. `PUID` and `PGID` decide who owns the files in the data folder.

```
docker run -d \
  --name melomancer \
  --restart unless-stopped \
  -p 8080:8080 \
  -v /srv/melomancer:/data \
  -e DISCORD_TOKEN='PASTE_THE_BOT_TOKEN_HERE' \
  -e ADMIN_USERNAME='admin' \
  -e ADMIN_PASSWORD='choose-a-password-of-10-or-more-characters' \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ='Europe/Warsaw' \
  ghcr.io/radzupl/melomancer:latest
```

Check that it started:

```
docker logs melomancer
```

You should see `Logged in as <bot name>` and no errors. Open http://localhost:8080/ (or the address of the machine) and log in.

## 3. Docker Compose

Download or copy `docker-compose.yml` and `.env.example` from the repository into one folder, then create the settings file:

```
cp .env.example .env
```

Edit `.env`: set `DISCORD_TOKEN`, `ADMIN_PASSWORD` (at least 10 characters), and `PUID` / `PGID` (run `id -u` and `id -g` to see yours). Then start it:

```
docker compose up -d
```

Logs:

```
docker compose logs -f melomancer
```

The music library and the database end up in `./data` next to the compose file.

## 4. Unraid

Unraid users normally add containers from a template in the Docker tab. The template ships in the repository as `unraid/my-melomancer.xml`.

1. Download `unraid/my-melomancer.xml` from the repository (https://github.com/RadzuPL/melomancer/blob/main/unraid/my-melomancer.xml, use the Raw button).
2. Copy it to the Unraid flash drive as `/boot/config/plugins/dockerMan/templates-user/my-melomancer.xml` (the file name has to start with `my-`, otherwise Unraid does not list it under *User templates*). Over the network this is the share `\\TOWER\flash\config\plugins\dockerMan\templates-user\` (replace `TOWER` with your server name).
3. Open the **Docker** tab, click **Add Container**, open the **Template** drop-down and choose **melomancer** under *User templates*.
4. Fill in the fields:

| Field | What to enter |
|---|---|
| Web panel port | `8080`, or another free host port |
| Data (database + music library) | A folder on a real disk or pool, for example `/mnt/nvme/appdata/melomancer`. Avoid `/mnt/user/...` for the database if you can; SQLite behaves better on a direct pool path than on the FUSE user share |
| Discord bot token | The token from [Creating the Discord bot](discord-bot.md) |
| Admin username / Admin password | The first administrator (password at least 10 characters) |
| PUID / PGID (advanced) | `99` and `100` on Unraid |

5. Click **Apply**. When the container is running, open its **WebUI** from the Docker tab.

If the image is private (your own fork), do the registry login from section 1 first, otherwise Unraid shows a pull error.

Updates: Docker tab, **Check for Updates**, then **apply update** next to the container. If you run Watchtower it will pick up new `latest` images by itself. A new image is also built every Monday, which refreshes `yt-dlp` (it gets a new version number, the middle one goes up).

Bridge or custom network: if a Cloudflare Tunnel container reaches the panel by container name, put Melomancer on the same custom Docker network and use `http://melomancer:8080` as the tunnel's service URL.

## 5. First login

Open the panel and log in with `ADMIN_USERNAME` and `ADMIN_PASSWORD`. These variables are used only when the database has no users, so changing them later does nothing. Change the password from the account menu (your name in the top right corner).

Then:

1. **Users** tab: create accounts for your other game masters and tick which Discord servers each one may control.
2. **Library** tab: upload some music.
3. **Playlists** tab: create a set and a playlist in it (folders are optional).
4. **Player** tab: pick the server and channel and press a playlist.

The panel is explained in [Using the panel](usage.md).

## 6. Exposing the panel to the internet

Do not publish port 8080 directly. Put the panel behind a Cloudflare Tunnel with a Cloudflare Access policy, or reach it over a VPN. See [Security](security.md).

## 7. Update, back up, recover

Update (Docker run):

```
docker pull ghcr.io/radzupl/melomancer:latest
```

```
docker stop melomancer && docker rm melomancer
```

Then run the `docker run` command from section 2 again. The data lives in the mounted folder and is kept.

Update (Compose):

```
docker compose pull && docker compose up -d
```

Backup: everything is in the data folder. For a copy without stopping the bot, first make a consistent database copy:

```
docker exec melomancer python -c "import sqlite3; s=sqlite3.connect('/data/melomancer.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d); d.close(); s.close()"
```

Then copy the whole data folder (`backup.db`, `melomancer.db` and the `music` folder) with your usual backup tool.

Forgot the administrator password:

```
docker exec -it melomancer python -m app.cli reset-password admin
```

The command asks for a new password, re-enables the account and ends its sessions.
