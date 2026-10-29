# Windows (eksperyment)

Języki: [English](../en/windows.md) · **Polski**

Melomancer działa też na komputerze z Windows 10 lub 11 bez Dockera: ta sama aplikacja, uruchamiana z rozpakowanego folderu. To pierwszy, eksperymentalny krok. Nie ma jeszcze instalatora, ikony w zasobniku ani samoaktualizacji, a paczka nie jest podpisana.

## Skąd ją wziąć i jak uruchomić

**Z wydania:** każde wydanie Melomancera ma paczkę jako `Melomancer-win64-<wersja>.zip` (dołączoną kilka minut po samym wydaniu, zbudowaną i sprawdzoną uruchomieniem przez workflow `windows-release.yml`; link jest w notatkach wydania), zob. https://github.com/RadzuPL/melomancer/releases. Jeśli pliku brakuje, ten build się nie udał: weź poprzednie wydanie. **Z pull requesta lub budowy testowej:** Paczkę buduje workflow **Windows package (experimental)** (`.github/workflows/windows.yml`) i jest ona artefaktem jego uruchomień, a nie wydaniem: otwórz uruchomienie w zakładce **Actions** na https://github.com/RadzuPL/melomancer/actions, pobierz `Melomancer-win64-<wersja>-build<numer>` (numer builda odróżnia dwa buildy tej samej wersji; jest też wypisany w oknie konsoli) z dołu strony (potrzebne konto GitHub). Rozpakuj go (**Wyodrębnij wszystko**) gdzie chcesz, na przykład do `C:\Melomancer` (nie do Program Files). W zipie jest od razu folder z programem; jako wydanie będzie to docelowo jeden zip.

Uruchom `Melomancer.cmd`. Otworzy się okno, a gdy serwer wstanie, przeglądarka pokaże panel pod adresem http://127.0.0.1:8080/. Zamknięcie okna zatrzymuje Melomancera.

