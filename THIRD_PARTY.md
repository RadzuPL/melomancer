# Third-party components / Komponenty zewnętrzne

The MIT license in [LICENSE](LICENSE) covers the code in this repository only. / Licencja MIT z pliku [LICENSE](LICENSE) obejmuje tylko kod z tego repozytorium.

Melomancer uses the software below. It is not part of this repository: the libraries are installed from `requirements.txt` when the image is built, the rest comes from the base image. Each keeps its own license, and the container image contains all of it. / Melomancer korzysta z oprogramowania poniżej. Nie jest ono częścią tego repozytorium: biblioteki są instalowane z `requirements.txt` przy budowie obrazu, reszta pochodzi z obrazu bazowego. Każdy komponent zachowuje własną licencję, a obraz kontenera zawiera je wszystkie.

| Component / Komponent | Used for / Do czego | License (as published by the project) / Licencja |
|---|---|---|
| [discord.py](https://github.com/Rapptz/discord.py) | Discord bot and voice | MIT |
| [davey](https://github.com/Snazzah/davey) | Discord end-to-end encryption (DAVE) | MIT |
| [FastAPI](https://github.com/fastapi/fastapi), [Starlette](https://github.com/encode/starlette) | Web API | MIT / BSD-3-Clause |
| [uvicorn](https://github.com/encode/uvicorn) | Web server | BSD-3-Clause |
| [argon2-cffi](https://github.com/hynek/argon2-cffi) | Password hashing | MIT |
| [python-multipart](https://github.com/Kludex/python-multipart) | File uploads | Apache-2.0 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Downloading tracks / Pobieranie utworów | Unlicense (the PyPI package; its standalone binaries are not used / paczka z PyPI, samodzielnych plików binarnych nie używamy) |
| [Deno](https://github.com/denoland/deno) | JavaScript runtime that yt-dlp needs / środowisko JavaScript wymagane przez yt-dlp | MIT |
| [FFmpeg](https://ffmpeg.org/) | Decoding, loudness and silence analysis / Dekodowanie, analiza głośności i ciszy | LGPL or GPL, depending on the build; the Debian package in the image is built with GPL options and runs as a separate process, it is not linked into Melomancer / LGPL lub GPL zależnie od kompilacji; pakiet Debiana w obrazie jest zbudowany z opcjami GPL i działa jako osobny proces, nie jest linkowany do Melomancera |
| [Python](https://www.python.org/), [Debian](https://www.debian.org/) | Runtime and base image / Środowisko i obraz bazowy | PSF License, various / różne |

The list is kept by hand. Check the license of each project before relying on this table, and the `LICENSE` or `METADATA` file of an installed version for the exact text. / Lista jest prowadzona ręcznie. Przed oparciem się na tej tabeli sprawdź licencję każdego projektu, a dokładny tekst w pliku `LICENSE` lub `METADATA` zainstalowanej wersji.
