# Architektura

Języki: [English](../en/architecture.md) · **Polski**

## Przegląd

Jeden proces Pythona, jeden kontener:

```
 przeglądarka ──HTTP──► FastAPI (app/main.py) ──► SQLite  /data/melomancer.db
                          │   ├─ routes_auth       logowanie, użytkownicy, system
                          │   ├─ routes_library    wgrywanie, tagi, utwory, pobrania
                          │   ├─ routes_playlists  zestawy, foldery, playlisty
                          │   └─ routes_player     połączenie, odtwarzanie, głośność
                          │
                          ├─► BotManager (app/player.py) ──► discord.py ──► gateway + głos Discorda (UDP)
                          │        └─ jeden GuildPlayer na serwer ──► ffmpeg ──► Opus
                          │
                          └─► wątek Downloader (app/downloader.py) ──► yt-dlp + ffmpeg ──► biblioteka
 pliki: /data/music/<id utworu>.<rozszerzenie>
```

Klient Discorda działa na tej samej pętli asyncio co serwer WWW. Dostęp do bazy to zwykły `sqlite3` z krótką transakcją na żądanie. Odtwarzanie dekoduje `ffmpeg` i wysyła Opus do Discorda przez `discord.py` (z `davey` dla szyfrowanego end-to-end protokołu głosu DAVE).

Strona przeglądarkowa to statyczna strona (`app/static`): zwykły JavaScript, bez kroku budowania, słowniki polski i angielski w `i18n.js`.

## Moduły

| Plik | Rola |
|---|---|
| `app/main.py` | Fabryka aplikacji, nagłówki bezpieczeństwa, pierwszy administrator, cykl życia (uruchamia i zatrzymuje bota i pobieracz) |
| `app/config.py` | Ustawienia ze zmiennych środowiskowych |
| `app/db.py` | Migracje schematu (`PRAGMA user_version`) i pomocnik transakcji |
| `app/security.py` | Haszowanie Argon2, tokeny sesji, ogranicznik logowań |
| `app/deps.py` | Uwierzytelnianie, sprawdzenie administratora, kontrola nagłówka CSRF |
| `app/library.py` | Sprawdzanie ffprobe, deduplikacja po SHA-256, tagi, nadgrobki, lista utworów |
| `app/downloader.py` | Walidacja adresów, dzienny limit, wątek roboczy z kolejką wokół yt-dlp |
| `app/player.py` | `GuildPlayer` (kolejka, głośność, odstęp po zerwaniu) i `BotManager` |
| `app/loudness.py` | Analiza w tle (głośność i cisza jednym przebiegiem ffmpeg), wzmocnienie przy odtwarzaniu, `RuntimeSettings` (wszystko, co administrator zmienia w panelu) |
| `app/sysload.py` | CPU i pamięć kontenera z cgroup (v2 lub v1), próbkowane co 2 s, dla zakładki Ustawienia |
| `app/mixer.py` | Mikser PCM: warstwy dekodowane z wyprzedzeniem przez wątki, przejścia equal-power, następny utwór kolejkowany przed końcem bieżącego |
| `app/routes_*.py` | API HTTP |
| `app/cli.py` | Polecenie ratunkowe `reset-password` |

## Model danych

```
users ──< sessions
  │  └──< guild_access (użytkownik, id serwera)
  │
  ├──< tracks (właściciel)  ──< track_tags (tagi wspólne)
  │        │             └──< user_tags (użytkownik, utwór, tag osobisty)
  │        └──────────────┐
  └──< sets ──< playlists ──< playlist_items ─┘
         └──< set_groups (folder, optional) ──< playlists
downloads (użytkownik, url, stan, utwór)
```

