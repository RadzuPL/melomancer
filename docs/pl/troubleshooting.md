# Rozwiązywanie problemów

Języki: [English](../en/troubleshooting.md) · **Polski**

Zacznij od logu, zwykle mówi, co jest nie tak:

```
docker logs --tail 100 melomancer
```

Dla szczegółów ustaw `LOG_LEVEL=DEBUG` i zrestartuj kontener.

## Bot

**„Bot Discord jest wyłączony: brak DISCORD_TOKEN.”**
Zmienna jest pusta albo jej nie ma w ustawieniach kontenera. Ustaw ją i zrestartuj.

**„Discord odrzucił token bota.”**
Token jest błędny albo został zresetowany. Skopiuj nowy: Developer Portal, twoja aplikacja, **Bot**, **Reset Token** (zobacz [Tworzenie bota Discord](discord-bot.md)). Wklej bez spacji i cudzysłowów.

**Bot jest online, ale mojego serwera nie ma w zakładce Odtwarzacz.**
- Bot nie został zaproszony na ten serwer. Użyj linku z [Tworzenie bota Discord](discord-bot.md).
- Nie jesteś administratorem i nikt nie zaznaczył ci tego serwera (zakładka Administracja, **Serwery**).
- Na liście są tylko kanały głosowe, na które bot może się **Połączyć**. Sprawdź uprawnienia kanału.

**„Bot nie ma uprawnień na tym kanale.”**
Zezwól roli bota na tym kanale głosowym na View Channel, Connect i Speak (nadpisanie uprawnień kanału może odbierać to, na co serwer pozwala).

**„Poprzednia sesja głosowa dopiero się zakończyła. Spróbuj za N s.”**
To celowe 35 sekund oczekiwania po zerwaniu sesji głosowej. Poczekaj i naciśnij ponownie. Jeśli zrywa się ciągle, szukaj w logu `Voice session in guild ... ended unexpectedly` i sprawdź sieć między serwerem a Discordem.

**Połączony, ale nie ma dźwięku.**
- Czy coś naprawdę gra (odtwarzacz pokazuje utwór i poruszający się pasek)?
- Suwak głośności na 0 % albo bot wyciszony przez ciebie w Discordzie. Kliknij bota prawym przyciskiem na kanale, żeby zobaczyć jego głośność użytkownika.
- Log pokazuje `File missing for ...`: plik audio zniknął z folderu danych. Zastąp go albo wgraj ponownie.
- Sprawdź, czy pierwsze linie logu mówią `discord.py 2.7.x, davey ...`, a nie `davey MISSING`. Głos potrzebuje obu od czasu wymogu szyfrowania end-to-end w Discordzie (https://docs.discord.com/developers/topics/voice-connections). Jeśli brakuje, pobierz najnowszy obraz.

**Inny użytkownik widzi „Ten serwer obsługuje teraz ktoś inny.”**
Na tym serwerze gra playlista innego użytkownika. On (albo administrator) naciska **Stop**.

## Wgrywanie

**„Plik jest za duży dla serwera lub tunelu.”** (HTTP 413)
Cloudflare dopuszcza 100 MB na żądanie w planach Free i Pro. Wgraj ten plik z wnętrza swojej sieci, np. `http://<adres serwera>:8080`, albo podziel go. Zobacz [Bezpieczeństwo](security.md).

**„To nie jest plik audio.”** / **„Nieobsługiwany typ pliku.”**
Przyjmowane są tylko pliki mp3, ogg, opus, flac, wav, m4a, aac i webm, które zawierają strumień audio.

## Pobieranie

Otwórz zakładkę Pobieranie, tekst błędu jest obok zlecenia.

**„Sign in to confirm you're not a bot”.**
YouTube na razie odrzuca żądania z twojego adresu IP. Przestań pobierać na kilka dni, obniż `YTDLP_DAILY_LIMIT`, podnieś `YTDLP_MIN_GAP_SECONDS`. Odtwarzanie muzyki, która już jest w bibliotece, nie jest tym dotknięte. Nie podawaj mu ciasteczek swojego głównego konta.

**„Requested format is not available”, błędy o środowisku JavaScript lub „challenge”.**
yt-dlp jest nieaktualny albo nie może uruchomić swojego pomocnika JavaScript. Pobierz najnowszy obraz (nowy powstaje co poniedziałek) i sprawdź środowisko w środku:

```
docker exec melomancer deno --version
```

**„Dzienny limit pobrań został wykorzystany.”**
`YTDLP_DAILY_LIMIT` w ostatnich 24 godzinach. Podnieś go albo poczekaj.

## Kontenery, pliki i baza

**`PermissionError` dla `/data`.**
Ustaw `PUID` i `PGID` na właściciela folderu danych na hoście (Unraid: 99 i 100). Kontener uruchomiony jako root poprawia właściciela folderu danych przy starcie.

**„database is locked” albo uszkodzona baza na Unraidzie.**
Przenieś folder danych z `/mnt/user/...` na bezpośrednią ścieżkę puli, np. `/mnt/nvme/appdata/melomancer`. SQLite nie lubi udziału użytkownika FUSE.

**Unraid nie może pobrać obrazu: „unauthorized”.**
Pakiet jest prywatny, a logowanie do rejestru zniknęło (na Unraidzie logowanie nie przetrwa restartu). Zobacz pierwszy punkt w [Instalacji](installation.md): zaloguj się ponownie, zautomatyzuj logowanie skryptem albo ustaw pakiet jako publiczny.

**Panel wygląda staro po aktualizacji.**
Odśwież stronę przez Ctrl+F5. Strona i jej skrypty niosą numer wersji, więc zwykle dzieje się to samo.

**Zapomniałem hasła administratora.**

```
docker exec -it melomancer python -m app.cli reset-password admin
```

**Zablokowałem się zbyt wieloma błędnymi hasłami.**
Blokada trwa 5 minut (`LOGIN_WINDOW_SECONDS`) i znika po restarcie kontenera.
