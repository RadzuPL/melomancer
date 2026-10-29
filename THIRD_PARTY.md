# Third-party components

[Przejdź do wersji polskiej ↓](#komponenty-zewnętrzne)

## English

The MIT license in [LICENSE](LICENSE) covers the code in this repository only.

Melomancer uses the software below. It is not part of this repository: the libraries are installed from `requirements.txt` when the image is built, the rest comes from the base image. Each keeps its own license, and the container image contains all of it.

| Component | Used for | License (as published by the project) |
|---|---|---|
| [discord.py](https://github.com/Rapptz/discord.py) | Discord bot and voice | MIT |
| [davey](https://github.com/Snazzah/davey) | Discord end-to-end encryption (DAVE) | MIT |
| [FastAPI](https://github.com/fastapi/fastapi), [Starlette](https://github.com/encode/starlette) | Web API | MIT / BSD-3-Clause |
| [uvicorn](https://github.com/encode/uvicorn) | Web server | BSD-3-Clause |
| [argon2-cffi](https://github.com/hynek/argon2-cffi) | Password hashing | MIT |
| [python-multipart](https://github.com/Kludex/python-multipart) | File uploads | Apache-2.0 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Downloading tracks | Unlicense (the PyPI package; its standalone binaries are not used) |
| [Deno](https://github.com/denoland/deno) | JavaScript runtime that yt-dlp needs | MIT |
| [FFmpeg](https://ffmpeg.org/) | Decoding, loudness and silence analysis | LGPL or GPL, depending on the build; the Debian package in the image is built with GPL options and runs as a separate process, it is not linked into Melomancer |
| [Python](https://www.python.org/), [Debian](https://www.debian.org/) | Runtime and base image | PSF License, various |

The Windows package ([docs/en/windows.md](docs/en/windows.md)) carries, besides the libraries above and [psutil](https://github.com/giampaolo/psutil) (BSD-3-Clause), the embeddable Python from python.org (PSF License), the LGPL build of FFmpeg from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) (LGPL; shared libraries next to a separate process, its license text is in the package's `licenses` folder, the source is available from the project) and the Deno binary (MIT).

The list is kept by hand. Check the license of each project before relying on this table, and the `LICENSE` or `METADATA` file of an installed version for the exact text.

## Komponenty zewnętrzne

[Go to the English version ↑](#english)

Licencja MIT z pliku [LICENSE](LICENSE) obejmuje tylko kod z tego repozytorium.

Melomancer korzysta z oprogramowania poniżej. Nie jest ono częścią tego repozytorium: biblioteki są instalowane z `requirements.txt` przy budowie obrazu, reszta pochodzi z obrazu bazowego. Każdy komponent zachowuje własną licencję, a obraz kontenera zawiera je wszystkie.

| Komponent | Do czego | Licencja (wg autorów projektu) |
|---|---|---|
| [discord.py](https://github.com/Rapptz/discord.py) | Bot Discord i głos | MIT |
| [davey](https://github.com/Snazzah/davey) | Szyfrowanie end-to-end Discorda (DAVE) | MIT |
| [FastAPI](https://github.com/fastapi/fastapi), [Starlette](https://github.com/encode/starlette) | API webowe | MIT / BSD-3-Clause |
| [uvicorn](https://github.com/encode/uvicorn) | Serwer webowy | BSD-3-Clause |
| [argon2-cffi](https://github.com/hynek/argon2-cffi) | Haszowanie haseł | MIT |
| [python-multipart](https://github.com/Kludex/python-multipart) | Wgrywanie plików | Apache-2.0 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Pobieranie utworów | Unlicense (paczka z PyPI, samodzielnych plików binarnych nie używamy) |
| [Deno](https://github.com/denoland/deno) | Środowisko JavaScript wymagane przez yt-dlp | MIT |
| [FFmpeg](https://ffmpeg.org/) | Dekodowanie, analiza głośności i ciszy | LGPL lub GPL zależnie od kompilacji; pakiet Debiana w obrazie jest zbudowany z opcjami GPL i działa jako osobny proces, nie jest linkowany do Melomancera |
| [Python](https://www.python.org/), [Debian](https://www.debian.org/) | Środowisko i obraz bazowy | PSF License, różne |

Paczka dla Windows ([docs/pl/windows.md](docs/pl/windows.md)) zawiera, oprócz bibliotek powyżej i [psutil](https://github.com/giampaolo/psutil) (BSD-3-Clause), embeddable Pythona z python.org (PSF License), build LGPL FFmpeg z [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) (LGPL; biblioteki współdzielone obok osobnego procesu, tekst licencji jest w folderze `licenses` paczki, źródła są dostępne u projektu) oraz plik wykonywalny Deno (MIT).

Lista jest prowadzona ręcznie. Przed oparciem się na tej tabeli sprawdź licencję każdego projektu, a dokładny tekst w pliku `LICENSE` lub `METADATA` zainstalowanej wersji.
