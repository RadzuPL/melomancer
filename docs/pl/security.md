# Bezpieczeństwo

Języki: [English](../en/security.md) · **Polski**

Panel steruje botem, który mówi na twoich serwerach Discord i pobiera pliki z internetu, więc traktuj go jak narzędzie administratora.

## Co robi aplikacja

- **Logowanie.** Hasła są haszowane Argon2 i muszą mieć co najmniej 10 znaków. Sesje to losowe tokeny, w bazie przechowywane jako hasze, wysyłane w ciasteczku `HttpOnly`, `SameSite=Lax` (z flagą `Secure`, gdy panel otwarto przez https). Wyłączenie użytkownika albo zmiana hasła kończy jego sesje.
- **Zgadywanie haseł.** Po 5 nieudanych logowaniach (na nazwę użytkownika lub adres, w ciągu 5 minut) kolejne próby są na jakiś czas odrzucane. Nieznana nazwa użytkownika dostaje odpowiedź równie wolno jak znana.
- **Podrabiane żądania (CSRF).** Każde żądanie zmieniające stan musi mieć własny nagłówek, który wysyła tylko skrypt panelu.
- **Prywatność między mistrzami gry.** Zestawy, foldery i playlisty należą do właściciela. Inni użytkownicy dostają „nie znaleziono”, a nie „brak uprawnień”, więc nawet ich istnienie nie wychodzi na jaw. Przy usuwaniu utworu widać liczbę playlist, które go używają, nigdy ich nazwy ani właścicieli. Tagi osobiste widzi tylko ich autor. Wspólna biblioteka, z oryginalnymi tytułami i tagami wspólnymi, jest widoczna dla każdego zalogowanego, więc dobieraj tytuły i tagi wspólne z tą myślą.
- **Dostęp do serwerów.** Użytkownik widzi i obsługuje tylko te serwery Discord, które zaznaczył mu administrator.
- **Bezpieczeństwo treści.** Zawartość plików i tytuły są zawsze wstawiane jako tekst, nigdy jako HTML, a polityka bezpieczeństwa treści blokuje skrypty inline. Wgrywane pliki są sprawdzane `ffprobe` i muszą zawierać strumień audio, nazwy plików na dysku są generowane.
- **Pobieranie.** Przyjmowane są tylko adresy `https://` z listy dozwolonych hostów, użytkownik nie może przekazać opcji do yt-dlp, playlisty nie są rozwijane.
- **Kontener.** Kontener startuje jako root tylko po to, by poprawić właściciela plików, a potem działa jako `PUID:PGID`. Bot nie potrzebuje portu przychodzącego.

## Postaw panel za Cloudflare Access

Nie otwieraj portu 8080 na routerze. Dwie dobre opcje:

1. **Cloudflare Tunnel + Access** (zalecane, jeśli masz domenę w Cloudflare). Dokumentacja: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/ dla tunelu i https://developers.cloudflare.com/cloudflare-one/policies/access/ dla polityk Access.
2. **VPN** do twojej sieci, a potem panel pod adresem lokalnym.

Z tunelem:

1. Utwórz publiczną nazwę hosta, np. `muzyka.example.com`, z usługą `http://melomancer:8080` (ta sama sieć Dockera) albo `http://<adres serwera>:8080`.
2. Utwórz **aplikację Access** dla tej nazwy hosta z polityką dopuszczającą tylko adresy e-mail twoich mistrzów gry.
3. Efekt: dwie warstwy. Cloudflare Access najpierw identyfikuje osobę (np. jednorazowym kodem przesłanym e-mailem), a dopiero potem panel pyta o własną nazwę użytkownika i hasło. To praktyczny drugi składnik przed panelem.

Uwagi:

- **Rozmiar wgrywanych plików.** Cloudflare ogranicza pojedyncze żądanie do 100 MB w planach Free i Pro (200 MB Business, 500 MB Enterprise). Panel wysyła każdy plik jako osobne żądanie, więc zawodzi tylko pojedynczy plik powyżej limitu, z komunikatem „Plik jest za duży dla serwera lub tunelu”. Źródło: https://developers.cloudflare.com/workers/platform/limits/ . Taki plik wgraj z wnętrza swojej sieci (`http://<adres serwera>:8080`) albo podziel.
- Jeśli na swoich nazwach hostów stosujesz już reguły regionów, botów lub podejrzanego ruchu, panel z nimi działa. Bot Discord łączy się na zewnątrz i nie jest nimi dotknięty.
- Zostaw `COOKIE_SECURE=auto` (domyślnie), wtedy ciasteczko samo staje się `Secure` przez https.

## Logowanie bez hasła (paczka dla Windows)

