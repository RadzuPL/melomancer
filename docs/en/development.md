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

## Continuous integration and versions

The workflow `.github/workflows/build.yml` does the following:

| Event | Test | Image | Release |
|---|---|---|---|
| Pull request | yes | no | no |
| Push to `main` | yes | built, smoke tested, pushed as `latest` and `X.Y.Z` | new tag and GitHub release |
| Monday 03:23 UTC (schedule) | yes | rebuilt with fresh base image and the newest yt-dlp, pushed as `latest` and the current version | none |
| Manual run | yes | like a push | like a push |

The version is computed by `scripts/next_version.sh` from the newest `vX.Y.Z` tag and the commit messages since it:

| Commit message | Bump |
|---|---|
| contains `BREAKING CHANGE`, or a subject like `refactor!: ...` | major |
| subject starts with `feat:` or `feat(scope):` | minor |
| anything else (`fix:`, `docs:`, `ci:` ...) | patch |

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
