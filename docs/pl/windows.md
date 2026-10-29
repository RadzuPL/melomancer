# Windows (eksperyment)

Języki: [English](../en/windows.md) · **Polski**

Melomancer działa też na komputerze z Windows 10 lub 11 bez Dockera: ta sama aplikacja, uruchamiana z rozpakowanego folderu. To pierwszy, eksperymentalny krok. Nie ma jeszcze instalatora, ikony w zasobniku ani samoaktualizacji, a paczka nie jest podpisana.

## Skąd ją wziąć i jak uruchomić

Paczkę buduje workflow **Windows package (experimental)** (`.github/workflows/windows.yml`) i jest ona artefaktem jego uruchomień, a nie wydaniem: otwórz uruchomienie w zakładce **Actions** na https://github.com/RadzuPL/melomancer/actions, pobierz `Melomancer-win64-<wersja>` z dołu strony (potrzebne konto GitHub) i rozpakuj gdzie chcesz, na przykład do `C:\Melomancer` (nie do Program Files).

Uruchom `Melomancer.cmd`. Otworzy się okno, a gdy serwer wstanie, przeglądarka pokaże panel pod adresem http://127.0.0.1:8080/. Zamknięcie okna zatrzymuje Melomancera.

Plik nie jest podpisany, więc Windows może pokazać „System Windows ochronił ten komputer": **Więcej informacji**, potem **Uruchom mimo to**. Na świeżym Windows 11 z włączoną funkcją Smart App Control niepodpisane programy mogą być blokowane całkowicie; to znane ograniczenie tego eksperymentu.

## Ustawienia

Pierwsze uruchomienie tworzy `%LOCALAPPDATA%\Melomancer\config.toml`, pełny zakomentowanych przykładów, i wypisuje, gdzie leży. Usuń `#` przed wybraną linią, zapisz i uruchom Melomancera ponownie. Wpisz tam token bota (`discord_token`, zob. [Bot Discord](discord-bot.md)); bez niego panel działa, a bot zostaje offline.

Każdy klucz to nazwa zmiennej środowiskowej z [Konfiguracji](configuration.md) małymi literami, plus `host` i `port` dla launchera. Zmienna środowiskowa, która jest już ustawiona, ma pierwszeństwo przed plikiem. Ścieżki pisz w pojedynczych cudzysłowach: `music_dir = 'D:\Music\Melomancer'`.

| Co | Gdzie |
|---|---|
| Plik ustawień | `%LOCALAPPDATA%\Melomancer\config.toml` |
| Baza danych (i muzyka, o ile nie ustawiono `music_dir`) | `%LOCALAPPDATA%\Melomancer\data` |
| Pierwszy administrator | `admin_username` i `admin_password` w pliku; bez hasła jest generowane losowe i pokazane raz w oknie |
| Adres | `127.0.0.1` (tylko ten komputer, więc Windows nie pyta o zaporę); `host = '0.0.0.0'` otwiera panel dla sieci |

## Czym różni się od kontenera

- Panel domyślnie nasłuchuje na 127.0.0.1 i nie ma tunelu. Odtwarzanie w przeglądarce („Graj tutaj") działa jak dotąd.
- Utworu, który jest właśnie odtwarzany lub streamowany, nie da się skasować z dysku w Windows: utwór znika z biblioteki i zostaje wpis w logu, a plik zostaje w folderze z muzyką.
- Kafelki obciążenia w Ustawieniach pokazują proces Melomancera i jego procesy ffmpeg (nie ma kontenera do pomiaru).

## Jak powstaje paczka

`scripts/windows/build_package.py` pobiera oficjalnego embeddable Pythona w tej samej wersji co runner, instaluje do niego `requirements.txt` jako gotowe wheels, dokłada build LGPL ffmpeg (https://github.com/BtbN/FFmpeg-Builds) i deno (środowisko JavaScript, którego yt-dlp potrzebuje dla YouTube) i pakuje folder do zipa. `scripts/windows/smoke_test.py` uruchamia potem rozpakowaną paczkę z folderu z polskimi literami w nazwie, loguje się, wgrywa plik z polskimi literami w tagu, czeka na analizę głośności i kasuje utwór. Workflow wcześniej puszcza cały zestaw testów na `windows-latest`. Nic z tego nie było próbowane na prawdziwym kanale głosowym Discorda na Windowsie.
