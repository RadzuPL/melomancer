# Windows: szczegóły dla zaawansowanych

Języki: [English](../en/windows-advanced.md) · **Polski**

Instrukcja krok po kroku to [Melomancer na Windows](windows.md). Ta strona zawiera to, czego tam brakuje: wszystkie ustawienia, jak działa logowanie, gdzie co leży, czym różni się od kontenera, techniczną stronę problemów i budowę paczki.

## Plik ustawień

`%LOCALAPPDATA%\Melomancer\config.toml` zawiera każde ustawienie z objaśnieniem po polsku i angielsku (program tworzy go sam przy pierwszym starcie). Skrót `Ustawienia - Settings.cmd` otwiera plik w Notatniku. Usuń `#` przed linią, żeby jej użyć, zapisz plik, zamknij i uruchom Melomancera ponownie. Ścieżki wpisuj w pojedynczych cudzysłowach: `music_dir = 'D:\Music\Melomancer'`. Plik musi być zapisany jako UTF-8 (to domyślne w Notatniku w Windows 11). Token bota i Application ID można też wkleić w panelu (**Ustawienia**, karta **Bot Discord**): panel zmienia w tym pliku tylko te dwie linie (zamienia linię aktywną albo zakomentowany przykład z szablonu, a gdy brak jednej i drugiej, dopisuje nową na końcu), zachowuje komentarze, końce linii i BOM, przed zapisem wczytuje wynik jeszcze raz jako TOML, a plik podmienia atomowo. Zmiana działa od razu, bez restartu: stary klient Discorda zostaje zamknięty (bot wychodzi z kanałów głosowych), a nowy loguje się z nowym tokenem. Token jest tylko do zapisu, żaden endpoint go nie zwraca. Jeśli `DISCORD_TOKEN` jest ustawiony w zmiennych środowiskowych Windows, to on wygrywa z plikiem przy następnym starcie. Gdy nowsza wersja ma ustawienia, o których Twój plik jeszcze nie wspomina, Melomancer dopisuje je na końcu jako zakomentowane linie pod nagłówkiem z wersją i mówi o tym w oknie; nigdy nie zmienia linii, które napisałeś.

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
| Logi (obracane, 1 MB, 3 kopie) | `%LOCALAPPDATA%\Melomancer\logs\melomancer.log` |

`%LOCALAPPDATA%` to `C:\Users\<Ty>\AppData\Local`. Żeby trzymać muzykę gdzie indziej (na większym dysku), skopiuj zawartość `data\music` do nowego folderu, ustaw w `music_dir` jego ścieżkę i uruchom ponownie.

## Logowanie

Domyślnie panel wpuszcza **ten komputer** jako administratora bez hasła (`auto_login = true`): przeglądarka otwarta przez Melomancera jest od razu zalogowana, nie ma strony logowania ani pozycji **Wyloguj**. Ustaw `auto_login = false` w `config.toml`, żeby panel pytał o hasło jak w kontenerze.

Odmowa następuje niezależnie od pliku, chyba że spełnione jest wszystko naraz: panel nasłuchuje tylko na `127.0.0.1` (`host = '0.0.0.0'` wyłącza tryb, a okno o tym informuje), żądanie przychodzi z adresu pętli zwrotnej, jego nagłówek `Host` to `127.0.0.1` lub `localhost` (strona z innego serwisu, która kieruje własną nazwę na Twój komputer, jest odrzucana) i nie ma na nim nagłówków proxy ani tunelu. Tunel Cloudflare albo reverse proxy na tym samym komputerze nie wejdzie więc bez hasła. Czego to nie zatrzyma: każdy program i każde inne konto Windows na tym komputerze może otworzyć panel jako administrator. Na komputerze, z którego korzysta kilka osób, ustaw `auto_login = false`. Szczegóły: [Bezpieczeństwo](security.md).

## Tryb w tle i uruchamianie razem z Windows

`Melomancer.cmd` uruchamia `runtime\pythonw.exe -m app.winmain` (bez okna konsoli) i od razu się zamyka. Program działa w tle jako ikona przy zegarze (`pystray`); serwer webowy pracuje w wątku obok niej. Naraz działa jedna kopia (nazwany mutex sesji użytkownika): drugi start tylko otwiera panel pierwszej.

Pozycja **Uruchamiaj z Windows** w menu ikony zapisuje wartość `Melomancer` w kluczu `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run` (własny klucz użytkownika, bez uprawnień administratora). Polecenie to `"<folder>\runtime\pythonw.exe" -m app.winmain --no-browser`, więc przy logowaniu nie otwiera się przeglądarka. Jeśli folder przeniesiesz albo rozpakujesz nowszą paczkę gdzie indziej, a pozycja jest zaznaczona, Melomancer przy następnym starcie poprawia wpis tak, żeby wskazywał na ten folder.

Pozycja **Dostępna aktualizacja** w menu ikony pyta ten sam sprawdzacz wydań co panel (`lifecycle.pending_update`), więc nie robi własnych zapytań do GitHuba; dymek pokazuje się raz na wersję i uruchomienie.

