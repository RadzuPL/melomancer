# Melomancer

**[English](#english) · [Polski](#polski)**

---

## English

[Przejdź do wersji polskiej ↓](#polski)

A self-hosted Discord music bot with a web panel, made for tabletop RPG sessions. One shared music library, private **playlists** collected in **sets** (a game system or a scenario), optionally sorted into **folders** (for example locations or kinds of scenes), one-click playback into a voice channel, live volume control, and several game masters on one server, each with playlists the others cannot see.

### Features

- Web panel (Polish and English) with its own user accounts. Put it behind Cloudflare Access for a second factor.
- Shared library: upload many files or whole folders at once, shared tags and personal tags, edit titles and tags, preview in the browser.
- Add a single YouTube, SoundCloud or Bandcamp track by URL: audio is downloaded once with yt-dlp, with rate limits to protect your IP address. Playback always comes from disk.
- Private sets, playlists and optional folders. Automatic playlists built from tags, and a quick pick by tags in the player. Deleting a track leaves a greyed-out entry in playlists that use it, so the author can replace it.
- Player: choose a Discord server and voice channel, press a playlist, pause, skip, loop, shuffle, fade in and out, volume 0 to 150 %.
- Several Discord servers with one bot; per-user access to servers; one controller per server at a time.
- Voice with Discord's end-to-end encryption (DAVE), reconnect protection, leaves empty channels.
- One container, SQLite, no external services. Image on GitHub Container Registry, built and versioned automatically. Unraid template included.

### Quick start

1. Create the bot and copy its token: [docs/en/discord-bot.md](docs/en/discord-bot.md)
2. Run the container (Docker, Docker Compose or Unraid): [docs/en/installation.md](docs/en/installation.md)
3. Log in at http://localhost:8080/ with the administrator you configured, add music, build playlists, press play.

Minimal Compose file (the repository contains a complete one):

```yaml
services:
  melomancer:
    image: ghcr.io/radzupl/melomancer:latest
    restart: unless-stopped
    environment:
      DISCORD_TOKEN: "paste-the-bot-token"
      ADMIN_PASSWORD: "at-least-10-characters"
      PUID: 1000
      PGID: 1000
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
```

### Documentation

| | |
|---|---|
| [Installation](docs/en/installation.md) | Docker, Docker Compose, Unraid, updates, backup |
| [Creating the Discord bot](docs/en/discord-bot.md) | Developer Portal step by step, invite link |
| [Configuration](docs/en/configuration.md) | All environment variables, data folder, ports |
| [Using the panel](docs/en/usage.md) | Library, tags, playlists, player, downloads, administration |
| [Security](docs/en/security.md) | Cloudflare Access, privacy between users, notes on downloading from YouTube |
| [Architecture](docs/en/architecture.md) | Components, data model, permissions, API |
| [Development](docs/en/development.md) | Running locally, tests, CI, automatic versions |
| [Troubleshooting](docs/en/troubleshooting.md) | Common problems and fixes |

---

## Polski

[Go to the English version ↑](#english)

Własny bot muzyczny Discord z panelem webowym, stworzony na sesje RPG. Jedna wspólna biblioteka muzyki, prywatne **playlisty** zebrane w **zestawy** (system gry albo scenariusz), opcjonalnie podzielone na **foldery** (np. lokacje albo rodzaje scen), odpalanie jednym przyciskiem na kanale głosowym, regulacja głośności na żywo oraz kilku mistrzów gry na jednym serwerze, każdy z playlistami niewidocznymi dla pozostałych.

### Funkcje

- Panel webowy (polski i angielski) z własnymi kontami użytkowników. Postaw go za Cloudflare Access, żeby mieć drugi składnik logowania.
- Wspólna biblioteka: wgrywanie wielu plików lub całych folderów naraz, tagi wspólne i osobiste, edycja tytułów i tagów, podgląd w przeglądarce.
- Dodawanie pojedynczego utworu z YouTube, SoundCloud lub Bandcamp po adresie URL: dźwięk jest pobierany raz przez yt-dlp, z limitami chroniącymi twój adres IP. Odtwarzanie zawsze idzie z dysku.
- Prywatne zestawy, playlisty i opcjonalne foldery. Playlisty automatyczne z tagów oraz szybki wybór z tagów w odtwarzaczu. Usunięcie utworu zostawia wyszarzony wpis w playlistach, które go używają, żeby autor mógł go zastąpić.
- Odtwarzacz: wybierasz serwer Discord i kanał głosowy, naciskasz playlistę, pauza, pomijanie, pętla, losowo, płynne wejście i wyjście, głośność 0 do 150 %.
- Kilka serwerów Discord z jednym botem; dostęp użytkowników do serwerów; jeden sterujący na serwer naraz.
- Głos z szyfrowaniem end-to-end Discorda (DAVE), ochrona przed pętlą ponownych połączeń, opuszczanie pustych kanałów.
- Jeden kontener, SQLite, żadnych usług zewnętrznych. Obraz w GitHub Container Registry, budowany i wersjonowany automatycznie. W zestawie szablon Unraid.

### Szybki start

1. Utwórz bota i skopiuj jego token: [docs/pl/discord-bot.md](docs/pl/discord-bot.md)
2. Uruchom kontener (Docker, Docker Compose lub Unraid): [docs/pl/installation.md](docs/pl/installation.md)
3. Zaloguj się pod adresem http://localhost:8080/ jako skonfigurowany administrator, dodaj muzykę, ułóż playlisty i naciśnij odtwarzanie.

Minimalny plik Compose (repozytorium zawiera pełny):

```yaml
services:
  melomancer:
    image: ghcr.io/radzupl/melomancer:latest
    restart: unless-stopped
    environment:
      DISCORD_TOKEN: "wklej-token-bota"
      ADMIN_PASSWORD: "co-najmniej-10-znakow"
      PUID: 1000
      PGID: 1000
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
```

### Dokumentacja

| | |
|---|---|
| [Instalacja](docs/pl/installation.md) | Docker, Docker Compose, Unraid, aktualizacje, kopie zapasowe |
| [Tworzenie bota Discord](docs/pl/discord-bot.md) | Developer Portal krok po kroku, link zaproszenia |
| [Konfiguracja](docs/pl/configuration.md) | Wszystkie zmienne środowiskowe, folder danych, porty |
| [Obsługa panelu](docs/pl/usage.md) | Biblioteka, tagi, playlisty, odtwarzacz, pobieranie, administracja |
| [Bezpieczeństwo](docs/pl/security.md) | Cloudflare Access, prywatność między użytkownikami, uwagi o pobieraniu z YouTube |
| [Architektura](docs/pl/architecture.md) | Komponenty, model danych, uprawnienia, API |
| [Rozwój](docs/pl/development.md) | Uruchomienie lokalne, testy, CI, automatyczne wersje |
| [Rozwiązywanie problemów](docs/pl/troubleshooting.md) | Typowe problemy i ich rozwiązania |