Plik nie jest podpisany, więc po uruchomieniu `Melomancer.cmd` Windows pokaże „Nie można zweryfikować wydawcy" (Otwieranie pliku - ostrzeżenie o zabezpieczeniach, wydawca „Nieznany wydawca"): wybierz **Uruchom**. To samo okno ma pole **Zawsze pytaj przed otwarciem tego pliku**: odznacz je przed kliknięciem **Uruchom**, a Windows przestanie pytać. Zwykła strona SmartScreen („System Windows ochronił ten komputer") wymaga **Więcej informacji**, potem **Uruchom mimo to**. Na świeżym Windows 11 z włączoną funkcją Smart App Control niepodpisane programy mogą być blokowane całkowicie; to znane ograniczenie tego eksperymentu.

## Ustawienia

Pierwsze uruchomienie tworzy `%LOCALAPPDATA%\Melomancer\config.toml`, pełny zakomentowanych przykładów, i wypisuje, gdzie leży. Usuń `#` przed wybraną linią, zapisz i uruchom Melomancera ponownie. Wpisz tam token bota (`discord_token`, zob. [Bot Discord](discord-bot.md)); bez niego panel działa, a bot zostaje offline. Opcjonalnie dodaj Application ID bota jako `discord_client_id`: zakładka **Ustawienia** pokaże wtedy link **Dodaj bota do serwera**. Plik jest dwujęzyczny i zawiera każde ustawienie z objaśnieniem. Skrót `Ustawienia - Settings.cmd` w folderze paczki otwiera go w Notatniku, a ta sama lista leży w folderze paczki jako `config.example.toml`. Gdy nowsza wersja ma ustawienia, o których Twój plik jeszcze nie wspomina, Melomancer dopisuje je na końcu jako zakomentowane linie pod nagłówkiem z wersją (nigdy nie zmienia linii, które napisałeś) i mówi o tym w oknie.

Każdy klucz to nazwa zmiennej środowiskowej z [Konfiguracji](configuration.md) małymi literami, plus `host` i `port` dla launchera. Zmienna środowiskowa, która jest już ustawiona, ma pierwszeństwo przed plikiem. Ścieżki pisz w pojedynczych cudzysłowach: `music_dir = 'D:\Music\Melomancer'`.

| Co | Gdzie |
|---|---|
| Plik ustawień | `%LOCALAPPDATA%\Melomancer\config.toml` |
| Baza danych (i muzyka, o ile nie ustawiono `music_dir`) | `%LOCALAPPDATA%\Melomancer\data` |
| Pierwszy administrator | `admin_username` i `admin_password` w pliku; bez hasła jest generowane losowe i pokazane raz w oknie (potrzebne dopiero, gdy wyłączysz `auto_login` albo wejdziesz na panel z innego komputera) |
| Adres | `127.0.0.1` (tylko ten komputer, więc Windows nie pyta o zaporę); `host = '0.0.0.0'` otwiera panel dla sieci |

## Logowanie

Domyślnie panel wpuszcza **ten komputer** jako administratora bez hasła (`auto_login = true`): przeglądarka otwarta przez Melomancera jest od razu zalogowana, nie ma strony logowania ani pozycji **Wyloguj**. Ustaw `auto_login = false` w `config.toml`, żeby panel pytał o hasło jak w kontenerze.

Odmowa następuje niezależnie od pliku, chyba że spełnione jest wszystko naraz: panel nasłuchuje tylko na `127.0.0.1` (`host = '0.0.0.0'` wyłącza tryb, a okno o tym informuje), żądanie przychodzi z adresu pętli zwrotnej, jego nagłówek `Host` to `127.0.0.1` lub `localhost` (strona z innego serwisu, która kieruje własną nazwę na Twój komputer, jest odrzucana) i nie ma na nim nagłówków proxy ani tunelu. Tunel Cloudflare albo reverse proxy na tym samym komputerze nie wejdzie więc bez hasła. Czego to nie zatrzyma: każdy program i każde inne konto Windows na tym komputerze może otworzyć panel jako administrator. Na komputerze, z którego korzysta kilka osób, ustaw `auto_login = false`. Szczegóły: [Bezpieczeństwo](security.md).

## Czym różni się od kontenera

- Panel domyślnie nasłuchuje na 127.0.0.1 i nie ma tunelu. Odtwarzanie w przeglądarce („Graj tutaj") działa jak dotąd.
- Utworu, który jest właśnie odtwarzany lub streamowany, nie da się skasować z dysku w Windows: utwór znika z biblioteki i zostaje wpis w logu, a plik zostaje w folderze z muzyką.
- Kafelki obciążenia w Ustawieniach pokazują proces Melomancera i jego procesy ffmpeg (nie ma kontenera do pomiaru), a komunikat „Dostępna aktualizacja" każe pobrać nowszą paczkę zamiast aktualizować obraz. Ustawienia i dane leżą poza folderem programu, więc rozpakowanie nowszej paczki na starą je zachowuje.
- W oknie konsoli mogą pojawiać się nieszkodliwe komunikaty ze stosu webowego; komunikat Windows „połączenie zostało gwałtownie zamknięte", który pojawia się, gdy przeglądarka zrywa połączenie, jest ukryty.

## Jak powstaje paczka

`scripts/windows/build_package.py` pobiera oficjalnego embeddable Pythona w tej samej wersji co runner, instaluje do niego `requirements.txt` jako gotowe wheels, dokłada build LGPL ffmpeg (https://github.com/BtbN/FFmpeg-Builds) i deno (środowisko JavaScript, którego yt-dlp potrzebuje dla YouTube) i pakuje folder do zipa. `scripts/windows/smoke_test.py` uruchamia potem rozpakowaną paczkę z folderu z polskimi literami w nazwie, loguje się, wgrywa plik z polskimi literami w tagu, czeka na analizę głośności i kasuje utwór. Workflow wcześniej puszcza cały zestaw testów na `windows-latest`. Nic z tego nie było próbowane na prawdziwym kanale głosowym Discorda na Windowsie.
