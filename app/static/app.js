"use strict";

/* ---------- small helpers ---------- */

const AUDIO_EXT = new Set([".mp3", ".ogg", ".oga", ".opus", ".flac", ".wav", ".m4a", ".aac", ".webm"]);
const state = {
  user: null, lang: "pl", tab: "player", system: null,
  tracks: [], tags: { shared: [], mine: [] }, sets: [], showAllSets: false,
  lib: { q: "", tag: "", mine: false, selected: new Set() },
  player: { guilds: [], guildId: "", channelId: "", setId: "", st: null, stAt: 0, timer: null, armed: null },
  pl: { selected: null, detail: null },
  dlTags: { shared: [], mine: [] }, upTags: { shared: [], mine: [] },
  quick: { tags: new Set(), mode: "any" },
};

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value" || k === "checked" || k === "disabled" || k === "selected") el[k] = v;
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

function put(el, ...kids) {
  el.append(...kids.flat(Infinity)
    .filter((k) => k !== null && k !== undefined && k !== false)
    .map((k) => (k.nodeType ? k : document.createTextNode(String(k)))));
}

/* Like replaceChildren, but accepts arrays, nulls and plain text the way h() does. */
function fill(el, ...kids) {
  el.replaceChildren(...kids.flat(Infinity)
    .filter((k) => k !== null && k !== undefined && k !== false)
    .map((k) => (k.nodeType ? k : document.createTextNode(String(k)))));
}

function tr(key, vars) {
  const dict = I18N[state.lang] || I18N.en;
  let text = dict[key] !== undefined ? dict[key] : (I18N.en[key] !== undefined ? I18N.en[key] : key);
  for (const [name, value] of Object.entries(vars || {})) text = text.replaceAll("{" + name + "}", value);
  return text;
}
const t = tr;

function pref(key, value) {
  try {
    if (value === undefined) return localStorage.getItem("melomancer." + key) || "";
    localStorage.setItem("melomancer." + key, value);
  } catch (_) { /* storage can be unavailable; the panel works without it */ }
  return value;
}

function fmtTime(sec) {
  if (sec === null || sec === undefined || Number.isNaN(sec)) return "–";
  sec = Math.max(0, Math.round(sec));
  const m = Math.floor(sec / 60), s = sec % 60;
  return m + ":" + String(s).padStart(2, "0");
}

/* ---------- listening in the panel ---------- */

/* One audio element serves the whole panel. Every play button mirrors it (▶ or ⏸), and the track being listened to
   gets a seek bar right under its row. The sound stops when the screen or dialog it was started from goes away. */
const Preview = {
  audio: new Audio(),
  track: null,
  scope: null,
  dragging: false,
  buttons: new Map(),   // play button -> track id
  bars: new Set(),      // seek bars on screen
  watchers: new Map(),  // list element -> function that puts the bar under the current row

  toggle(track, scope) {
    const a = this.audio;
    if (this.track && this.track.id === track.id) {
      if (a.paused) a.play().catch(() => { /* the browser may refuse; the button stays as it is */ }); else a.pause();
      return;
    }
    this.track = { id: track.id, title: track.title, duration: track.duration || 0 };
    this.scope = scope;
    a.src = `/api/tracks/${track.id}/stream`;
    a.play().catch(() => { /* see above */ });
    this.changed();
  },

  stop() {
    this.track = null;
    this.scope = null;
    this.audio.pause();
    this.audio.removeAttribute("src");
    this.audio.load();
    this.changed();
  },

  /* The track being listened to changed: move the bar, then bring every control up to date. */
  changed() {
    for (const [box, place] of [...this.watchers]) {
      if (!box.isConnected) this.watchers.delete(box); else place();
    }
    this.refresh();
  },

  refresh() {
    for (const [button, id] of [...this.buttons]) {
      if (!button.isConnected) this.buttons.delete(button); else this.paintButton(button, id);
    }
    for (const bar of [...this.bars]) {
      if (!bar.el.isConnected) this.bars.delete(bar); else this.paintBar(bar);
    }
  },

  paintButton(button, id) {
    const on = !!this.track && this.track.id === id;
    const playing = on && !this.audio.paused;
    button.textContent = playing ? "⏸" : "▶";
    button.classList.toggle("on", on);
    button.title = playing ? tr("preview_pause") : tr("preview_play");
    button.setAttribute("aria-label", button.title);
  },

  paintBar(bar) {
    const a = this.audio;
    const total = Number.isFinite(a.duration) && a.duration > 0 ? a.duration : (this.track ? this.track.duration : 0);
    bar.range.max = total || 0;
    if (!this.dragging) bar.range.value = a.currentTime || 0;
    bar.range.style.setProperty("--pos", (total ? Math.min(100, ((a.currentTime || 0) / total) * 100) : 0) + "%");
    bar.time.textContent = fmtTime(a.currentTime || 0) + " / " + fmtTime(total);
  },
};

for (const name of ["play", "pause", "ended", "timeupdate", "loadedmetadata", "durationchange"]) {
  Preview.audio.addEventListener(name, () => {
    if (Preview.scope && !Preview.scope.isConnected) Preview.stop(); else Preview.refresh();
  });
}
Preview.audio.addEventListener("error", () => {
  if (Preview.track) { toast(tr("preview_failed"), "err"); Preview.stop(); }
});

/* A ▶/⏸ button for a track ({id, title, duration}). */
function previewButton(track) {
  const button = h("button", { class: "btn small icon", onclick: (e) => {
    e.stopPropagation();
    Preview.toggle(track, button.closest(".overlay") || button.closest("main"));
  } });
  Preview.buttons.set(button, track.id);
  Preview.paintButton(button, track.id);
  return button;
}

function previewBar(track) {
  const range = h("input", { type: "range", class: "seek", min: 0, max: track.duration || 0, step: 1, value: 0, "aria-label": tr("seek"),
    oninput: (e) => { Preview.dragging = true; Preview.audio.currentTime = Number(e.target.value); Preview.refresh(); },
    onchange: () => { Preview.dragging = false; },
    onpointerup: () => setTimeout(() => { Preview.dragging = false; }, 200) });
  const time = h("span", { class: "muted small previewtime" });
  const close = h("button", { class: "btn small icon", title: tr("close"), "aria-label": tr("close"), onclick: () => Preview.stop() }, "✕");
  const bar = { el: h("div", { class: "previewbar" }, range, time, close), range, time };
  Preview.bars.add(bar);
  Preview.paintBar(bar);
  return bar.el;
}

/* Keeps the seek bar of the track being listened to right under its row. Rows carry data-preview-id. Returns the
   function a list calls after it has rebuilt its rows. */
function previewSlot(box) {
  const place = () => {
    box.querySelectorAll(".previewslot").forEach((n) => n.remove());
    box.querySelectorAll(".previewing").forEach((n) => n.classList.remove("previewing"));
    const current = Preview.track;
    if (!current) return;
    const row = [...box.querySelectorAll("[data-preview-id]")].find((n) => n.dataset.previewId === current.id);
    if (!row) return;
    row.classList.add("previewing");
    const bar = previewBar(current);
    row.after(row.tagName === "TR" ? h("tr", { class: "previewslot" }, h("td", { colspan: 99 }, bar))
      : row.tagName === "LI" ? h("li", { class: "previewslot" }, bar)
        : h("div", { class: "previewslot" }, bar));
  };
  Preview.watchers.set(box, place);
  place();
  return place;
}

/* A volume slider (0 to 150 %) with ticks under it, so that it is clear where the volume is aimed: a long tick at 0,
   50, 100 and 150, a short one at 25, 75 and 125. The slider is drawn like the seek bars, so that the ticks line up with
   the middle of its handle in every browser. Returns {el, paint}; call paint() after setting the value from code. */
function volumeSlider(input) {
  input.classList.add("seek", "vol");
  const paint = () => input.style.setProperty("--pos", (Number(input.value) / Number(input.max)) * 100 + "%");
  input.addEventListener("input", paint);
  const ticks = h("div", { class: "voltick", "aria-hidden": "true" }, [0, 25, 50, 75, 100, 125, 150].map((pct) => {
    const tick = h("span", { class: "tick" + (pct % 50 === 0 ? " major" : "") });
    tick.style.setProperty("--at", pct / 150);
    return tick;
  }));
  paint();
  return { el: h("div", { class: "voltrack" }, input, ticks), paint };
}

/* "m:ss.d" for a point in a track, and the reverse: seconds, "m:ss" or "m:ss.d" (a comma works as well). */
function fmtPoint(sec) {
  if (sec === null || sec === undefined) return "";
  const whole = Math.floor(sec), tenth = Math.round((sec - whole) * 10);
  const s = tenth === 10 ? whole + 1 : whole, t = tenth === 10 ? 0 : tenth;
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0") + (t ? "." + t : "");
}
function parsePoint(text) {
  const raw = String(text || "").trim().replace(",", ".");
  if (!raw) return null;
  const m = /^(?:(\d+):)?(\d+(?:\.\d+)?)$/.exec(raw);
  return m ? (m[1] ? Number(m[1]) * 60 : 0) + Number(m[2]) : NaN;
}

/* Runs fn at most once per `ms` while it is called over and over, with the latest arguments, and once more at the end. */
function throttle(fn, ms) {
  let last = 0, timer = null, pending = null;
  return (...args) => {
    pending = args;
    const wait = ms - (Date.now() - last);
    if (wait <= 0) {
      clearTimeout(timer);
      timer = null;
      last = Date.now();
      fn(...pending);
      pending = null;
    } else if (!timer) {
      timer = setTimeout(() => { timer = null; last = Date.now(); if (pending) { fn(...pending); pending = null; } }, wait);
    }
  };
}

function debounce(fn, ms) {
  let timer = null;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

function toast(message, kind) {
  const el = h("div", { class: "toast " + (kind || "") }, message);
  $("#toasts").append(el);
  setTimeout(() => el.remove(), 5500);
}
function $(sel, root) { return (root || document).querySelector(sel); }

function errorText(err) {
  const raw = (err && err.message) || "error";
  const [code, arg] = raw.split(":");
  const key = "err." + code;
  const msg = tr(key, { n: arg });
  return msg === key ? raw : msg;
}
const fail = (err) => toast(errorText(err), "err");

async function api(method, path, body) {
  const opts = { method, headers: { "X-Melomancer": "1" }, credentials: "same-origin" };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty body */ }
  if (!res.ok) {
    if (res.status === 401 && path !== "/api/auth/login") { state.user = null; stopPolling(); render(); }
    const code = data && typeof data.detail === "string" ? data.detail : "http_" + res.status;
    const err = new Error(code);
    err.status = res.status;
    throw err;
  }
  return data;
}

/* ---------- dialogs ---------- */

