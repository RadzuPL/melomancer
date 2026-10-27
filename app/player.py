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
from .loudness import RuntimeSettings, linear_gain
from .mixer import Layer, Mixer

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
    loudness: float | None = None  # measured LUFS, None while unknown
    peak: float | None = None      # measured true peak in dBTP


class MixerSource(discord.AudioSource):
    """What the voice client plays: it asks the mixer for the next 20 ms frame."""

    def __init__(self, mixer: Mixer) -> None:
        self.mixer = mixer

    def read(self) -> bytes:
        return self.mixer.read()

    def is_opus(self) -> bool:
        return False

    def cleanup(self) -> None:
        self.mixer.close()


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
        self._mixer: Mixer | None = None   # what the voice client is playing; lives across tracks
        self._layer: Layer | None = None   # the track that is "now playing" (the newest one in the mix)

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

    def _fresh_order(self, first: int | None = None) -> list[int]:
        indexes = list(range(len(self.items)))
        if self.shuffle:
            random.shuffle(indexes)
            if first is not None and first in indexes:
                indexes.remove(first)
                indexes.insert(0, first)
        return indexes

    def _build_order(self, first: int | None = None) -> None:
        self.order = self._fresh_order(first)

    def elapsed(self) -> float:
        if self.state == "playing":
            return self._elapsed_base + (time.monotonic() - self._t_start)
        return self._elapsed_base

    def _ffmpeg_options(self, item: QueueItem, offset: float = 0.0) -> str:
        options = "-vn"
        # With a cross-fade the mixer does the fading between tracks; the per-playlist fade is the old way.
        fade = self.fade if self.manager.crossfade_seconds() <= 0 else 0.0
        if fade > 0:
            filters = [f"afade=t=in:st=0:d={fade:g}"]
            remaining = (item.duration or 0) - offset  # the filter clock starts at the seek position
            if item.duration and remaining > fade * 3:
                filters.append(f"afade=t=out:st={remaining - fade:.2f}:d={fade:g}")
            options += " -af " + ",".join(filters)
        return options

    def _new_layer(self, item: QueueItem, offset: float = 0.0) -> Layer:
        before = f"-ss {offset:.2f}" if offset > 0 else None
        source = discord.FFmpegPCMAudio(item.path, before_options=before, options=self._ffmpeg_options(item, offset))
        return Layer(source, item=item, offset=offset, duration=item.duration, gain=self.manager.gain_for(item))

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
        self._stop_audio()
        self.state = "idle"
        self.items, self.order, self.pos = [], [], -1
        self.playlist = None
        self.controller = None
        self._elapsed_base = 0.0

    def _stop_audio(self) -> None:
        """Silence now: stop the voice client and free every stream of the mix."""
        mixer, self._mixer, self._layer = self._mixer, None, None
        vc = self.vc
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        if mixer:
            mixer.close()

    async def play(self, items: list[QueueItem], playlist: dict | None, controller: dict, *, loop: bool,
                   shuffle: bool, fade: float, volume: float | None) -> None:
        if not self.connected():
            raise PlayerError("not_connected", 409)
        playable = [i for i in items if os.path.isfile(i.path)]
        if not playable:
            raise PlayerError("empty_playlist", 400)
        self._gen += 1
        self.items = playable
        self.playlist, self.controller = playlist, controller
        self.loop, self.shuffle, self.fade = loop, shuffle, fade
        if volume is not None:
            self.volume = max(0.0, min(volume, 1.5))
        self._build_order()
        self.pos = 0
        self._fail_streak = 0
        self._start_current()  # whatever plays now is cross-faded into the new playlist

    def _play_layer(self, layer: Layer, fade: float, keep_paused: bool = False) -> bool:
        """Make `layer` the audio. Returns True when the player stays paused (only a seek can ask for that).

        A running mix takes the layer in with a cross-fade; otherwise a new mix is started on the voice client.
        """
        vc = self.vc
        assert vc is not None
        mixer = self._mixer
        if mixer is not None and (vc.is_playing() or vc.is_paused()) and mixer.switch_to(layer, fade, fade):
            if vc.is_paused() and not keep_paused:
                vc.resume()
                return False
            return vc.is_paused()
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        loop = self.manager.loop
        mixer = Mixer(
            volume=self.volume, crossfade=self.manager.crossfade_seconds(),
            on_preroll=lambda lay: loop.call_soon_threadsafe(self._on_preroll, lay),
            on_transition=lambda token: loop.call_soon_threadsafe(self._on_transition, token))
        mixer.switch_to(layer, fade, 0.0)
        self._mixer = mixer
        vc.play(MixerSource(mixer), after=lambda err, m=mixer: loop.call_soon_threadsafe(self._on_mixer_end, m, err))
        return False

    def _start_current(self, offset: float = 0.0, *, fade: float | None = None, keep_paused: bool = False) -> None:
        vc = self.vc
        if not (vc and vc.is_connected()):
            self.state = "idle"
            return
        item = self.items[self.order[self.pos]]
        self._gen += 1
        if fade is None:
            fade = self.manager.crossfade_seconds()
        layer = None
        try:
            layer = self._new_layer(item, offset)
            paused = self._play_layer(layer, fade, keep_paused)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not start %s: %s", item.track_id, exc)
            if layer:
                layer.close()
            self.state = "idle"
            return
        self._layer = layer
        self.state = "paused" if paused else "playing"
        self._t_start = time.monotonic()
        self._elapsed_base = offset

    def _plan_next(self) -> tuple[list[int], int] | None:
        """Where the queue goes after the current track, without touching the queue itself."""
        order, pos, count = self.order, self.pos, len(self.order)
        for _ in range(count):
            pos += 1
            if pos >= count:
                if not self.loop:
                    return None
                order, pos = self._fresh_order(), 0
            if os.path.isfile(self.items[order[pos]].path):
                return order, pos
        return None

    def _on_preroll(self, layer: Layer) -> None:
        """The current track is about to end: prepare the next one so that it can fade in over it."""
        mixer = self._mixer
        if mixer is None or layer is not self._layer:
            return
        if self.state != "playing":  # paused in the meantime: ask again after resume
            mixer.cancel_pending(rearm=True)
            return
        fade = self.manager.crossfade_seconds()
        plan = self._plan_next() if fade > 0 else None
        if plan is None:
            return
        order, pos = plan
        try:
            following = self._new_layer(self.items[order[pos]])
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not prepare the next track: %s", exc)
            return
        if not mixer.set_next(following, fade=fade, after=layer, token=(self._gen, order, pos, following)):
            following.close()

    def _on_transition(self, token: tuple) -> None:
        """The prepared track has started to fade in: it is now the current one."""
        gen, order, pos, layer = token
        if gen != self._gen or self._mixer is None:
            return
        self.order, self.pos, self._layer = order, pos, layer
        self._fail_streak = 0
        self._t_start = time.monotonic()
        self._elapsed_base = 0.0

    def _on_mixer_end(self, mixer: Mixer, err: Exception | None) -> None:
        """The whole mix ran dry: no cross-fade was possible (last track, unknown length, a failure)."""
        if mixer is not self._mixer or self.state != "playing":
            return  # a stopped or replaced mix reporting in late
        self._mixer = self._layer = None
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
        self._stop_audio()
        self.state = "idle"
        self.controller = None
        self.playlist = None
        self._elapsed_base = 0.0

    def stop(self) -> None:
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
        self.state = "playing"
        self._advance(step)

    def jump(self, index: int) -> None:
        """Play the track at this position of the playlist (the order of the queue as listed in the panel)."""
        if self.state == "idle" or not self.items:
            raise PlayerError("not_playing", 409)
        if not 0 <= index < len(self.items):
            raise PlayerError("bad_index", 400)
        self._gen += 1
        self.pos = self.order.index(index)
        self.state = "playing"
        self._fail_streak = 0
        self._start_current()

    def seek(self, seconds: float) -> None:
        """Continue the current track from this position, cross-faded (a paused player stays paused)."""
        if self.state == "idle" or not 0 <= self.pos < len(self.order):
            raise PlayerError("not_playing", 409)
        item = self.items[self.order[self.pos]]
        if not item.duration:
            raise PlayerError("bad_seek", 400)
        # Never seek into the last two seconds: a track that ends at once would look like a failed one.
        target = max(0.0, min(float(seconds), item.duration - 2.0))
        was_paused = self.state == "paused"
        self._gen += 1
        self._fail_streak = 0
        self._start_current(target, fade=self.manager.scrub_seconds(), keep_paused=was_paused)

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(volume, 1.5))
        if self._mixer:
            self._mixer.volume = self.volume

    def refresh_settings(self) -> None:
        """The administrator changed the loudness or fade settings: apply them to what is playing right now."""
        mixer = self._mixer
        if mixer is None:
            return
        mixer.crossfade = self.manager.crossfade_seconds()
        for layer in mixer.layers():
            if layer.item is not None:
                layer.gain = self.manager.gain_for(layer.item)

    def set_options(self, loop: bool | None, shuffle: bool | None) -> None:
        changed = False
        if loop is not None and loop != self.loop:
            self.loop, changed = loop, True
        if shuffle is not None and shuffle != self.shuffle:
            self.shuffle, changed = shuffle, True
            if self.order and 0 <= self.pos < len(self.order):
                current = self.order[self.pos]
                self._build_order(first=current)
                self.pos = 0 if shuffle else current
        if changed and self._mixer:  # the next track was planned with the old options: plan it again
            self._mixer.cancel_pending(rearm=True)

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

    def __init__(self, settings: Settings, runtime: RuntimeSettings | None = None) -> None:
        self.settings = settings
        self.runtime = runtime or RuntimeSettings(settings)
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

    def gain_for(self, item: QueueItem) -> float:
        """Linear loudness gain for a track: 1.0 when evening-out is off or the track has not been measured."""
        if not self.runtime.normalize:
            return 1.0
        return linear_gain(item.loudness, item.peak, self.runtime.target, self.runtime.max_boost)

    def crossfade_seconds(self) -> float:
        return self.runtime.crossfade

    def scrub_seconds(self) -> float:
        return self.runtime.scrub

    def refresh_settings(self) -> None:
        """The administrator changed the loudness or fade settings: apply them to what is playing right now."""
        for player in self._players.values():
            player.refresh_settings()

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
        elif action == "seek":
            player.seek(float(value))
        elif action == "volume":
            player.set_volume(float(value))
        elif action == "options":
            player.set_options(value.get("loop"), value.get("shuffle"))
        else:
            raise PlayerError("bad_action", 400)
