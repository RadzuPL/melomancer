# Instalacja

Języki: [English](../en/installation.md) · **Polski**

Melomancer to jeden kontener, a kontener to na razie jedyny sposób uruchamiania opisany w tej dokumentacji (zwykły komputer z Windowsem albo otoczka desktopowa nie są wykluczone na później). Potrzebuje tylko ruchu wychodzącego do internetu (Discord przez HTTPS/WebSocket oraz UDP dla głosu), dla bota nie otwierasz żadnych portów przychodzących. Panel webowy nasłuchuje na porcie **8080**.

Zanim zaczniesz, potrzebujesz **tokena bota Discord**. Najpierw załóż bota: [Tworzenie bota Discord](discord-bot.md).

## 1. Pobranie obrazu

Obraz jest budowany przez GitHub Actions i publikowany w GitHub Container Registry:

```
ghcr.io/radzupl/melomancer:latest
```

Pakiet jest publiczny, więc nie trzeba logować się do rejestru: `docker pull` i szablon Unraida działają od razu.

Jeśli zrobisz fork repozytorium i zbudujesz własny obraz, GitHub domyślnie tworzy nowy pakiet jako prywatny. Wtedy albo ustaw go jako publiczny (strona pakietu, Package settings, Danger Zone, Change package visibility), albo zaloguj się na maszynie z Dockerem. Do logowania utwórz klasyczny token dostępu (personal access token) tylko z uprawnieniem `read:packages` na stronie https://github.com/settings/tokens, a potem uruchom:

```
docker login ghcr.io -u TWOJA_NAZWA_NA_GITHUBIE
```

Jako hasło wklej token.

> Unraid: system plików roota leży w RAM-ie, więc `docker login` wpisany w terminalu zwykle znika po restarcie i późniejsze aktualizacje kończą się błędem „unauthorized”. Publiczny pakiet albo zadanie w User Scripts wykonujące `docker login` przy starcie macierzy rozwiązuje ten problem.

## 2. Docker run

Podmień token, hasło i folder na hoście. `PUID` i `PGID` określają właściciela plików w folderze danych.

```
docker run -d \
  --name melomancer \
  --restart unless-stopped \
  -p 8080:8080 \
  -v /srv/melomancer:/data \
  -e DISCORD_TOKEN='TU_WKLEJ_TOKEN_BOTA' \
  -e ADMIN_USERNAME='admin' \
  -e ADMIN_PASSWORD='haslo-co-najmniej-10-znakow' \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ='Europe/Warsaw' \
  ghcr.io/radzupl/melomancer:latest
```

Sprawdź, czy wystartował:

```
docker logs melomancer
```

Powinieneś zobaczyć `Logged in as <nazwa bota>` i żadnych błędów. Otwórz http://localhost:8080/ (albo adres maszyny) i zaloguj się.

## 3. Docker Compose

Pobierz albo skopiuj `docker-compose.yml` i `.env.example` z repozytorium do jednego folderu, a potem utwórz plik ustawień:

```
cp .env.example .env
```

Edytuj `.env`: ustaw `DISCORD_TOKEN`, `ADMIN_PASSWORD` (co najmniej 10 znaków) oraz `PUID` / `PGID` (swoje wartości pokażą `id -u` i `id -g`). Potem uruchom:

```
docker compose up -d
```

Logi:

```
docker compose logs -f melomancer
```

Biblioteka muzyczna i baza trafiają do folderu `./data` obok pliku compose.

## 4. Unraid

Na Unraidzie kontenery zwykle dodaje się z szablonu w zakładce Docker. Szablon leży w repozytorium jako `unraid/my-melomancer.xml`.

