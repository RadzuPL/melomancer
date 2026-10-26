"use strict";

/* ---------- small helpers ---------- */

const AUDIO_EXT = new Set([".mp3", ".ogg", ".oga", ".opus", ".flac", ".wav", ".m4a", ".aac", ".webm"]);
const state = {
  user: null, lang: "pl", tab: "player", system: null,
  tracks: [], tags: { shared: [], mine: [] }, sets: [], showAllSets: false,
  lib: { q: "", tag: "", mine: false, selected: new Set() },
  player: { guilds: [], guildId: "", channelId: "", setId: "", st: null, stAt: 0, timer: null },
  pl: { selected: null, detail: null },
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

/* ---------- shell ---------- */

function render() {
  const root = $("#app");
  root.replaceChildren();
  document.documentElement.lang = state.lang;
  if (!state.user) { root.append(viewLogin()); return; }
  const tabs = [["player", "tab.player"], ["library", "tab.library"], ["playlists", "tab.playlists"], ["downloads", "tab.downloads"]];
  if (state.user.role === "admin") tabs.push(["admin", "tab.admin"]);
  const main = h("main", {});
  root.append(
    h("header", { class: "top" },
      h("span", { class: "brand" }, "Melomancer"),
      h("nav", { class: "tabs" }, tabs.map(([id, label]) => h("button", {
        class: state.tab === id ? "active" : "", onclick: () => { state.tab = id; stopPolling(); render(); },
      }, tr(label)))),
      h("span", { class: "grow" }),
      h("select", { "aria-label": tr("language"), onchange: (e) => setLang(e.target.value) },
        h("option", { value: "pl", selected: state.lang === "pl" }, "Polski"),
        h("option", { value: "en", selected: state.lang === "en" }, "English")),
      h("button", { class: "btn small", onclick: accountDialog }, state.user.username),
      h("button", { class: "btn small", onclick: logout }, tr("logout"))),
    main,
    h("footer", { class: "foot" }, "Melomancer " + (state.system ? state.system.version : "")));
  const views = { player: viewPlayer, library: viewLibrary, playlists: viewPlaylists, downloads: viewDownloads, admin: viewAdmin };
  views[state.tab](main).catch(fail);
}

async function setLang(lang) {
  state.lang = lang;
  pref("lang", lang);
  try { await api("PATCH", "/api/auth/me", { lang }); } catch (_) { /* cosmetic */ }
  render();
}

async function logout() {
  try { await api("POST", "/api/auth/logout"); } catch (_) { /* already gone */ }
  state.user = null;
  stopPolling();
  render();
}

async function accountDialog() {
  const current = h("input", { type: "password", autocomplete: "current-password" });
  const next = h("input", { type: "password", autocomplete: "new-password" });
  await modal(tr("account"), h("div", { class: "stack" },
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
    h("div", { class: "row", }, h("span", { class: "grow" }),
      h("select", { "aria-label": tr("language"), onchange: (e) => { state.lang = e.target.value; pref("lang", state.lang); render(); } },
        h("option", { value: "pl", selected: state.lang === "pl" }, "Polski"),
        h("option", { value: "en", selected: state.lang === "en" }, "English"))));
}

/* ---------- player ---------- */

function stopPolling() { clearInterval(state.player.timer); state.player.timer = null; }

async function viewPlayer(main) {
  const ps = state.player;
  const [guilds, , system] = await Promise.all([api("GET", "/api/player/guilds"), loadSets(), api("GET", "/api/system")]);
  state.system = system;
  ps.guilds = guilds;
  if (!guilds.some((g) => g.id === ps.guildId)) ps.guildId = guilds.some((g) => g.id === pref("guild")) ? pref("guild") : (guilds[0] ? guilds[0].id : "");
  const own = state.sets;
  if (!own.some((s) => String(s.id) === ps.setId)) ps.setId = own.some((s) => String(s.id) === pref("set")) ? pref("set") : (own[0] ? String(own[0].id) : "");
  const guild = () => ps.guilds.find((g) => g.id === ps.guildId);

  const guildSel = h("select", { "aria-label": tr("server"), onchange: (e) => { ps.guildId = e.target.value; pref("guild", ps.guildId); ps.channelId = ""; ps.st = null; fillChannels(); poll(); } });
  const chanSel = h("select", { "aria-label": tr("channel"), onchange: (e) => { ps.channelId = e.target.value; pref("channel", ps.channelId); } });
  const status = h("span", { class: "badge" });
  const connectBtn = h("button", { class: "btn primary", onclick: toggleConnect });
  const titleEl = h("div", { class: "title" });
  const subEl = h("div", { class: "muted small" });
  const bar = h("div", {});
  const timeEl = h("span", { class: "muted small" });
  const btn = (label, title, fn) => h("button", { class: "btn", title, "aria-label": title, onclick: fn }, label);
  const prevB = btn("⏮", tr("prev"), () => control("prev"));
  const toggleB = btn("⏯", tr("pause_resume"), () => control(ps.st && ps.st.state === "paused" ? "resume" : "pause"));
  const nextB = btn("⏭", tr("next"), () => control("next"));
  const stopB = btn("⏹", tr("stop"), () => control("stop"));
  const loopB = h("button", { class: "btn", onclick: () => options({ loop: !(ps.st && ps.st.loop) }) }, "🔁 " + tr("loop"));
  const shuffleB = h("button", { class: "btn", onclick: () => options({ shuffle: !(ps.st && ps.st.shuffle) }) }, "🔀 " + tr("shuffle"));
  const volLabel = h("span", { class: "small", }, "");
  let dragging = false;
  const sendVolume = debounce(async (v) => { try { applyState(await api("POST", `/api/player/${ps.guildId}/volume`, { volume: v / 100 })); } catch (err) { fail(err); } }, 150);
  const vol = h("input", { type: "range", min: 0, max: 150, step: 1, value: 40, "aria-label": tr("volume"),
    onpointerdown: () => { dragging = true; }, onpointerup: () => { dragging = false; }, onchange: () => { dragging = false; },
    oninput: (e) => { volLabel.textContent = e.target.value + "%"; sendVolume(Number(e.target.value)); } });
  const padsBox = h("div", {});
  const setSel = h("select", { "aria-label": tr("set"), onchange: (e) => { ps.setId = e.target.value; pref("set", ps.setId); fillPads(); } },
    own.map((s) => h("option", { value: s.id, selected: String(s.id) === ps.setId }, s.name + (state.showAllSets ? " (" + s.owner + ")" : ""))));
  const allBox = state.user.role === "admin"
    ? h("label", { class: "row small" }, h("input", { type: "checkbox", checked: state.showAllSets, onchange: async (e) => { state.showAllSets = e.target.checked; render(); } }), tr("show_all_sets"))
    : null;

  put(main, 
    system.bot_status !== "ready" ? h("div", { class: "notice" }, tr("bot." + system.bot_status)) : null,
    h("div", { class: "card" }, h("div", { class: "row" },
      guildSel, chanSel, connectBtn, status, h("span", { class: "grow" }),
      guilds.length === 0 && system.bot_status === "ready" ? h("span", { class: "muted small" }, tr("no_servers")) : null)),
    h("div", { class: "card now" }, titleEl, subEl, h("div", { class: "progress" }, bar), timeEl,
      h("div", { class: "controls" }, prevB, toggleB, nextB, stopB, loopB, shuffleB,
        h("div", { class: "volume" }, "🔈", vol, volLabel))),
    h("div", { class: "card" }, h("div", { class: "row" }, h("h2", { class: "grow" }, tr("playlists")), setSel, allBox), padsBox));

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
    }, p.name, h("span", { class: "count" }, tr("n_tracks", { n: p.count - p.missing }) + (p.missing ? " ⚠ " + p.missing : "")));
    if (set.playlists.length) padsBox.append(h("div", { class: "pads" }, set.playlists.map(pad)));
    for (const group of set.groups) {
      if (group.playlists.length) padsBox.append(h("h3", {}, "📁 " + group.name), h("div", { class: "pads" }, group.playlists.map(pad)));
    }
  }

  function applyState(st) {
    if (st) { ps.st = st; ps.stAt = Date.now(); }
    const s = ps.st;
    const connected = !!(s && s.connected);
    status.className = "badge " + (connected ? "ok" : "");
    status.textContent = connected ? tr("connected_to", { name: s.channel_name }) : tr("disconnected");
    connectBtn.textContent = connected && s.channel_id === ps.channelId ? tr("disconnect") : (connected ? tr("move") : tr("connect"));
    const playing = s && s.state !== "idle";
    titleEl.textContent = playing && s.now ? s.now.title : tr("nothing_playing");
    subEl.textContent = playing && s.playlist ? s.playlist.name + (s.playlist.set ? " · " + s.playlist.set : "") + (s.controller ? " · " + s.controller : "") : "";
    for (const b of [prevB, toggleB, nextB, stopB]) b.disabled = !playing;
    toggleB.textContent = s && s.state === "paused" ? "▶" : "⏸";
    loopB.classList.toggle("on", !!(s && s.loop));
    shuffleB.classList.toggle("on", !!(s && s.shuffle));
    if (s && !dragging) { vol.value = Math.round(s.volume * 100); volLabel.textContent = vol.value + "%"; }
    for (const pad of padsBox.querySelectorAll(".pad")) {
      pad.classList.toggle("active", !!(playing && s.playlist && String(s.playlist.id) === pad.dataset.id));
    }
    tickBar();
  }

  function tickBar() {
    const s = ps.st;
    if (!s || !s.now) { bar.style.width = "0"; timeEl.textContent = ""; return; }
    const elapsed = s.now.elapsed + (s.state === "playing" ? (Date.now() - ps.stAt) / 1000 : 0);
    const total = s.now.duration;
    bar.style.width = total ? Math.min(100, (elapsed / total) * 100) + "%" : "0";
    timeEl.textContent = fmtTime(elapsed) + (total ? " / " + fmtTime(total) : "");
  }

  async function poll() {
    if (!ps.guildId || document.hidden || state.tab !== "player") return;
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
  async function control(action) { try { applyState(await api("POST", `/api/player/${ps.guildId}/${action}`)); } catch (err) { fail(err); } }
  async function options(body) { try { applyState(await api("PATCH", `/api/player/${ps.guildId}/options`, body)); } catch (err) { fail(err); } }
  async function playPad(p) {
    if (!ps.guildId) return toast(tr("pick_server"), "err");
    try {
      if (!(ps.st && ps.st.connected)) {
        if (!ps.channelId) return toast(tr("pick_channel"), "err");
        await api("POST", `/api/player/${ps.guildId}/connect`, { channel_id: ps.channelId });
      }
      applyState(await api("POST", `/api/player/${ps.guildId}/play`, { playlist_id: p.id }));
    } catch (err) { fail(err); }
  }

  fillChannels();
  fillPads();
  stopPolling();
  ps.timer = setInterval(() => { poll(); }, 2500);
  const tickId = setInterval(() => { if (state.tab !== "player" || !document.body.contains(bar)) clearInterval(tickId); else tickBar(); }, 1000);
  poll();
}

