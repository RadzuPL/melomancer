# Obsługa panelu

Języki: [English](../en/usage.md) · **Polski**

Panel ma cztery zakładki dla wszystkich, **Odtwarzacz**, **Biblioteka**, **Playlisty** i **Pobieranie**, oraz dwie dla administratorów: **Użytkownicy** i **Ustawienia**. Po prawej w górnym pasku są trzy małe kontrolki: ikona **motywu** (każde kliknięcie przełącza na następny: automatyczny, jasny, ciemny; automatyczny podąża za systemem, jasny jest celowo stonowany, a nie biały, wybór zapamiętuje przeglądarka), znacznik **PL / EN** (kliknięcie przełącza język, zapamiętywany dla każdego użytkownika) oraz **nazwa użytkownika**, która otwiera menu ze **Zmień hasło** i **Wyloguj**.

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

**Tagi przy dodawaniu.** Pole wgrywania i formularz pobierania mają po dwa pola tagów: **tagi wspólne** i **moje tagi** (tylko dla ciebie). Pod każdym polem proponowane są tagi, które już istnieją, najczęściej używane na początku: kliknij, żeby dodać, albo zacznij pisać, żeby zawęzić podpowiedzi; Enter dodaje wpisany tekst jako nowy tag. Pobranie na konkretną sesję możesz od razu otagować, np. moim tagiem `sesja 3`. Wybrane tagi zostają między pobraniami i dotyczą każdego dodawanego pliku, dopóki ich nie usuniesz. Jeśli plik już jest w bibliotece, nie jest dodawany drugi raz, ale dostaje twoje tagi osobiste (a wspólne tylko wtedy, gdy jesteś jego właścicielem).

**Szukanie muzyki.** Wpisz tekst w polu wyszukiwania (tytuł lub tag), wybierz tag albo zaznacz „tylko moje”. Kliknięcie tagu w tabeli filtruje po nim.

**Tagi.** Każdy utwór ma dwa rodzaje tagów:

- **Tagi wspólne** (szare) widzą wszyscy, edytuje je właściciel utworu lub administrator. Używaj neutralnych: ambient, walka, karczma, deszcz.
- **Moje tagi** (fioletowy obrys) widzisz tylko ty, na dowolnym utworze w bibliotece. Używaj ich do wszystkiego, co byłoby spoilerem, np. nazwy lokacji.

**Edycja.** Przycisk ołówka otwiera okno edycji: tytuł i tagi wspólne (właściciel lub administrator), własne tagi (każdy). Oryginalny tytuł jest zachowany i pokazany w oknie.

**Początek i koniec utworu.** W oknie edycji są też pola **Początek** i **Koniec** dla utworów, których wstęp albo zakończenie nie pasują (właściciel lub administrator; dotyczy utworu dla wszystkich). Wpisz czas w pliku, np. `0:12` albo `12,5`, albo odsłuchaj utwór w oknie, znajdź miejsce suwakiem i naciśnij **Ustaw tutaj**. Puste pole oznacza automatycznie: cisza wykryta przez analizę (zobacz Ustawienia). Wpisana wartość ma nad nią pierwszeństwo, tylko po swojej stronie, i działa także przy wyłączonym przycinaniu ciszy; **Auto** czyści pole. Utwór z ręcznym punktem ma w bibliotece znaczek ✂. Po cięciu musi zostać co najmniej sekunda dźwięku, inaczej zapis jest odrzucany, a koniec za długością pliku oznacza „do końca”. Pliki nie są zmieniane.

**Usuwanie.** Utwór może usunąć tylko właściciel lub administrator. Jeśli utwór jest użyty w playlistach, dowiadujesz się **ile ich jest** (nie które, żeby nic o cudzych scenariuszach nie wyciekło). Po usunięciu plik audio znika, ale tytuł zostaje w tych playlistach jako wyszarzony, przekreślony wpis, żeby autor playlisty to zauważył i mógł go zastąpić.

