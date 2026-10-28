# Melomancer: notes for an agent working on this repository

A self-hosted music player for tabletop RPG sessions with a web panel, playing in the browser or through a Discord
bot (Python 3.12, FastAPI, SQLite, discord.py, ffmpeg; vanilla JS panel, no build step). It runs as one container on the maintainer's Unraid server behind
Cloudflare Tunnel and Access. What it does and how it is built is in `docs/en/` (and `docs/pl/`): start with
`usage.md` and `architecture.md`; `development.md` has the human setup. This file only holds what the code does not
tell you and what already cost time.

## Working with the maintainer

- He writes Polish. Answer in Polish, conclusion first, then the details. Write the code, the commits and the docs
  in English, with the Polish docs next to the English ones (see "Documentation").
- Say what you verified and what you could not. Audio on a real Discord voice channel, a real Unraid and a real
  browser session cannot be checked from the sandbox: he tests those and reports back. Do not invent facts, logs or
  tool capabilities.
- Links as full `https://` URLs, commands in separate copy-ready code blocks.
- Start working when the request is clear; ask only when a wrong guess would be expensive. Send a short message when
  a long job starts and when something changes the plan.
- Never paste or store a Discord token or a password. A real bot token once ended up in a pasted log and had to be
  reset. If you see one, tell him to reset it.

## Releases: every push is one

- Every push to `main` builds, tests and publishes `ghcr.io/radzupl/melomancer` and creates a GitHub release with
  the next patch number (`scripts/next_version.sh`). That includes a push that only changes docs. Batch related work
  into one push.
- `[minor]` or `[major]` bump those parts, but only when they end the commit **subject**. Never write those words
  anywhere else, not in the body, not as examples: it once produced an unwanted v1.0.0, and an agent session cannot
  delete tags or releases. The Monday 03:23 UTC schedule makes its own release (middle number up).
- CI is the test runner here: the sandbox cannot reach pypi, so pytest, fastapi and discord.py are not installed
  locally. Watch a run with `gh run list --limit 1`; a failure is easiest to read in the annotations of the job
  (`gh api repos/RadzuPL/melomancer/check-runs/<job id>/annotations`). `gh release list` fails (no GraphQL), use
  `git fetch --tags` and `git tag --sort=-v:refname | head -1`.
- Commit messages end with the attribution trailer your harness asks for.

## Checking a change before you push

```
node --check app/static/app.js
```

```
node scripts/check_i18n.js
```

```
PYTHONPATH=scripts/dev/stubs python3.12 -W ignore scripts/dev/run_tests.py tests.test_mixer tests.test_player_logic tests.test_db
```

```
python3 scripts/dev/ui_smoke.py
```

The third command runs the mixer, player and database tests without pytest, with a stub `discord` module and real
ffmpeg (Python 3.12 because 3.13 has no `audioop`). It cannot run the API tests, which need fastapi: those only run
in CI. The last one drives the panel in headless Chromium against a mocked API (needs `playwright`), and is where
UI changes are checked: extend its mock data and assertions with every UI change.

## Decisions that stand

- Tuning lives in the panel (Settings tab, stored in the `app_settings` table), not in container variables. A new
  environment variable needs a good reason: it is deployment (paths, token, limits), never taste.
- Tracks are one shared library. Sets, folders and playlists are private to their owner (an administrator sees all);
  someone else's id answers 404, never 403. Personal tags are private to their user.
- Deleting a track keeps its row (a "tombstone") so playlists show a greyed entry; the same file uploaded again
  revives it.
- Settings that change what is heard apply at once, without a restart or a reconnect, and volume or gain changes
  glide instead of jumping.
- Everything user-facing exists in Polish and English (panel and docs).
- The look follows Ant Design (blue accent, grey layout with white containers, 32 px controls, underlined tabs), written as
  plain CSS in `app/static/style.css` with no library. New components use the existing variables, never a colour literal.
- The panel can also play in the browser (`app/static/local.js`, `app/playback.py`, `app/routes_local.py`). The server decides what plays and where it starts and ends; the page does the playing. There are two implementations of the player: change a fade, the volume rule or the queue behaviour in `app/player.py` / `app/mixer.py` and in `local.js` together. Playing here and on Discord exclude each other on purpose.
- Not built yet, by choice for now: ambient layers and a sound-effects board. The mixer (`app/mixer.py`) is where
  they belong.

## Invariants

- No inline scripts or styles: the CSP is `script-src 'self'; style-src 'self'`. Set styles through the CSSOM
  (`el.style.setProperty`), never with a `style` attribute or a `<style>` tag.
- State-changing requests need the header `X-Melomancer: 1`. Anything user-controlled goes in with `textContent`.
- Database changes are a new entry at the end of `MIGRATIONS` in `app/db.py`, never an edit of an old one, with a
  test in `tests/test_db.py` that upgrades a database built from the older migrations.
- The mixer's audio thread (`Mixer.read`, every 20 ms) never blocks and never touches the database. It reports
  events and the player hands them to the event loop with `call_soon_threadsafe`.
- API errors are short codes in `detail`; the panel translates them under `err.<code>` in `i18n.js`.
- Colours in CSS come from the variables (the light and the dark theme both depend on that), not from literals.
- i18n: every key in `pl` and `en`; keys built at run time go in the `dynamic` list in `scripts/check_i18n.js`.
- JS helpers: `h()` builds elements, `fill()` and `put()` take arrays and null. `replaceChildren` with a null prints
  "null" in the page.

## Gotchas that already bit

- Tests of the mixer and the player read frames far faster than every 20 ms, so a stream can be momentarily empty:
  use the helpers (`ready`, `read_audio`, `drain`, `settle`, `pull`) and never assert exact frame counts across a
  boundary that depends on decoding speed.
- Selectors: an element's own class can lose to a base rule of higher specificity (`input[type="range"].seek` beat
  `.previewbar .seek`). In Playwright `has-text` is a case-insensitive substring match ("admin" matches
  "Administracja"). The CSP also blocks `page.add_style_tag`.
- A PATCH body can say "clear this field" with an explicit `null`; read it with `model_fields_set`. Uploading
  returns 201, and deleting a track that is on a playlist needs `?force=true`.
- Text whose width changes (a percentage, a time) next to a flexible slider makes the slider resize: give the text a
  fixed width.
- The ffmpeg analysis (`loudnorm` and `silencedetect` in one pass) is run under `nice`, so that it does not compete
  with the voice stream.

## Documentation

The diagrams and the screenshots in `docs/img/` are generated, never edited by hand: `scripts/dev/diagrams.py` draws the
diagrams (English and Polish from one source) and `scripts/dev/screenshots.py` takes the screenshots from the real panel
against demo data (English and Polish, light and dark; needs `playwright` and `pillow`). Run them again after the look of
the panel or the architecture changes, and commit the files together.

A feature is not done until it is in `docs/en/` and `docs/pl/` (`usage.md` for what a person sees,
`architecture.md` for how it works, `configuration.md` only for environment variables), in both language blocks of
`README.md`, and, when a variable changes, in `unraid/my-melomancer.xml` and `.env.example`. Third-party software
and its licenses are listed in `THIRD_PARTY.md`. The code is MIT licensed (`LICENSE`).
