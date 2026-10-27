# Rozwój

Języki: [English](../en/development.md) · **Polski**

## Uruchomienie lokalne

Potrzebny jest Python 3.12 lub nowszy i `ffmpeg` (razem z `ffprobe`).

```
python3 -m venv .venv
```

```
.venv/bin/pip install -r requirements-dev.txt
```

```
DATA_DIR=./data ADMIN_PASSWORD='haslo-deweloperskie' .venv/bin/uvicorn app.main:app_factory --factory --reload --port 8080
```

Otwórz http://localhost:8080/. Bez `DISCORD_TOKEN` panel działa, a bot pozostaje offline, co wystarcza do prac nad biblioteką, playlistami i administracją. Do pobierania z YouTube zainstaluj też środowisko JavaScript, np. Deno (https://deno.com/), yt-dlp go potrzebuje.

## Testy

```
.venv/bin/python -m pytest
```

Albo w tym samym obrazie, którego używa CI (bez lokalnego Pythona):

```
docker build --target test -t melomancer:test .
```

```
docker run --rm --entrypoint python melomancer:test -m pytest -p no:cacheprovider
```

Testy uruchamiają prawdziwe API na tymczasowej bazie i prawdziwych plikach audio zrobionych przez ffmpeg. Stronę Discorda zastępuje atrapa o tym samym interfejsie (`tests/conftest.py`), a wątek pobierania dostaje wstrzykniętą funkcję pobierającą, więc żaden test nie dotyka sieci. Kontrole skryptów panelu:

```
node --check app/static/app.js
```

```
node scripts/check_i18n.js
```

Drugie polecenie zawodzi, gdy słowniki polski i angielski się różnią albo gdy `app.js` używa brakującego klucza.

## Ciągła integracja i wersje

Workflow `.github/workflows/build.yml` robi to:

| Zdarzenie | Testy | Obraz | Wydanie |
|---|---|---|---|
| Pull request | tak | nie | nie |
| Push na `main` | tak | zbudowany, przetestowany dymnie, wypchnięty jako `latest` i `X.Y.Z` | nowy tag i wydanie GitHub |
| Poniedziałek 03:23 UTC (harmonogram) | tak | przebudowany ze świeżym obrazem bazowym, ffmpeg i najnowszym yt-dlp, wypchnięty jako `latest` i nowa wersja | nowy tag i wydanie, środkowa liczba w górę |
| Uruchomienie ręczne | tak | jak push | jak push |

Wersję liczy `scripts/next_version.sh` z najnowszego tagu `vX.Y.Z` i komunikatów commitów od niego. Każdy push na `main` to wydanie poprawkowe (`0.6.1`, `0.6.2` ...). Cotygodniowa przebudowa podnosi środkową liczbę i zeruje ostatnią (`0.6.7` zmienia się w `0.7.0`), więc każdy odświeżony obraz ma własną wersję, a numer wersji zawsze wskazuje jeden niezmienny obraz. Pierwsza lub środkowa liczba zmienia się tylko wtedy, gdy **temat commita** (jego pierwsza linia) kończy się znacznikiem; tekst w innym miejscu komunikatu jest ignorowany:

| Temat commita kończy się na | Podbicie |
|---|---|
| `[major]` | major (`1.0.0`) |
| `[minor]` | minor (`0.7.0`) |
| nic szczególnego (`feat:`, `fix:`, `docs:` ... wszystkie tak samo) | patch |

Pierwsze wydanie to `0.1.0`. Wersja jest wpisana w obraz (`APP_VERSION`, widoczna w stopce panelu i w `/api/health`). Tag powstaje dopiero po wypchnięciu obrazu, więc nieudana budowa nie zużywa numeru. Tag `latest` śledzi Watchtower.

Jeśli testy zawiodą, nic nie jest publikowane. Log zadania nie zawsze jest dostępny, więc po nieudanych testach koniec wyjścia pytest pojawia się jako adnotacje na stronie przebiegu.

## Budowa obrazu lokalnie

```
docker build -t melomancer:dev --build-arg APP_VERSION=dev .
```

```
bash scripts/smoke_test.sh melomancer:dev
```

## Konwencje

- API nie zna szczegółów Discorda. Trasy rozmawiają z `BotManager`, testy z atrapą.
- Jako `detail` zwracaj krótkie kody maszynowe (`not_found`, `in_use`, ...). Panel tłumaczy je w `i18n.js` pod `err.<kod>`.
- Wszystko, co pochodzi od użytkownika, trafia na stronę przez `textContent` lub `createTextNode`, nigdy jako HTML.
- Zmiany w bazie dodawaj jako nowy wpis na końcu `MIGRATIONS` w `app/db.py`, nigdy nie edytuj starego. Przed aktualizacją istniejącej bazy obok niej zapisywana jest kopia `melomancer.db.before-vN`. Dodaj test, który aktualizuje bazę zbudowaną ze starszych migracji (zobacz `tests/test_db.py`).