**Akcje zbiorcze.** Zaznacz utwory (pole w nagłówku zaznacza wszystkie widoczne). Na dole pojawia się pasek: **Dodaj do playlisty** dopisuje zaznaczone na koniec jednej z twoich playlist, **Dodaj mój tag** nadaje im osobisty tag.

**Podgląd.** Przycisk ▶ puszcza utwór w twojej przeglądarce (nie na Discordzie). Gdy gra, zmienia się w ⏸, a tuż pod wierszem tego utworu rozwija się **pasek przewijania** z czasem i ✕ do zamknięcia: przeciągnij go, żeby znaleźć interesujące miejsce. Ten sam przycisk i pasek są na liście utworów playlisty i w oknie **Dodaj utwory**, więc kandydata możesz odsłuchać bez wychodzenia z playlisty. Gra jeden utwór naraz; dźwięk zatrzymuje się, gdy opuścisz ekran albo zamkniesz okno, z którego go włączyłeś.

## Playlisty

Po lewej twoje drzewo. Użyj **+ Zestaw**, potem przycisku **♪+** przy zestawie (nowa playlista wprost w zestawie) albo **📁+** (nowy folder). Folder ma własny **♪+** na playlisty w środku. Ołówek zmienia nazwę, krzyżyk usuwa, strzałki zmieniają kolejność. Usunięcie zestawu, grupy lub playlisty nigdy nie usuwa muzyki z biblioteki.

Po prawej wybrana playlista.

**Playlisty automatyczne.** Przy tworzeniu playlisty (przyciski **♪+**) wybierasz jej rodzaj. Playlista **ręczna** zawiera utwory, które wybierzesz. Playlista **automatyczna** zawiera zamiast tego regułę: jeden lub kilka tagów i informację, czy utwór ma mieć **wszystkie** z nich, czy **dowolny**. Jej utworami jest to, co w chwili naciśnięcia pasuje do reguły, w kolejności alfabetycznej, więc otagowanie nowego utworu w Bibliotece dodaje go do każdej playlisty, której regułę spełnia, a usunięcie utworu zabiera go z listy bez wyszarzonego wpisu. Tag się liczy, gdy jest tagiem wspólnym utworu albo jednym z twoich tagów osobistych, więc playlistę na sesję możesz zbudować z tagu osobistego nadanego przy pobieraniu. Playlisty automatyczne mają znaczek 🏷, regułę edytujesz po prawej (lista pasujących utworów odświeża się od razu), a utworów nie dodajesz i nie przestawiasz w nich ręcznie. Ustawienia odtwarzania (pętla, losowo, fade, głośność) działają jak w ręcznych.

- **Pętla**: odtwarzaj listę w kółko. **Losowo**: losowa kolejność (przy każdej rundzie na nowo).
- **Płynne wejście/wyjście**: każdy utwór wchodzi i wychodzi przez tyle sekund (0 wyłącza). Przydatne przy muzyce tła. Działa tylko, gdy płynne przejście między utworami jest wyłączone (zobacz Ustawienia); przy włączonym przejściu utwory nakładają się i to pole nie ma wpływu.
- **Własna głośność**: po zaznaczeniu naciśnięcie tej playlisty ustawia głośność bota na tę wartość. Bez zaznaczenia zostaje obecna głośność.
- **Przenieś playlistę** umieszcza ją wprost w zestawie albo w dowolnym folderze (w dowolnym z twoich zestawów).
- **Kopiuj do…** daje innej osobie jej własną kopię playlisty. Trafia do zestawu na jej koncie nazwanego od ciebie („Od <twoja nazwa>”, a dla odbiorcy z angielskim „From <your name>”) i od tej chwili obie listy są niezależne: nikt nie widzi ani nie zmienia cudzej. Kopiowana jest tylko playlista, same utwory i tak są wspólne dla wszystkich. Utwory, które usunąłeś, są pomijane. Zaznacz **Skopiuj też moje prywatne tagi z tych utworów**, żeby odbiorca dostał również twoje osobiste tagi do nich; bez tego nie dostaje żadnego prywatnego tagu. Playlista automatyczna jest kopiowana jako reguła, więc jeśli reguła używa twojego prywatnego tagu, zaznacz to pole, inaczej kopia nic nie znajdzie u odbiorcy (panel ostrzeże).
- **Dodaj utwory** otwiera wybieralkę z wyszukiwaniem i filtrem tagów, zaznacz dowolną liczbę utworów. Utwory, które już są na tej playliście, nie są proponowane.
- Strzałki przesuwają utwór, krzyżyk usuwa go z playlisty (nie z biblioteki).
- Wyszarzony, przekreślony wpis to utwór usunięty z biblioteki. **Zastąp** pozwala wybrać inny utwór na to samo miejsce.