[Paczka dla Windows](windows.md) domyślnie loguje administratora bez hasła, dla żądań z tego samego komputera. Serwer decyduje na podstawie trzech rzeczy naraz (`app/localaccess.py`): uczestnik połączenia TCP to adres pętli zwrotnej, nagłówek `Host` to `127.0.0.1`, `localhost` lub `::1`, a żądanie nie ma nagłówków `Forwarded`, `X-Forwarded-*`, `X-Real-IP` ani nagłówków Cloudflare. Tunel Cloudflare albo reverse proxy na tym samym komputerze też łączy się z 127.0.0.1, ale dokłada te nagłówki i niesie publiczną nazwę w `Host`, więc dostaje odmowę. Strona z innego serwisu też z tego nie skorzysta. Jej żądanie wysłane prosto na http://127.0.0.1:8080/ przychodzi z adresu pętli zwrotnej z `Host` z pętli zwrotnej, ale endpoint logowania (`POST /api/auth/local`) wymaga własnego nagłówka `X-Melomancer`, a przeglądarka wysyła taki nagłówek między serwisami dopiero po sprawdzeniu zgody, której serwer nigdy nie daje. Strona, która najpierw skieruje własną nazwę na 127.0.0.1 (DNS rebinding), przechodzi to sprawdzenie, ale wtedy w nagłówku `Host` jest jej własna nazwa, która jest odrzucana. Launcher wyłącza też tryb, gdy każesz panelowi nasłuchiwać na czymkolwiek poza adresem pętli zwrotnej.

Czego to nie zatrzyma: każdy program uruchomiony na tym komputerze i każde inne konto Windows na nim może wywołać endpoint i dostać sesję administratora. To to samo zaufanie co do folderu z danymi, który i tak mogą odczytać, ale na komputerze współdzielonym ustaw `auto_login = false`. W kontenerze zostaw `AUTO_LOGIN` nieustawione: żądania przychodzą z sieci kontenera, nie z adresu pętli zwrotnej, więc i tak dostałyby odmowę.

## Sekrety

- `DISCORD_TOKEN` to hasło bota. Trzymaj go w ustawieniach kontenera albo w pliku `.env`, którego nie wrzucasz do repozytorium. Jeśli wycieknie, użyj **Reset Token** w Developer Portal i zaktualizuj kontener.
- Nie używaj hasła administratora nigdzie indziej. Zmień je po pierwszym logowaniu.
- Rób kopię folderu danych, zawiera bazę z hasłami w postaci haszy.

## Pobieranie z YouTube: uczciwe uwagi

- Regulamin YouTube zabrania pobierania treści, jeśli serwis nie oferuje do nich linku do pobrania, oraz zabrania obchodzenia mechanizmów ograniczających kopiowanie. Używanie yt-dlp jest więc niezgodne z regulaminem, także do użytku prywatnego. W praktyce skutki dla prywatnego, niekomercyjnego serwera dotykają twojego **adresu IP i kont** (ograniczanie tempa, blokady „potwierdź, że nie jesteś botem”, w najgorszym razie ograniczenie konta), a nie ciebie przed sądem, ale to opis, nie porada prawna.
- Subskrypcja **YouTube Premium** niczego tu nie zmienia: jej tryb offline działa tylko w oficjalnych aplikacjach YouTube.
- **Nigdy** nie dawaj yt-dlp ciasteczek swojego głównego konta Google (`YTDLP_COOKIES_FILE`). Jeśli musisz użyć ciasteczek, użyj jednorazowego konta.
- Twój serwer ma pewnie stały adres IP. Melomancer jest zbudowany łagodnie: jedno pobieranie naraz, przerwa między pobraniami (`YTDLP_MIN_GAP_SECONDS`), dzienny limit (`YTDLP_DAILY_LIMIT`), tylko pojedyncze filmy, a pobiera raz zamiast streamować, więc odtwarzanie w trakcie sesji nigdy nie dotyka YouTube. Jeśli YouTube zacznie odmawiać, pobrania kończą się błędem, a reszta działa dalej. Obniż limity albo przestań pobierać na kilka dni.
- Bezpieczniejsze źródła: własne pliki, muzyka kupiona (Bandcamp, itch.io) i muzyka na wolnych licencjach. Tabletop Audio (https://tabletopaudio.com/about.html) oferuje 10-minutowe ambienty na licencji Creative Commons Uznanie autorstwa-Użycie niekomercyjne-Bez utworów zależnych, sprawdź jej warunki przed użyciem.
- Odtwarzanie muzyki na serwerze Discord podlega też regulaminowi Discorda (https://discord.com/terms). Używaj bota w prywatnych grupach.
