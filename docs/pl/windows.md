# Melomancer na Windows (eksperyment)

Języki: [English](../en/windows.md) · **Polski**

Melomancer działa na komputerze z Windows 10 lub 11 bez Dockera: to ta sama aplikacja co w kontenerze, uruchamiana z rozpakowanego folderu. Ta strona jest dla kogoś, kto chce to wypróbować.

**Status: eksperyment.** Sprawdzone dotąd na Windows 11 z prawdziwym botem Discorda: muzyka przez głos Discorda, odtwarzanie w przeglądarce, pobieranie z YouTube, playlisty, plik ustawień. Nie ma jeszcze instalatora, ikony w zasobniku ani wbudowanej aktualizacji, a program nie jest podpisany cyfrowo, więc Windows prosi o potwierdzenie przy starcie (krok 3).

## Czego potrzebujesz

- Windows 10 lub 11, 64-bitowy. Bez uprawnień administratora, bez Dockera, bez WSL, nic nie trzeba instalować.
- Około 140 MB do pobrania; po rozpakowaniu zajmuje kilkaset MB (w środku są Python, ffmpeg i środowisko JavaScript). Twoja muzyka dochodzi do tego.
- Dostępu do internetu (Discord, pobieranie, sprawdzanie nowszej wersji).
- Do muzyki na kanale głosowym Discorda: własnego bota i jego tokena, zob. krok 5. Bez bota panel i **Odtwarzaj tutaj** (dźwięk z głośników tego komputera) i tak działają.

## 1. Pobranie