## Odtwarzacz

1. Wybierz **serwer** i **kanał głosowy**. Bot musi być na tym serwerze (zobacz [Tworzenie bota Discord](discord-bot.md)).
2. Wybierz **zestaw**. Jego playlisty pojawią się jako przyciski, foldery jako nagłówki z playlistami pod spodem.
3. Naciśnij playlistę albo użyj **Szybkiego wyboru z tagów** pod playlistami: zaznacz jeden lub kilka tagów, wybierz, czy utwór ma mieć wszystkie z nich czy dowolny, i naciśnij **Zagraj (N)**, żeby zagrać wszystkie pasujące utwory bez tworzenia playlisty (losowo, w pętli). Liczba przy tagu to liczba utworów z tym tagiem, liczba na przycisku to liczba utworów pasujących do twojego wyboru.
4. Naciśnij playlistę. Jeśli bota nie ma jeszcze na kanale, najpierw do niego dołączy, potem zacznie grać. Aktywna playlista jest podświetlona.

Pod przyciskami widać **listę utworów grającej playlisty** z podświetlonym bieżącym. Kliknij dowolny utwór, żeby zagrać go od razu; odtwarzanie idzie dalej od niego (przy losowaniu dalej w wylosowanej kolejności). Brakujące i usunięte utwory nie są na liście.

Pasek postępu bieżącego utworu jest też **suwakiem przewijania**: przeciągnij go albo kliknij w wybranym miejscu, żeby tam skoczyć, co przydaje się przy utworach, które długo się rozkręcają. Nowe miejsce wchodzi płynnie na stare (krótkie przejście, domyślnie 0,3 s), więc nie ma trzasku ani przerwy. Wstrzymany odtwarzacz zostaje wstrzymany i skacze dopiero po wznowieniu.

Sterowanie: poprzedni, pauza/wznów, następny, stop, pętla, losowo oraz suwak **głośności** (0 do 150 %), z kreskami pod spodem, żeby było widać, w co celujesz: długa na 0, 50, 100 i 150 %, krótka na 25, 75 i 125 %. Własna głośność playlisty ma taki sam suwak. Bot idzie za suwakiem podczas przeciągania i przechodzi między głośnościami płynnie, więc nawet kliknięcie ze 100 % na 10 % jest gładkim ściszeniem, a nie szarpnięciem. Jak wolno, ustawia **Płynna zmiana głośności** w Ustawieniach (domyślnie 0,25 s jako stała czasowa: około pół sekundy, żeby przejść większość drogi, i półtorej sekundy, żeby się ustalić; od 0 do 2 s, więcej znaczy łagodniej, 0 to jedna ramka 20 ms). To samo dotyczy włączania i wyłączania wyrównywania głośności. Gracze mogą też osobno ściszyć bota w Discordzie.

**Połącz / Rozłącz / Przenieś tutaj** zarządzają obecnością bota na kanale. Odpalenie playlisty na innym kanale wymaga najpierw kliknięcia **Przenieś tutaj**.