Opcje linii poleceń (`runtime\python.exe -m app.winmain ...`): `--console` zostaje w oknie konsoli zamiast w ikonie (to robi `Diagnostyka - Diagnostics.cmd`), `--tray` pokazuje ikonę także przy starcie z konsoli, `--no-browser`, `--port`, `--host`, `--config <plik>`, `--edit-config`.

## Czym różni się od kontenera

- Panel domyślnie nasłuchuje na 127.0.0.1 i nie ma tunelu. **Odtwarzaj tutaj** działa jak dotąd.
- Utworu, który jest właśnie odtwarzany lub streamowany, nie da się w tej chwili skasować z dysku w Windows: znika z biblioteki, zostaje wpis w logu, a plik zostaje w folderze z muzyką.
- Kafelki obciążenia w Ustawieniach pokazują proces Melomancera i jego programy ffmpeg (nie ma kontenera do pomiaru), a przy „Dostępna aktualizacja" jest przycisk **Pobierz i zainstaluj**, który aktualizuje paczkę zamiast obrazu kontenera (jak to działa: [Aktualizacja paczki dla Windows](architecture.md#aktualizacja-paczki-dla-windows)).
- Komunikaty ze stosu webowego trafiają do pliku z logami (i do okna w trybie diagnostycznym); komunikat Windows „połączenie zostało gwałtownie zamknięte", który pojawia się, gdy przeglądarka zrywa połączenie, jest ukryty.

## Problemy

| Co widzisz | Co to znaczy |
|---|---|
| `... is not valid TOML` | Któraś linia w `config.toml` jest źle zapisana (na przykład brakuje cudzysłowu). Popraw ją albo skasuj plik, żeby powstał nowy. |
| `... is not saved as UTF-8` | W Notatniku użyj **Zapisz jako** i wybierz kodowanie **UTF-8**. |
| Okno mówi o zajętym adresie | Inny program używa portu 8080. Ustaw `port = 8081` w `config.toml` i otwórz http://127.0.0.1:8081/. |
| Aktualizacja z panelu kończy się komunikatem | Kod z panelu mówi, co jest nie tak (brak miejsca, brak uprawnień do zapisu obok folderu, suma kontrolna, paczka jeszcze się buduje). Szczegóły są w `update.log` w folderze z logami; po nieudanej podmianie poprzednia wersja wraca sama, a kopie bazy leżą w `data\backups`. Zawsze można zaktualizować ręcznie (rozpakować paczkę do nowego folderu). |
| `DISCORD_TOKEN is not set` (w logu) | W `config.toml` brakuje tokena. |
| Okienko „Melomancer nie mógł wystartować" | Zwykle zajęty adres albo błąd w `config.toml`; szczegóły w logu. Zob. też wiersze `... is not valid TOML` i zajętego adresu wyżej: bez konsoli komunikaty pokazuje okienko, a pełny tekst jest w `melomancer.log`. |
| Brak ikony przy zegarze | Windows mógł ją schować pod strzałką **^**. Jeśli jej nie ma w ogóle, uruchom `Diagnostyka - Diagnostics.cmd` (tryb konsolowy, bez ikony) i sprawdź komunikaty; `melomancer.log` zawiera wtedy wpis o ikonie. |
| Bot się loguje, ale milczy | Zob. [Tworzenie bota Discord](discord-bot.md) i [Rozwiązywanie problemów](troubleshooting.md). Okno wypisuje `Voice connection complete`, gdy połączenie działa. |
| Pobieranie nie działa | Zaktualizuj do najnowszego wydania (co poniedziałek wychodzi nowe z najnowszym yt-dlp); pamiętaj o `ytdlp_daily_limit` i `ytdlp_min_gap_seconds`. |
| Antywirus wrzuca pliki do kwarantanny | Paczka jest niepodpisana, a niektóre antywirusy oznaczają takie programy. Zezwól na folder albo użyj kontenera. |
| Windows 11 blokuje program całkowicie | Inteligentna kontrola aplikacji (Smart App Control) blokuje niepodpisane programy bez opcji „uruchom mimo to". Można ją wyłączyć w Zabezpieczeniach Windows, ale to decyzja dotycząca całego komputera. |

## Jak powstaje paczka

`scripts/windows/build_package.py` pobiera oficjalnego embeddable Pythona w tej samej wersji co runner, instaluje do niego `requirements.txt` jako gotowe wheels, dokłada build LGPL ffmpeg (https://github.com/BtbN/FFmpeg-Builds) i deno (środowisko JavaScript, którego yt-dlp potrzebuje dla YouTube), zapisuje pliki startowe i pakuje folder do zipa. `scripts/windows/smoke_test.py` uruchamia potem rozpakowaną paczkę z folderu z polskimi literami w nazwie, loguje się, wgrywa plik z polskimi literami w tagu, czeka na analizę głośności i kasuje utwór. Workflow `windows.yml` puszcza cały zestaw testów na `windows-latest` dla każdego pull requesta i zachowuje paczkę jako artefakt uruchomienia; `windows-release.yml` buduje paczkę dla każdego wydania i dołącza ją do niego. Więcej: [Rozwój](development.md). Czego nie próbowano: komputera z Windows 10, komputera z włączoną Inteligentną kontrolą aplikacji i głosu Discorda dłużej niż przez krótką sesję.