function modal(title, body, actions) {
  return new Promise((resolve) => {
    const close = (value) => { overlay.remove(); document.removeEventListener("keydown", onKey); resolve(value); };
    const onKey = (e) => {
      if (e.key === "Escape") close(undefined);
      if (e.key === "Enter" && e.target.tagName === "INPUT" && e.target.type !== "checkbox") {
        const primary = $("button.primary", overlay);
        if (primary) primary.click();
      }
    };
    const buttons = (actions || []).map((a) => h("button", {
      class: "btn " + (a.class || ""),
      onclick: async () => {
        if (a.run) {
          const result = await a.run();
          if (result === false) return;
          close(result === undefined ? a.value : result);
        } else close(a.value);
      },
    }, a.label));
    const overlay = h("div", { class: "overlay" },
      h("div", { class: "dialog", role: "dialog", "aria-modal": "true" },
        h("h3", {}, title), body, h("div", { class: "dialog-actions" }, buttons)));
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) close(undefined); });
    document.addEventListener("keydown", onKey);
    document.body.append(overlay);
    const first = $("input:not([type=checkbox]), select, textarea", overlay);
    if (first) first.focus();
  });
}

async function confirmDialog(text, danger) {
  const v = await modal(tr("confirm"), h("p", {}, text), [
    { label: tr("cancel"), value: false },
    { label: tr("ok"), class: danger ? "danger" : "primary", value: true },
  ]);
  return v === true;
}

async function promptDialog(title, label, initial, type) {
  const input = h("input", { type: type || "text", value: initial || "", "aria-label": label, maxlength: 100 });
  const v = await modal(title, h("div", { class: "stack" }, h("label", {}, label), input), [
    { label: tr("cancel"), value: null },
    { label: tr("ok"), class: "primary", run: () => input.value.trim() || false },
  ]);
  return v === undefined ? null : v;
}

/* ---------- data loading ---------- */

async function loadTracks() {
  const [tracks, tags] = await Promise.all([api("GET", "/api/tracks"), api("GET", "/api/tags")]);
  state.tracks = tracks;
  state.tags = tags;
}
async function loadSets() { state.sets = await api("GET", "/api/sets" + (state.showAllSets ? "?all=true" : "")); }

function allTagNames() {
  return [...new Set([...state.tags.shared.map((x) => x.tag), ...state.tags.mine.map((x) => x.tag)])].sort();
}
function trackMatches(track, f) {
  if (f.q) {
    const q = f.q.toLowerCase();
    if (!track.title.toLowerCase().includes(q) && !track.tags.some((x) => x.includes(q)) &&
        !track.my_tags.some((x) => x.includes(q))) return false;
  }
  if (f.tag && !track.tags.includes(f.tag) && !track.my_tags.includes(f.tag)) return false;
  if (f.mine && track.owner_id !== state.user.id) return false;
  return true;
}
const parseTags = (text) => text.split(",").map((x) => x.trim()).filter(Boolean);

/* Every tag the user can use (shared + personal) with the number of tracks that carry it. */
function allTagPool() {
  const counts = new Map();
  for (const t of state.tracks) for (const tag of new Set([...t.tags, ...t.my_tags])) counts.set(tag, (counts.get(tag) || 0) + 1);
  return [...counts].map(([tag, count]) => ({ tag, count }));
}

/* Asks for the name, the kind and, for an automatic playlist, its tag rule. Resolves to a request body or null. */
async function newPlaylistDialog() {
  const name = h("input", { maxlength: 100, "aria-label": tr("name") });
  const kind = h("select", { "aria-label": tr("playlist_type") },
    h("option", { value: "manual" }, tr("kind_manual")), h("option", { value: "tags" }, tr("kind_tags")));
  const mode = h("select", { "aria-label": tr("match_mode") },
    h("option", { value: "any" }, tr("mode_any")), h("option", { value: "all" }, tr("mode_all")));
  const tags = tagInput([], allTagPool());
  const rule = h("div", { class: "stack hidden" }, h("label", { class: "small" }, tr("rule_tags")), tags.el, mode,
    h("div", { class: "muted small" }, tr("auto_hint")));
  kind.addEventListener("change", () => rule.classList.toggle("hidden", kind.value !== "tags"));
  const body = await modal(tr("new_playlist"), h("div", { class: "stack" },
    h("label", {}, tr("name")), name, h("label", {}, tr("playlist_type")), kind, rule), [
    { label: tr("cancel"), value: null },
    { label: tr("ok"), class: "primary", run: () => {
      if (!name.value.trim()) return false;
      const chosen = kind.value === "tags" ? tags.get() : [];
      if (kind.value === "tags" && !chosen.length) { toast(tr("pick_a_tag"), "err"); return false; }
      return { name: name.value.trim(), kind: kind.value, tags: chosen, mode: mode.value };
    } },
  ]);
  return body || null;
}

/* Tag field: chosen tags as chips, suggestions from tags that already exist (most used first), free typing for new ones.
   pool = [{tag, count}], opts = {placeholder, onchange}. Returns {el, get()}. */
function tagInput(initial, pool, opts) {
  const options = opts || {};
  const chosen = new Set(initial || []);
  const ranked = [...(pool || [])].sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag));
  const chipBox = h("div", { class: "taglist" });
  const input = h("input", { placeholder: options.placeholder || tr("tags_placeholder"), autocomplete: "off", maxlength: 40,
    "aria-label": options.placeholder || tr("tags_placeholder") });
  const suggestBox = h("div", { class: "suggest" });
  const normalise = (raw) => raw.trim().toLowerCase().replace(/\s+/g, " ").slice(0, 40);
  const changed = () => { if (options.onchange) options.onchange([...chosen]); };
  const add = (raw) => {
    for (const part of String(raw).split(",")) { const tag = normalise(part); if (tag) chosen.add(tag); }
    input.value = ""; paint(); changed();
  };
  const remove = (tag) => { chosen.delete(tag); paint(); changed(); };
  function paint() {
    chipBox.replaceChildren(...[...chosen].map((t) => h("span", { class: "chip active", title: tr("remove"), onclick: () => remove(t) }, t + " ×")));
    const q = normalise(input.value);
    const matches = ranked.filter((x) => !chosen.has(x.tag) && (!q || x.tag.includes(q))).slice(0, 14);
    suggestBox.replaceChildren(...matches.map((x) => h("span", { class: "chip", onclick: () => { add(x.tag); input.focus(); } },
      x.tag, h("span", { class: "muted" }, " " + x.count))));
    if (q && !chosen.has(q) && !ranked.some((x) => x.tag === q)) {
      suggestBox.append(h("span", { class: "chip new", onclick: () => { add(q); input.focus(); } }, tr("add_tag", { tag: q })));
    }
  }
  input.addEventListener("input", paint);
  input.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === ",") && input.value.trim()) { e.preventDefault(); e.stopPropagation(); add(input.value); }
    else if (e.key === "Backspace" && !input.value && chosen.size) remove([...chosen].pop());
  });
  paint();
  return { el: h("div", { class: "taginput" }, chipBox, input, suggestBox), get: () => { if (input.value.trim()) add(input.value); return [...chosen]; } };
}

/* ---------- shell ---------- */

function render() {
  const root = $("#app");
  if (Preview.track) Preview.stop();  // a new screen: whatever was being listened to ends
  root.replaceChildren();
  document.documentElement.lang = state.lang;
  if (!state.user) { root.append(viewLogin()); return; }
  const tabs = [["player", "tab.player"], ["library", "tab.library"], ["playlists", "tab.playlists"], ["downloads", "tab.downloads"]];
  if (state.user.role === "admin") tabs.push(["users", "tab.users"], ["settings", "tab.settings"]);
  const main = h("main", {});
  root.append(
    h("header", { class: "top" },
      h("span", { class: "brand" }, "Melomancer"),
      h("nav", { class: "tabs" }, tabs.map(([id, label]) => h("button", {
        class: state.tab === id ? "active" : "", onclick: () => { state.tab = id; stopPolling(); render(); },
      }, tr(label)))),
      h("span", { class: "grow" }),
      h("div", { class: "hdr-right" }, themeMenu(), langToggle(), userMenu())),
    main,
    footer());
  const views = { player: viewPlayer, library: viewLibrary, playlists: viewPlaylists, downloads: viewDownloads, users: viewUsers, settings: viewSettings };
  views[state.tab](main).catch(fail);
}

const REPO_URL = "https://github.com/RadzuPL/melomancer";
function footer() {
  const link = (href, text) => h("a", { href, target: "_blank", rel: "noopener noreferrer" }, text);
  const version = state.system ? state.system.version : "";
  return h("footer", { class: "foot" }, link(REPO_URL, "Melomancer"), " ",
    version ? link(REPO_URL + "/releases", version) : null, " · by ", link("https://radzu.net/", "Radzu"));
}

/* A button that opens a small list. `items` is a function so that the list is current each time it opens. */
function menu(trigger, items) {
  const list = h("div", { class: "menu hidden", role: "menu" });
  const wrap = h("div", { class: "dropdown" }, trigger, list);
  const close = () => {
    list.classList.add("hidden");
    trigger.setAttribute("aria-expanded", "false");
    document.removeEventListener("mousedown", away);
    document.removeEventListener("keydown", escape);
  };
  const away = (e) => { if (!wrap.contains(e.target)) close(); };
  const escape = (e) => { if (e.key === "Escape") { close(); trigger.focus(); } };
  trigger.setAttribute("aria-haspopup", "menu");
  trigger.setAttribute("aria-expanded", "false");
  trigger.addEventListener("click", () => {
    if (!list.classList.contains("hidden")) { close(); return; }
    list.replaceChildren(...items().map((it) => h("button", { class: "menuitem" + (it.active ? " active" : ""), role: "menuitem",
      onclick: () => { close(); it.onclick(); } }, it.label)));
    list.classList.remove("hidden");
    trigger.setAttribute("aria-expanded", "true");
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
  });
  return wrap;
}

function langToggle() {
  const other = state.lang === "pl" ? "en" : "pl";
  const label = tr("switch_language", { lang: other.toUpperCase() });
  return h("button", { class: "ghost", title: label, "aria-label": label, onclick: () => setLang(other) }, state.lang.toUpperCase());
}

function themeMenu() {
  const icons = { auto: "◐", light: "☀", dark: "☾" };
  const order = ["auto", "light", "dark"];
  const button = h("button", { class: "ghost icon-only" });
  const paint = () => {
    const mode = MelomancerTheme.get();
    const label = tr("theme") + ": " + tr("theme_" + mode);
    button.textContent = icons[mode];
    button.title = label;
    button.setAttribute("aria-label", label);
  };
  button.addEventListener("click", () => {
    MelomancerTheme.set(order[(order.indexOf(MelomancerTheme.get()) + 1) % order.length]);
    paint();
  });
  paint();
  return button;
}

function userMenu() {
  const trigger = h("button", { class: "btn small" }, state.user.username + " ▾");
  return menu(trigger, () => [
    { label: tr("change_password"), onclick: accountDialog },
    { label: tr("logout"), onclick: logout },
  ]);
}