**Granie tutaj zamiast na Discordzie.** Przycisk **Odtwarzaj tutaj** obok **Połącz** sprawia, że muzykę gra sama strona, na głośnikach komputera, na którym panel jest otwarty, bez żadnego Discorda. Może z niego korzystać każdy, na dowolnym komputerze, i kilka osób naraz: każda przeglądarka gra niezależnie i nikt nikogo nie blokuje. Oba tryby się wykluczają: gdy grasz tutaj, **Połącz** jest wyłączone, a wybór serwera i kanału ukryty; gdy bot jest połączony z serwerem, **Odtwarzaj tutaj** jest wyłączone, dopóki go nie rozłączysz (bot, przez którego gra ktoś inny, ci nie przeszkadza). Reszta działa jak z botem: playlisty i szybki wybór, lista utworów, suwak przewijania, pętla, losowo, głośność, przejścia, przycinanie ciszy i wyrównywanie głośności, wszystko z wartościami z Ustawień. Przełączanie kart panelu nie zatrzymuje muzyki. Zatrzymuje ją odświeżenie lub zamknięcie strony, bo dźwięk żyje w tej stronie, a także włączenie muzyki w innej karcie panelu (dwie nigdy nie grają naraz) i wylogowanie. Pierwszy start wymaga kliknięcia na stronie, tak jak chce każda przeglądarka. Głośność tutaj jest osobna od głośności bota. Wskazówka: otwieraj panel pod adresem serwera w sieci domowej, a nie przez tunel, żeby dźwięk nie robił wycieczki przez internet.

**Jeden sterujący na serwer.** Dopóki czyjaś playlista gra na serwerze, inny użytkownik (nie administrator) dostaje komunikat „Ten serwer obsługuje teraz ktoś inny”, aż tamta sesja zostanie zatrzymana. Administrator może zawsze przejąć sterowanie.

Jeśli połączenie samo się zerwie, bot czeka około 35 sekund, zanim będzie mógł dołączyć ponownie. To celowe, szybsze ponowne wejście zwykle kończy się tym, że Discord zabija także nową sesję. W komunikacie zobaczysz, ile sekund zostało.

Bot opuszcza kanał po 30 minutach bez żadnego człowieka w środku (`IDLE_LEAVE_MINUTES`).

## Pobieranie

Wklej adres **jednego** filmu lub utworu z dozwolonego serwisu (domyślnie YouTube, SoundCloud, Bandcamp) i naciśnij **Pobierz**. Serwer pobiera dźwięk jeden raz, konwertuje go i dodaje do wspólnej biblioteki z wpisanymi tagami. Potem gra z dysku, więc w trakcie sesji nic nie zależy od YouTube.

Lista pokazuje, co robi każde pobieranie: przygotowanie (łączenie z serwisem, potrafi trwać kilka sekund, liczone są sekundy od startu), pobieranie z paskiem postępu, szybkością i czasem do końca, konwersję oraz dodawanie do biblioteki. Zlecenie czekające w kolejce pokazuje, ile sekund zostało z przerwy między pobraniami. Po zakończeniu lub błędzie pobierania pojawia się komunikat.

Zasady chroniące twój adres IP: jedno pobieranie naraz, przerwa między nimi, dzienny limit (zobacz [Konfiguracja](configuration.md)), playlisty nie są rozwijane. Nieudane zlecenie pokazuje powód, np. YouTube prosi o „potwierdzenie, że nie jesteś botem”. Pobranie świeżego obrazu przynosi nowszy `yt-dlp`, zobacz [Rozwiązywanie problemów](troubleshooting.md). Najpierw przeczytaj uwagi o regulaminach w [Bezpieczeństwie](security.md). Wgrywanie własnych plików albo muzyka na wolnych licencjach to zawsze bezpieczna droga.

## Użytkownicy

Zakładka **Użytkownicy** (tylko dla administratorów):

- **Użytkownicy**: zakładanie kont (nazwa, hasło co najmniej 10 znaków, rola), zmiana ról, reset hasła, wyłączanie i włączanie konta. Wyłączone konto jest natychmiast wylogowywane. Ostatniego aktywnego administratora nie można zdegradować ani wyłączyć.
- **Serwery**: dla każdego użytkownika niebędącego administratorem zaznacz serwery Discord, którymi może sterować. Użytkownik bez zaznaczonego serwera widzi pustą zakładkę Odtwarzacz.

