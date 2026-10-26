# Obsługa panelu

Języki: [English](../en/usage.md) · **Polski**

Panel ma pięć zakładek: **Odtwarzacz**, **Biblioteka**, **Playlisty**, **Pobieranie** i, dla administratorów, **Administracja**. Język (polski lub angielski) przełączasz w górnym pasku, zapamiętuje się dla każdego użytkownika.

## Idea w minutę

- **Biblioteka** to jedna wspólna pula muzyki. Każdy zalogowany widzi każdy utwór z oryginalnym tytułem.
- **Playlisty** są prywatne. Mieszkają w drzewie: **zestaw** (system gry albo scenariusz, np. „Zew Cthulhu: Druga”) zawiera **playlisty** (listy utworów z biblioteki). Gdy w zestawie robi się tłoczno, możesz w nim dodać **foldery** (np. lokację albo rodzaj sceny) i wkładać do nich playlisty; folder to jeden poziom, bez zagnieżdżania, i w pełni opcjonalny.
- Nazwy i układ twoich zestawów, folderów i playlist widzisz tylko ty (oraz administratorzy). Inny mistrz gry nie zobaczy, że twoja playlista nazywa się „Port w Innsmouth”.
- W zakładce **Odtwarzacz** wybierasz serwer i kanał głosowy i naciskasz playlistę.

## Role

| | Użytkownik | Administrator |
|---|---|---|
| Widzi całą bibliotekę, odsłuchuje utwory | tak | tak |
| Wgrywa i pobiera muzykę | tak | tak |
| Edytuje lub usuwa utwór | własne utwory | wszystkie utwory |
| Widzi i edytuje zestawy, foldery, playlisty | tylko własne | wszystkie (przełącznik „pokaż zestawy wszystkich”) |
| Steruje botem | tylko na serwerach nadanych przez administratora | wszystkie serwery |
| Zarządza użytkownikami i dostępem do serwerów | nie | tak |

## Biblioteka

**Dodawanie muzyki.** Naciśnij **Wybierz pliki** albo **Wybierz folder**, albo przeciągnij pliki audio na przerywane pole. Wiele plików naraz to nie problem, wysyłane są jeden po drugim (po dwa równocześnie) z linijką stanu dla każdego. Obsługiwane typy: mp3, ogg, opus, flac, wav, m4a, aac, webm. Wgrywanie folderu może zamienić nazwy folderów na **tagi wspólne** (pole wyboru obok przycisków).

Plik, który już jest w bibliotece (ta sama zawartość), nie zostanie dodany drugi raz: zobaczysz „już w bibliotece”. Jeśli utwór został wcześniej usunięty i wisi wyszarzony w czyjejś playliście, wgranie tego samego pliku przywraca go i wpis na playliście znów się „zapala”.

**Szukanie muzyki.** Wpisz tekst w polu wyszukiwania (tytuł lub tag), wybierz tag albo zaznacz „tylko moje”. Kliknięcie tagu w tabeli filtruje po nim.

**Tagi.** Każdy utwór ma dwa rodzaje tagów:

- **Tagi wspólne** (szare) widzą wszyscy, edytuje je właściciel utworu lub administrator. Używaj neutralnych: ambient, walka, karczma, deszcz.
- **Moje tagi** (fioletowy obrys) widzisz tylko ty, na dowolnym utworze w bibliotece. Używaj ich do wszystkiego, co byłoby spoilerem, np. nazwy lokacji.

**Edycja.** Przycisk ołówka otwiera okno edycji: tytuł i tagi wspólne (właściciel lub administrator), własne tagi (każdy). Oryginalny tytuł jest zachowany i pokazany w oknie.

**Usuwanie.** Utwór może usunąć tylko właściciel lub administrator. Jeśli utwór jest użyty w playlistach, dowiadujesz się **ile ich jest** (nie które, żeby nic o cudzych scenariuszach nie wyciekło). Po usunięciu plik audio znika, ale tytuł zostaje w tych playlistach jako wyszarzony, przekreślony wpis, żeby autor playlisty to zauważył i mógł go zastąpić.

**Akcje zbiorcze.** Zaznacz utwory (pole w nagłówku zaznacza wszystkie widoczne). Na dole pojawia się pasek: **Dodaj do playlisty** dopisuje zaznaczone na koniec jednej z twoich playlist, **Dodaj mój tag** nadaje im osobisty tag.

**Podgląd.** Przycisk odtwarzania puszcza utwór w twojej przeglądarce (nie na Discordzie).

## Playlisty

Po lewej twoje drzewo. Użyj **+ Zestaw**, potem przycisku **♪+** przy zestawie (nowa playlista wprost w zestawie) albo **📁+** (nowy folder). Folder ma własny **♪+** na playlisty w środku. Ołówek zmienia nazwę, krzyżyk usuwa, strzałki zmieniają kolejność. Usunięcie zestawu, grupy lub playlisty nigdy nie usuwa muzyki z biblioteki.

