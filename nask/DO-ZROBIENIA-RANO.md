# Rano: 15 minut, które rozstrzygają najwięcej

Trzy rzeczy po kolei, każda z gotowym kryterium „tak/nie”. Bez tego dalsza praca to
zgadywanie, z tym — decyzja.

## 1. Sprawdź wersję mwdb (2 minuty, bez konta)

```bash
curl -s https://mwdb.cert.pl/api/server
```

Kryterium:

- `server_version` **< 2.20.0** → produkcja nie ma poprawki XSS w atrybutach Rich
  (mwdb-core #1272/#1274). **Warto to sprawdzić**, bo mamy działający wektor i jest
  o krok od klasy 08. Przechodzisz do punktu 2.
- `server_version` **≥ 2.20.0** → temat zamknięty, nie tracimy na niego czasu.
  Przechodzisz od razu do punktu 3.

## 2. Konto na mwdb + jeden obiekt (10 minut)

1. Rejestracja: <https://mwdb.cert.pl> (zwykła, Twoje własne konto — nie potrzebuję hasła).
2. Utwórz **własny** obiekt (cokolwiek, np. plik tekstowy).
3. Dodaj atrybut → typ **Rich attribute** → w treści wklej:

   ```markdown
   [kliknij mnie](javascript:alert(document.domain))
   ```

4. Zapisz, otwórz obiekt w przeglądarce, kliknij link.

Kryterium:

- **wyskakuje `alert`** → mamy potwierdzony XSS w wersji produkcyjnej. To jeszcze
  self-XSS, więc **nie zgłaszamy**. Teraz pytanie, czy obiekt da się udostępnić grupie
  (`share`) — jeśli tak, i link działa u drugiego użytkownika, to jest klasa **08**
  z realnym wpływem = 4 000 zł, a przy kradzieży sesji argumentacja rośnie.
  Wtedy: zrzut ekranu, dokładna wersja, treść atrybutu, kroki — i zgłoszenie.
- **nic się nie dzieje** → poprawka jest wdrożona. Zamykamy wątek, Zero żalu.

## 3. Konto na hack.cert.pl + awatar (5 minut)

1. Rejestracja: <https://hack.cert.pl> (to samo konto służy do zgłoszeń — i tak musisz je mieć).
2. Ustawienia profilu → awatar. Wgraj plik **SVG** o treści:

   ```xml
   <svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.domain)</script></svg>
   ```

3. Otwórz swój profil (albo `/users/<twoje-id>/view`) i sprawdź, czy plik się wyświetla,
   a jeśli tak — czy skrypt się wykonuje.

Kryterium:

- **plik odrzucony** → walidacja działa, wątek zamknięty (i tak trzeba było sprawdzić).
- **plik przyjęty i wyświetla się jako obraz** → potencjalne stored XSS; sprawdź, czy
  awatar widać na profilu publicznym. Jeśli tak — to już nie self-XSS, tylko wektor
  na innych użytkowników = klasa **08**, a w kontekście platformy z danymi wypłat
  argumentacja po CVSS 4.0 rośnie.

## Czego mi NIE wysyłaj

Haseł, ciasteczek sesji, tokenów. Jeśli wynik będzie „tak”, wystarczy mi:
wersja aplikacji, zrzut ekranu i dokładne kroki. Reszta to moja robota — raport,
PoC, uzasadnienie CVSS.

## Jeśli wszystkie trzy odpowiedzi to „nie”

To też jest wynik i nie jest porażką: właśnie wykluczyliśmy trzy najbardziej
prawdopodobne wektory **własnymi rękami, a nie cudzym skanerem**. Wtedy następne
w kolejce są `dataannotation.pllum.org.pl` (IDOR na anotacjach, wymaga konta)
i `komunikator.narodowy.gov.pl` (mass assignment przy rejestracji) — oba opisane
w `POMYSLY.md`, oba wymagają Twojego zalogowania.