- **tracks** nigdy nie są fizycznie usuwane. Usunięcie ustawia `deleted_at` i kasuje plik, więc `playlist_items` nadal wskazują wiersz ze starym tytułem (wyszarzony wpis). Częściowy indeks unikalny pilnuje unikalności `sha256` tylko wśród żywych utworów, więc ponowne wgranie identycznej zawartości przywraca stary wiersz (to samo id).
- Zestawy, foldery i playlisty usuwają się kaskadowo. Utworów to nie dotyka.
- Pozycje to liczby całkowite, przepisywane przy zapisie kolejności.
- `tracks.silence_lead`, `tracks.silence_trail` i `tracks.silence_db` trzymają ciszę na początku i końcu utworu w sekundach oraz próg, z którym ją zmierzono (ten sam przebieg ffmpeg używa `silencedetect` przed `loudnorm`). Utwór, którego `silence_db` różni się od bieżącego progu, jest mierzony od nowa. Przy włączonym przycinaniu `GuildPlayer._span` zaczyna warstwę od `lead` (`-ss`) i kończy ją na `duration - trail`: ten punkt staje się `duration` warstwy, więc od niego liczy się przejście i preroll, a `Layer.stop_at` kończy warstwę tam, gdy przejścia nie ma. Zegar playera zostaje w czasie pliku.
- `tracks.loudness` (głośność całkowita w LUFS) i `tracks.peak` (true peak, dBTP) uzupełnia wątek w tle (`app/loudness.py`): bierze najnowszy niezmierzony utwór, mierzy go przez ffmpeg `loudnorm` (tylko analiza, uruchamiana przez `nice`) i ustawia `loudness_tried`. NULL oznacza „nieznane”: utwór gra bez zmian. Przy odtwarzaniu `BotManager.gain_for` zamienia pomiar na wzmocnienie (cel minus głośność, ograniczone maksymalnym podbiciem i utrzymaniem szczytu poniżej -1 dBTP), które mnoży głośność `PCMVolumeTransformer`; nic nie jest przekodowywane. Przełącznik, poziom docelowy i maksymalne podbicie ustawia administrator w panelu i leżą w tabeli `app_settings` (`RuntimeSettings` w `app/loudness.py`); nie ma dla nich zmiennych środowiskowych.
- `playlists.kind` to `manual` (wiersze w `playlist_items`) albo `tags` (reguła JSON w `playlists.rule`: `{"tags": [...], "mode": "all"|"any"}`). Playlista z tagów nie przechowuje utworów, są liczone przez `library.tracks_for_tags` przy wyświetlaniu lub odtwarzaniu, ze wspólnych tagów i tagów osobistych właściciela. `POST /player/{guild}/play` przyjmuje też wprost `tags` i `mode`, żeby zagrać niezapisany wybór.

## Uprawnienia

| Zasób | Odczyt | Zapis |
|---|---|---|
| Lista biblioteki, podgląd | każdy użytkownik | nie dotyczy |
| Tytuł utworu, tagi wspólne, usunięcie | każdy użytkownik | właściciel, administrator |
| Tagi osobiste | tylko autor | autor |
| Zestawy, foldery, playlisty | właściciel, administrator | właściciel, administrator |
| Zlecenia pobrań | właściciel, administrator | właściciel, administrator |
| Użytkownicy, dostęp do serwerów | administrator | administrator |
| Odtwarzacz serwera Discord | użytkownicy z nadanym serwerem, administratorzy | tak samo, jeden sterujący naraz |

## Odtwarzanie

- Jeden `GuildPlayer` na serwer Discord trzyma kolejkę (id utworów, tytuły, ścieżki), kolejność (losową lub nie), flagi pętli i losowania, głośność i sterującego użytkownika.
- Każdy utwór gra przez `FFmpegPCMAudio` owinięte w `PCMVolumeTransformer`. Zmiana głośności ustawia głośność transformera, więc działa w obrębie jednej ramki (20 ms).
- **Miksowanie i przejścia.** Klient głosowy gra jedno `MixerSource` na całą playlistę, a nie jedno źródło na utwór. `app/mixer.py` trzyma do trzech *warstw* (każda to `discord.FFmpegPCMAudio` czytane z wyprzedzeniem przez własny wątek, więc wątek audio co 20 ms nigdy nie czeka na pipe), przechodzi między nimi krzywymi equal-power (sin przy wejściu, cos przy wyjściu, stosowane cztery razy na ramkę) i oddaje sumę. Gdy bieżącej warstwie zostaje `crossfade + 2,5 s`, mikser zgłasza *preroll*; player planuje wtedy następny utwór (`GuildPlayer._plan_next`, który zawija i tasuje od nowa, gdy playlista się zapętla) i kolejkuje go przez `set_next`. Zakolejkowana warstwa zaczyna wchodzić, gdy bieżącej zostaje `crossfade` sekund, a player dostaje zdarzenie *transition*, żeby `pos` szedł za dźwiękiem. Ręczne następny, poprzedni, skok, przewinięcie i nowa playlista używają zamiast tego `switch_to`: nowa warstwa wchodzi, gdy tylko zdekoduje pierwszą ramkę, a stare się wyciszają. Przewinięcie to takie przełączenie na ten sam utwór z innym offsetem, z krótkim przejściem. Mikser, któremu skończy się dźwięk (ostatni utwór, nieznana długość, uszkodzony utwór), kończy źródło klienta głosowego, a `after` każe playerowi uruchomić nowe, i to samo dzieje się, gdy przejście wynosi 0. Wtedy działa starszy filtr ffmpeg `afade` z czasem fade z playlisty; przy włączonym przejściu jest pomijany, bo oba naraz dawałyby podwójne ściszenie.
- **Licznik generacji.** Każde uruchomione lub zatrzymane źródło podbija licznik. Callback `after` źródła, które zostało zastąpione lub zatrzymane, widzi starą liczbę i nic nie robi, dzięki czemu pomijanie, stop i zamiana nie ścigają się ze sobą.
- **Awarie.** Utwór, który kończy się w ciągu 1,5 s lub zgłasza błąd, liczy się jako porażka. Jeśli wszystkie utwory kolejki zawiodą pod rząd, odtwarzanie się zatrzymuje zamiast kręcić się w nieskończoność. Brakujące pliki są pomijane.
- **Ponowne łączenie.** Jeśli sesja głosowa zakończy się niespodziewanie, odtwarzacz się resetuje i przez 35 sekund odrzuca nowe połączenia. `discord.py` trzyma timer starej sesji przez około 30 sekund, a ponowne wejście w tym oknie potrafi zabić każdą nową sesję. Tę samą lekcję zawiera projekt `discord-stream-bot`.
- **Wychodzenie przy bezczynności.** Zadanie w tle sprawdza co 30 sekund; kanał bez człowieka przez `IDLE_LEAVE_MINUTES` jest opuszczany.
- Identyfikatory Discorda w API są zawsze tekstami (JavaScript nie utrzyma 64-bitowych liczb całkowitych).