Każde wydanie Melomancera ma paczkę dla Windows jako załącznik, `Melomancer-win64-<wersja>.zip` (około 140 MB). Pojawia się kilka minut po samym wydaniu, a jej link jest w notatkach wydania („Windows package"). Wydania: https://github.com/RadzuPL/melomancer/releases

Jeśli najnowsze wydanie nie ma jeszcze takiego pliku, poczekaj kilka minut. Jeśli dalej go nie ma, ten build się nie udał: weź poprzednie wydanie.

## 2. Rozpakowanie

Kliknij zipa prawym przyciskiem i wybierz **Wyodrębnij wszystko** albo użyj dowolnego programu do rozpakowywania. Wybierz zwykły folder, do którego możesz zapisywać, na przykład `C:\Melomancer`; unikaj Program Files. W rozpakowanym folderze są `Melomancer.cmd`, `Ustawienia - Settings.cmd`, `config.example.toml`, `README-WINDOWS.txt` i sam program (`runtime`, `app`, `bin`).

## 3. Pierwsze uruchomienie

Kliknij dwukrotnie `Melomancer.cmd`. Ponieważ program nie jest podpisany, Windows pokaże okno **Otwieranie pliku - ostrzeżenie o zabezpieczeniach** z napisem „Nie można zweryfikować wydawcy" i wydawcą „Nieznany wydawca". Tak ma być.

1. Odznacz **Zawsze pytaj przed otwarciem tego pliku**, żeby Windows nie pytał ponownie.
2. Kliknij **Uruchom**.

Jeśli zamiast tego Windows pokaże niebieską stronę SmartScreen „System Windows ochronił ten komputer", kliknij **Więcej informacji**, a potem **Uruchom mimo to**. Na świeżym Windows 11 z włączoną funkcją **Inteligentna kontrola aplikacji** (Smart App Control) niepodpisane programy mogą być blokowane całkowicie; to znane ograniczenie tego eksperymentu (można ją wyłączyć w Zabezpieczeniach Windows, ale to decyzja dotycząca całego komputera).

Otworzy się czarne okno i wypisze mniej więcej to:

```
Melomancer 0.6.39
Settings file: C:\Users\TwojaNazwa\AppData\Local\Melomancer\config.toml  (created now, edit it to add your Discord bot token)
Panel: http://127.0.0.1:8080/   (Ctrl+C or closing this window stops it)
```

Po kilku sekundach przeglądarka otworzy panel. Jesteś już zalogowany jako administrator (zob. „Logowanie" niżej). **Czarne okno ma zostać otwarte, dopóki używasz Melomancera**; jego zamknięcie albo Ctrl+C w nim zatrzymuje program.

## 4. Muzyka bez Discorda

Bez bota działa już wszystko inne:

- Zakładka **Biblioteka**: wgraj pliki albo wklej adres z YouTube, SoundCloud lub Bandcamp w zakładce **Pobieranie** (potrzebne narzędzia są w paczce).
- Zakładka **Playlisty**: zrób zestaw i playlistę.
- Zakładka **Odtwarzacz**: kliknij **Odtwarzaj tutaj**, potem playlistę. Dźwięk idzie z głośników tego komputera, a przełączanie zakładek panelu go nie zatrzymuje.

Jak działa panel, szczegółowo: [Obsługa panelu](usage.md).

## 5. Podłączenie bota Discorda

Z Discord Developer Portal potrzebujesz dwóch wartości: **tokena bota** i **Application ID**. Jak założyć bota, co wyłączyć i jak go zaprosić: [Tworzenie bota Discord](discord-bot.md), kroki od 1 do 4. W skrócie: https://discord.com/developers/applications, Twoja aplikacja, **General Information** (skopiuj **APPLICATION ID**) oraz **Bot**, potem **Reset Token** (skopiuj token, Discord pokazuje go raz).

1. Kliknij dwukrotnie `Ustawienia - Settings.cmd` w folderze Melomancera. Plik ustawień otworzy się w Notatniku. (Bez skrótu: naciśnij Win+R, wpisz poniższe polecenie i naciśnij Enter.)

   ```
   notepad %LOCALAPPDATA%\Melomancer\config.toml
   ```

2. Znajdź dwie linie `# discord_token = ''` i `# discord_client_id = ''`. Usuń `#` i spację za nim, a wartości wpisz między pojedyncze cudzysłowy:

   ```
   discord_token = 'skopiowany-token'
   discord_client_id = '123456789012345678'
   ```

3. Zapisz (Ctrl+S) i zamknij Notatnik. Plik musi zostać zapisany jako UTF-8 (to domyślne w Notatniku w Windows 11).
4. Zamknij czarne okno Melomancera i uruchom `Melomancer.cmd` ponownie. Okno napisze, że bot się zalogował: `Logged in as <nazwa Twojego bota>`.
5. W panelu otwórz **Ustawienia**: kafelek bota pokazuje **Działa**, a dzięki Application ID także link **Dodaj bota do serwera**. Użyj go, żeby zaprosić bota (potrzebujesz uprawnienia „Zarządzanie serwerem" na tym serwerze Discorda).
6. W zakładce **Odtwarzacz** wybierz serwer i kanał głosowy, kliknij **Połącz**, potem kliknij playlistę.

Token to hasło: nigdy nie wklejaj go do wiadomości, zgłoszenia ani zrzutu ekranu. Jeśli kiedyś wycieknie, kliknij ponownie **Reset Token** w Developer Portal i wpisz nowy do pliku.

## Plik ustawień

`%LOCALAPPDATA%\Melomancer\config.toml` zawiera każde ustawienie z objaśnieniem po polsku i angielsku; w folderze paczki leży ta sama lista jako `config.example.toml`. Usuń `#` przed linią, żeby jej użyć, zapisz plik, zamknij i uruchom Melomancera ponownie. Ścieżki wpisuj w pojedynczych cudzysłowach: `music_dir = 'D:\Music\Melomancer'`. Gdy nowsza wersja ma ustawienia, o których Twój plik jeszcze nie wspomina, Melomancer dopisuje je na końcu jako zakomentowane linie pod nagłówkiem z wersją i mówi o tym w oknie; nigdy nie zmienia linii, które napisałeś.

| Ustawienie | Domyślnie | Znaczenie |
|---|---|---|
| `discord_token` | (puste) | Token bota. Bez niego bot zostaje offline. |
| `discord_client_id` | (puste) | Application ID bota, dla linku **Dodaj bota do serwera** w Ustawieniach. |
| `admin_username`, `admin_password` | `admin`, (puste) | Pierwszy administrator, tworzony tylko przy pustej bazie. Bez hasła powstaje losowe, pokazane raz w oknie (potrzebne tylko, gdy wyłączysz `auto_login` albo wejdziesz na panel z innego komputera). |
| `host`, `port` | `127.0.0.1`, `8080` | Gdzie nasłuchuje panel. `127.0.0.1` to tylko ten komputer (więc Windows nie pyta o zaporę); `host = '0.0.0.0'` otwiera panel dla sieci, a Windows zapyta o zaporę. |
| `auto_login` | `true` | Loguje ten komputer jako administratora bez hasła, zob. niżej. |
| `data_dir`, `music_dir` | `%LOCALAPPDATA%\Melomancer\data`, folder `music` w nim | Gdzie leżą baza danych i pliki audio. |
| `ytdlp_enabled`, `ytdlp_daily_limit`, `ytdlp_min_gap_seconds` | `true`, `50`, `20` | Pobieranie z YouTube i podobnych serwisów: włączone lub nie, limit na 24 godziny, przerwa między dwoma pobraniami. |
| `max_upload_mb` | `300` | Największy pojedynczy plik, w MB. |
| `idle_leave_minutes` | `30` | Bot opuszcza kanał głosowy bez ludzi po tylu minutach (0 oznacza nigdy). |
| `default_volume` | `0.4` | Głośność startowa, od 0.0 do 1.5. |
| `log_level` | `INFO` | `DEBUG`, `INFO`, `WARNING` lub `ERROR`. |

Działa też każda inna zmienna z [Konfiguracji](configuration.md), zapisana małymi literami. Zmienna środowiskowa, która jest już ustawiona, ma pierwszeństwo przed plikiem.

## Gdzie co leży

| Co | Gdzie |
|---|---|
| Program | Folder, który rozpakowałeś (można go skasować i podmienić) |
| Plik ustawień | `%LOCALAPPDATA%\Melomancer\config.toml` |
| Baza danych i, domyślnie, muzyka | `%LOCALAPPDATA%\Melomancer\data` |

`%LOCALAPPDATA%` to `C:\Users\<Ty>\AppData\Local`. Wszystko, co zrobiłeś, leży tam, a nie w folderze programu, dlatego aktualizacja jest prosta. Żeby trzymać muzykę gdzie indziej (na większym dysku), skopiuj zawartość `data\music` do nowego folderu, ustaw w `music_dir` jego ścieżkę i uruchom ponownie.

## Logowanie

Domyślnie panel wpuszcza **ten komputer** jako administratora bez hasła (`auto_login = true`): przeglądarka otwarta przez Melomancera jest od razu zalogowana, nie ma strony logowania ani pozycji **Wyloguj**. Ustaw `auto_login = false` w `config.toml`, żeby panel pytał o hasło jak w kontenerze.

Odmowa następuje niezależnie od pliku, chyba że spełnione jest wszystko naraz: panel nasłuchuje tylko na `127.0.0.1` (`host = '0.0.0.0'` wyłącza tryb, a okno o tym informuje), żądanie przychodzi z adresu pętli zwrotnej, jego nagłówek `Host` to `127.0.0.1` lub `localhost` (strona z innego serwisu, która kieruje własną nazwę na Twój komputer, jest odrzucana) i nie ma na nim nagłówków proxy ani tunelu. Tunel Cloudflare albo reverse proxy na tym samym komputerze nie wejdzie więc bez hasła. Czego to nie zatrzyma: każdy program i każde inne konto Windows na tym komputerze może otworzyć panel jako administrator. Na komputerze, z którego korzysta kilka osób, ustaw `auto_login = false`. Szczegóły: [Bezpieczeństwo](security.md).

## Aktualizacja

Zakładka **Ustawienia**, grupa **Aktualizacje**, mówi, kiedy jest nowsze wydanie („Dostępna aktualizacja"). Wbudowanej aktualizacji jeszcze nie ma, więc:

1. Zamknij czarne okno Melomancera.
2. Pobierz nowszą paczkę i rozpakuj ją do **nowego** folderu (na przykład `C:\Melomancer-0.7.0`).
3. Uruchom `Melomancer.cmd` z nowego folderu. Windows jeszcze raz zapyta o niepodpisany plik, bo to nowe miejsce. Ustawienia i dane zostaną znalezione tam, gdzie były.
4. Gdy wszystko działa, skasuj stary folder.

Pobieranie z YouTube zależy od aktualnego yt-dlp, który często się zmienia: co poniedziałek wychodzi nowe wydanie z najnowszym, więc gdy pobieranie przestanie działać, zacznij od aktualizacji.

## Start razem z Windows (opcjonalnie)

Melomancer nie ma jeszcze własnego autostartu. Żeby startował po zalogowaniu do Windows: naciśnij Win+R, wpisz `shell:startup` i naciśnij Enter, potem włóż do otwartego folderu skrót do `Melomancer.cmd` (kliknij `Melomancer.cmd` prawym przyciskiem, **Pokaż więcej opcji**, **Utwórz skrót**, potem przenieś skrót tam). Czarne okno będzie się otwierać przy każdym zalogowaniu.

## Zatrzymanie i usunięcie

Zamknij czarne okno (albo naciśnij w nim Ctrl+C). Żeby usunąć Melomancera, skasuj folder programu. Żeby usunąć także bibliotekę i ustawienia, skasuj `%LOCALAPPDATA%\Melomancer`: **to kasuje wgraną muzykę i playlisty**, więc najpierw skopiuj, co chcesz zachować.

## Czym różni się od kontenera

- Panel domyślnie nasłuchuje na 127.0.0.1 i nie ma tunelu. **Odtwarzaj tutaj** działa jak dotąd.
- Utworu, który jest właśnie odtwarzany lub streamowany, nie da się w tej chwili skasować z dysku w Windows: znika z biblioteki, zostaje wpis w logu, a plik zostaje w folderze z muzyką.
- Kafelki obciążenia w Ustawieniach pokazują proces Melomancera i jego programy ffmpeg (nie ma kontenera do pomiaru), a „Dostępna aktualizacja" każe pobrać nowszą paczkę zamiast aktualizować obraz.
- Czarne okno może pokazywać nieszkodliwe komunikaty ze stosu webowego; komunikat Windows „połączenie zostało gwałtownie zamknięte", który pojawia się, gdy przeglądarka zrywa połączenie, jest ukryty.

## Problemy

| Co widzisz | Co zrobić |
|---|---|
| Windows pyta o wydawcę za każdym razem | Odznacz **Zawsze pytaj przed otwarciem tego pliku** w tym oknie przed kliknięciem **Uruchom**. |
| Niebieska strona „System Windows ochronił ten komputer" | **Więcej informacji**, potem **Uruchom mimo to**. |
| Nic się nie uruchamia, Windows albo antywirus pisze, że plik jest zablokowany lub w kwarantannie | Program jest niepodpisany, a niepodpisane programy bywają blokowane lub oznaczane omyłkowo. Zezwól na folder w antywirusie lub w Zabezpieczeniach Windows albo użyj kontenera. |
| Okno pokazuje błąd i czeka | `Melomancer.cmd` czeka, żebyś mógł go przeczytać. `... is not valid TOML` znaczy, że któraś linia w `config.toml` jest źle zapisana (na przykład brakuje cudzysłowu): popraw ją albo skasuj plik, żeby powstał nowy. `... is not saved as UTF-8`: w Notatniku użyj **Zapisz jako** i wybierz **UTF-8**. |
| Panel nie otwiera się w przeglądarce | Otwórz http://127.0.0.1:8080/ sam. Jeśli okno pisze, że adres jest już używany, inny program zajmuje port 8080: ustaw `port = 8081` w `config.toml` i otwórz http://127.0.0.1:8081/. |
| Kafelek bota pokazuje „Nie działa" | Okno i kafelek mówią dlaczego: `DISCORD_TOKEN is not set` (wpisz token do pliku) albo logowanie się nie udało (token jest zły lub został zresetowany: skopiuj nowy). |
| Zakładka Odtwarzacz nie pokazuje serwerów | Bot nie jest jeszcze na żadnym serwerze: użyj **Dodaj bota do serwera** w Ustawieniach (wymaga `discord_client_id`). |
| Bot jest połączony, ale nie ma dźwięku | Sprawdź jego uprawnienia na tym kanale głosowym, zob. [Tworzenie bota Discord](discord-bot.md) i [Rozwiązywanie problemów](troubleshooting.md). Okno wypisuje `Voice connection complete`, gdy połączenie działa. |
| Pobieranie z YouTube nie działa | Zaktualizuj do najnowszego wydania (zob. Aktualizacja); pamiętaj o limitach `ytdlp_daily_limit` i `ytdlp_min_gap_seconds`. |
| Coś innego | Zgłoś: https://github.com/RadzuPL/melomancer/issues. Napisz, co zrobiłeś, jaką wersję i jaki build pokazuje pierwsza linia okna, i skopiuj ostatnie linie okna. **Nigdy nie dołączaj tokena bota.** |

## Dla programistów: jak powstaje paczka

`scripts/windows/build_package.py` pobiera oficjalnego embeddable Pythona w tej samej wersji co runner, instaluje do niego `requirements.txt` jako gotowe wheels, dokłada build LGPL ffmpeg (https://github.com/BtbN/FFmpeg-Builds) i deno (środowisko JavaScript, którego yt-dlp potrzebuje dla YouTube), zapisuje pliki startowe i pakuje folder do zipa. `scripts/windows/smoke_test.py` uruchamia potem rozpakowaną paczkę z folderu z polskimi literami w nazwie, loguje się, wgrywa plik z polskimi literami w tagu, czeka na analizę głośności i kasuje utwór. Workflow `windows.yml` puszcza cały zestaw testów na `windows-latest` dla każdego pull requesta i zachowuje paczkę jako artefakt uruchomienia; `windows-release.yml` buduje paczkę dla każdego wydania i dołącza ją do niego. Więcej: [Rozwój](development.md). Czego nie próbowano: komputera z Windows 10, komputera z włączoną Inteligentną kontrolą aplikacji i głosu Discorda dłużej niż przez krótką sesję.