async function setLang(lang) {
  state.lang = lang;
  pref("lang", lang);
  try { await api("PATCH", "/api/auth/me", { lang }); } catch (_) { /* cosmetic */ }
  render();
}

async function logout() {
  LocalPlayer.disable();  // the sound belongs to the person who logged in
  try { await api("POST", "/api/auth/logout"); } catch (_) { /* already gone */ }
  state.user = null;
  stopPolling();
  render();
}

async function accountDialog() {
  const current = h("input", { type: "password", autocomplete: "current-password" });
  const next = h("input", { type: "password", autocomplete: "new-password" });
  await modal(tr("change_password"), h("div", { class: "stack" },
    h("div", { class: "muted" }, state.user.username + " (" + tr("role." + state.user.role) + ")"),
    h("label", {}, tr("current_password")), current,
    h("label", {}, tr("new_password") + " (" + tr("min_chars", { n: 10 }) + ")"), next), [
    { label: tr("close"), value: null },
    {
      label: tr("change_password"), class: "primary", run: async () => {
        try { await api("POST", "/api/auth/password", { current: current.value, new: next.value }); toast(tr("saved"), "ok"); }
        catch (err) { fail(err); return false; }
      },
    },
  ]);
}

/* ---------- login ---------- */

function viewLogin() {
  const user = h("input", { autocomplete: "username", required: true, "aria-label": tr("username") });
  const pass = h("input", { type: "password", autocomplete: "current-password", required: true, "aria-label": tr("password") });
  const form = h("form", {
    onsubmit: async (e) => {
      e.preventDefault();
      try {
        state.user = await api("POST", "/api/auth/login", { username: user.value.trim(), password: pass.value });
        state.lang = state.user.lang || state.lang;
        state.system = await api("GET", "/api/system");
        render();
      } catch (err) { fail(err); pass.value = ""; }
    },
  }, h("label", {}, tr("username")), user, h("label", {}, tr("password")), pass,
  h("button", { class: "btn primary", type: "submit" }, tr("login")));
  return h("div", { class: "login card" }, h("h1", {}, "Melomancer"), form,
    h("div", { class: "row" }, h("span", { class: "grow" }), themeMenu(),
      h("button", { class: "ghost", title: tr("switch_language", { lang: (state.lang === "pl" ? "en" : "pl").toUpperCase() }),
        onclick: () => { state.lang = state.lang === "pl" ? "en" : "pl"; pref("lang", state.lang); render(); } }, state.lang.toUpperCase())));
}

/* ---------- player ---------- */

function stopPolling() { clearInterval(state.player.timer); state.player.timer = null; }