Twoja nazwa w górnym pasku otwiera okno konta: zmiana hasła. Zmiana hasła wylogowuje cię wszędzie indziej.

## Ustawienia

Zakładka **Ustawienia** (tylko dla administratorów) pokazuje wersję, stan bota, **obciążenie kontenera** (CPU i pamięć, odświeżane co 3 sekundy: wartość bieżąca, średnia z 60 sekund i szczyt z ostatnich 10 minut; 100 % to jeden rdzeń, tak jak w `docker stats`) oraz ustawienia poniżej, w trzech grupach: Głośność, Przejścia i Cisza.

**Wyrównywanie głośności.** Gdy jest włączone, każdy utwór jest raz zmierzony w tle (linia pod przełącznikiem pokazuje, ile już jest gotowych) i odtwarzany z korektą, więc cichy ambient i głośny motyw walki wychodzą na podobnym poziomie. Pliki nigdy nie są zmieniane, korekta dzieje się podczas odtwarzania, więc wyłączenie działa od razu, także na utwór, który właśnie gra. Utwór jeszcze niezmierzony albo cichy jak makiem zasiał gra bez zmian. Suwak w Odtwarzaczu nadal ustawia ogólną głośność na wierzchu korekty. **Płynne przejście.** Utwory nakładają się: następny wchodzi, gdy bieżący się wycisza, domyślnie przez 3 sekundy. Dotyczy to też ręcznego „następny”, „poprzedni” i skoku do utworu oraz nowej playlisty puszczonej na działającą. Playlista w pętli przechodzi płynnie z ostatniego utworu do pierwszego. Pierwszy utwór playlisty puszczonej w ciszy wchodzi płynnie. **Płynne przejście między utworami** (0 do 12 s, 0 = twarde cięcie) i **Płynne przewijanie** (0 do 2 s) ustawia się w tej samej karcie System, też są w bazie i działają od razu. Utwór o nieznanej długości nie może się nakładać i po prostu następuje po poprzednim. W trakcie przejścia dekodują dwa procesy ffmpeg naraz, czyli przez kilka sekund trochę więcej CPU.

**Cisza.** Wiele utworów zaczyna się albo kończy chwilą ciszy, przez co przejście brzmi jak dziura. Gdy włączone jest **Przycinanie ciszy na początku i końcu utworów**, każdy utwór jest raz analizowany w tle (tym samym przebiegiem co głośność) i potem gra od pierwszego do ostatniego dźwięku: początek jest pomijany, a przejście do następnego liczy się od ostatniego dźwięku, a nie od końca pliku. Cisza to wszystko cichsze od **progu ciszy** (domyślnie -50 dB, od -70 do -30); niższa wartość, np. -60, przycina mniej. Przycinana jest tylko cisza trwająca co najmniej ćwierć sekundy na samym początku lub końcu, przycięcie, po którym zostałaby mniej niż sekunda, jest ignorowane, a niewielki zapas zostaje, żeby nie ucinać wygaszania. Zmiana progu analizuje bibliotekę od nowa w tle (linia pod sekcją pokazuje, ile utworów czeka). Pliki nigdy nie są zmieniane. Wyłączenie działa od następnego utworu. Zegar i pasek przewijania w Odtwarzaczu liczą dalej od początku pliku, więc przycięty utwór zaczyna się np. od 0:03.

Obok przełącznika głośności są dwie liczby: **poziom docelowy** w LUFS (domyślnie -16, od -30 do -8; niżej znaczy ciszej ogólnie) oraz **maksymalne podbicie** w dB (domyślnie 6, od 0 do 12; żeby bardzo cichy utwór nie był podbijany do szumu). Utwór nigdy nie jest podbijany do przesterowania, niezależnie od podbicia. Te ustawienia są tylko tutaj, w bazie, a nie w zmiennych kontenera, i każda zmiana działa od razu. Jeśli w środku sesji coś brzmi źle, wyłącz wyrównywanie tutaj zamiast restartować kontener.
