"""Discord voice playback: one GuildPlayer per server, owned by the BotManager."""
from __future__ import annotations

import asyncio
import importlib.metadata
import logging
import os
import random
import time
from dataclasses import dataclass

import discord

from .config import Settings

log = logging.getLogger("melomancer.player")

# After a voice session dies on its own, discord.py keeps a 30 s timer for the old session. Joining again
# inside that window can get every new session killed (seen with discord-stream-bot on 2026-10-09).
REJOIN_COOLDOWN = 35
JANITOR_INTERVAL = 30


class PlayerError(Exception):
    def __init__(self, code: str, status: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass
class QueueItem:
    track_id: str
    title: str
    path: str
    duration: float | None


class GuildPlayer:
    def __init__(self, manager: "BotManager", guild_id: int, volume: float) -> None:
        self.manager = manager
        self.guild_id = guild_id
        self.items: list[QueueItem] = []
        self.order: list[int] = []
        self.pos = -1
        self.loop = True
        self.shuffle = False
        self.fade = 0.0
        self.volume = volume
        self.playlist: dict | None = None
        self.controller: dict | None = None
        self.state = "idle"  # idle | playing | paused
        self.wanted = False
        self.dropped_at: float | None = None
        self.empty_since: float | None = None
        self._gen = 0
        self._fail_streak = 0
        self._t_start = 0.0
        self._elapsed_base = 0.0

    # ---- helpers ---------------------------------------------------------

    @property
    def guild(self) -> discord.Guild | None:
        return self.manager.client.get_guild(self.guild_id) if self.manager.client else None

    @property
    def vc(self) -> discord.VoiceClient | None:
        guild = self.guild
        return guild.voice_client if guild else None  # type: ignore[return-value]

    def connected(self) -> bool:
        vc = self.vc
        return bool(vc and vc.is_connected())

    def _build_order(self, first: int | None = None) -> None:
        indexes = list(range(len(self.items)))
        if self.shuffle:
            random.shuffle(indexes)
            if first is not None and first in indexes:
                indexes.remove(first)
                indexes.insert(0, first)
        self.order = indexes

    def elapsed(self) -> float:
        if self.state == "playing":
            return self._elapsed_base + (time.monotonic() - self._t_start)
        return self._elapsed_base

    def _ffmpeg_options(self, item: QueueItem) -> str:
        options = "-vn"
        fade = self.fade
        if fade > 0:
            filters = [f"afade=t=in:st=0:d={fade:g}"]
            if item.duration and item.duration > fade * 3:
                filters.append(f"afade=t=out:st={item.duration - fade:.2f}:d={fade:g}")
            options += " -af " + ",".join(filters)
        return options

    # ---- connection ------------------------------------------------------

    async def connect(self, channel_id: int) -> None:
        guild = self.guild
        if guild is None:
            raise PlayerError("guild_not_found", 404)
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            raise PlayerError("channel_not_found", 404)
        perms = channel.permissions_for(guild.me)
        if not (perms.view_channel and perms.connect and perms.speak):
            raise PlayerError("no_permission", 403)
        vc = guild.voice_client
        if vc and vc.is_connected():
            if vc.channel.id != channel.id:
                await vc.move_to(channel)
            self.wanted = True
            return
        if self.dropped_at is not None:
            wait = REJOIN_COOLDOWN - (time.monotonic() - self.dropped_at)
            if wait > 0:
                raise PlayerError(f"cooldown:{int(wait) + 1}", 429)
        if vc:  # a half-dead client would make connect() fail with "already connected"
            await vc.disconnect(force=True)
        try:
            await asyncio.wait_for(channel.connect(reconnect=True), timeout=30)
        except asyncio.TimeoutError:
            stale = guild.voice_client
            if stale:
                await stale.disconnect(force=True)
            raise PlayerError("connect_timeout", 504) from None
        except discord.Forbidden:
            raise PlayerError("no_permission", 403) from None
        except discord.DiscordException as exc:
            log.warning("Voice connect failed in guild %s: %s", self.guild_id, exc)
            raise PlayerError("connect_failed", 502) from None
        self.wanted = True
        self.dropped_at = None
        self.empty_since = None

    async def disconnect(self) -> None:
        self.wanted = False
        self._reset_playback()
        vc = self.vc
        if vc:
            await vc.disconnect(force=True)

    def on_voice_dropped(self) -> None:
        """The bot lost its voice session without us asking (kicked, moved out, network)."""
        if self.wanted:
            self.dropped_at = time.monotonic()
            log.warning("Voice session in guild %s ended unexpectedly", self.guild_id)
        self.wanted = False
        self._reset_playback()

    # ---- playback --------------------------------------------------------

    def _reset_playback(self) -> None:
        self._gen += 1
        vc = self.vc
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        self.state = "idle"
        self.items, self.order, self.pos = [], [], -1
        self.playlist = None
        self.controller = None
        self._elapsed_base = 0.0

    async def play(self, items: list[QueueItem], playlist: dict | None, controller: dict, *, loop: bool,
                   shuffle: bool, fade: float, volume: float | None) -> None:
        if not self.connected():
            raise PlayerError("not_connected", 409)
        playable = [i for i in items if os.path.isfile(i.path)]
        if not playable:
            raise PlayerError("empty_playlist", 400)
        self._gen += 1
        vc = self.vc
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        self.items = playable
        self.playlist, self.controller = playlist, controller
        self.loop, self.shuffle, self.fade = loop, shuffle, fade
        if volume is not None:
            self.volume = max(0.0, min(volume, 1.5))
        self._build_order()
        self.pos = 0
        self._fail_streak = 0
        self._start_current()

    def _start_current(self) -> None:
        vc = self.vc
        if not (vc and vc.is_connected()):
            self.state = "idle"
            return
        item = self.items[self.order[self.pos]]
        self._gen += 1
        gen = self._gen
        try:
            source = discord.FFmpegPCMAudio(item.path, options=self._ffmpeg_options(item))
            source = discord.PCMVolumeTransformer(source, volume=self.volume)
            vc.play(source, after=lambda err, g=gen: self.manager.loop.call_soon_threadsafe(self._on_after, g, err))
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not start %s: %s", item.track_id, exc)
            self.state = "idle"
            return
        self.state = "playing"
        self._t_start = time.monotonic()
        self._elapsed_base = 0.0

    def _on_after(self, gen: int, err: Exception | None) -> None:
        if gen != self._gen or self.state != "playing":
            return  # a stopped or replaced source reporting in late
        quick = (time.monotonic() - self._t_start) < 1.5
        if err or quick:
            self._fail_streak += 1
            if err:
                log.warning("Playback error in guild %s: %s", self.guild_id, err)
        else:
            self._fail_streak = 0
        if self._fail_streak > len(self.items):
            log.warning("Every track in the queue failed in guild %s, stopping", self.guild_id)
            self._finish()
            return
        self._advance(1)

    def _advance(self, step: int) -> None:
        count = len(self.order)
        for _ in range(count):
            self.pos += step
            if self.pos >= count:
                if not self.loop:
                    self._finish()
                    return
                self._build_order()
                self.pos = 0
            elif self.pos < 0:
                self.pos = count - 1 if self.loop else 0
            if os.path.isfile(self.items[self.order[self.pos]].path):
                self._start_current()
                return
            log.warning("File missing for %s, skipping", self.items[self.order[self.pos]].track_id)
        self._finish()

    def _finish(self) -> None:
        self._gen += 1
        self.state = "idle"
        self.controller = None
        self.playlist = None
        self._elapsed_base = 0.0

    def stop(self) -> None:
        self._gen += 1
        vc = self.vc
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        self._finish()

    def pause(self) -> None:
        vc = self.vc
        if self.state != "playing" or not vc:
            raise PlayerError("not_playing", 409)
        vc.pause()
        self._elapsed_base = self.elapsed()
        self.state = "paused"

    def resume(self) -> None:
        vc = self.vc
        if self.state != "paused" or not vc:
            raise PlayerError("not_paused", 409)
        vc.resume()
        self._t_start = time.monotonic()
        self.state = "playing"

    def skip(self, step: int) -> None:
        if self.state == "idle":
            raise PlayerError("not_playing", 409)
        self._gen += 1
        vc = self.vc
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        self.state = "playing"
        self._advance(step)

    def jump(self, index: int) -> None:
        """Play the track at this position of the playlist (the order of the queue as listed in the panel)."""
        if self.state == "idle" or not self.items:
            raise PlayerError("not_playing", 409)
        if not 0 <= index < len(self.items):
            raise PlayerError("bad_index", 400)
        self._gen += 1
        vc = self.vc
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        self.pos = self.order.index(index)
        self.state = "playing"
        self._fail_streak = 0
        self._start_current()

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(volume, 1.5))
        vc = self.vc
        if vc and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = self.volume

    def set_options(self, loop: bool | None, shuffle: bool | None) -> None:
        if loop is not None:
            self.loop = loop
        if shuffle is not None and shuffle != self.shuffle:
            self.shuffle = shuffle
            if self.order and 0 <= self.pos < len(self.order):
                current = self.order[self.pos]
                self._build_order(first=current)
                self.pos = 0 if shuffle else current

    def snapshot(self) -> dict:
        vc = self.vc
        channel = vc.channel if vc and vc.is_connected() else None
        now = None
        if self.state in {"playing", "paused"} and 0 <= self.pos < len(self.order):
            item = self.items[self.order[self.pos]]
            now = {"track_id": item.track_id, "title": item.title, "duration": item.duration,
                   "elapsed": round(self.elapsed(), 1), "index": self.order[self.pos]}
        return {
            "guild_id": str(self.guild_id),
            "connected": channel is not None,
            "channel_id": str(channel.id) if channel else None,
            "channel_name": channel.name if channel else None,
            "state": self.state,
            "volume": self.volume,
            "loop": self.loop,
            "shuffle": self.shuffle,
            "playlist": self.playlist,
            "now": now,
            "position": self.pos + 1 if self.state != "idle" else 0,
            "queue_length": len(self.items),
            "queue": [{"track_id": i.track_id, "title": i.title, "duration": i.duration} for i in self.items]
            if self.state != "idle" else [],
            "controller_id": self.controller["id"] if self.controller else None,
            "controller": self.controller["username"] if self.controller else None,
        }


