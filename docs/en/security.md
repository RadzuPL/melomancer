# Security

Languages: **English** · [Polski](../pl/security.md)

The panel controls a bot that speaks on your Discord servers and fetches files from the internet, so treat it like an admin tool.

## What the application does

- **Logins.** Passwords are hashed with Argon2 and need at least 10 characters. Sessions are random tokens stored hashed in the database, sent in an `HttpOnly`, `SameSite=Lax` cookie (marked `Secure` when the panel is opened over https). Disabling a user or changing a password ends their sessions.
- **Brute force.** After 5 failed logins (per user name or per address, within 5 minutes) further attempts are refused for a while. Unknown user names take as long to answer as known ones.
- **Forged requests (CSRF).** Every state-changing request must carry a custom header that only the panel's own script sends.
- **Privacy between game masters.** Sets, groups and playlists belong to their owner. Other users get "not found" for them, not "forbidden", so even their existence is not revealed. When you delete a track, the number of playlists using it is shown, never their names or owners. Personal tags are visible only to their author. The shared library, with original titles and shared tags, is visible to every logged-in user, so choose shared tags and titles with that in mind.
- **Server access.** A user can only list and control the Discord servers an administrator ticked for them.
- **Content safety.** Page content from files and titles is always inserted as text, never as HTML, and a content security policy blocks inline scripts. Uploaded files are checked with `ffprobe` and must contain an audio stream, file names on disk are generated.
- **Downloads.** Only `https://` addresses on the allowed host list are accepted, a user cannot pass options to yt-dlp, playlists are not expanded.
- **Container.** The container starts as root only to fix file ownership and then runs as `PUID:PGID`. The bot needs no inbound port.

## Put the panel behind Cloudflare Access

Do not open port 8080 on your router. Two good options:

1. **Cloudflare Tunnel + Access** (recommended if you have a domain on Cloudflare). Documentation: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/ for the tunnel and https://developers.cloudflare.com/cloudflare-one/policies/access/ for Access policies.
2. A **VPN** into your network, then open the panel on its local address.

With a tunnel:

1. Create a public hostname, for example `muzyka.example.com`, whose service is `http://melomancer:8080` (same Docker network) or `http://<server address>:8080`.
2. Create an **Access application** for that hostname with a policy that allows only the e-mail addresses of your game masters.
3. Result: two layers. Cloudflare Access identifies the person first (for example with a one-time code sent by e-mail), then the panel asks for its own user name and password. This is a practical second factor in front of the panel.

Notes:

- **Upload size.** Cloudflare limits one request to 100 MB on the Free and Pro plans (200 MB Business, 500 MB Enterprise). The panel sends every file as its own request, so only a single file above the limit fails with "The file is too large for the server or tunnel". Source: https://developers.cloudflare.com/workers/platform/limits/ . Upload such a file from inside your network (`http://<server address>:8080`) or split it.
- If you already apply region, bot or suspicious-traffic rules to your hostnames, the panel works with them. The Discord bot connects outwards and is not affected.
- Keep `COOKIE_SECURE=auto` (default) so the cookie becomes `Secure` over https automatically.

## Secrets

- `DISCORD_TOKEN` is the bot's password. Keep it in the container settings or an `.env` file that is not committed. If it leaks, use **Reset Token** in the Developer Portal and update the container.
- Do not reuse the administrator password elsewhere. Change it after the first login.
- Back up the data folder, it contains the database with password hashes.

## Downloading from YouTube: honest notes

- The terms of service of YouTube forbid downloading content unless the service offers a download link for it, and forbid bypassing features that restrict copying. Using yt-dlp is therefore against those terms even for private use. In practice the consequences for a private, non-commercial server fall on your **IP address and accounts** (rate limiting, "confirm you are not a bot" blocks, in the worst case an account restriction), not on you in court, but this is a description, not legal advice.
- A **YouTube Premium** subscription does not change this: its offline feature works only inside YouTube's own apps.
- **Never** give yt-dlp the cookies of your main Google account (`YTDLP_COOKIES_FILE`). If you must use cookies, use a throw-away account.
- Your server probably has a fixed IP address. Melomancer is built to be gentle: one download at a time, a pause between downloads (`YTDLP_MIN_GAP_SECONDS`), a daily cap (`YTDLP_DAILY_LIMIT`), single videos only, and it downloads once instead of streaming, so playback during a session never touches YouTube. If YouTube starts refusing, downloads fail with an error and the rest keeps working. Lower the limits, or stop downloading for a few days.
- Safer sources: your own files, music you bought (Bandcamp, itch.io), and music under free licences. Tabletop Audio (https://tabletopaudio.com/about.html) offers 10-minute ambiences under a Creative Commons Attribution-NonCommercial-NoDerivatives licence, check its terms before reusing them.
- Playing music on a Discord server is subject to Discord's terms too (https://discord.com/terms). Keep the bot to private groups.
