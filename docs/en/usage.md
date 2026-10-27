# Using the panel

Languages: **English** · [Polski](../pl/usage.md)

The panel has five tabs: **Player**, **Library**, **Playlists**, **Downloads** and, for administrators, **Administration**. At the right of the top bar there are three small controls: the **theme** icon (each click switches to the next one: automatic, light, dark; automatic follows your system, the light theme is deliberately soft rather than white, and the choice is remembered in the browser), the **PL / EN** marker (click to switch the language; it is remembered per user) and your **user name**, which opens a menu with **Change password** and **Log out**.

## The idea in one minute

- The **Library** is one shared pool of music. Everyone logged in sees every track with its original title.
- **Playlists** are private. They live in a tree: **set** (a game system or a scenario, for example "Call of Cthulhu: Druga") containing **playlists** (lists of tracks from the library). When a set gets crowded you can add **folders** (for example a location or a type of scene) inside it and put playlists there; a folder is one level, not nested further, and entirely optional.
- Names and structure of your sets, folders and playlists are visible only to you (and to administrators). Another game master cannot see that your playlist is called "Innsmouth harbour".
- On the **Player** tab you pick a server and a voice channel and press a playlist.

## Roles

| | User | Administrator |
|---|---|---|
| See the whole library, preview tracks | yes | yes |
| Upload and download music | yes | yes |
| Edit or delete a track | own tracks | all tracks |
| See and edit sets, folders, playlists | own only | all (switch "show everyone's sets") |
| Control the bot | only on servers granted by an administrator | all servers |
| Manage users and server access | no | yes |

## Library

**Adding music.** Press **Choose files** or **Choose folder**, or drag audio files onto the dashed area. Many files at once are fine, they are sent one after another (two at a time) with a status line for each. Accepted types: mp3, ogg, opus, flac, wav, m4a, aac, webm. Folder upload can turn folder names into **shared tags** (the checkbox next to the buttons).

A file that is already in the library (same content) is not added twice: you see "already in the library". If the track was deleted earlier and still sits greyed out in somebody's playlist, uploading the same file brings it back and the playlist entry lights up again.

**Tags when adding.** Both the upload area and the download form have two tag fields: **shared tags** and **my tags** (only you). Tags that already exist are offered under each field, most used first: click one to add it, or type to filter the suggestions; Enter adds what you typed as a new tag. A download for a session can be tagged right away, for example my tag `sesja 3`. The chosen tags are kept between downloads and apply to every file added until you remove them. If a file is already in the library, it is not added twice but still gets your personal tags (and the shared ones, only if you are its owner).

**Finding music.** Type in the search box (title or tag), pick a tag, or tick "mine only". Click a tag chip in the table to filter by it.

**Tags.** Every track has two kinds of tags:

- **Shared tags** (grey) are visible to everybody and are edited by the track's owner or an administrator. Use neutral ones: ambient, combat, tavern, rain.
- **My tags** (purple outline) are visible only to you, on any track in the library. Use them for anything that would be a spoiler, for example a location name.

**Editing.** The pencil button opens the edit dialog: title and shared tags (owner or administrator), your own tags (anyone). The original title is kept and shown in the dialog.

