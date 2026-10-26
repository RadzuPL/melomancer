# Tworzenie bota Discord

Języki: [English](../en/discord-bot.md) · **Polski**

Melomancer potrzebuje własnego konta bota. To około pięciu minut pracy, robisz to raz. Oficjalne materiały: https://docs.discord.com/developers/quick-start/getting-started i https://discordpy.readthedocs.io/en/latest/discord.html

## 1. Utwórz aplikację

1. Otwórz https://discord.com/developers/applications i zaloguj się swoim kontem Discord.
2. Kliknij **New Application**, wpisz nazwę (na przykład `Melomancer`), zaakceptuj regulamin i kliknij **Create**.
3. Trafisz na stronę **General Information**. Skopiuj **Application ID**, będzie potrzebne do linku zaproszenia w kroku 4.

## 2. Pobierz token bota

1. W lewym menu otwórz **Bot**.
2. Kliknij **Reset Token** i potwierdź. Skopiuj token, który się pojawi, Discord pokazuje go tylko raz.
3. Wpisz go do kontenera jako `DISCORD_TOKEN` (zobacz [Instalacja](installation.md)).

Token to hasło bota. Nigdzie go nie publikuj i nie wrzucaj do repozytorium. Jeśli wycieknie, kliknij **Reset Token** ponownie, co unieważni stary, i zaktualizuj `DISCORD_TOKEN`.

## 3. Sprawdź ustawienia bota

Nadal na stronie **Bot**:

- **Privileged Gateway Intents**: zostaw wszystkie trzy **wyłączone**. Melomancer nie potrzebuje żadnego z nich (ani treści wiadomości, ani listy członków, ani statusów).
- **Public Bot**: wyłącz, jeśli tylko ty masz móc dodawać tego bota na serwery. (Gdy jest wyłączone, zaprosić go może tylko właściciel aplikacji.)
- **Require OAuth2 Code Grant**: zostaw wyłączone.

## 4. Zaproś bota na serwer

Na serwerze, na który zapraszasz, musisz mieć uprawnienie **Zarządzanie serwerem** (Manage Server).

Użyj tego linku, podmieniając `YOUR_APPLICATION_ID` na Application ID z kroku 1:

```
https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&scope=bot&permissions=3147776
```

Otwórz go w przeglądarce, wybierz serwer, kliknij **Continue** i **Authorize**. Liczba `3147776` to zestaw uprawnień potrzebnych botowi: **View Channels** (wyświetlanie kanałów), **Connect** (łączenie) i **Speak** (mówienie). Nic więcej.

Alternatywa bez wpisywania linku: w Developer Portal otwórz **OAuth2**, potem **URL Generator**, zaznacz scope `bot`, zaznacz uprawnienia **View Channels**, **Connect** i **Speak**, a **Generated URL** skopiuj z dołu strony.

Zaproszenie powtórz dla każdego serwera, na którym chcesz grać.

## 5. Sprawdź, czy działa

1. Uruchom kontener z ustawionym tokenem.
2. W Discordzie bot powinien pojawić się jako online na liście członków serwera.
3. Otwórz panel i przejdź do zakładki **Odtwarzacz**: twoje serwery i ich kanały głosowe pojawią się automatycznie. Nie musisz kopiować żadnych ID.
4. Administratorzy widzą wszystkie serwery, na których jest bot. Pozostałym użytkownikom administrator zaznacza w zakładce **Administracja**, którymi serwerami mogą sterować.

## Warto wiedzieć

- **Uprawnienia kanału.** Jeśli kanał głosowy ma własne nadpisania uprawnień, które odbierają roli bota **Connect** albo **Speak**, panel pokaże „Bot nie ma uprawnień na tym kanale”. Zezwól botowi na tym kanale na View Channel, Connect i Speak.
- **Jeden kanał głosowy na serwer na bota.** Discord pozwala botowi być naraz w jednym kanale głosowym na serwer. Dla dwóch równoległych sesji na tym samym serwerze potrzebujesz drugiej aplikacji i drugiego kontenera.
- **Drugi bot na kanale to nie problem.** Na przykład rejestrator sesji może siedzieć na tym samym kanale. Muzyka pojawia się jako osobny uczestnik, więc gracze mogą ją osobno ściszyć w Discordzie (prawy klik na bocie, głośność użytkownika).
- **Szyfrowanie głosu (DAVE).** Od 2026-03-01 Discord wymaga szyfrowania głosu end-to-end. Obraz zawiera potrzebne biblioteki (`discord.py` 2.7.1 lub nowszy i `davey`). Log wypisuje ich wersje przy starcie. Szczegóły: https://docs.discord.com/developers/topics/voice-connections
- **Kopiowanie ID (opcjonalnie).** Potrzebne tylko, gdy chcesz ręcznie dodać użytkownikowi serwer: w Discordzie otwórz **Ustawienia użytkownika**, **Zaawansowane**, włącz **Tryb dewelopera**, potem kliknij prawym przyciskiem ikonę serwera i wybierz **Kopiuj ID serwera**. Artykuł pomocy: https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID
