# Creating the Discord bot

Languages: **English** · [Polski](../pl/discord-bot.md)

Melomancer needs its own bot account. This takes about five minutes and you do it once. Official background: https://docs.discord.com/developers/quick-start/getting-started and https://discordpy.readthedocs.io/en/latest/discord.html

## 1. Create the application

1. Open https://discord.com/developers/applications and log in with your Discord account.
2. Click **New Application**, enter a name (for example `Melomancer`), accept the terms and click **Create**.
3. You land on **General Information**. Copy the **Application ID**, you need it for the invite link in step 4.

## 2. Get the bot token

1. In the left sidebar open **Bot**.
2. Click **Reset Token** and confirm. Copy the token that appears, Discord shows it only once.
3. Put it into the container as `DISCORD_TOKEN` (see [Installation](installation.md)).

Optionally put the Application ID from step 1 into the container as `DISCORD_CLIENT_ID` as well. The **Settings** tab then shows the invite link of step 4 ready made, next to the bot status.

The token is the password of the bot. Never post it, never commit it to a repository. If it leaks, click **Reset Token** again, which invalidates the old one, and update `DISCORD_TOKEN`.

## 3. Check the bot settings

Still on the **Bot** page:

- **Privileged Gateway Intents**: leave all three switched **off**. Melomancer needs none of them (no message content, no member list, no presence).
- **Public Bot**: switch it **off** if you want to be the only person who can add this bot to servers. (When it is off, only the application owner can invite it.)
- **Require OAuth2 Code Grant**: leave it off.

## 4. Invite the bot to your server

You need the **Manage Server** permission on the server you invite it to.

Use this link, replacing `YOUR_APPLICATION_ID` with the Application ID from step 1:

```
https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&scope=bot&permissions=3146752
```

Open it in a browser, choose the server, click **Continue** and **Authorize**. The number `3146752` is the permission set the bot needs: **View Channels**, **Connect** and **Speak**. Nothing else.

Alternative without typing the link: in the Developer Portal open **OAuth2**, then **URL Generator**, tick the scope `bot`, tick the permissions **View Channels**, **Connect** and **Speak**, and copy the **Generated URL** from the bottom of the page.

Repeat the invite for every server you want to play on.

## 5. Check that it works

1. Start the container with the token set.
2. In Discord the bot should appear as online in the member list of the server.
3. Open the panel, go to the **Player** tab: your servers and their voice channels are listed automatically. You do not need to copy any IDs.
4. Administrators see all servers the bot is on. For other users, an administrator ticks the servers they may control in the **Users** tab.

## Good to know

- **Channel permissions.** If a voice channel has its own permission overrides that deny **Connect** or **Speak** for the bot's role, the panel shows "The bot lacks permissions in that channel". Allow View Channel, Connect and Speak for the bot in that channel.
- **One voice channel per server per bot.** Discord lets a bot be in one voice channel per server at a time. For two simultaneous sessions on the same server you need a second application and a second container.
- **Another bot in the channel is fine.** For example a session recorder can sit in the same channel. The music appears as a separate participant, so players can lower its volume individually in Discord (right-click the bot, User Volume).
- **Voice encryption (DAVE).** Since 2026-03-01 Discord requires end-to-end encrypted voice. The image includes the libraries for that (`discord.py` 2.7.1 or newer and `davey`). The log prints their versions at start. Details: https://docs.discord.com/developers/topics/voice-connections
- **Copying IDs (optional).** Only needed if you want to add a server to a user by hand: in Discord open **User Settings**, **Advanced**, switch **Developer Mode** on, then right-click the server icon and choose **Copy Server ID**. Help article: https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID
