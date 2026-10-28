"use strict";

/* ---------- playing in this browser instead of on Discord ----------
 *
 * The server decides what plays (`POST /api/local/queue`): the tracks in order, where each one starts and ends
 * (hand-set points, silence trimming) and the loudness gain. This file only does the playing, with the same rules
 * as the bot (app/player.py, app/mixer.py): the next track fades in over the end of the current one, a seek is a
 * short cross-fade, the volume glides. Whenever you change a fade or the volume here, change it there too.
 *
 * It is one object for the whole page, outside every view, so that switching tabs of the panel does not touch the
 * sound. Reloading the page or closing it does stop it: the sound lives in this page.
 *
 * Signal path of a track:  <audio> -> track gain (loudness) -> envelope (fades) -> master (volume) -> speakers.
 */

const LocalPlayer = {
  on: false,                // the person chose to play here (the button next to "Connect")
  state: "idle",            // idle | playing | paused, like the bot's
  items: [], order: [], pos: -1,
  loop: false, shuffle: false, volume: 0.4,
  playlist: null,
  cfg: { crossfade: 3, scrub: 0.3, glide: 0.25, rev: 0 },
  ctx: null, master: null,
  cur: null,                // the layer that is the sound now
  next: null,               // the layer prepared to fade in over the end of the current one
  nextNone: false,          // the queue has no next track (do not look again until something changes)
  dying: new Set(),         // layers fading out
  gen: 0,                   // grows with every action of the person; a slower, older job sees that and gives up
  switching: false,
  failStreak: 0,
  timer: null, cfgTimer: null,
  listeners: new Set(),
  onerror: null,
  id: Math.random().toString(36).slice(2),
  channel: "BroadcastChannel" in window ? new BroadcastChannel("melomancer-local") : null,

  /* ----- switching the mode on and off ----- */

  async enable() {
    this.on = true;
    this.ensureContext();
    await this.loadConfig();
    this.emit();
  },

  disable() {
    this.stop();
    this.on = false;
    this.emit();
  },

  ensureContext() {
    if (!this.ctx) {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
      this.master = this.ctx.createGain();
      this.master.gain.value = this.volume;
      this.master.connect(this.ctx.destination);
    }
    if (this.ctx.state === "suspended") this.ctx.resume().catch(() => { /* needs a click first */ });
  },

  async loadConfig() {
    const sys = await api("GET", "/api/system");
    this.applyConfig(sys);
  },

  /* `keepRev`: the queue was fetched with an older revision; only the refresh below may move it forward. */
  applyConfig(sys, keepRev) {
    this.cfg.crossfade = sys.crossfade_seconds;
    this.cfg.scrub = sys.scrub_seconds;
    this.cfg.glide = sys.volume_glide_seconds;
    if (!keepRev) this.cfg.rev = sys.settings_rev;
  },

  /* ----- listeners (the player view) ----- */

  subscribe(fn) { this.listeners.add(fn); },

  emit() {
    const snap = this.snapshot();
    for (const fn of [...this.listeners]) {
      let keep = true;
      try { keep = fn(snap) !== false; } catch (_) { keep = false; }
      if (!keep) this.listeners.delete(fn);
    }
  },

  /* The same shape as the bot's state, so that the panel paints both with the same code. */
  snapshot() {
    const live = this.state !== "idle";
    const index = live ? this.order[this.pos] : undefined;
    const item = index === undefined ? null : this.items[index];
    return {
      guild_id: null, connected: false, local: true, channel_id: null, channel_name: null,
      state: this.state, volume: this.volume, loop: this.loop, shuffle: this.shuffle,
      playlist: live ? this.playlist : null,
      now: item && this.cur ? { track_id: this.cur.item.track_id, title: this.cur.item.title, duration: this.cur.item.duration,
        elapsed: Math.round((this.cur.a.currentTime || 0) * 10) / 10, index } : null,
      position: live ? this.pos + 1 : 0, queue_length: this.items.length,
      queue: live ? this.items.map((i) => ({ track_id: i.track_id, title: i.title, duration: i.duration })) : [],
      controller_id: null, controller: null,
    };
  },

  /* ----- starting ----- */

  /* target: {playlist_id} | {track_id} | {tags, mode} -- exactly what the bot's play request takes. */
  async play(target) {
    this.ensureContext();
    const data = await api("POST", "/api/local/queue", target);
    this.items = data.items;
    this.playlist = data.playlist;
    this.loop = data.options.loop;
    this.shuffle = data.options.shuffle;
    if (data.options.volume !== null && data.options.volume !== undefined) this.setVolume(data.options.volume);
    this.cfg.rev = data.settings_rev;
    this.gen++;
    this.dropNext();
    this.order = this.freshOrder();
    this.failStreak = 0;
    this.pos = 0;
    this.state = "playing";  // a track that cannot be loaded is skipped from here
    if (this.channel) this.channel.postMessage({ type: "start", id: this.id });  // other tabs of this panel go quiet
    await this.begin(this.order, 0, { fade: this.cfg.crossfade });
    if (this.state !== "idle") this.startTimers();
  },

  freshOrder(first) {
    const order = this.items.map((_, i) => i);
    if (this.shuffle) {
      for (let i = order.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [order[i], order[j]] = [order[j], order[i]];
      }
      if (first !== undefined) { order.splice(order.indexOf(first), 1); order.unshift(first); }
    }
    return order;
  },

  /* Where in the file to play: a seek replaces the start; with under a second left the end is ignored (as on the bot). */
  spanOf(item, offset) {
    if (offset > 0) {
      const end = item.end === null || item.end === undefined ? item.duration : item.end;
      if (item.duration && end - offset < 1) return { start: offset, end: item.duration };
      return { start: offset, end };
    }
    return { start: item.start, end: item.end };
  },

  makeLayer(item, offset) {
    const a = new Audio();
    a.preload = "auto";
    a.src = `/api/tracks/${item.track_id}/stream`;
    const source = this.ctx.createMediaElementSource(a);
    const trackGain = this.ctx.createGain();
    trackGain.gain.value = item.gain;
    const env = this.ctx.createGain();
    env.gain.value = 0;
    source.connect(trackGain);
    trackGain.connect(env);
    env.connect(this.master);
    const span = this.spanOf(item, offset || 0);
    const layer = { a, source, trackGain, env, item, start: span.start, end: span.end, seeked: (offset || 0) > 0, ready: null };
    layer.ready = new Promise((resolve, reject) => {
      const placed = () => { try { if (layer.start > 0) a.currentTime = layer.start; } catch (_) { /* set once it is known */ } resolve(); };
      if (a.readyState >= 1) placed(); else a.addEventListener("loadedmetadata", placed, { once: true });
      a.addEventListener("error", () => reject(new Error("media")), { once: true });
    });
    layer.ready.catch(() => { /* handled where it is awaited */ });
    a.addEventListener("ended", () => this.onEnded(layer));
    return layer;
  },

  /* Make the track at order[pos] the sound, fading in over whatever plays now. */
  async begin(order, pos, { fade, offset = 0 }) {
    const gen = this.gen;
    const item = this.items[order[pos]];
    let layer = null;
    try {
      layer = this.makeLayer(item, offset);
      await layer.ready;
      if (gen !== this.gen) return this.drop(layer);
      await layer.a.play();
      if (gen !== this.gen) return this.drop(layer);
    } catch (err) {
      if (layer) this.drop(layer);
      if (gen === this.gen) await this.trackFailed(err);
      return;
    }
    const old = this.cur;
    this.order = order;
    this.pos = pos;
    this.cur = layer;
    this.state = "playing";
    this.failStreak = 0;
    this.dropNext();
    this.fadeIn(layer, fade);
    if (old) this.retire(old, fade);
    this.emit();
  },

  /* A track could not be loaded: try the next one; when none works, stop. */
  async trackFailed(err) {
    if (this.onerror) this.onerror(err);
    this.failStreak++;
    if (this.failStreak >= Math.max(1, this.items.length)) return this.stop();
    await this.advance(1, 0);
  },

  /* ----- fades (equal power, like the mixer's) ----- */

  curve(rising, scale) {
    const n = 64;
    return Float32Array.from({ length: n }, (_, i) => {
      const x = (i / (n - 1)) * Math.PI / 2;
      return (rising ? Math.sin(x) : Math.cos(x)) * scale;
    });
  },

  fadeIn(layer, seconds) {
    const g = layer.env.gain;
    const t = this.ctx.currentTime;
    g.cancelScheduledValues(t);
    if (seconds < 0.01) { g.setValueAtTime(1, t); return; }
    g.setValueAtTime(0, t);
    g.setValueCurveAtTime(this.curve(true, 1), t, seconds);
  },

  fadeOut(layer, seconds) {
    const g = layer.env.gain;
    const t = this.ctx.currentTime;
    const from = g.value;
    g.cancelScheduledValues(t);
    if (seconds < 0.01) { g.setValueAtTime(0, t); return; }
    g.setValueAtTime(from, t);
    g.setValueCurveAtTime(this.curve(false, from), t, seconds);
  },

  /* A layer that is no longer the sound: fade it out, then throw it away. */
  retire(layer, seconds) {
    this.fadeOut(layer, seconds);
    this.dying.add(layer);
    setTimeout(() => this.drop(layer), seconds * 1000 + 100);
  },

  drop(layer) {
    this.dying.delete(layer);
    if (this.cur === layer) this.cur = null;
    try {
      layer.a.pause();
      layer.source.disconnect();
      layer.trackGain.disconnect();
      layer.env.disconnect();
    } catch (_) { /* already gone */ }
    layer.a.removeAttribute("src");
    layer.a.load();
  },

  dropNext() {
    if (this.next) this.drop(this.next.layer);
    this.next = null;
    this.nextNone = false;
  },

  /* ----- the clock: prepare the next track, fade into it near the end ----- */

  startTimers() {
    if (!this.timer) this.timer = setInterval(() => this.tick(), 100);
    if (!this.cfgTimer) this.cfgTimer = setInterval(() => this.refreshSettings(), 10000);
  },

  stopTimers() {
    clearInterval(this.timer); clearInterval(this.cfgTimer);
    this.timer = this.cfgTimer = null;
  },

  /* The next position of the queue, without changing it (like GuildPlayer._plan_next). */
  planNext() {
    if (!this.order.length) return null;
    if (this.pos + 1 < this.order.length) return { order: this.order, pos: this.pos + 1 };
    if (!this.loop) return null;
    return { order: this.freshOrder(), pos: 0 };
  },

  prepareNext() {
    const plan = this.planNext();
    if (!plan) { this.nextNone = true; return; }
    try {
      this.next = { ...plan, layer: this.makeLayer(this.items[plan.order[plan.pos]], 0) };
    } catch (_) {
      this.nextNone = true;
    }
  },

  tick() {
    const layer = this.cur;
    if (!layer || this.state !== "playing" || this.switching) return;
    const a = layer.a;
    const end = layer.end !== null && layer.end !== undefined ? layer.end : (Number.isFinite(a.duration) ? a.duration : null);
    if (end === null) return;
    const left = end - a.currentTime;
    const fade = this.cfg.crossfade;
    if (!this.next && !this.nextNone && left <= fade + 2.5) this.prepareNext();
    if (this.next) {
      if (left <= fade + 0.03) this.crossInto(fade);
    } else if (left <= 0.03) {
      this.reachedEnd();
    }
  },

  /* The current track is over (cut point or end of file) and there was no fade planned. */
  reachedEnd() {
    const plan = this.planNext();
    if (!plan) { this.stop(); return; }
    this.advance(1, 0);
  },

  onEnded(layer) {
    if (layer === this.cur && this.state === "playing" && !this.switching) this.reachedEnd();
  },

  /* The prepared track starts now and fades in while the current one fades out. */
  async crossInto(fade) {
    const nx = this.next;
    if (!nx || this.switching) return;
    this.switching = true;
    const gen = this.gen;
    try {
      await nx.layer.ready;
      if (gen !== this.gen) return;
      await nx.layer.a.play();
      if (gen !== this.gen) return;
      const old = this.cur;
      this.next = null;
      this.order = nx.order;
      this.pos = nx.pos;
      this.cur = nx.layer;
      this.nextNone = false;
      this.failStreak = 0;
      this.fadeIn(nx.layer, fade);
      if (old) this.retire(old, fade);
      this.emit();
    } catch (err) {
      if (gen === this.gen) { this.dropNext(); await this.trackFailed(err); }
    } finally {
      this.switching = false;
    }
  },

  /* ----- what the person does ----- */

  /* Skip forward or back (like GuildPlayer._advance). */
  async advance(step, fade) {
    if (this.state === "idle") return;
    this.gen++;
    this.switching = false;
    let order = this.order;
    let pos = this.pos + step;
    if (pos >= order.length) {
      if (!this.loop) { this.stop(); return; }
      order = this.freshOrder();
      pos = 0;
    } else if (pos < 0) {
      pos = this.loop ? order.length - 1 : 0;
    }
    await this.begin(order, pos, { fade: fade === undefined ? this.cfg.crossfade : fade });
  },

  async skip(step) { await this.advance(step); },

  async jump(index) {
    if (this.state === "idle" || index < 0 || index >= this.items.length) return;
    this.gen++;
    this.switching = false;
    await this.begin(this.order, this.order.indexOf(index), { fade: this.cfg.crossfade });
  },

  pause() {
    if (this.state !== "playing" || !this.cur) return;
    this.state = "paused";
    for (const layer of [...this.dying]) this.drop(layer);
    const layer = this.cur;
    this.fadeOut(layer, 0.04);
    setTimeout(() => { if (this.state === "paused") layer.a.pause(); }, 60);
    this.emit();
  },

  async resume() {
    if (this.state !== "paused" || !this.cur) return;
    this.ensureContext();
    this.state = "playing";
    try { await this.cur.a.play(); } catch (_) { this.state = "paused"; return; }
    this.fadeIn(this.cur, 0.04);
    this.emit();
  },

  stop() {
    this.gen++;
    this.switching = false;
    const last = this.cur;
    for (const layer of [...this.dying]) if (layer !== last) this.drop(layer);
    this.cur = null;
    if (last) this.retire(last, 0.05);
    this.dropNext();
    this.state = "idle";
    this.playlist = null;
    this.order = []; this.pos = -1;
    this.stopTimers();
    this.emit();
  },

  /* Continue the current track from here, cross-faded (a paused player stays paused). */
  async seek(seconds) {
    const old = this.cur;
    if (!old || this.state === "idle") return;
    if (this.state === "paused") {
      try { old.a.currentTime = seconds; } catch (_) { /* not seekable yet */ }
      this.emit();
      return;
    }
    const gen = ++this.gen;
    this.switching = false;
    const item = old.item;
    let layer = null;
    try {
      layer = this.makeLayer(item, seconds);
      await layer.ready;
      if (gen !== this.gen) return this.drop(layer);
      await layer.a.play();
      if (gen !== this.gen) return this.drop(layer);
    } catch (err) {
      if (layer) this.drop(layer);
      if (this.onerror) this.onerror(err);
      return;
    }
    this.cur = layer;
    this.dropNext();
    this.fadeIn(layer, this.cfg.scrub);
    this.retire(old, this.cfg.scrub);
    this.emit();
  },

  setVolume(v) {
    this.volume = Math.max(0, Math.min(1.5, v));
    if (this.master) this.master.gain.setTargetAtTime(this.volume, this.ctx.currentTime, Math.max(0.005, this.cfg.glide / 3));
    this.emit();
  },

  setOptions({ loop, shuffle }) {
    let changed = false;
    if (loop !== undefined && loop !== this.loop) { this.loop = loop; changed = true; }
    if (shuffle !== undefined && shuffle !== this.shuffle) {
      this.shuffle = shuffle;
      changed = true;
      if (this.order.length && this.pos >= 0) {
        const current = this.order[this.pos];
        this.order = this.freshOrder(current);
        this.pos = shuffle ? 0 : current;
      }
    }
    if (changed) { this.dropNext(); this.emit(); }  // the next track was planned with the old options
  },

  /* ----- following the administrator's settings while playing ----- */

  async refreshSettings() {
    if (this.state === "idle") return;
    try {
      const sys = await api("GET", "/api/system");
      const changed = sys.settings_rev !== this.cfg.rev;
      this.applyConfig(sys);
      if (!changed) return;
      const ids = [...new Set(this.items.map((i) => i.track_id))];
      const fresh = await api("POST", "/api/local/resolve", { track_ids: ids });
      const byId = new Map(fresh.items.map((i) => [i.track_id, i]));
      this.items = this.items.map((i) => ({ ...i, ...(byId.get(i.track_id) || {}) }));
      const layer = this.cur;
      if (layer) {
        const item = this.items.find((i) => i.track_id === layer.item.track_id);
        if (item) {
          layer.item = item;
          if (!layer.seeked) layer.end = item.end;
          layer.trackGain.gain.setTargetAtTime(item.gain, this.ctx.currentTime, 0.1);
        }
      }
      this.dropNext();  // prepared with the old points and gain: prepare it again
    } catch (_) { /* transient: the next round tries again */ }
  },
};

/* Another tab of the panel started playing: this one goes quiet, so that two never play at once. */
if (LocalPlayer.channel) {
  LocalPlayer.channel.onmessage = (e) => {
    if (e.data && e.data.type === "start" && e.data.id !== LocalPlayer.id && LocalPlayer.state !== "idle") LocalPlayer.stop();
  };
}
