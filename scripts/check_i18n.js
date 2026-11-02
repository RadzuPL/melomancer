// Fails when the Polish and English dictionaries differ, or when app.js uses a key that is missing.
// Run from the repository root: node scripts/check_i18n.js
"use strict";
const fs = require("fs");
const path = require("path");

const dir = path.join(__dirname, "..", "app", "static");
const I18N = new Function(fs.readFileSync(path.join(dir, "i18n.js"), "utf8") + "\nreturn I18N;")();
const app = fs.readFileSync(path.join(dir, "app.js"), "utf8");

// Keys built at run time (prefix + value) are listed here so that they are checked as well.
const dynamic = [
  "tab.player", "tab.library", "tab.playlists", "tab.downloads", "tab.users", "tab.settings",
  "upload.created", "upload.revived", "upload.duplicate",
  "dl.queued", "dl.running", "dl.done", "dl.error",
  "dl.preparing", "dl.downloading", "dl.converting", "dl.importing",
  "role.user", "role.admin",
  "theme_auto", "theme_light", "theme_dark",
  "update_err_unreachable", "update_err_rate_limited", "update_err_bad_response",
  "bot.disabled", "bot.starting", "bot.ready", "bot.login_failed", "bot.error",
  "botd.disabled", "botd.login_failed", "botd.error",
  "upd_phase_checking", "upd_phase_downloading", "upd_phase_verifying", "upd_phase_unpacking",
  "upd_err_unreachable", "upd_err_rate_limited", "upd_err_bad_response", "upd_err_no_update", "upd_err_package_not_ready", "upd_err_no_space",
  "upd_err_no_write_access", "upd_err_bad_package", "upd_err_checksum", "upd_err_failed",
];
const used = new Set([...app.matchAll(/\btr\(\s*"([^"]+)"/g)].map((m) => m[1]).filter((k) => !k.endsWith(".") && !k.endsWith("_")));
dynamic.forEach((k) => used.add(k));

let problems = 0;
for (const lang of ["pl", "en"]) {
  for (const key of used) if (!(key in I18N[lang])) { console.error(`missing in ${lang}: ${key}`); problems++; }
}
for (const key of Object.keys(I18N.pl)) if (!(key in I18N.en)) { console.error(`only in pl: ${key}`); problems++; }
for (const key of Object.keys(I18N.en)) if (!(key in I18N.pl)) { console.error(`only in en: ${key}`); problems++; }
if (problems) process.exit(1);
console.log(`i18n ok: ${Object.keys(I18N.pl).length} keys in both languages`);