/* ---------- library ---------- */

const uploader = { items: [], running: 0, box: null, onDone: null };

function dirTags(file) {
  const parts = (file.webkitRelativePath || "").split("/");
  return parts.slice(0, -1);
}

function queueFiles(files, withFolderTags) {
  for (const file of files) {
    const m = file.name.toLowerCase().match(/\.[a-z0-9]+$/);
    const item = { file, status: "wait", msg: "", tags: withFolderTags ? dirTags(file) : [] };
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
  const fileInput = h("input", { type: "file", multiple: true, accept: "audio/*,.opus,.flac,.m4a,.ogg,.mp3,.wav,.webm,.aac", class: "hidden",
    onchange: (e) => { queueFiles([...e.target.files], false); e.target.value = ""; } });
  const dirInput = h("input", { type: "file", multiple: true, webkitdirectory: true, class: "hidden",
    onchange: (e) => { queueFiles([...e.target.files], folderTags.checked); e.target.value = ""; } });
  const drop = h("div", { class: "drop" }, tr("drop_here"));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); queueFiles([...e.dataTransfer.files], false); });

  const search = h("input", { type: "search", placeholder: tr("search"), value: lib.q, "aria-label": tr("search"),
    oninput: debounce((e) => { lib.q = e.target.value; paintTable(); }, 120) });
  const tagSel = h("select", { "aria-label": tr("tag"), onchange: (e) => { lib.tag = e.target.value; paintTable(); } });
  const fillTagSel = () => tagSel.replaceChildren(h("option", { value: "" }, tr("all_tags")),
    ...allTagNames().map((tag) => h("option", { value: tag, selected: tag === lib.tag }, tag)));
  fillTagSel();
  const mineBox = h("input", { type: "checkbox", checked: lib.mine, onchange: (e) => { lib.mine = e.target.checked; paintTable(); } });

  const preview = h("audio", { controls: true, class: "hidden" });
  const previewTitle = h("div", { class: "muted small hidden" });

  put(main, 
    h("div", { class: "card" }, h("h2", {}, tr("add_music")),
      h("div", { class: "row" },
        h("button", { class: "btn primary", onclick: () => fileInput.click() }, tr("choose_files")),
        h("button", { class: "btn", onclick: () => dirInput.click() }, tr("choose_folder")),
        h("label", { class: "row small" }, folderTags, tr("folders_as_tags")),
        h("span", { class: "muted small" }, tr("max_size", { n: state.system ? state.system.max_upload_mb : "?" }))),
      fileInput, dirInput, drop, uploadBox),
    h("div", { class: "card" },
      h("div", { class: "row" }, h("h2", { class: "grow" }, tr("tab.library")), counter),
      h("div", { class: "row" }, search, tagSel, h("label", { class: "row small" }, mineBox, tr("only_mine"))),
      list, bulk, preview, previewTitle));
  paintUploads();

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
      h("tbody", {}, rows.map((r) => h("tr", { class: lib.selected.has(r.id) ? "selected" : "" },
        h("td", {}, h("input", { type: "checkbox", checked: lib.selected.has(r.id), "aria-label": r.title,
          onchange: (e) => { e.target.checked ? lib.selected.add(r.id) : lib.selected.delete(r.id); paintTable(); } })),
        h("td", { class: "title-cell", title: r.title }, r.title),
        h("td", {}, r.tags.map((x) => h("span", { class: "chip", onclick: () => { lib.tag = x; tagSel.value = x; paintTable(); } }, x)),
          r.my_tags.map((x) => h("span", { class: "chip mine", title: tr("my_tag"), onclick: () => { lib.tag = x; paintTable(); } }, x))),
        h("td", { class: "muted small" }, r.owner),
        h("td", { class: "num" }, fmtTime(r.duration)),
        h("td", { class: "actions" },
          h("button", { class: "btn small icon", title: tr("preview"), onclick: () => previewTrack(r) }, "▶"),
          h("button", { class: "btn small icon", title: tr("edit"), onclick: () => editTrack(r) }, "✎"),
          r.can_edit ? h("button", { class: "btn small icon danger", title: tr("delete"), onclick: () => deleteTrack(r) }, "✕") : null))))));
    const n = lib.selected.size;
    bulk.classList.toggle("hidden", n === 0);
    fill(bulk, h("span", { class: "grow" }, tr("n_selected", { n })),
      h("button", { class: "btn primary", onclick: addSelectedToPlaylist }, tr("add_to_playlist")),
      h("button", { class: "btn", onclick: tagSelected }, tr("add_my_tag")),
      h("button", { class: "btn", onclick: () => { lib.selected.clear(); paintTable(); } }, tr("clear")));
  }

  function previewTrack(r) {
    preview.src = `/api/tracks/${r.id}/stream`;
    preview.classList.remove("hidden");
    previewTitle.classList.remove("hidden");
    previewTitle.textContent = r.title;
    preview.play().catch(() => { /* autoplay can be blocked; controls stay visible */ });
  }

  async function editTrack(r) {
    const title = h("input", { value: r.title, maxlength: 200, disabled: !r.can_edit });
    const shared = h("input", { value: r.tags.join(", "), disabled: !r.can_edit });
    const mine = h("input", { value: r.my_tags.join(", ") });
    const ok = await modal(tr("edit_track"), h("div", { class: "stack" },
      h("label", {}, tr("title")), title,
      h("label", {}, tr("shared_tags") + " (" + tr("comma_sep") + ")"), shared,
      h("label", {}, tr("my_tags") + " (" + tr("comma_sep") + ", " + tr("only_you") + ")"), mine,
      r.source_url ? h("div", { class: "muted small" }, tr("source") + ": " + r.source_url) : null,
      r.title !== r.original_title ? h("div", { class: "muted small" }, tr("original") + ": " + r.original_title) : null), [
      { label: tr("cancel"), value: false },
      {
        label: tr("save"), class: "primary", run: async () => {
          try {
            if (r.can_edit) await api("PATCH", `/api/tracks/${r.id}`, { title: title.value, tags: parseTags(shared.value) });
            await api("PUT", `/api/tracks/${r.id}/my-tags`, { tags: parseTags(mine.value) });
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
    const text = await promptDialog(tr("add_my_tag"), tr("comma_sep"), "");
    if (!text) return;
    const add = parseTags(text);
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
    for (const p of s.playlists) options.push({ id: p.id, label: `${s.name} › ${p.name}` });
    for (const g of s.groups) for (const p of g.playlists) options.push({ id: p.id, label: `${s.name} › 📁 ${g.name} › ${p.name}` });
  }
  if (!options.length) { toast(tr("no_playlists_yet"), "err"); return null; }
  const sel = h("select", { "aria-label": tr("playlist") }, options.map((o) => h("option", { value: o.id }, o.label)));
  const v = await modal(tr("add_to_playlist"), h("div", { class: "stack" }, sel), [
    { label: tr("cancel"), value: null },
    { label: tr("ok"), class: "primary", run: () => sel.value },
  ]);
  return v || null;
}

async function pickTracks(title, multi) {
  if (!state.tracks.length) await loadTracks();
  const f = { q: "", tag: "", mine: false };
  const chosen = new Set();
  const listBox = h("div", { class: "picker-list" });
  const q = h("input", { type: "search", placeholder: tr("search"), oninput: (e) => { f.q = e.target.value; paint(); } });
  const tagSel = h("select", { onchange: (e) => { f.tag = e.target.value; paint(); } },
    h("option", { value: "" }, tr("all_tags")), ...allTagNames().map((x) => h("option", { value: x }, x)));
  function paint() {
    listBox.replaceChildren(...state.tracks.filter((x) => trackMatches(x, f)).slice(0, 300).map((x) => h("label", {},
      h("input", { type: multi ? "checkbox" : "radio", name: "pick", checked: chosen.has(x.id), onchange: (e) => {
        if (!multi) chosen.clear();
        e.target.checked ? chosen.add(x.id) : chosen.delete(x.id);
      } }), h("span", { class: "grow" }, x.title), h("span", { class: "muted small" }, fmtTime(x.duration)))));
  }
  paint();
  const v = await modal(title, h("div", {}, h("div", { class: "row" }, q, tagSel), listBox), [
    { label: tr("cancel"), value: null },
    { label: tr("ok"), class: "primary", run: () => (chosen.size ? [...chosen] : false) },
  ]);
  return v || null;
}

/* ---------- playlists ---------- */

async function viewPlaylists(main) {
  await Promise.all([loadSets(), state.tracks.length ? null : loadTracks()]);
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
        p.name + " (" + (p.count - p.missing) + (p.missing ? " ⚠" + p.missing : "") + ")"),
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
            small("♪+", tr("new_playlist"), async () => { const name = await promptDialog(tr("new_playlist"), tr("name"), ""); if (name) act(() => api("POST", `/api/sets/${s.id}/playlists`, { name })); }),
            small("📁+", tr("new_group"), async () => { const name = await promptDialog(tr("new_group"), tr("name"), ""); if (name) act(() => api("POST", `/api/sets/${s.id}/groups`, { name })); })),
          s.playlists.map((p, pi) => plRow(p, s.playlists, pi, `/api/sets/${s.id}/playlists/order`, true)),
          s.groups.map((g, gi) => h("div", { class: "group" },
            h("div", { class: "head" }, h("span", { class: "grow" }, "📁 " + g.name),
              small("▲", tr("up"), () => act(() => api("PUT", `/api/sets/${s.id}/groups/order`, { ids: move(s.groups.map((x) => x.id), gi, -1) })), gi === 0),
              small("▼", tr("down"), () => act(() => api("PUT", `/api/sets/${s.id}/groups/order`, { ids: move(s.groups.map((x) => x.id), gi, 1) })), gi === s.groups.length - 1),
              small("✎", tr("rename"), async () => { const name = await promptDialog(tr("rename"), tr("name"), g.name); if (name) act(() => api("PATCH", `/api/groups/${g.id}`, { name })); }),
              small("✕", tr("delete"), async () => { if (await confirmDialog(tr("delete_group", { name: g.name }), true)) act(() => api("DELETE", `/api/groups/${g.id}`)); }),
              small("♪+", tr("new_playlist"), async () => { const name = await promptDialog(tr("new_playlist"), tr("name"), ""); if (name) act(() => api("POST", `/api/groups/${g.id}/playlists`, { name })); })),
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
    const total = p.items.filter((i) => !i.deleted).reduce((sum, i) => sum + (i.duration || 0), 0);
    fill(detail, 
      h("div", { class: "row" }, h("h2", { class: "grow" }, p.name),
        h("button", { class: "btn small", onclick: () => movePlaylist(p) }, tr("move_playlist")),
        h("button", { class: "btn small", onclick: async () => { const name = await promptDialog(tr("rename"), tr("name"), p.name); if (name) { await patch({ name }); paintDetail(); } } }, tr("rename")),
        h("button", { class: "btn small danger", onclick: async () => { if (await confirmDialog(tr("delete_playlist", { name: p.name }), true)) { state.pl.selected = null; act(() => api("DELETE", `/api/playlists/${id}`)); } } }, tr("delete"))),
      h("div", { class: "row" },
        h("label", { class: "row" }, h("input", { type: "checkbox", checked: p.loop, onchange: (e) => patch({ loop: e.target.checked }) }), tr("loop")),
        h("label", { class: "row" }, h("input", { type: "checkbox", checked: p.shuffle, onchange: (e) => patch({ shuffle: e.target.checked }) }), tr("shuffle")),
        h("label", { class: "row" }, tr("fade_s"), h("input", { type: "number", min: 0, max: 10, step: 0.5, value: p.fade, "aria-label": tr("fade_s"),
          onchange: (e) => patch({ fade: Math.min(10, Math.max(0, Number(e.target.value) || 0)) }) })),
        h("label", { class: "row" }, volCheck, tr("own_volume"), volRange)),
      h("div", { class: "row" },
        h("button", { class: "btn primary", onclick: async () => {
          const ids = await pickTracks(tr("add_tracks"), true);
          if (ids) { try { await api("POST", `/api/playlists/${id}/items`, { track_ids: ids }); await loadSets(); paintTree(); paintDetail(); } catch (err) { fail(err); } }
        } }, tr("add_tracks")),
        h("span", { class: "muted small" }, tr("n_tracks", { n: p.items.length }) + " · " + fmtTime(total))),
      p.items.length ? null : h("p", { class: "muted" }, tr("playlist_empty")),
      h("ul", { class: "items" }, p.items.map((it, i) => h("li", { class: it.deleted ? "gone" : "" },
        h("span", { class: "muted small" }, i + 1),
        h("span", { class: "t", title: it.title }, it.title),
        it.deleted ? h("span", { class: "badge warn" }, tr("removed")) : h("span", { class: "muted small" }, fmtTime(it.duration)),
        it.deleted ? h("button", { class: "btn small", onclick: async () => {
          const picked = await pickTracks(tr("replace_track"), false);
          if (picked) { try { await api("PUT", `/api/playlists/${id}/items/${it.id}`, { track_id: picked[0] }); await loadSets(); paintTree(); paintDetail(); } catch (err) { fail(err); } }
        } }, tr("replace")) : null,
        small("▲", tr("up"), async () => { try { await api("PUT", `/api/playlists/${id}/order`, { ids: move(p.items.map((x) => x.id), i, -1) }); paintDetail(); } catch (err) { fail(err); } }, i === 0),
        small("▼", tr("down"), async () => { try { await api("PUT", `/api/playlists/${id}/order`, { ids: move(p.items.map((x) => x.id), i, 1) }); paintDetail(); } catch (err) { fail(err); } }, i === p.items.length - 1),
        small("✕", tr("remove"), async () => { try { await api("DELETE", `/api/playlists/${id}/items/${it.id}`); await loadSets(); paintTree(); paintDetail(); } catch (err) { fail(err); } })))));
  }

  paintTree();
  await paintDetail().catch(() => { /* selection was stale */ });
}

/* ---------- downloads ---------- */

async function viewDownloads(main) {
  const system = await api("GET", "/api/system");
  state.system = system;
  const list = h("div", {});
  const url = h("input", { type: "url", placeholder: "https://…", required: true, "aria-label": "URL" });
  const tags = h("input", { placeholder: tr("tags") + " (" + tr("comma_sep") + ")" });
  let timer = null;
  const form = h("form", { class: "row", onsubmit: async (e) => {
    e.preventDefault();
    try { await api("POST", "/api/downloads", { url: url.value.trim(), tags: parseTags(tags.value) }); url.value = ""; toast(tr("queued"), "ok"); refresh(); }
    catch (err) { fail(err); }
  } }, url, tags, h("button", { class: "btn primary", type: "submit", disabled: !system.downloads_enabled }, tr("download")));
  put(main, 
    system.downloads_enabled ? null : h("div", { class: "notice" }, tr("downloads_off")),
    h("div", { class: "card" }, h("h2", {}, tr("tab.downloads")), form,
      h("p", { class: "muted small" }, tr("downloads_hint", { hosts: system.download_hosts.join(", ") }))),
    h("div", { class: "card" }, list));

  async function refresh() {
    clearTimeout(timer);
    if (state.tab !== "downloads" || !document.body.contains(list)) return;
    let jobs;
    try { jobs = await api("GET", "/api/downloads"); } catch (_) { return; }
    const badge = { queued: "", running: "warn", done: "ok", error: "bad" };
    list.replaceChildren(jobs.length ? h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, tr("status")), h("th", {}, "URL"), h("th", {}, tr("title")), h("th", {}, tr("owner")), h("th", {}))),
      h("tbody", {}, jobs.map((j) => h("tr", {},
        h("td", {}, h("span", { class: "badge " + badge[j.status] }, tr("dl." + j.status))),
        h("td", { class: "title-cell", title: j.url }, j.url),
        h("td", {}, j.title || "", j.error ? h("div", { class: "muted small" }, errorText(new Error(j.error))) : null),
        h("td", { class: "muted small" }, j.user),
        h("td", { class: "actions" }, j.status === "running" ? null : h("button", { class: "btn small icon", title: tr("delete"), onclick: async () => { try { await api("DELETE", `/api/downloads/${j.id}`); refresh(); } catch (err) { fail(err); } } }, "✕")))))) : h("p", { class: "muted" }, tr("no_downloads")));
    if (jobs.some((j) => j.status === "queued" || j.status === "running")) timer = setTimeout(refresh, 3000);
  }
  refresh();
}

/* ---------- admin ---------- */

async function viewAdmin(main) {
  const [users, guilds, system] = await Promise.all([api("GET", "/api/users"), api("GET", "/api/player/guilds"), api("GET", "/api/system")]);
  state.system = system;
  const refresh = () => { render(); };
  const name = h("input", { placeholder: tr("username"), autocomplete: "off" });
  const pass = h("input", { type: "password", placeholder: tr("password") + " (" + tr("min_chars", { n: 10 }) + ")", autocomplete: "new-password" });
  const role = h("select", {}, h("option", { value: "user" }, tr("role.user")), h("option", { value: "admin" }, tr("role.admin")));

  put(main, 
    h("div", { class: "card" }, h("h2", {}, tr("system")),
      h("div", {}, "Melomancer " + system.version), h("div", {}, tr("bot_status") + ": " + tr("bot." + system.bot_status))),
    h("div", { class: "card" }, h("h2", {}, tr("tab.admin")),
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
document.addEventListener("visibilitychange", () => { /* polling resumes on the next tick */ });
boot();