class MelomancerClient(discord.Client):
    def __init__(self, manager: "BotManager") -> None:
        # Default intents are enough: guilds + voice_states, nothing privileged.
        super().__init__(intents=discord.Intents.default())
        self.manager = manager

    async def on_ready(self) -> None:
        self.manager.status = "ready"
        log.info("Logged in as %s, in %d guild(s)", self.user, len(self.guilds))

    async def on_voice_state_update(self, member, before, after) -> None:
        if self.user and member.id == self.user.id and before.channel and after.channel is None:
            self.manager.player(before.channel.guild.id).on_voice_dropped()


class BotManager:
    """Owns the Discord client and one GuildPlayer per server."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: MelomancerClient | None = None
        self.status = "disabled"  # disabled | starting | ready | login_failed | error
        self.loop: asyncio.AbstractEventLoop | None = None
        self._players: dict[int, GuildPlayer] = {}
        self._tasks: list[asyncio.Task] = []

    # ---- lifecycle -------------------------------------------------------

    async def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        try:
            davey = importlib.metadata.version("davey")
        except importlib.metadata.PackageNotFoundError:
            davey = None
        log.info("discord.py %s, davey %s", discord.__version__, davey or "MISSING")
        if davey is None:
            log.warning("'davey' is not installed - Discord voice requires DAVE support since 2026-03-01.")
        if not self.settings.discord_token:
            log.warning("DISCORD_TOKEN is not set: the panel runs, but the bot stays offline.")
            return
        self.client = MelomancerClient(self)
        self.status = "starting"
        self._tasks.append(asyncio.create_task(self._run(), name="discord-client"))
        self._tasks.append(asyncio.create_task(self._janitor(), name="voice-janitor"))

    async def _run(self) -> None:
        assert self.client is not None
        try:
            await self.client.start(self.settings.discord_token)
        except discord.LoginFailure:
            self.status = "login_failed"
            log.error("Discord rejected the bot token (DISCORD_TOKEN).")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            self.status = "error"
            log.exception("The Discord client stopped unexpectedly")

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self.client:
            await self.client.close()

    async def _janitor(self) -> None:
        """Leave voice channels that have had no human in them for IDLE_LEAVE_MINUTES."""
        limit = self.settings.idle_leave_minutes * 60
        while True:
            await asyncio.sleep(JANITOR_INTERVAL)
            if not limit:
                continue
            for player in list(self._players.values()):
                vc = player.vc
                if not (vc and vc.is_connected()):
                    player.empty_since = None
                    continue
                humans = [m for m in vc.channel.members if not m.bot]
                if humans:
                    player.empty_since = None
                elif player.empty_since is None:
                    player.empty_since = time.monotonic()
                elif time.monotonic() - player.empty_since > limit:
                    log.info("Leaving guild %s: nobody in the channel for %d min", player.guild_id,
                             self.settings.idle_leave_minutes)
                    await player.disconnect()

    # ---- access for the API ---------------------------------------------

    def player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer(self, guild_id, self.settings.default_volume)
        return self._players[guild_id]

    def require_ready(self) -> None:
        if self.status != "ready" or self.client is None:
            raise PlayerError("bot_offline", 503)

    def list_guilds(self) -> list[dict]:
        if self.status != "ready" or self.client is None:
            return []
        result = []
        for guild in sorted(self.client.guilds, key=lambda g: g.name.lower()):
            channels = [
                {"id": str(c.id), "name": c.name}
                for c in guild.voice_channels
                if c.permissions_for(guild.me).connect
            ]
            result.append({"id": str(guild.id), "name": guild.name, "channels": channels,
                           "state": self.player(guild.id).snapshot()})
        return result

    def state(self, guild_id: int) -> dict:
        self.require_ready()
        return self.player(guild_id).snapshot()

    async def connect(self, guild_id: int, channel_id: int) -> None:
        self.require_ready()
        await self.player(guild_id).connect(channel_id)

    async def disconnect(self, guild_id: int) -> None:
        self.require_ready()
        await self.player(guild_id).disconnect()

    async def play(self, guild_id: int, items: list[QueueItem], playlist: dict | None, controller: dict, *,
                   loop: bool, shuffle: bool, fade: float, volume: float | None) -> None:
        self.require_ready()
        await self.player(guild_id).play(items, playlist, controller, loop=loop, shuffle=shuffle, fade=fade,
                                         volume=volume)

    def control(self, guild_id: int, action: str, value=None) -> None:
        self.require_ready()
        player = self.player(guild_id)
        if action == "pause":
            player.pause()
        elif action == "resume":
            player.resume()
        elif action == "next":
            player.skip(1)
        elif action == "prev":
            player.skip(-1)
        elif action == "stop":
            player.stop()
        elif action == "jump":
            player.jump(int(value))
        elif action == "volume":
            player.set_volume(float(value))
        elif action == "options":
            player.set_options(value.get("loop"), value.get("shuffle"))
        else:
            raise PlayerError("bad_action", 400)