async function viewPlayer(main) {
  const ps = state.player;
  const [guilds, , system] = await Promise.all([api("GET", "/api/player/guilds"), loadSets(), api("GET", "/api/system"), loadTracks()]);
  state.system = system;
  ps.guilds = guilds;
  if (!guilds.some((g) => g.id === ps.guildId)) ps.guildId = guilds.some((g) => g.id === pref("guild")) ? pref("guild") : (guilds[0] ? guilds[0].id : "");
  LocalPlayer.applyConfig(system, true);
  if (pref("local") === "1" && !LocalPlayer.on) { LocalPlayer.on = true; LocalPlayer.volume = Number(pref("local_volume") || 40) / 100; }
  const own = state.sets;
  if (!own.some((s) => String(s.id) === ps.setId)) ps.setId = own.some((s) => String(s.id) === pref("set")) ? pref("set") : (own[0] ? String(own[0].id) : "");
  const guild = () => ps.guilds.find((g) => g.id === ps.guildId);

  const guildSel = h("select", { "aria-label": tr("server"), onchange: (e) => { ps.guildId = e.target.value; pref("guild", ps.guildId); ps.channelId = ""; ps.st = null; fillChannels(); poll(); } });
  const chanSel = h("select", { "aria-label": tr("channel"), onchange: (e) => { ps.channelId = e.target.value; pref("channel", ps.channelId); } });
  const status = h("span", { class: "badge" });
  const connectBtn = h("button", { class: "btn primary", onclick: toggleConnect });
  const localBtn = h("button", { class: "btn primary", onclick: toggleLocal });
  const localHint = h("p", { class: "muted small hidden" }, tr("local_hint"));
  const notice = system.bot_status !== "ready" ? h("div", { class: "notice" }, tr("bot." + system.bot_status)) : null;
  const titleEl = h("div", { class: "title" });
  const subEl = h("div", { class: "muted small" });
  let seeking = false;
  const seekBar = h("input", { type: "range", class: "seek", min: 0, max: 0, step: 1, value: 0, disabled: true, "aria-label": tr("seek"),
    oninput: (e) => { seeking = true; timeEl.textContent = fmtTime(Number(e.target.value)) + " / " + fmtTime(Number(e.target.max)); },
    onchange: async (e) => {
      try {
        if (LocalPlayer.on) { await LocalPlayer.seek(Number(e.target.value)); applyState(LocalPlayer.snapshot()); }
        else applyState(await api("POST", `/api/player/${ps.guildId}/seek`, { seconds: Number(e.target.value) }));
      } catch (err) { fail(err); }
      seeking = false;
    },
    onpointerup: () => setTimeout(() => { seeking = false; }, 300) });
  const timeEl = h("span", { class: "muted small" });
  const btn = (label, title, fn) => h("button", { class: "btn", title, "aria-label": title, onclick: fn }, label);
  const prevB = btn("⏮", tr("prev"), () => control("prev"));
  const toggleB = btn("⏯", tr("pause_resume"), () => {
    if (armedReady()) return playArmed();
    control(ps.st && ps.st.state === "paused" ? "resume" : "pause");
  });
  const nextB = btn("⏭", tr("next"), () => control("next"));
  const stopB = btn("⏹", tr("stop"), () => control("stop"));
  const loopB = h("button", { class: "btn", onclick: () => options({ loop: !(ps.st && ps.st.loop) }) }, "🔁 " + tr("loop"));
  const shuffleB = h("button", { class: "btn", onclick: () => options({ shuffle: !(ps.st && ps.st.shuffle) }) }, "🔀 " + tr("shuffle"));
  const volLabel = h("span", { class: "small vollabel" }, "");
  let dragging = false;
  // The bot follows the slider while it is dragged (the server glides between the values, so it sounds smooth).
  // Requests go out one after another, so that an older value can never arrive after a newer one.
  let volumeChain = Promise.resolve();
  const postVolume = (v) => {
    if (LocalPlayer.on) { LocalPlayer.setVolume(v / 100); pref("local_volume", String(v)); return Promise.resolve(LocalPlayer.snapshot()); }
    volumeChain = volumeChain.then(() => api("POST", `/api/player/${ps.guildId}/volume`, { volume: v / 100 }));
    return volumeChain;
  };
  const sendVolume = throttle((v) => { postVolume(v).catch(fail); }, 80);
  const vol = h("input", { type: "range", min: 0, max: 150, step: 1, value: 40, "aria-label": tr("volume"),
    onpointerdown: () => { dragging = true; }, onpointerup: () => { dragging = false; },
    onchange: async (e) => { dragging = false; try { applyState(await postVolume(Number(e.target.value))); } catch (err) { fail(err); } },
    oninput: (e) => { volLabel.textContent = e.target.value + "%"; sendVolume(Number(e.target.value)); } });
  const volUi = volumeSlider(vol);
  const padsBox = h("div", {});
  const quickChips = h("div", { class: "quickchips" });
  const quickInfo = h("span", { class: "muted small" });
  const quickMode = h("select", { "aria-label": tr("match_mode"), onchange: (e) => { state.quick.mode = e.target.value; paintQuick(); } },
    h("option", { value: "any", selected: state.quick.mode === "any" }, tr("mode_any")),
    h("option", { value: "all", selected: state.quick.mode === "all" }, tr("mode_all")));
  const quickPlay = h("button", { class: "btn primary", onclick: () => playQuick() });
  const quickClear = h("button", { class: "btn", onclick: () => { state.quick.tags.clear(); paintQuick(); } }, tr("clear"));
  const queueBox = h("div", { class: "queue" });
  const queueWrap = h("div", { class: "hidden" }, h("div", { class: "muted small" }, tr("queue_hint")), queueBox);
  let queueKey = "";
  const setSel = h("select", { "aria-label": tr("set"), onchange: (e) => { ps.setId = e.target.value; pref("set", ps.setId); fillPads(); } },
    own.map((s) => h("option", { value: s.id, selected: String(s.id) === ps.setId }, s.name + (state.showAllSets ? " (" + s.owner + ")" : ""))));
  const allBox = state.user.role === "admin"
    ? h("label", { class: "row small" }, h("input", { type: "checkbox", checked: state.showAllSets, onchange: async (e) => { state.showAllSets = e.target.checked; render(); } }), tr("show_all_sets"))
    : null;

  put(main, 
    notice,
    h("div", { class: "card" }, h("div", { class: "row" },
      guildSel, chanSel, connectBtn, localBtn, status, h("span", { class: "grow" }),
      guilds.length === 0 && system.bot_status === "ready" ? h("span", { class: "muted small" }, tr("no_servers")) : null), localHint),
    h("div", { class: "card now" }, titleEl, subEl, seekBar, timeEl,
      h("div", { class: "controls" }, prevB, toggleB, nextB, stopB, loopB, shuffleB,
        h("div", { class: "volume" }, "🔈", volUi.el, volLabel)),
      queueWrap),
    h("div", { class: "card" }, h("div", { class: "row" }, h("h2", { class: "grow" }, tr("playlists")), setSel, allBox), padsBox),
    h("div", { class: "card" }, h("h2", {}, "🏷 " + tr("quick_title")), h("p", { class: "muted small" }, tr("quick_hint")),
      quickChips, h("div", { class: "row" }, quickMode, quickPlay, quickClear, quickInfo)));

  function fillChannels() {
    guildSel.replaceChildren(...ps.guilds.map((g) => h("option", { value: g.id, selected: g.id === ps.guildId }, g.name)));
    const g = guild();
    const channels = g ? g.channels : [];
    if (!channels.some((c) => c.id === ps.channelId)) ps.channelId = channels.some((c) => c.id === pref("channel")) ? pref("channel") : (channels[0] ? channels[0].id : "");
    chanSel.replaceChildren(...channels.map((c) => h("option", { value: c.id, selected: c.id === ps.channelId }, "🔊 " + c.name)));
    if (g && !ps.st) ps.st = g.state;
    applyState();
  }

  function fillPads() {
    const set = state.sets.find((s) => String(s.id) === ps.setId);
    padsBox.replaceChildren();
    if (!set) { padsBox.append(h("p", { class: "muted" }, tr("no_sets_hint"))); return; }
    if (!set.playlists.length && !set.groups.some((g) => g.playlists.length)) padsBox.append(h("p", { class: "muted" }, tr("no_groups_hint")));
    const pad = (p) => h("button", {
      class: "pad" + (ps.st && ps.st.playlist && ps.st.playlist.id === p.id ? " active" : ""), "data-id": p.id,
      onclick: () => playPad(p),
    }, (p.kind === "tags" ? "🏷 " : "") + p.name, h("span", { class: "count" }, tr("n_tracks", { n: p.count - p.missing }) + (p.missing ? " ⚠ " + p.missing : "")));
    if (set.playlists.length) padsBox.append(h("div", { class: "pads" }, set.playlists.map(pad)));
    for (const group of set.groups) {
      if (group.playlists.length) padsBox.append(h("h3", {}, "📁 " + group.name), h("div", { class: "pads" }, group.playlists.map(pad)));
    }
  }

  function applyState(st) {
    if (st) { ps.st = st; ps.stAt = Date.now(); }
    const s = ps.st;
    const connected = !!(s && s.connected);
    const here = LocalPlayer.on;
    status.className = "badge " + (connected || here ? "ok" : "");
    status.textContent = here ? tr("local_badge") : (connected ? tr("connected_to", { name: s.channel_name }) : tr("disconnected"));
    connectBtn.textContent = connected && s.channel_id === ps.channelId ? tr("disconnect") : (connected ? tr("move") : tr("connect"));
    // Playing here and playing on Discord exclude each other: one button blocks the other.
    const busyElsewhere = connected && !here && !!s.controller_id && s.controller_id !== state.user.id && s.state !== "idle";
    connectBtn.disabled = here;
    connectBtn.title = here ? tr("local_blocks_connect") : "";
    localBtn.textContent = "🖥 " + (here ? tr("stop_here") : tr("play_here"));
    localBtn.classList.toggle("on", here);
    localBtn.disabled = !here && connected && !busyElsewhere;
    localBtn.title = localBtn.disabled ? tr("connect_blocks_local") : "";
    for (const el of [guildSel, chanSel]) el.classList.toggle("hidden", here);
    localHint.classList.toggle("hidden", !here);
    if (notice) notice.classList.toggle("hidden", here);
    const playing = s && s.state !== "idle";
    const armed = !playing && !here && ps.armed;
    titleEl.textContent = playing && s.now ? s.now.title : (armed ? tr("armed_title", { name: ps.armed.name }) : tr("nothing_playing"));
    subEl.textContent = playing && s.playlist ? s.playlist.name + (s.playlist.set ? " · " + s.playlist.set : "") + (s.controller ? " · " + s.controller : "")
      : (armed ? tr(connected ? "armed_ready" : "armed_connect") : "");
    for (const b of [prevB, toggleB, nextB, stopB]) b.disabled = !playing;
    toggleB.disabled = !playing && !armedReady();
    toggleB.textContent = (s && s.state === "paused") || (!playing && armed) ? "▶" : "⏸";
    loopB.classList.toggle("on", !!(s && s.loop));
    shuffleB.classList.toggle("on", !!(s && s.shuffle));
    if (s && !dragging) { vol.value = Math.round(s.volume * 100); volUi.paint(); volLabel.textContent = vol.value + "%"; }
    paintQueue(s, playing);
    for (const pad of padsBox.querySelectorAll(".pad")) {
      pad.classList.toggle("active", !!(playing && s.playlist && String(s.playlist.id) === pad.dataset.id));
      pad.classList.toggle("armed", !!(armed && ps.armed.target.playlist_id !== undefined && String(ps.armed.target.playlist_id) === pad.dataset.id));
    }
    tickBar();
  }

  function quickMatches() {
    const chosen = [...state.quick.tags];
    if (!chosen.length) return [];
    return state.tracks.filter((t) => {
      const own = new Set([...t.tags, ...t.my_tags]);
      return state.quick.mode === "all" ? chosen.every((c) => own.has(c)) : chosen.some((c) => own.has(c));
    });
  }

  function paintQuick() {
    const pool = allTagPool().sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag));
    const known = new Set(pool.map((x) => x.tag));
    for (const tag of [...state.quick.tags]) if (!known.has(tag)) state.quick.tags.delete(tag);  // tag no longer exists
    fill(quickChips, pool.length ? pool.map((x) => h("span", { class: "chip big" + (state.quick.tags.has(x.tag) ? " active" : ""),
      onclick: () => { state.quick.tags.has(x.tag) ? state.quick.tags.delete(x.tag) : state.quick.tags.add(x.tag); paintQuick(); } },
      x.tag, h("span", { class: "muted" }, " " + x.count))) : h("span", { class: "muted small" }, tr("no_tags_yet")));
    const n = quickMatches().length;
    quickPlay.textContent = tr("play_selection", { n });
    quickPlay.disabled = n === 0;
    quickClear.disabled = state.quick.tags.size === 0;
    quickInfo.textContent = state.quick.tags.size && !n ? tr("nothing_matches") : "";
  }

  async function playQuick() {
    const target = { tags: [...state.quick.tags], mode: state.quick.mode };
    if (LocalPlayer.on) return playHere(target);
    return playOnDiscord(target, "# " + target.tags.join(state.quick.mode === "all" ? " + " : " | "));
  }

  function paintQueue(s, playing) {
    const queue = playing && s.queue ? s.queue : [];
    queueWrap.classList.toggle("hidden", queue.length === 0);
    const key = queue.map((q) => q.track_id).join(",");
    if (key !== queueKey) {
      queueKey = key;
      queueBox.replaceChildren(...queue.map((q, i) => h("button", { class: "qrow", "data-index": i, title: q.title, onclick: () => jump(i) },
        h("span", { class: "muted small qnum" }, i + 1), h("span", { class: "t" }, q.title), h("span", { class: "muted small" }, fmtTime(q.duration)))));
    }
    const current = playing && s.now ? s.now.index : -1;
    for (const row of queueBox.children) row.classList.toggle("current", Number(row.dataset.index) === current);
  }

  async function jump(index) {
    try {
      if (LocalPlayer.on) { await LocalPlayer.jump(index); applyState(LocalPlayer.snapshot()); }
      else applyState(await api("POST", `/api/player/${ps.guildId}/jump`, { index }));
    } catch (err) { fail(err); }
  }

  function tickBar() {
    if (LocalPlayer.on) { ps.st = LocalPlayer.snapshot(); ps.stAt = Date.now(); }
    const s = ps.st;
    if (seeking) return;  // the person is dragging the handle: do not fight them
    if (!s || !s.now) {
      seekBar.disabled = true; seekBar.max = 0; seekBar.value = 0; seekBar.style.setProperty("--pos", "0%"); timeEl.textContent = "";
      return;
    }
    const elapsed = s.now.elapsed + (s.state === "playing" ? (Date.now() - ps.stAt) / 1000 : 0);
    const total = s.now.duration;
    seekBar.disabled = !total;
    seekBar.max = total || 0;
    seekBar.value = Math.min(elapsed, total || 0);
    seekBar.style.setProperty("--pos", (total ? Math.min(100, (elapsed / total) * 100) : 0) + "%");
    timeEl.textContent = fmtTime(elapsed) + (total ? " / " + fmtTime(total) : "");
  }

  async function poll() {
    if (!ps.guildId || document.hidden || state.tab !== "player" || LocalPlayer.on) return;
    try { applyState(await api("GET", `/api/player/${ps.guildId}/state`)); } catch (_) { /* transient */ }
  }
  async function toggleConnect() {
    if (!ps.guildId) return;
    const s = ps.st;
    try {
      if (s && s.connected && s.channel_id === ps.channelId) applyState(await api("POST", `/api/player/${ps.guildId}/disconnect`));
      else applyState(await api("POST", `/api/player/${ps.guildId}/connect`, { channel_id: ps.channelId }));
    } catch (err) { fail(err); }
  }
  async function control(action) {
    try {
      if (LocalPlayer.on) {
        const run = { pause: () => LocalPlayer.pause(), resume: () => LocalPlayer.resume(), next: () => LocalPlayer.skip(1),
          prev: () => LocalPlayer.skip(-1), stop: () => LocalPlayer.stop() }[action];
        await run();
        applyState(LocalPlayer.snapshot());
      } else applyState(await api("POST", `/api/player/${ps.guildId}/${action}`));
    } catch (err) { fail(err); }
  }
  async function options(body) {
    try {
      if (LocalPlayer.on) { LocalPlayer.setOptions(body); applyState(LocalPlayer.snapshot()); }
      else applyState(await api("PATCH", `/api/player/${ps.guildId}/options`, body));
    } catch (err) { fail(err); }
  }
  async function playHere(target) {
    try {
      if (Preview.track) Preview.stop();  // what was being auditioned would play over the music
      await LocalPlayer.play(target);
      applyState(LocalPlayer.snapshot());
    } catch (err) { fail(err); }
  }
  async function toggleLocal() {
    try {
      if (LocalPlayer.on) {
        LocalPlayer.disable();
        pref("local", "0");
        ps.st = null;
        fillChannels();
        poll();
      } else {
        if (Preview.track) Preview.stop();
        ps.armed = null;
        await LocalPlayer.enable();
        pref("local", "1");
        LocalPlayer.setVolume(Number(pref("local_volume") || 40) / 100);
        applyState(LocalPlayer.snapshot());
      }
    } catch (err) { fail(err); }
  }
  async function playPad(p) {
    if (LocalPlayer.on) return playHere({ playlist_id: p.id });
    return playOnDiscord({ playlist_id: p.id }, p.name);
  }
  /* Never connects by itself: a bot that is not in a channel only gets the playlist loaded (selected, stopped).
     The person connects on purpose, and then starts it with ▶ or by pressing the playlist again. */
  async function playOnDiscord(target, name) {
    if (!ps.guildId) return toast(tr("pick_server"), "err");
    if (!(ps.st && ps.st.connected)) { ps.armed = { target, name }; applyState(); return; }
    try {
      ps.armed = null;
      applyState(await api("POST", `/api/player/${ps.guildId}/play`, target));
    } catch (err) { fail(err); }
  }
  const armedReady = () => !LocalPlayer.on && !!ps.armed && !!(ps.st && ps.st.connected) && ps.st.state === "idle";
  async function playArmed() {
    const { target, name } = ps.armed;
    await playOnDiscord(target, name);
  }

  fillChannels();
  fillPads();
  paintQuick();
  if (LocalPlayer.on) applyState(LocalPlayer.snapshot());
  // The engine outlives this screen: it tells whichever player screen is on display what it is doing.
  LocalPlayer.subscribe((snap) => {
    if (!document.body.contains(seekBar)) return false;
    if (LocalPlayer.on) applyState(snap);
    return true;
  });
  stopPolling();
  ps.timer = setInterval(() => { poll(); }, 2500);
  const tickId = setInterval(() => { if (state.tab !== "player" || !document.body.contains(seekBar)) clearInterval(tickId); else tickBar(); }, 1000);
  poll();
}

/* ---------- library ---------- */