Po prawej wybrana playlista.

- **Pętla**: odtwarzaj listę w kółko. **Losowo**: losowa kolejność (przy każdej rundzie na nowo).
- **Płynne wejście/wyjście**: każdy utwór wchodzi i wychodzi przez tyle sekund (0 wyłącza). Przydatne przy muzyce tła.
- **Własna głośność**: po zaznaczeniu naciśnięcie tej playlisty ustawia głośność bota na tę wartość. Bez zaznaczenia zostaje obecna głośność.
- **Przenieś playlistę** umieszcza ją wprost w zestawie albo w dowolnym folderze (w dowolnym z twoich zestawów).
- **Dodaj utwory** otwiera wybieralkę z wyszukiwaniem i filtrem tagów, zaznacz dowolną liczbę utworów.
- Strzałki przesuwają utwór, krzyżyk usuwa go z playlisty (nie z biblioteki).
- Wyszarzony, przekreślony wpis to utwór usunięty z biblioteki. **Zastąp** pozwala wybrać inny utwór na to samo miejsce.

## Odtwarzacz

1. Wybierz **serwer** i **kanał głosowy**. Bot musi być na tym serwerze (zobacz [Tworzenie bota Discord](discord-bot.md)).
2. Wybierz **zestaw**. Jego playlisty pojawią się jako przyciski, foldery jako nagłówki z playlistami pod spodem.
3. Naciśnij playlistę. Jeśli bota nie ma jeszcze na kanale, najpierw do niego dołączy, potem zacznie grać. Aktywna playlista jest podświetlona.

Sterowanie: poprzedni, pauza/wznów, następny, stop, pętla, losowo oraz suwak **głośności** (0 do 150 %). Zmiany głośności działają od razu. Gracze mogą też osobno ściszyć bota w Discordzie.

**Połącz / Rozłącz / Przenieś tutaj** zarządzają obecnością bota na kanale. Odpalenie playlisty na innym kanale wymaga najpierw kliknięcia **Przenieś tutaj**.

**Jeden sterujący na serwer.** Dopóki czyjaś playlista gra na serwerze, inny użytkownik (nie administrator) dostaje komunikat „Ten serwer obsługuje teraz ktoś inny”, aż tamta sesja zostanie zatrzymana. Administrator może zawsze przejąć sterowanie.

Jeśli połączenie samo się zerwie, bot czeka około 35 sekund, zanim będzie mógł dołączyć ponownie. To celowe, szybsze ponowne wejście zwykle kończy się tym, że Discord zabija także nową sesję. W komunikacie zobaczysz, ile sekund zostało.

Bot opuszcza kanał po 30 minutach bez żadnego człowieka w środku (`IDLE_LEAVE_MINUTES`).

## Pobieranie

Wklej adres **jednego** filmu lub utworu z dozwolonego serwisu (domyślnie YouTube, SoundCloud, Bandcamp) i naciśnij **Pobierz**. Serwer pobiera dźwięk jeden raz, konwertuje go i dodaje do wspólnej biblioteki z wpisanymi tagami. Potem gra z dysku, więc w trakcie sesji nic nie zależy od YouTube.

Lista pokazuje, co robi każde pobieranie: przygotowanie (łączenie z serwisem, potrafi trwać kilka sekund), pobieranie z paskiem postępu, szybkością i czasem do końca, konwersję oraz dodawanie do biblioteki. Zlecenie czekające w kolejce pokazuje, ile sekund zostało z przerwy między pobraniami. Po zakończeniu lub błędzie pobierania pojawia się komunikat.

Zasady chroniące twój adres IP: jedno pobieranie naraz, przerwa między nimi, dzienny limit (zobacz [Konfiguracja](configuration.md)), playlisty nie są rozwijane. Nieudane zlecenie pokazuje powód, np. YouTube prosi o „potwierdzenie, że nie jesteś botem”. Pobranie świeżego obrazu przynosi nowszy `yt-dlp`, zobacz [Rozwiązywanie problemów](troubleshooting.md). Najpierw przeczytaj uwagi o regulaminach w [Bezpieczeństwie](security.md). Wgrywanie własnych plików albo muzyka na wolnych licencjach to zawsze bezpieczna droga.

## Administracja

- **Użytkownicy**: zakładanie kont (nazwa, hasło co najmniej 10 znaków, rola), zmiana ról, reset hasła, wyłączanie i włączanie konta. Wyłączone konto jest natychmiast wylogowywane. Ostatniego aktywnego administratora nie można zdegradować ani wyłączyć.
- **Serwery**: dla każdego użytkownika niebędącego administratorem zaznacz serwery Discord, którymi może sterować. Użytkownik bez zaznaczonego serwera widzi pustą zakładkę Odtwarzacz.
- **System**: wersja i stan bota.

Twoja nazwa w górnym pasku otwiera okno konta: zmiana hasła. Zmiana hasła wylogowuje cię wszędzie indziej.