## Pobieranie

1. `POST /api/downloads` waliduje adres (https, dozwolony host), sprawdza dzienny limit i dodaje wiersz `queued`.
2. Wątek roboczy bierze najstarsze zlecenie, uruchamia yt-dlp (tylko dźwięk, jeden film, limit rozmiaru) do folderu tymczasowego, wyciąga Opus ffmpegiem i przekazuje plik do tej samej funkcji przyjmowania co wgrywanie (sprawdzenie, hasz, deduplikacja, zapis).
3. Wiersz zmienia się na `done` albo `error` z krótkim powodem. Po zleceniu wątek czeka `YTDLP_MIN_GAP_SECONDS`.
4. Zlecenia przerwane restartem wracają do kolejki.

## API HTTP

Wszystkie ścieżki są pod `/api`; żądania zmieniające stan wymagają nagłówka `X-Melomancer: 1`; każda ścieżka poza `/auth/login` i `/health` wymaga ciasteczka sesji.

| Obszar | Endpointy |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET/PATCH /auth/me`, `POST /auth/password` |
| Użytkownicy | `GET/POST /users`, `PATCH /users/{id}`, `PUT /users/{id}/guilds` |
| Biblioteka | `GET /tracks`, `POST /tracks/upload`, `PATCH/DELETE /tracks/{id}`, `GET /tracks/{id}/usage`, `GET /tracks/{id}/stream`, `PUT /tracks/{id}/my-tags`, `GET /tags` |
| Pobrania | `GET/POST /downloads` (lista niesie też postęp na żywo, upłynięte sekundy i pozostałą przerwę; `POST` przyjmuje `tags` i `my_tags`), `DELETE /downloads/{id}` |
| Playlisty | `GET/POST /sets`, `PATCH/DELETE /sets/{id}`, `POST /sets/{id}/playlists`, `PUT /sets/{id}/playlists/order`, `POST /sets/{id}/groups`, `PUT /sets/{id}/groups/order`, `PATCH/DELETE /groups/{id}`, `POST /groups/{id}/playlists`, `PUT /groups/{id}/playlists/order`, `GET/PATCH/DELETE /playlists/{id}`, `POST /playlists/{id}/copy`, `POST /playlists/{id}/items`, `PUT /playlists/{id}/order`, `PUT/DELETE /playlists/{id}/items/{item}` |
| Odtwarzacz | `GET /player/guilds`, `GET /player/{guild}/state`, `POST /player/{guild}/connect`, `disconnect`, `play`, `pause`, `resume`, `next`, `prev`, `jump`, `seek`, `stop`, `volume`, `PATCH /player/{guild}/options` |
| Osoby | `GET /people` (aktywne konta poza twoim, tylko nazwy, do wyboru odbiorcy kopii) |
| System | `GET /system`, `PATCH /system` (administrator: ustawienia głośności, przejść i ciszy), `GET /system/load` (administrator: CPU i pamięć), `GET /health` |

## Jeszcze nie zrobione

Warstwy ambientu pod muzyką i tablica efektów dźwiękowych (mikser jest miejscem dla obu). Model danych nie stoi na drodze żadnemu z tych pomysłów.