const uploader = { items: [], running: 0, box: null, onDone: null };

function dirTags(file) {
  const parts = (file.webkitRelativePath || "").split("/");
  return parts.slice(0, -1);
}

function queueFiles(files, withFolderTags, extra) {
  for (const file of files) {
    const m = file.name.toLowerCase().match(/\.[a-z0-9]+$/);
    const item = { file, status: "wait", msg: "", tags: withFolderTags ? dirTags(file) : [],
      shared: (extra && extra.shared) || [], mine: (extra && extra.mine) || [] };
    if (!m || !AUDIO_EXT.has(m[0])) { item.status = "skip"; item.msg = tr("err.unsupported_type"); }
    uploader.items.push(item);
  }
  pumpUploads();
  paintUploads();
}

function pumpUploads() {
  while (uploader.running < 2) {
    const next = uploader.items.find((i) => i.status === "wait");
    if (!next) break;
    next.status = "up";
    uploader.running++;
    paintUploads();
    sendOne(next).finally(() => {
      uploader.running--;
      if (!uploader.items.some((i) => i.status === "wait" || i.status === "up") && uploader.onDone) uploader.onDone();
      pumpUploads();
      paintUploads();
    });
  }
}

async function sendOne(item) {
  const body = new FormData();
  body.append("file", item.file, item.file.name);
  body.append("folder_tags", JSON.stringify(item.tags));
  body.append("tags", JSON.stringify(item.shared));
  body.append("my_tags", JSON.stringify(item.mine));
  try {
    const res = await api("POST", "/api/tracks/upload", body);
    item.status = res.status === "created" || res.status === "revived" ? "ok" : "dup";
    item.msg = tr("upload." + res.status);
  } catch (err) { item.status = "err"; item.msg = errorText(err); }
}

function paintUploads() {
  if (!uploader.box || !document.body.contains(uploader.box)) return;
  const icon = { wait: "⏳", up: "⬆", ok: "✅", dup: "♻", err: "❌", skip: "⏭" };
  uploader.box.replaceChildren(...uploader.items.slice(-60).map((i) =>
    h("div", {}, h("span", {}, icon[i.status]), h("span", { class: "name" }, i.file.name), h("span", { class: "muted" }, i.msg))));
  uploader.box.scrollTop = uploader.box.scrollHeight;
}

async function viewLibrary(main) {
  await loadTracks();
  const lib = state.lib;
  const list = h("div", {});
  const counter = h("span", { class: "muted small" });
  const bulk = h("div", { class: "bulk row hidden" });
  const uploadBox = h("div", { class: "uploads" });
  uploader.box = uploadBox;
  uploader.onDone = async () => { await loadTracks(); paintTable(); };
  const folderTags = h("input", { type: "checkbox", checked: true });
  const upShared = tagInput(state.upTags.shared, state.tags.shared, { onchange: (v) => { state.upTags.shared = v; } });
  const upMine = tagInput(state.upTags.mine, state.tags.mine, { onchange: (v) => { state.upTags.mine = v; } });
  const extraTags = () => ({ shared: upShared.get(), mine: upMine.get() });
  const fileInput = h("input", { type: "file", multiple: true, accept: "audio/*,.opus,.flac,.m4a,.ogg,.mp3,.wav,.webm,.aac", class: "hidden",
    onchange: (e) => { queueFiles([...e.target.files], false, extraTags()); e.target.value = ""; } });
  const dirInput = h("input", { type: "file", multiple: true, webkitdirectory: true, class: "hidden",
    onchange: (e) => { queueFiles([...e.target.files], folderTags.checked, extraTags()); e.target.value = ""; } });
  const drop = h("div", { class: "drop" }, tr("drop_here"));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); queueFiles([...e.dataTransfer.files], false, extraTags()); });

  const search = h("input", { type: "search", placeholder: tr("search"), value: lib.q, "aria-label": tr("search"),
    oninput: debounce((e) => { lib.q = e.target.value; paintTable(); }, 120) });
  const tagSel = h("select", { "aria-label": tr("tag"), onchange: (e) => { lib.tag = e.target.value; paintTable(); } });
  const fillTagSel = () => tagSel.replaceChildren(h("option", { value: "" }, tr("all_tags")),
    ...allTagNames().map((tag) => h("option", { value: tag, selected: tag === lib.tag }, tag)));
  fillTagSel();
  const mineBox = h("input", { type: "checkbox", checked: lib.mine, onchange: (e) => { lib.mine = e.target.checked; paintTable(); } });

  put(main, 
    h("div", { class: "card" }, h("h2", {}, tr("add_music")),
      h("div", { class: "row" },
        h("button", { class: "btn primary", onclick: () => fileInput.click() }, tr("choose_files")),
        h("button", { class: "btn", onclick: () => dirInput.click() }, tr("choose_folder")),
        h("label", { class: "row small" }, folderTags, tr("folders_as_tags")),
        h("span", { class: "muted small" }, tr("max_size", { n: state.system ? state.system.max_upload_mb : "?" }))),
      h("div", { class: "tagpair" },
        h("div", {}, h("label", { class: "small" }, tr("shared_tags_new")), upShared.el),
        h("div", {}, h("label", { class: "small" }, tr("my_tags_new")), upMine.el)),
      fileInput, dirInput, drop, uploadBox),
    h("div", { class: "card" },
      h("div", { class: "row" }, h("h2", { class: "grow" }, tr("tab.library")), counter),
      h("div", { class: "row" }, search, tagSel, h("label", { class: "row small" }, mineBox, tr("only_mine"))),
      list, bulk));
  paintUploads();
  const placePreview = previewSlot(list);

  function visible() { return state.tracks.filter((x) => trackMatches(x, lib)); }

  function paintTable() {
    fillTagSel();
    const rows = visible();
    counter.textContent = tr("n_of_m", { n: rows.length, m: state.tracks.length });
    for (const id of [...lib.selected]) if (!state.tracks.some((x) => x.id === id)) lib.selected.delete(id);
    const allBox = h("input", { type: "checkbox", "aria-label": tr("select_all"), checked: rows.length > 0 && rows.every((r) => lib.selected.has(r.id)),
      onchange: (e) => { for (const r of rows) e.target.checked ? lib.selected.add(r.id) : lib.selected.delete(r.id); paintTable(); } });
    list.replaceChildren(h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, allBox), h("th", {}, tr("title")), h("th", {}, tr("tags")), h("th", {}, tr("owner")), h("th", { class: "num" }, tr("length")), h("th", {}))),
      h("tbody", {}, rows.map((r) => h("tr", { class: lib.selected.has(r.id) ? "selected" : "", "data-preview-id": r.id },
        h("td", {}, h("input", { type: "checkbox", checked: lib.selected.has(r.id), "aria-label": r.title,
          onchange: (e) => { e.target.checked ? lib.selected.add(r.id) : lib.selected.delete(r.id); paintTable(); } })),
        h("td", { class: "title-cell", title: r.title }, r.title,
          r.trim_start !== null || r.trim_end !== null ? h("span", { class: "muted small", title: tr("trim_manual_badge") }, " ✂") : null),
        h("td", {}, r.tags.map((x) => h("span", { class: "chip", onclick: () => { lib.tag = x; tagSel.value = x; paintTable(); } }, x)),
          r.my_tags.map((x) => h("span", { class: "chip mine", title: tr("my_tag"), onclick: () => { lib.tag = x; paintTable(); } }, x))),
        h("td", { class: "muted small" }, r.owner),
        h("td", { class: "num" }, fmtTime(r.duration)),
        h("td", { class: "actions" },
          previewButton(r),
          h("button", { class: "btn small icon", title: tr("edit"), onclick: () => editTrack(r) }, "✎"),
          r.can_edit ? h("button", { class: "btn small icon danger", title: tr("delete"), onclick: () => deleteTrack(r) }, "✕") : null))))));
    placePreview();
    const n = lib.selected.size;
    bulk.classList.toggle("hidden", n === 0);
    fill(bulk, h("span", { class: "grow" }, tr("n_selected", { n })),
      h("button", { class: "btn primary", onclick: addSelectedToPlaylist }, tr("add_to_playlist")),
      h("button", { class: "btn", onclick: tagSelected }, tr("add_my_tag")),
      h("button", { class: "btn", onclick: () => { lib.selected.clear(); paintTable(); } }, tr("clear")));
  }

  async function editTrack(r) {
    const title = h("input", { value: r.title, maxlength: 200, disabled: !r.can_edit });
    const shared = tagInput(r.tags, state.tags.shared);
    const mine = tagInput(r.my_tags, state.tags.mine);

    /* Start and end of the track: empty means automatic (the silence analysis), a typed value wins over it. */
    const startText = fmtPoint(r.trim_start), endText = fmtPoint(r.trim_end);
    const autoStart = fmtPoint(r.lead || 0) || "0:00";
    const autoEnd = r.duration ? fmtPoint(r.trail ? r.duration - r.trail : r.duration) : "";
    const startIn = h("input", { type: "text", class: "timefield", inputmode: "decimal", value: startText, disabled: !r.can_edit,
      placeholder: tr("trim_auto", { v: autoStart }), "aria-label": tr("trim_start") });
    const endIn = h("input", { type: "text", class: "timefield", inputmode: "decimal", value: endText, disabled: !r.can_edit,
      placeholder: tr("trim_auto", { v: autoEnd }), "aria-label": tr("trim_end") });
    const here = (field) => () => {
      if (!Preview.track || Preview.track.id !== r.id) { toast(tr("trim_play_first"), "err"); return; }
      field.value = fmtPoint(Preview.audio.currentTime);
    };
    const pointRow = (label, field) => h("div", { class: "row" }, h("span", { class: "trimlabel" }, label), field,
      h("button", { class: "btn small", disabled: !r.can_edit, onclick: here(field) }, tr("trim_set_here")),
      h("button", { class: "btn small", disabled: !r.can_edit, title: tr("trim_auto_title"), onclick: () => { field.value = ""; } }, tr("trim_auto_btn")));
    const listenBox = h("div", {}, h("div", { class: "row", "data-preview-id": r.id }, previewButton(r),
      h("span", { class: "muted small" }, tr("trim_listen_hint"))));
    previewSlot(listenBox);

    const ok = await modal(tr("edit_track"), h("div", { class: "stack" },
      h("label", {}, tr("title")), title,
      h("label", {}, tr("shared_tags")), r.can_edit ? shared.el : h("div", { class: "muted small" }, r.tags.join(", ") || "–"),
      h("label", {}, tr("my_tags") + " (" + tr("only_you") + ")"), mine.el,
      h("label", {}, tr("trim_title")), listenBox, pointRow(tr("trim_start"), startIn), pointRow(tr("trim_end"), endIn),
      h("div", { class: "muted small" }, tr("trim_hint_edit")),
      r.source_url ? h("div", { class: "muted small" }, tr("source") + ": " + r.source_url) : null,
      r.title !== r.original_title ? h("div", { class: "muted small" }, tr("original") + ": " + r.original_title) : null), [
      { label: tr("cancel"), value: false },
      {
        label: tr("save"), class: "primary", run: async () => {
          try {
            if (r.can_edit) {
              const patch = { title: title.value, tags: shared.get() };
              const s0 = parsePoint(startIn.value), e0 = parsePoint(endIn.value);
              if (Number.isNaN(s0) || Number.isNaN(e0)) { toast(tr("err.bad_trim"), "err"); return false; }
              if (startIn.value.trim() !== startText) patch.trim_start = s0;   // null: back to automatic
              if (endIn.value.trim() !== endText) patch.trim_end = e0;
              await api("PATCH", `/api/tracks/${r.id}`, patch);
            }
            await api("PUT", `/api/tracks/${r.id}/my-tags`, { tags: mine.get() });
            return true;
          } catch (err) { fail(err); return false; }
        },
      },
    ]);
    if (ok) { await loadTracks(); paintTable(); }
  }

  async function deleteTrack(r) {
    try {
      const { playlists } = await api("GET", `/api/tracks/${r.id}/usage`);
      const text = playlists ? tr("delete_used", { title: r.title, n: playlists }) : tr("delete_unused", { title: r.title });
      if (!(await confirmDialog(text, true))) return;
      await api("DELETE", `/api/tracks/${r.id}${playlists ? "?force=true" : ""}`);
      lib.selected.delete(r.id);
      await loadTracks();
      paintTable();
    } catch (err) { fail(err); }
  }

  async function tagSelected() {
    const field = tagInput([], state.tags.mine);
    const add = await modal(tr("add_my_tag"), h("div", { class: "stack" }, h("label", {}, tr("my_tags") + " (" + tr("only_you") + ")"), field.el), [
      { label: tr("cancel"), value: null },
      { label: tr("ok"), class: "primary", run: () => { const v = field.get(); return v.length ? v : false; } },
    ]);
    if (!add) return;
    try {
      for (const id of lib.selected) {
        const track = state.tracks.find((x) => x.id === id);
        if (track) await api("PUT", `/api/tracks/${id}/my-tags`, { tags: [...new Set([...track.my_tags, ...add])] });
      }
      await loadTracks();
      paintTable();
      toast(tr("saved"), "ok");
    } catch (err) { fail(err); }
  }

  async function addSelectedToPlaylist() {
    await loadSets();
    const target = await choosePlaylist();
    if (!target) return;
    try {
      const res = await api("POST", `/api/playlists/${target}/items`, { track_ids: [...lib.selected] });
      toast(tr("added_n", { n: res.added }), "ok");
      lib.selected.clear();
      paintTable();
    } catch (err) { fail(err); }
  }

  paintTable();
}

