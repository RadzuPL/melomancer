# Konfiguracja

Języki: [English](../en/configuration.md) · **Polski**

Wszystko konfiguruje się zmiennymi środowiskowymi. Uwagi wymagają tylko `DISCORD_TOKEN` i hasło pierwszego administratora, reszta ma rozsądne wartości domyślne.

## Zmienne środowiskowe

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `DISCORD_TOKEN` | (puste) | Token bota ([jak go zdobyć](discord-bot.md)). Bez niego panel działa, ale bot pozostaje offline. |
| `DISCORD_CLIENT_ID` | (puste) | Opcjonalne. Application ID bota ([gdzie je znaleźć](discord-bot.md)). Z nim zakładka **Ustawienia** pokazuje link dodający bota do serwera; puste znaczy brak linku. |
| `ADMIN_USERNAME` | `admin` | Nazwa pierwszego administratora. Używana tylko wtedy, gdy baza nie ma użytkowników. |
| `ADMIN_PASSWORD` | (puste) | Hasło pierwszego administratora, minimum 10 znaków. Używane tylko wtedy, gdy baza nie ma użytkowników. Jeśli puste lub za krótkie, generowane jest losowe hasło wypisane raz w logu kontenera. |
| `PUID` / `PGID` | `99` / `100` | Właściciel plików w folderze danych. Kontener startuje jako root tylko po to, żeby poprawić właściciela, i od razu przechodzi na tego użytkownika. Na typowym Linuksie użyj `1000` / `1000`. |
| `TZ` | `UTC` | Strefa czasowa znaczników czasu w logach, np. `Europe/Warsaw`. |
| `DATA_DIR` | `/data` | Gdzie leżą baza i, domyślnie, muzyka. Zamontuj tu wolumen. |
| `MUSIC_DIR` | `$DATA_DIR/music` | Opcjonalny osobny folder na pliki audio, np. żeby trzymać bibliotekę na dużym dysku macierzy, a bazę na szybkim nośniku. To ścieżka **wewnątrz kontenera**: zamontuj tam folder z hosta (użyj `/music`) i ustaw tę zmienną na niego. Zobacz [Muzyka na innym dysku](#muzyka-na-innym-dysku). |
| `MAX_UPLOAD_MB` | `300` | Największy pojedynczy plik przyjmowany z wgrywania lub pobierania. Cloudflare Tunnel ogranicza pojedyncze żądanie do 100 MB w planach Free i Pro, zobacz [Bezpieczeństwo](security.md). |
| `YTDLP_ENABLED` | `true` | `false` wyłącza pobieranie, wgrywanie plików nadal działa. |
| `YTDLP_DAILY_LIMIT` | `50` | Maksymalna liczba pobrań w ruchomych 24 godzinach (0 = bez limitu). Chroni twój adres IP. |
| `YTDLP_MIN_GAP_SECONDS` | `20` | Przerwa między dwoma pobraniami. |
| `YTDLP_ALLOWED_HOSTS` | `youtube.com,youtu.be,music.youtube.com,soundcloud.com,bandcamp.com` | Hosty, z których wolno pobierać (razem z subdomenami). Przyjmowane są tylko adresy `https://`. |
| `YTDLP_COOKIES_FILE` | (puste) | Ścieżka w kontenerze do pliku cookies dla yt-dlp. Używaj tylko jednorazowego konta, nigdy głównego konta Google. |
| `IDLE_LEAVE_MINUTES` | `30` | Bot opuszcza kanał głosowy, gdy przez tyle minut nie ma w nim człowieka (0 = nigdy). |
| `DEFAULT_VOLUME` | `0.4` | Głośność początkowa, od 0.0 do 1.5 (1.0 = 100 %). |
| `SESSION_HOURS` | `168` | Jak długo trwa logowanie (7 dni). |
| `COOKIE_SECURE` | `auto` | `auto` oznacza ciasteczko logowania jako Secure, gdy panel otwarto przez https. `true` / `false` wymuszają wartość. |
| `LOGIN_MAX_FAILURES` | `5` | Liczba nieudanych logowań na nazwę użytkownika lub adres przed czasową blokadą. |
| `LOGIN_WINDOW_SECONDS` | `300` | Długość tego okna i blokady. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` lub `ERROR`. |

## Folder danych

```
/data                         DATA_DIR: tu zamontuj szybki dysk
├── melomancer.db             baza SQLite: użytkownicy, utwory, tagi, zestawy, playlisty, zlecenia pobrań
├── melomancer.db.before-v2   automatyczna kopia sprzed aktualizacji bazy (zostaje, skasuj ją, gdy wszystko działa)
├── tmp/                      wgrywania i pobrania w toku (czyszczone przy starcie)
└── music/                    pliki audio, nazwane <id utworu>.<rozszerzenie>   (tylko gdy MUSIC_DIR nie jest ustawione)

/music                        MUSIC_DIR (opcjonalnie): pliki audio w osobnym folderze, np. na dużym dysku
```

Bez `MUSIC_DIR` pliki audio są w `music/` w folderze danych, i to jest najprostsza konfiguracja. Z nim leżą w folderze, na który wskażesz, a folder danych zostaje tylko z bazą i plikami tymczasowymi.

Pliki audio mają wygenerowane nazwy. Tytuł widoczny w panelu jest w bazie, więc nie zmieniasz nazw ani nie przenosisz plików ręcznie w tych folderach. Używaj panelu.

## Muzyka na innym dysku

Przydaje się, gdy biblioteka jest duża, a folder danych leży na małym, szybkim dysku (np. pula NVMe w Unraidzie). `MUSIC_DIR` to ścieżka wewnątrz kontenera, więc muszą się zgadzać dwie rzeczy: **montowanie** folderu z hosta do `/music` oraz `MUSIC_DIR=/music`. Sama zmienna nie wystarczy: bez montowania pliki zostałyby zapisane wewnątrz kontenera i przepadły przy jego odtworzeniu.

- **Docker:** dodaj do polecenia `docker run` `-v /mnt/user/rpg/melomancer:/music -e MUSIC_DIR=/music`.
- **Compose:** dodaj `- /mnt/user/rpg/melomancer:/music` w `volumes` i `MUSIC_DIR: /music` w `environment`.
- **Unraid:** szablon ma ścieżkę **Music library** (ścieżka w kontenerze `/music`): ustaw jej ścieżkę na hoście, np. `/mnt/user/rpg/melomancer`. Zmienną **Music folder in the container** zostaw na `/music`.

Żeby przenieść istniejącą bibliotekę, najpierw zatrzymaj kontener, potem skopiuj stary folder, sprawdź kopię i dopiero wtedy skasuj stary (na Unraidzie w jego terminalu; dopasuj obie ścieżki):

```
rsync -a --info=progress2 /mnt/user/appdata/melomancer/music/ /mnt/user/rpg/melomancer/
```

```
rsync -avnc /mnt/user/appdata/melomancer/music/ /mnt/user/rpg/melomancer/
```

Drugie polecenie tylko porównuje oba foldery i nie wypisuje żadnych nazw plików, gdy są identyczne. Potem usuń stary folder i uruchom kontener z nowymi ustawieniami. Na koniec zagraj utwór i poszukaj w playlistach znaczków ⚠, które oznaczają nieznaleziony plik (zwykle montowanie i `MUSIC_DIR` się nie zgadzają).

Dwie rzeczy do zapamiętania: kopia zapasowa musi obejmować także ten folder, bo nie leży już w folderze danych, a dysk, który się usypia, potrzebuje kilku sekund na rozkręcenie przy pierwszym utworze.

## Porty i sieć

| Port | Kierunek | Do czego |
|---|---|---|
| 8080/tcp | przychodzący | Panel webowy. Nie wystawiaj go bezpośrednio do internetu. |
| 443/tcp i UDP głosu Discorda | wychodzący | Gateway i głos Discorda. Zwykły NAT wystarcza. |
| 443/tcp | wychodzący | Pobieranie yt-dlp, tylko gdy pobieranie jest włączone. |
| 443/tcp | wychodzący | `api.github.com`: sprawdzanie nowszego wydania (Ustawienia, można wyłączyć). |

## Reverse proxy i tunel

Kontener uruchamia uvicorn z włączonymi nagłówkami proxy, więc adres klienta i schemat `https` z nagłówków `X-Forwarded-*` są respektowane. WebSockety nie są używane. Cloudflare Tunnel z Access opisuje [Bezpieczeństwo](security.md).
