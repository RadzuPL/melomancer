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
  "tab.player", "tab.library", "tab.playlists", "tab.downloads", "tab.admin",
  "upload.created", "upload.revived", "upload.duplicate",
  "dl.queued", "dl.running", "dl.done", "dl.error",
  "role.user", "role.admin",
  "bot.disabled", "bot.starting", "bot.ready", "bot.login_failed", "bot.error",
];
const used = new Set([...app.matchAll(/\btr\(\s*"([^"]+)"/g)].map((m) => m[1]).filter((k) => !k.endsWith(".")));
dynamic.forEach((k) => used.add(k));

let problems = 0;
for (const lang of ["pl", "en"]) {
  for (const key of used) if (!(key in I18N[lang])) { console.error(`missing in ${lang}: ${key}`); problems++; }
}
for (const key of Object.keys(I18N.pl)) if (!(key in I18N.en)) { console.error(`only in pl: ${key}`); problems++; }
for (const key of Object.keys(I18N.en)) if (!(key in I18N.pl)) { console.error(`only in en: ${key}`); problems++; }
if (problems) process.exit(1);
console.log(`i18n ok: ${Object.keys(I18N.pl).length} keys in both languages`);
