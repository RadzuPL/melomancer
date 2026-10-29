# Development

Languages: **English** · [Polski](../pl/development.md)

## Run it locally

Python 3.12 or newer and `ffmpeg` (with `ffprobe`) are needed.

```
python3 -m venv .venv
```

```
.venv/bin/pip install -r requirements-dev.txt
```

```
DATA_DIR=./data ADMIN_PASSWORD='development-password' .venv/bin/uvicorn app.main:app_factory --factory --reload --port 8080
```

Open http://localhost:8080/. Without `DISCORD_TOKEN` the panel works and the bot stays offline, which is enough for working on the library, playlists and administration. For YouTube downloads also install a JavaScript runtime such as Deno (https://deno.com/), yt-dlp needs it.

## Tests

```
.venv/bin/python -m pytest
```

Or in the same image CI uses (no local Python needed):

```
docker build --target test -t melomancer:test .
```

```
docker run --rm --entrypoint python melomancer:test -m pytest -p no:cacheprovider
```

The tests run the real API against a temporary database and real audio files made by ffmpeg. The Discord side is replaced by a fake with the same interface (`tests/conftest.py`), and the download worker gets an injected fetch function, so no test touches the network. Checks for the panel scripts:

```
node --check app/static/app.js
```

```
node scripts/check_i18n.js
```

The second command fails when the Polish and English dictionaries differ or when `app.js` uses a key that is missing.

### Without installing everything

In a place that cannot install the dependencies (a sandbox, a bare machine), `scripts/dev/` has two helpers. They are conveniences, CI stays the source of truth.

```
PYTHONPATH=scripts/dev/stubs python3.12 -W ignore scripts/dev/run_tests.py tests.test_mixer tests.test_player_logic tests.test_db
```

runs the mixer, player and database tests without pytest, with a stub `discord` module and real ffmpeg (Python 3.12, because 3.13 has no `audioop`). It cannot run the tests that need FastAPI.

```
python3 scripts/dev/ui_smoke.py
```

opens the panel in headless Chromium against a mocked API (`pip install playwright` and `playwright install chromium` first) and drives every screen. Change its mock data together with the API.

## Continuous integration and versions

The workflow `.github/workflows/build.yml` does the following:

| Event | Test | Image | Release |
|---|---|---|---|
| Pull request | yes | no | no |
| Push to `main` | yes | built, smoke tested, pushed as `latest` and `X.Y.Z` | new tag and GitHub release |
| Monday 03:23 UTC (schedule) | yes | rebuilt with fresh base image, ffmpeg and the newest yt-dlp, pushed as `latest` and a new version | new tag and release, middle number up |
| Manual run | yes | like a push | like a push |

The version is computed by `scripts/next_version.sh` from the newest `vX.Y.Z` tag and the commit messages since it. Every push to `main` is a patch release (`0.6.1`, `0.6.2` ...). The weekly rebuild raises the middle number and resets the last one (`0.6.7` becomes `0.7.0`), so every refreshed image has a version of its own and a version number always points at one fixed image. The first or the middle number changes only when the **subject line** of a commit (its first line) ends with a marker; text elsewhere in a commit message is ignored:

| Commit subject ends with | Bump |
|---|---|
| `[major]` | major (`1.0.0`) |
| `[minor]` | minor (`0.7.0`) |
| nothing special (`feat:`, `fix:`, `docs:` ... are all the same) | patch |

The first release is `0.1.0`. The version is baked into the image (`APP_VERSION`, shown in the panel footer and `/api/health`). The tag is created only after the image was pushed, so a failed build does not use up a number. The `latest` tag is what Watchtower follows.

If tests fail, nothing is published. The job log is not always reachable, so a failed test run prints the tail of the pytest output as annotations on the run page.

## Build the image locally

```
docker build -t melomancer:dev --build-arg APP_VERSION=dev .
```

```
bash scripts/smoke_test.sh melomancer:dev
```

## Conventions

- Keep the API free of Discord specifics. Routes talk to `BotManager`, tests talk to a fake.
- Return short machine codes as `detail` (`not_found`, `in_use`, ...). The panel translates them in `i18n.js` under `err.<code>`.
- Anything user-controlled goes into the page with `textContent` or `createTextNode`, never as HTML.
- Add database changes as a new entry at the end of `MIGRATIONS` in `app/db.py`, never edit an old one. Before an upgrade of an existing database a copy is saved next to it as `melomancer.db.before-vN`. Add a test that upgrades a database built from the older migrations (see `tests/test_db.py`).


## Releases and their notes

Every push to `main` is a release (see `.github/workflows/build.yml`): the tests run, the image is built and pushed to `ghcr.io/radzupl/melomancer`, a GitHub release is made with the next patch number, and every Monday a rebuild is released with a fresh base image, ffmpeg and yt-dlp.

The text of a release comes from the commit messages (`scripts/release_notes.py`). A push lists the commits since the previous release, the Monday rebuild lists every release since the previous rebuild, grouped by version. The body of a commit message is what the reader sees, so write it for them: what changed and why it matters. When a pull request is squashed, its description or the squash message is that text. Tool trailers (`Co-Authored-By`, `Claude-Session`) are left out. A pull request shows a preview of both texts in the summary of its `notes-preview` job.

A few minutes after a release, `.github/workflows/windows-release.yml` builds the [Windows package](windows.md) from the tag, starts it as a check, attaches `Melomancer-win64-<version>.zip` to the release and adds the link to the notes. It is a separate workflow so that a Windows failure never touches the container release. To make the package for an existing release by hand, run the workflow from the **Actions** tab and give the tag (for example `v0.6.36`).

## Windows package

The experimental Windows package, how CI builds and tests it: [Windows (for advanced users)](windows-advanced.md).