async function choosePlaylist() {
  const sets = state.sets.filter((s) => s.owner_id === state.user.id);
  const options = [];
  for (const s of sets) {
    for (const p of s.playlists) if (p.kind !== "tags") options.push({ id: p.id, label: `${s.name} › ${p.name}` });
    for (const g of s.groups) for (const p of g.playlists) if (p.kind !== "tags") options.push({ id: p.id, label: `${s.name} › 📁 ${g.name} › ${p.name}` });
  }
  if (!options.length) { toast(tr("no_playlists_yet"), "err"); return null; }
  const sel = h("select", { "aria-label": tr("playlist") }, options.map((o) => h("option", { value: o.id }, o.label)));
  const v = await modal(tr("add_to_playlist"), h("div", { class: "stack" }, sel), [
    { label: tr("cancel"), value: null },
    { label: tr("ok"), class: "primary", run: () => sel.value },
  ]);
  return v || null;
}

async function pickTracks(title, multi, exclude) {
  if (!state.tracks.length) await loadTracks();
  const skip = exclude || new Set();
  const f = { q: "", tag: "", mine: false };
  const chosen = new Set();
  const listBox = h("div", { class: "picker-list" });
  const q = h("input", { type: "search", placeholder: tr("search"), oninput: (e) => { f.q = e.target.value; paint(); } });
  const tagSel = h("select", { onchange: (e) => { f.tag = e.target.value; paint(); } },
    h("option", { value: "" }, tr("all_tags")), ...allTagNames().map((x) => h("option", { value: x }, x)));
  function paint() {
    const candidates = state.tracks.filter((x) => !skip.has(x.id) && trackMatches(x, f));
    if (!candidates.length) { listBox.replaceChildren(h("p", { class: "muted small pad-text" }, tr(skip.size ? "nothing_left_to_add" : "no_matches"))); placePreview(); return; }
    listBox.replaceChildren(...candidates.slice(0, 300).map((x) => h("label", { "data-preview-id": x.id },
      h("input", { type: multi ? "checkbox" : "radio", name: "pick", checked: chosen.has(x.id), onchange: (e) => {
        if (!multi) chosen.clear();
        e.target.checked ? chosen.add(x.id) : chosen.delete(x.id);
      } }), previewButton(x), h("span", { class: "grow" }, x.title), h("span", { class: "muted small" }, fmtTime(x.duration)))));
    placePreview();
  }
  const placePreview = previewSlot(listBox);
  paint();
  const v = await modal(title, h("div", {}, h("div", { class: "row" }, q, tagSel), listBox), [
    { label: tr("cancel"), value: null },
    { label: tr("ok"), class: "primary", run: () => (chosen.size ? [...chosen] : false) },
  ]);
  return v || null;
}

/* ---------- playlists ---------- */