1. Pobierz `unraid/my-melomancer.xml` z repozytorium (https://github.com/RadzuPL/melomancer/blob/main/unraid/my-melomancer.xml, przycisk Raw).
2. Skopiuj go na pendrive Unraida jako `/boot/config/plugins/dockerMan/templates-user/my-melomancer.xml` (nazwa pliku musi zaczynać się od `my-`, inaczej Unraid nie pokaże go w *User templates*). Przez sieć jest to udział `\\TOWER\flash\config\plugins\dockerMan\templates-user\` (zamień `TOWER` na nazwę swojego serwera).
3. Otwórz zakładkę **Docker**, kliknij **Add Container**, rozwiń listę **Template** i wybierz **melomancer** w sekcji *User templates*.
4. Wypełnij pola:

| Pole | Co wpisać |
|---|---|
| Web panel port | `8080` albo inny wolny port hosta |
| Data (database + music library) | Folder na prawdziwym dysku lub puli, np. `/mnt/nvme/appdata/melomancer`. Jeśli możesz, unikaj `/mnt/user/...` dla bazy; SQLite zachowuje się lepiej na bezpośredniej ścieżce puli niż na udziale FUSE |
| Discord bot token | Token z instrukcji [Tworzenie bota Discord](discord-bot.md) |
| Admin username / Admin password | Pierwszy administrator (hasło co najmniej 10 znaków) |
| PUID / PGID (advanced) | `99` i `100` na Unraidzie |

5. Kliknij **Apply**. Gdy kontener działa, otwórz jego **WebUI** z zakładki Docker.

Jeśli obraz jest prywatny (twój własny fork), najpierw wykonaj logowanie do rejestru z punktu 1, inaczej Unraid pokaże błąd pobierania.

Aktualizacje: zakładka Docker, **Check for Updates**, potem **apply update** przy kontenerze. Jeśli masz Watchtowera, sam podmieni nowe obrazy `latest`. Nowy obraz powstaje też co poniedziałek, co odświeża `yt-dlp` (dostaje nowy numer wersji, środkowa liczba rośnie).

Sieć bridge albo własna: jeśli kontener Cloudflare Tunnel łączy się z panelem po nazwie kontenera, ustaw Melomancera w tej samej własnej sieci Dockera i użyj `http://melomancer:8080` jako adresu usługi w tunelu.

## 5. Pierwsze logowanie

Otwórz panel i zaloguj się danymi z `ADMIN_USERNAME` i `ADMIN_PASSWORD`. Te zmienne działają tylko wtedy, gdy baza nie ma jeszcze żadnych użytkowników, więc późniejsza zmiana niczego nie robi. Hasło zmienisz w menu konta (twoja nazwa w prawym górnym rogu).

Dalej:

1. Zakładka **Użytkownicy**: załóż konta pozostałym MG i zaznacz, którymi serwerami Discord każdy może sterować.
2. Zakładka **Biblioteka**: wgraj muzykę.
3. Zakładka **Playlisty**: utwórz zestaw i playlistę w nim (foldery są opcjonalne).
4. Zakładka **Odtwarzacz**: wybierz serwer i kanał, i naciśnij playlistę.

Panel opisuje [Obsługa panelu](usage.md).

## 6. Wystawienie panelu do internetu

Nie publikuj portu 8080 bezpośrednio. Postaw panel za Cloudflare Tunnel z polityką Cloudflare Access albo korzystaj z niego przez VPN. Zobacz [Bezpieczeństwo](security.md).

## 7. Aktualizacja, kopia zapasowa, odzyskiwanie

Aktualizacja (Docker run):

```
docker pull ghcr.io/radzupl/melomancer:latest
```

```
docker stop melomancer && docker rm melomancer
```

Potem uruchom ponownie polecenie `docker run` z punktu 2. Dane leżą w zamontowanym folderze i zostają.

Aktualizacja (Compose):

```
docker compose pull && docker compose up -d
```

Kopia zapasowa: wszystko jest w folderze danych. Żeby skopiować bez zatrzymywania bota, najpierw zrób spójną kopię bazy:

```
docker exec melomancer python -c "import sqlite3; s=sqlite3.connect('/data/melomancer.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d); d.close(); s.close()"
```

Potem skopiuj cały folder danych (`backup.db`, `melomancer.db` i folder `music`) swoim zwykłym narzędziem do kopii.

Zapomniane hasło administratora:

```
docker exec -it melomancer python -m app.cli reset-password admin
```

Polecenie pyta o nowe hasło, włącza konto z powrotem i kończy jego sesje.