**Deleting.** Only the owner or an administrator can delete a track. If the track is used in playlists, you are told **how many** (not which ones, so nothing about other people's scenarios leaks). After deletion the audio file is gone, but the title stays in those playlists as a greyed-out, struck-through entry so the playlist's author notices and can replace it.

**Bulk actions.** Tick tracks (the header checkbox selects all visible ones). A bar appears at the bottom: **Add to playlist** puts the selection at the end of one of your playlists, **Add my tag** gives them a personal tag.

**Preview.** The play button streams the track in your browser (not into Discord).

## Playlists

Left side: your tree. Use **+ Set**, then the **♪+** button on a set (new playlist directly in the set) or the **📁+** button (new folder). A folder has its own **♪+** for playlists inside it. The pencil renames, the cross deletes, the arrows change the order. Deleting a set, group or playlist never deletes music from the library.

Right side: the selected playlist.

**Automatic playlists.** When you create a playlist (the **♪+** buttons) you choose its type. A **manual** playlist holds the tracks you pick. An **automatic** playlist holds a rule instead: one or more tags and whether a track must have **all** of them or **any** of them. Its tracks are whatever matches the rule at the moment you press it, in alphabetical order, so tagging a new track in the Library adds it to every playlist whose rule it meets, and deleting a track removes it without a greyed-out entry. A tag counts when it is a shared tag of the track or one of your own personal tags, so you can build a playlist for a session from the personal tag you gave while downloading. Automatic playlists are marked with 🏷, the rule is edited on the right (the list of matching tracks updates at once), and you cannot add or reorder tracks by hand in them. Playback settings (loop, shuffle, fade, volume) work as in manual ones.

- **Loop**: play the list again and again. **Shuffle**: random order (re-shuffled on each lap).
- **Fade in/out**: each track fades in and out over this many seconds (0 turns it off). Useful for ambient music.
- **Own volume**: when ticked, pressing this playlist sets the bot's volume to this value. When not ticked, the current volume stays.
- **Move playlist** puts it directly under a set or into any folder (of any of your sets).
- **Add tracks** opens a picker with search and tag filter, tick any number of tracks. Tracks that are already on this playlist are not offered.
- Arrows move a track, the cross removes it from the playlist (not from the library).
- A greyed, struck-through entry is a track that was deleted from the library. **Replace** lets you pick another track for the same slot.

## Player

1. Choose the **server** and the **voice channel**. The bot has to be on that server (see [Creating the Discord bot](discord-bot.md)).
2. Choose a **set**. Its playlists appear as buttons, folders as headings with their playlists below.
3. Press a playlist, or use **Quick pick by tags** under the playlists: tick one or more tags, choose whether tracks need all or any of them, and press **Play (N)** to play every matching track without making a playlist (shuffled, looping). The number on a tag is how many tracks carry it, the number on the button how many tracks match your choice.
4. Press a playlist. If the bot is not in the channel yet it joins first, then starts playing. The active playlist is highlighted.

Below the controls the **tracks of the playing playlist** are listed, the current one highlighted. Click any track to play it right away; playback then continues from there (with shuffle on, the rest of the shuffled order follows). Missing or deleted tracks are not in the list.

The progress bar of the current track is also a **seek bar**: drag it or click a point to jump there, handy for tracks that take a long time to get going. The bot restarts the track from that position, so expect a brief gap; a paused player stays paused.

Controls: previous, pause/resume, next, stop, loop, shuffle and the **volume** slider (0 to 150 %). Volume changes apply immediately. Players can also lower the bot individually in Discord.

**Connect / Disconnect / Move here** manage the bot's presence in the channel. Playing a playlist on another channel needs a click on **Move here** first.

**One controller per server.** While somebody's playlist is playing on a server, another (non-administrator) user gets "Someone else is controlling this server right now" until that session is stopped. Administrators can always take over.

If the connection drops on its own, the bot waits about 35 seconds before it can join again. This is deliberate, a quicker rejoin tends to make Discord kill the new session as well. You will see the remaining seconds in the message.

The bot leaves a channel after 30 minutes without any human in it (`IDLE_LEAVE_MINUTES`).

## Downloads

Paste the address of **one** video or track from an allowed site (YouTube, SoundCloud, Bandcamp by default) and press **Download**. The server fetches the audio once, converts it, and adds it to the shared library, with the tags you typed. After that it plays from disk, so nothing depends on YouTube during the session.

The list shows what each download is doing: preparing (contacting the site, this can take several seconds, the seconds so far are counted), downloading with a progress bar, speed and time left, converting, and adding to the library. A job waiting in the queue shows how many seconds are left of the pause between downloads. A message pops up when a download finishes or fails.

Rules that protect your IP address: one download at a time, a pause between them, a daily limit (see [Configuration](configuration.md)), playlists are not expanded. A failed job shows the reason, for example YouTube asking to "sign in to confirm you are not a bot". Pulling a fresh image brings a newer `yt-dlp`, see [Troubleshooting](troubleshooting.md). Read the notes on terms of service in [Security](security.md) first. Uploading your own files or using music with a free licence is always the safe route.

## Administration

- **Users**: create accounts (username, password of at least 10 characters, role), change roles, reset a password, disable or enable an account. A disabled account is logged out immediately. The last active administrator cannot be demoted or disabled.
- **Servers**: for every non-administrator, tick the Discord servers they may control. A user without any ticked server sees an empty Player tab.
- **System**: the version and the bot status.

Your own name in the top bar opens the account dialog: change your password. Changing a password logs you out everywhere else.