async function viewPlaylists(main) {
  await Promise.all([loadSets(), loadTracks()]);
  const tree = h("div", { class: "tree card" });
  const detail = h("div", { class: "card" });
  put(main, h("div", { class: "split" }, tree, detail));

  async function act(fn) { try { await fn(); await loadSets(); paintTree(); if (state.pl.selected) await paintDetail(); } catch (err) { fail(err); } }
  const move = (ids, index, delta) => { const copy = [...ids]; const [x] = copy.splice(index, 1); copy.splice(index + delta, 0, x); return copy; };
  const small = (label, title, fn, disabled) => h("button", { class: "btn small icon", title, "aria-label": title, onclick: fn, disabled }, label);

  function plRow(p, siblings, index, orderUrl, root) {
    const ids = siblings.map((x) => x.id);
    return h("div", { class: "pl" + (root ? " root" : "") + (state.pl.selected === p.id ? " active" : "") },
      h("button", { class: "name", onclick: () => { state.pl.selected = p.id; paintTree(); paintDetail().catch(fail); } },
        (p.kind === "tags" ? "🏷 " : "") + p.name + " (" + (p.count - p.missing) + (p.missing ? " ⚠" + p.missing : "") + ")"),
      small("▲", tr("up"), () => act(() => api("PUT", orderUrl, { ids: move(ids, index, -1) })), index === 0),
      small("▼", tr("down"), () => act(() => api("PUT", orderUrl, { ids: move(ids, index, 1) })), index === siblings.length - 1));
  }

  function paintTree() {
    fill(tree,
      h("div", { class: "row" }, h("h2", { class: "grow" }, tr("sets")),
        state.user.role === "admin" ? h("label", { class: "row small" }, h("input", { type: "checkbox", checked: state.showAllSets,
          onchange: async (e) => { state.showAllSets = e.target.checked; await loadSets(); paintTree(); } }), tr("show_all_sets")) : null,
        h("button", { class: "btn small primary", onclick: async () => {
          const name = await promptDialog(tr("new_set"), tr("name"), "");
          if (name) act(() => api("POST", "/api/sets", { name }));
        } }, "+ " + tr("set"))),
      state.sets.length ? null : h("p", { class: "muted" }, tr("no_sets_hint")),
      state.sets.map((s) => {
        const mine = s.owner_id === state.user.id;
        return h("div", { class: "set" },
          h("div", { class: "head" }, h("span", { class: "grow" }, s.name, mine ? null : h("span", { class: "owner" }, " (" + s.owner + ")")),
            small("✎", tr("rename"), async () => { const name = await promptDialog(tr("rename"), tr("name"), s.name); if (name) act(() => api("PATCH", `/api/sets/${s.id}`, { name })); }),
            small("✕", tr("delete"), async () => { if (await confirmDialog(tr("delete_set", { name: s.name }), true)) { state.pl.selected = null; state.pl.detail = null; act(() => api("DELETE", `/api/sets/${s.id}`)); } }),
            small("♪+", tr("new_playlist"), async () => { const body = await newPlaylistDialog(); if (body) act(() => api("POST", `/api/sets/${s.id}/playlists`, body)); }),
            small("📁+", tr("new_group"), async () => { const name = await promptDialog(tr("new_group"), tr("name"), ""); if (name) act(() => api("POST", `/api/sets/${s.id}/groups`, { name })); })),
          s.playlists.map((p, pi) => plRow(p, s.playlists, pi, `/api/sets/${s.id}/playlists/order`, true)),
          s.groups.map((g, gi) => h("div", { class: "group" },
            h("div", { class: "head" }, h("span", { class: "grow" }, "📁 " + g.name),
              small("▲", tr("up"), () => act(() => api("PUT", `/api/sets/${s.id}/groups/order`, { ids: move(s.groups.map((x) => x.id), gi, -1) })), gi === 0),
              small("▼", tr("down"), () => act(() => api("PUT", `/api/sets/${s.id}/groups/order`, { ids: move(s.groups.map((x) => x.id), gi, 1) })), gi === s.groups.length - 1),
              small("✎", tr("rename"), async () => { const name = await promptDialog(tr("rename"), tr("name"), g.name); if (name) act(() => api("PATCH", `/api/groups/${g.id}`, { name })); }),
              small("✕", tr("delete"), async () => { if (await confirmDialog(tr("delete_group", { name: g.name }), true)) act(() => api("DELETE", `/api/groups/${g.id}`)); }),
              small("♪+", tr("new_playlist"), async () => { const body = await newPlaylistDialog(); if (body) act(() => api("POST", `/api/groups/${g.id}/playlists`, body)); })),
            g.playlists.map((p, pi) => plRow(p, g.playlists, pi, `/api/groups/${g.id}/playlists/order`, false)))));
      }));
  }

  async function movePlaylist(p) {
    const options = [];
    for (const s of state.sets) {
      options.push({ value: "s:" + s.id, label: s.name + " › " + tr("no_folder") });
      for (const g of s.groups) options.push({ value: "g:" + g.id, label: s.name + " › 📁 " + g.name });
    }
    const here = p.group_id ? "g:" + p.group_id : "s:" + p.set_id;
    const sel = h("select", { "aria-label": tr("move_playlist") },
      options.map((o) => h("option", { value: o.value, selected: o.value === here }, o.label)));
    const target = await modal(tr("move_playlist"), h("div", { class: "stack" }, sel), [
      { label: tr("cancel"), value: null },
      { label: tr("ok"), class: "primary", run: () => sel.value },
    ]);
    if (!target || target === here) return;
    const body = target.startsWith("g:") ? { group_id: Number(target.slice(2)) } : { group_id: null, set_id: Number(target.slice(2)) };
    act(() => api("PATCH", `/api/playlists/${p.id}`, body));
  }

  async function copyPlaylist(p) {
    let people;
    try { people = await api("GET", "/api/people"); } catch (err) { fail(err); return; }
    if (!people.length) { toast(tr("no_people"), "err"); return; }
    const who = h("select", { "aria-label": tr("copy_to") }, people.map((u) => h("option", { value: u.id }, u.username)));
    const mine = h("input", { type: "checkbox" });
    const choice = await modal(tr("copy_title", { name: p.name }), h("div", { class: "stack" },
      who, h("label", { class: "row" }, mine, tr("copy_with_tags")), h("p", { class: "muted small" }, tr("copy_hint"))), [
      { label: tr("cancel"), value: null },
      { label: tr("copy_do"), class: "primary", run: () => ({ user_id: Number(who.value), with_my_tags: mine.checked }) },
    ]);
    if (!choice) return;
    try {
      const r = await api("POST", `/api/playlists/${p.id}/copy`, choice);
      toast(tr("copied_to", { user: r.user, set: r.set_name, n: r.copied }) + (r.skipped ? " · " + tr("copied_skipped", { n: r.skipped }) : ""), "ok");
      if (p.kind === "tags" && r.copied === 0) toast(tr("copied_empty"), "err");
    } catch (err) { fail(err); }
  }

  async function paintDetail() {
    const id = state.pl.selected;
    if (!id) { fill(detail, h("p", { class: "muted" }, tr("select_playlist"))); return; }
    let p;
    try { p = await api("GET", `/api/playlists/${id}`); } catch (err) { state.pl.selected = null; fill(detail, h("p", { class: "muted" }, tr("select_playlist"))); throw err; }
    state.pl.detail = p;
    const patch = async (body) => { try { await api("PATCH", `/api/playlists/${id}`, body); await loadSets(); paintTree(); } catch (err) { fail(err); } };
    const volCheck = h("input", { type: "checkbox", checked: p.volume !== null, onchange: (e) => { volRange.disabled = !e.target.checked; patch({ volume: e.target.checked ? Number(volRange.value) / 100 : null }); } });
    const volRange = h("input", { type: "range", min: 0, max: 150, value: Math.round((p.volume === null ? 0.4 : p.volume) * 100), disabled: p.volume === null,
      onchange: (e) => patch({ volume: Number(e.target.value) / 100 }) });
    fill(detail, 
      h("div", { class: "row" }, h("h2", { class: "grow" }, p.name),
        h("button", { class: "btn small", onclick: () => movePlaylist(p) }, tr("move_playlist")),
        h("button", { class: "btn small", onclick: () => copyPlaylist(p) }, tr("copy_to")),
        h("button", { class: "btn small", onclick: async () => { const name = await promptDialog(tr("rename"), tr("name"), p.name); if (name) { await patch({ name }); paintDetail(); } } }, tr("rename")),
        h("button", { class: "btn small danger", onclick: async () => { if (await confirmDialog(tr("delete_playlist", { name: p.name }), true)) { state.pl.selected = null; act(() => api("DELETE", `/api/playlists/${id}`)); } } }, tr("delete"))),
      h("div", { class: "row" },
        h("label", { class: "row" }, h("input", { type: "checkbox", checked: p.loop, onchange: (e) => patch({ loop: e.target.checked }) }), tr("loop")),
        h("label", { class: "row" }, h("input", { type: "checkbox", checked: p.shuffle, onchange: (e) => patch({ shuffle: e.target.checked }) }), tr("shuffle")),
        h("label", { class: "row" }, tr("fade_s"), h("input", { type: "number", min: 0, max: 10, step: 0.5, value: p.fade, "aria-label": tr("fade_s"),
          onchange: (e) => patch({ fade: Math.min(10, Math.max(0, Number(e.target.value) || 0)) }) })),
        h("label", { class: "row" }, volCheck, tr("own_volume"), volumeSlider(volRange).el)),
      p.kind === "tags" ? tagRule(p, patch) : manualBody(p)); 
  }

  function matchList(items) {
    const total = items.reduce((sum, i) => sum + (i.duration || 0), 0);
    const ul = items.length ? h("ul", { class: "items" }, items.map((it, i) => h("li", { "data-preview-id": it.track_id },
      h("span", { class: "muted small" }, i + 1),
      previewButton({ id: it.track_id, title: it.title, duration: it.duration }),
      h("span", { class: "t", title: it.title }, it.title),
      h("span", { class: "muted small" }, fmtTime(it.duration))))) : null;
    if (ul) previewSlot(ul);
    return [h("div", { class: "muted small" }, tr("matching_tracks") + ": " + tr("n_tracks", { n: items.length }) + " · " + fmtTime(total)),
      ul || h("p", { class: "muted" }, tr("nothing_matches"))];
  }

  /* Automatic playlist: the rule is edited here, the tracks are whatever matches it right now. */
  function tagRule(p, patch) {
    const listBox = h("div", {});
    fill(listBox, matchList(p.items));
    let chosen = p.rule.tags;
    const modeSel = h("select", { "aria-label": tr("match_mode"), onchange: () => save() },
      h("option", { value: "any", selected: p.rule.mode === "any" }, tr("mode_any")),
      h("option", { value: "all", selected: p.rule.mode === "all" }, tr("mode_all")));
    const field = tagInput(p.rule.tags, allTagPool(), { onchange: (v) => { chosen = v; save(); } });
    async function save() {
      await patch({ tags: chosen, mode: modeSel.value });
      try { const fresh = await api("GET", `/api/playlists/${p.id}`); fill(listBox, matchList(fresh.items)); } catch (err) { fail(err); }
    }
    return h("div", { class: "stack" },
      h("div", { class: "stack" }, h("label", {}, tr("rule_tags")), field.el, modeSel, h("div", { class: "muted small" }, tr("auto_hint"))),
      listBox);
  }

  function manualBody(p) {
    const id = p.id;
    const total = p.items.filter((i) => !i.deleted).reduce((sum, i) => sum + (i.duration || 0), 0);
    const itemList = h("ul", { class: "items" }, p.items.map((it, i) => h("li", { class: it.deleted ? "gone" : "", "data-preview-id": it.deleted ? null : it.track_id },
      h("span", { class: "muted small" }, i + 1),
      it.deleted ? null : previewButton({ id: it.track_id, title: it.title, duration: it.duration }),
      h("span", { class: "t", title: it.title }, it.title),
      it.deleted ? h("span", { class: "badge warn" }, tr("removed")) : h("span", { class: "muted small" }, fmtTime(it.duration)),
      it.deleted ? h("button", { class: "btn small", onclick: async () => {
        const picked = await pickTracks(tr("replace_track"), false, new Set(p.items.map((i) => i.track_id)));
        if (picked) { try { await api("PUT", `/api/playlists/${id}/items/${it.id}`, { track_id: picked[0] }); await loadSets(); paintTree(); paintDetail(); } catch (err) { fail(err); } }
      } }, tr("replace")) : null,
      small("▲", tr("up"), async () => { try { await api("PUT", `/api/playlists/${id}/order`, { ids: move(p.items.map((x) => x.id), i, -1) }); paintDetail(); } catch (err) { fail(err); } }, i === 0),
      small("▼", tr("down"), async () => { try { await api("PUT", `/api/playlists/${id}/order`, { ids: move(p.items.map((x) => x.id), i, 1) }); paintDetail(); } catch (err) { fail(err); } }, i === p.items.length - 1),
      small("✕", tr("remove"), async () => { try { await api("DELETE", `/api/playlists/${id}/items/${it.id}`); await loadSets(); paintTree(); paintDetail(); } catch (err) { fail(err); } }))));
    previewSlot(itemList);
    return h("div", {},
      h("div", { class: "row" },
        h("button", { class: "btn primary", onclick: async () => {
          const ids = await pickTracks(tr("add_tracks"), true, new Set(p.items.map((i) => i.track_id)));
          if (ids) { try { await api("POST", `/api/playlists/${id}/items`, { track_ids: ids }); await loadSets(); paintTree(); paintDetail(); } catch (err) { fail(err); } }
        } }, tr("add_tracks")),
        h("span", { class: "muted small" }, tr("n_tracks", { n: p.items.length }) + " · " + fmtTime(total))),
      p.items.length ? null : h("p", { class: "muted" }, tr("playlist_empty")),
      itemList);
  }

  paintTree();
  await paintDetail().catch(() => { /* selection was stale */ });
}

/* ---------- downloads ---------- */

