# Melomancer on Windows

Languages: **English** · [Polski](../pl/windows.md)

Melomancer is a music player for tabletop RPG sessions. You can play the music from your computer's speakers, or through a bot in a Discord voice channel. This guide shows how to start it on an ordinary Windows computer, **without installing anything**.

This is a test version. It works, but there is no installer or tray icon yet, and Windows will ask for your permission the first time you start it (step 3).

## Before you start

- A computer with Windows 10 or 11. You do not need an administrator account.
- About 140 MB to download and a few hundred MB of free disk space, plus room for your music.
- Internet access.
- For music on Discord: a bot of your own and a Discord account. Without a bot you can still play, from the computer's speakers (step 4).

## Step 1. Download

1. Open https://github.com/RadzuPL/melomancer/releases
2. The newest version is at the top. In its description there is a line **Windows package** with a link. Click it. (The same file is further down, in the **Assets** section.)
3. Your browser downloads a file named like `Melomancer-win64-0.6.39.zip` (about 140 MB), usually into the **Downloads** folder.

If the newest version has no such file, wait a few minutes or take the previous version from the list.

## Step 2. Unpack

1. Right-click the downloaded file and choose **Extract all…**
2. As the place, type the folder where the program should stay, for example `C:\Melomancer`, and click **Extract**.

Two notes: do not start the program from inside the zip (unpack it first), and do not unpack into **Program Files**, because Windows asks for administrator rights there. After unpacking you can delete the downloaded zip.

## Step 3. Start it

In the unpacked folder double-click the file **Melomancer.cmd** (it has a gears icon).

Windows shows this window (here from a Polish Windows; in an English one it is titled "Open File - Security Warning" and says "Unable to verify the publisher"):

![The Windows warning when starting Melomancer.cmd](../img/windows-security-warning.png)

This is normal. Windows shows it for every program that has no paid publisher certificate, and Melomancer has none. If you trust the program:

1. **Untick** the box **Always ask before opening this file**, so that Windows does not ask every time.
2. Click **Run**.

Instead, you may get a blue page "Windows protected your PC". Then click **More info**, then **Run anyway**.

After a moment a **black window** with text opens. That is Melomancer running: **do not close it while you listen to music**. A few seconds later your browser opens the Melomancer page. You do not have to sign in.

If the browser does not open by itself, type this address into its address bar: http://127.0.0.1:8080/ (and bookmark it, it will be handy).

## Step 4. Add music and play

1. The **Library** tab: click **Choose files** (or **Choose folder**) and pick your tracks. You can also drag them with the mouse onto the dashed area.
2. Or the **Downloads** tab: paste the address of a YouTube video and click **Download**.
3. The **Playlists** tab: click **New set** (it is like a folder for a few playlists, for example one session), then **New playlist**, type a name, click **Create** and add tracks to it.
4. The **Player** tab: click **Play here**, then your playlist. The music plays from the computer's speakers.

More about the panel: [Using the panel](usage.md).

## Step 5 (optional). Music on Discord

To play music in a Discord voice channel you need a bot of your own: a robot account that you create for free on the Discord website. You will need two things:

- The **token**: a long secret string of characters, it works like a password for your bot.
- The **Application ID**: a long number that identifies your application.

1. Create the bot and copy those two things following the guide [Creating the Discord bot](discord-bot.md) (steps 1 to 4).
2. In the Melomancer folder double-click **Ustawienia - Settings.cmd**. Notepad opens with the settings file.
3. Find these two lines (they start with `#`, which means "this line is only a description, the program skips it"):

   ```
   # discord_token = ''
   # discord_client_id = ''
   ```

4. Remove the `#` and the space after it, and paste your values **between the apostrophes** (do not remove the apostrophes):

   ```
   discord_token = 'paste-the-token-here'
   discord_client_id = '123456789012345678'
   ```

5. Save the file (Ctrl+S) and close Notepad.
6. Close the black Melomancer window and start **Melomancer.cmd** again. The window shows a line saying the bot logged in.
7. In the panel open **Settings**. You will see that the bot is **Running**, and a button **Add the bot to a server**. Click it and pick your Discord server (you need the permission to manage that server).
8. In the **Player** tab choose the **Server** and the **Voice channel**, click **Connect**, then your playlist.

**Keep the token secret**: do not send it to anyone and do not paste it in messages or screenshots. If it ever leaks, click **Reset Token** in the Developer Portal and put the new one in the file.

## Every day

- **Start:** double-click **Melomancer.cmd** and wait for the browser to open.
- You can minimize the **black window**, but do not close it. Closing it switches Melomancer off and the music stops.
- **To finish:** close the black window.

## Updating

In the panel, in **Settings** in the group **Updates**, you will see "Update available" when there is a new version. To install it:

1. Close the black window.
2. Download the new package (step 1) and unpack it into a **new** folder, for example `C:\Melomancer-2` (step 2).
3. Start **Melomancer.cmd** from the new folder (Windows asks for permission again, because it is a new place, step 3).
4. When everything works, you can delete the old folder.

Your music, playlists and settings **stay**, because they live in a different place than the program.

## Removing

Close the black window and delete the program folder. That is all. To remove your library and settings too, delete the folder `C:\Users\YourName\AppData\Local\Melomancer` (to find it, press Win+R, type `%LOCALAPPDATA%` and press Enter). **Careful: that deletes the music you uploaded and the playlists**, so copy what you want to keep first.

## When something does not work

| What you see | What to do |
|---|---|
| Windows asks about the publisher every time | In that window untick **Always ask before opening this file** before you click **Run**. |
| Windows or the antivirus blocks the file or puts it in quarantine | The program has no digital signature, so it is sometimes blocked by mistake. Allow this folder in your antivirus or in Windows Security. |
| The black window shows an error and waits | Read what it says. Most often it is a typing mistake in the settings file: fix it, or delete the file `config.toml` (the program makes a new one at the next start). |
| The browser does not open | Type the address http://127.0.0.1:8080/ yourself. |
| The page does not open and the window talks about an address in use | Another program uses the same "port". See the [details for advanced users](windows-advanced.md#problems). |
| The bot shows "Not running" | Most likely the token is missing from the settings file or is wrong. Paste it again (step 5). |
| The Player has no servers | The bot is not on your server yet: in **Settings** use **Add the bot to a server**. |
| The bot is in the channel but there is no sound | Check that the bot may speak in that channel (the channel permissions in Discord). |
| Downloading from YouTube does not work | YouTube changes things often. Update Melomancer to the newest version. |

Something else? Report it at https://github.com/RadzuPL/melomancer/issues: say what you did, which version the first line of the black window shows, and include the last few lines of that window. **Never include the token.**

## For advanced users

All the settings, signing in without a password, starting with Windows, the differences from the container version and how the package is built: [Windows: details for advanced users](windows-advanced.md).