async function viewDownloads(main) {
  const system = await api("GET", "/api/system");
  state.system = system;
  const list = h("div", {});
  state.tags = await api("GET", "/api/tags");
  const url = h("input", { type: "url", placeholder: "https://…", required: true, "aria-label": "URL", class: "grow" });
  // The chosen tags stay between downloads: several tracks for one session usually get the same ones.
  const sharedTags = tagInput(state.dlTags.shared, state.tags.shared, { onchange: (v) => { state.dlTags.shared = v; } });
  const myTags = tagInput(state.dlTags.mine, state.tags.mine, { onchange: (v) => { state.dlTags.mine = v; } });
  let timer = null;
  const form = h("form", { class: "stack", onsubmit: async (e) => {
    e.preventDefault();
    try {
      await api("POST", "/api/downloads", { url: url.value.trim(), tags: sharedTags.get(), my_tags: myTags.get() });
      url.value = ""; toast(tr("queued"), "ok"); refresh();
    } catch (err) { fail(err); }
  } }, h("div", { class: "row" }, url, h("button", { class: "btn primary", type: "submit", disabled: !system.downloads_enabled }, tr("download"))),
  h("div", { class: "tagpair" },
    h("div", {}, h("label", { class: "small" }, tr("shared_tags_new")), sharedTags.el),
    h("div", {}, h("label", { class: "small" }, tr("my_tags_new")), myTags.el)));
  put(main, 
    system.downloads_enabled ? null : h("div", { class: "notice" }, tr("downloads_off")),
    h("div", { class: "card" }, h("h2", {}, tr("tab.downloads")), form,
      h("p", { class: "muted small" }, tr("downloads_hint", { hosts: system.download_hosts.join(", ") }))),
    h("div", { class: "card" }, list));

  const previous = new Map();
  const fmtSpeed = (bytes) => (bytes ? (bytes / 1048576 >= 1 ? (bytes / 1048576).toFixed(1) + " MB/s" : Math.round(bytes / 1024) + " kB/s") : "");

  function progressCell(j, first) {
    if (j.status === "queued") {
      const wait = first && pauseLeft > 0 ? " · " + tr("dl.starts_in", { n: pauseLeft }) : "";
      return h("div", { class: "muted small" }, tr("dl.queued") + wait);
    }
    if (j.status !== "running") return null;
    const known = typeof j.percent === "number";
    const bar = h("div", {});
    if (known) bar.style.width = Math.min(100, j.percent) + "%";
    const text = [tr("dl." + (j.stage || "preparing")), known ? j.percent.toFixed(0) + "%" : "", fmtSpeed(j.speed),
      j.eta ? tr("dl.eta", { t: fmtTime(j.eta) }) : "",
      j.elapsed !== null && j.elapsed !== undefined && j.stage !== "downloading" ? j.elapsed + " s" : ""].filter(Boolean).join(" · ");
    return h("div", {}, h("div", { class: "progress" + (known ? "" : " indeterminate") }, bar), h("div", { class: "muted small" }, text));
  }

  let pauseLeft = 0;
  async function refresh() {
    clearTimeout(timer);
    if (state.tab !== "downloads" || !document.body.contains(list)) return;
    let data;
    try { data = await api("GET", "/api/downloads"); } catch (_) { return; }
    const jobs = data.jobs;
    pauseLeft = data.pause_remaining;
    for (const j of jobs) {
      if (previous.get(j.id) === "running" && j.status === "done") toast(tr("dl.finished", { title: j.title || j.url }), "ok");
      if (previous.get(j.id) === "running" && j.status === "error") toast(tr("dl.failed") + ": " + errorText(new Error(j.error || "error")), "err");
      previous.set(j.id, j.status);
    }
    const firstQueued = [...jobs].reverse().find((j) => j.status === "queued");
    const badge = { queued: "", running: "warn", done: "ok", error: "bad" };
    list.replaceChildren(jobs.length ? h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, tr("status")), h("th", {}, tr("title")), h("th", {}, tr("owner")), h("th", {}))),
      h("tbody", {}, jobs.map((j) => h("tr", {},
        h("td", {}, h("span", { class: "badge " + badge[j.status] }, tr("dl." + j.status))),
        h("td", { class: "title-cell" },
          h("div", { title: j.url }, j.title || j.url),
          j.error ? h("div", { class: "muted small" }, errorText(new Error(j.error))) : null,
          progressCell(j, j === firstQueued)),
        h("td", { class: "muted small" }, j.user),
        h("td", { class: "actions" }, j.status === "running" ? null : h("button", { class: "btn small icon", title: tr("delete"), onclick: async () => { try { await api("DELETE", `/api/downloads/${j.id}`); refresh(); } catch (err) { fail(err); } } }, "✕")))))) : h("p", { class: "muted" }, tr("no_downloads")));
    if (jobs.some((j) => j.status === "queued" || j.status === "running")) timer = setTimeout(refresh, 1000);
  }
  refresh();
}

/* ---------- admin ---------- */

async function viewSettings(main) {
  const system = await api("GET", "/api/system");
  state.system = system;
  const refresh = () => { render(); };

  const saveNormalize = async (body) => {
    try { state.system = await api("PATCH", "/api/system", body); toast(tr("saved"), "ok"); } catch (err) { fail(err); }
    refresh();
  };
  const normBox = h("input", { type: "checkbox", checked: system.normalize, onchange: (e) => saveNormalize({ normalize: e.target.checked }) });
  const normNumber = (key, min, max, label) => h("label", { class: "row" }, label,
    h("input", { type: "number", min, max, step: 1, value: system[key], disabled: !system.normalize, "aria-label": label,
      onchange: (e) => saveNormalize({ [key]: Math.min(max, Math.max(min, Number(e.target.value))) }) }));
  const trimBox = h("input", { type: "checkbox", checked: system.trim_silence, onchange: (e) => saveNormalize({ trim_silence: e.target.checked }) });
  const fadeNumber = (key, max, step, label) => h("label", { class: "row" }, label,
    h("input", { type: "number", min: 0, max, step, value: system[key], "aria-label": label,
      onchange: (e) => saveNormalize({ [key]: Math.min(max, Math.max(0, Number(e.target.value))) }) }));
  const loud = system.loudness;
  const loadEl = h("div", { class: "muted small" }, tr("load_waiting"));
  const tickLoad = async () => {
    try {
      const l = await api("GET", "/api/system/load");
      const pct = (v) => (v === null || v === undefined ? "–" : v.toFixed(1));
      loadEl.textContent = tr("load_label") + ": " + tr("load_line", { cpu: pct(l.cpu), avg: pct(l.cpu_average), peak: pct(l.cpu_peak), mem: l.memory_mb });
      loadEl.title = tr("load_hint", { source: l.source, cores: l.cores });
    } catch (err) { /* keep the last value: the next tick tries again */ }
  };
  tickLoad();
  const loadTimer = setInterval(() => { if (!document.body.contains(loadEl)) clearInterval(loadTimer); else tickLoad(); }, 3000);

  put(main, 
    h("div", { class: "card" }, h("h2", {}, tr("system")),
      h("div", {}, "Melomancer " + system.version), h("div", {}, tr("bot_status") + ": " + tr("bot." + system.bot_status)),
      loadEl,
      h("h3", {}, tr("section_loudness")),
      h("label", { class: "row" }, normBox, tr("normalize_label")),
      h("div", { class: "row" },
        normNumber("normalize_target", -30, -8, tr("normalize_target")),
        normNumber("normalize_max_boost", 0, 12, tr("normalize_boost"))),
      h("div", { class: "muted small" }, tr("normalize_hint")),
      h("h3", {}, tr("section_fades")),
      h("div", { class: "row" },
        fadeNumber("crossfade_seconds", 12, 0.5, tr("crossfade_label")),
        fadeNumber("scrub_seconds", 2, 0.1, tr("scrub_label")),
        fadeNumber("volume_glide_seconds", 2, 0.05, tr("glide_label"))),
      h("div", { class: "muted small" }, tr("fade_hint")),
      h("h3", {}, tr("section_silence")),
      h("div", { class: "row" },
        h("label", { class: "row" }, trimBox, tr("trim_label")),
        h("label", { class: "row" }, tr("silence_label"),
          h("input", { type: "number", min: -70, max: -30, step: 1, value: system.silence_threshold, disabled: !system.trim_silence,
            "aria-label": tr("silence_label"), onchange: (e) => saveNormalize({ silence_threshold: Math.min(-30, Math.max(-70, Number(e.target.value))) }) }))),
      h("div", { class: "muted small" }, tr("trim_hint")),
      h("div", { class: "muted small" }, tr("normalize_status", { measured: loud.measured, total: loud.total })
        + (loud.waiting ? " · " + tr("normalize_waiting", { n: loud.waiting }) : ""))));
}

async function viewUsers(main) {
  const [users, guilds] = await Promise.all([api("GET", "/api/users"), api("GET", "/api/player/guilds")]);
  const refresh = () => { render(); };
  const name = h("input", { placeholder: tr("username"), autocomplete: "off" });
  const pass = h("input", { type: "password", placeholder: tr("password") + " (" + tr("min_chars", { n: 10 }) + ")", autocomplete: "new-password" });
  const role = h("select", {}, h("option", { value: "user" }, tr("role.user")), h("option", { value: "admin" }, tr("role.admin")));

  put(main,
    h("div", { class: "card" }, h("h2", {}, tr("tab.users")),
      h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, tr("username")), h("th", {}, tr("role")), h("th", {}, tr("servers")), h("th", {}))),
        h("tbody", {}, users.map((u) => h("tr", {},
          h("td", {}, u.username, u.disabled ? h("span", { class: "badge bad" }, " " + tr("disabled")) : null),
          h("td", {}, h("select", { "aria-label": tr("role"), onchange: async (e) => { try { await api("PATCH", `/api/users/${u.id}`, { role: e.target.value }); refresh(); } catch (err) { fail(err); refresh(); } } },
            h("option", { value: "user", selected: u.role === "user" }, tr("role.user")), h("option", { value: "admin", selected: u.role === "admin" }, tr("role.admin")))),
          h("td", { class: "muted small" }, u.role === "admin" ? tr("all_servers") : (u.guild_ids.length ? tr("n_servers", { n: u.guild_ids.length }) : "–")),
          h("td", { class: "actions" },
            u.role === "admin" ? null : h("button", { class: "btn small", onclick: () => guildDialog(u) }, tr("servers")),
            h("button", { class: "btn small", onclick: async () => {
              const pw = await promptDialog(tr("reset_password"), tr("new_password") + " (" + tr("min_chars", { n: 10 }) + ")", "", "password");
              if (pw) { try { await api("PATCH", `/api/users/${u.id}`, { password: pw }); toast(tr("saved"), "ok"); } catch (err) { fail(err); } }
            } }, tr("reset_password")),
            h("button", { class: "btn small " + (u.disabled ? "" : "danger"), onclick: async () => { try { await api("PATCH", `/api/users/${u.id}`, { disabled: !u.disabled }); refresh(); } catch (err) { fail(err); } } },
              u.disabled ? tr("enable") : tr("disable"))))))),
      h("h3", {}, tr("new_user")),
      h("form", { class: "row", onsubmit: async (e) => {
        e.preventDefault();
        try { await api("POST", "/api/users", { username: name.value.trim(), password: pass.value, role: role.value }); refresh(); } catch (err) { fail(err); }
      } }, name, pass, role, h("button", { class: "btn primary", type: "submit" }, tr("create")))));

  async function guildDialog(u) {
    const chosen = new Set(u.guild_ids);
    const manual = h("input", { placeholder: tr("server_id_manual") });
    const boxes = guilds.map((g) => h("label", { class: "row" }, h("input", { type: "checkbox", checked: chosen.has(g.id), onchange: (e) => { e.target.checked ? chosen.add(g.id) : chosen.delete(g.id); } }), g.name, h("span", { class: "muted small" }, g.id)));
    const ok = await modal(tr("servers") + ": " + u.username, h("div", { class: "stack" },
      h("p", { class: "muted small" }, tr("servers_hint")), boxes.length ? boxes : h("p", { class: "muted" }, tr("no_servers")), manual), [
      { label: tr("cancel"), value: false },
      { label: tr("save"), class: "primary", run: async () => {
        const extra = manual.value.trim();
        if (extra) chosen.add(extra);
        try { await api("PUT", `/api/users/${u.id}/guilds`, { guild_ids: [...chosen] }); return true; } catch (err) { fail(err); return false; }
      } },
    ]);
    if (ok) refresh();
  }
}

/* ---------- boot ---------- */

async function boot() {
  state.lang = pref("lang") || ((navigator.language || "pl").toLowerCase().startsWith("pl") ? "pl" : "en");
  try {
    state.user = await api("GET", "/api/auth/me");
    state.lang = state.user.lang || state.lang;
    state.system = await api("GET", "/api/system");
  } catch (_) { state.user = null; }
  render();
}
LocalPlayer.onerror = () => toast(tr("local_load_failed"), "err");
document.addEventListener("visibilitychange", () => { /* polling resumes on the next tick */ });
boot();
