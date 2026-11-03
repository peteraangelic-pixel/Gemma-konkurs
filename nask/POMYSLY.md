# Jak to wygrać — pomysły uszeregowane po pieniądzach, nie po kolejności „fajności”

Pytanie użytkownika: „napisz, jakie masz pomysły, by coś wygrać”. Odpowiedź poniżej jest
posortowana po **EV/dzień** (oczekiwana wartość na dzień pracy), bo konkurs trwa 28 dni,
a nie 28 tygodni. Kalkulację liczy `tools/triage.py`, dane w `plan.json` — można podmienić
założenia i przeliczyć.

## 0. Uczciwa arytmetyka, zanim cokolwiek innego

- Pula edycji: **100 000 zł**. Nagroda maksymalna: 20 000 zł. Nagroda typowa, realna: 600–4 000 zł.
- Suma EV **wszystkich 19 hipotez** z `plan.json`, przy moich założeniach o szansach: **≈ 9 900 zł**.
  To nie prognoza zarobku — to pokazuje skalę: nawet solidna praca przez miesiąc to rząd
  kilku tysięcy złotych oczekiwanej wartości, a nie „100k”.
- Wniosek praktyczny: **nie warto stawiać na tę konkurs jako źródło dochodu.** Warto zrobić
  go porządnie, bo (a) jedna trafiona luka IDOR = 4 000–9 000 zł, (b) reputacja w programie
  zostaje na kolejne edycje, (c) narzędzia i szablon raportu zostają na zawsze.

## 1. Przewaga, którą mamy i której nie ma 95 % uczestników: **kod otwartoźródłowy**

Dwa z najcenniejszych celów w Tier 1 CERT Polska to projekty z publicznym kodem:

| cel | co to jest | dlaczego to przewaga |
|---|---|---|
| `mwdb.cert.pl` | MWDB (Malware Database) — CERT Polska publikuje `mwdb-core` na GitHubie | czytamy kod i widzimy, gdzie **brakuje** sprawdzenia właściciela obiektu — zamiast zgadywać |
| `n6portal.cert.pl` | portal N6 (dane o zagrożeniach) — też otwarte źródła | jak wyżej; dodatkowo riznice uprawnień między rolami |

To jest **jedyna** klasa pracy, w której 5 req/s nas nie ogranicza: analiza kodu jest
offline. Konkurenci w tym czasie fuzzują katalogi i dostają 403 od WAF-a.

**Konkret planu:** przegląd `mwdb-core` pod kątem (a) widoków API zwracających obiekt po ID,
(b) uprawnień „właściciel vs. grupa vs. publiczne”, (c) uploadu plików i parserów
(kzip/YARA — tam błędy walidacji bolą najbardziej), (d) eksportów i share linków.
Każde miejsce, gdzie kod robi `Object.get(id)` bez `if obj.owner == user` — to kandydat
na klasę **09 (IDOR/BAC)** = **9 000 zł**, a jeśli obiekt zawiera dane osobowe → klasa **03**.

## 2. Gdzie realnie jest 20 000 zł

Najwyższa stawka jest za RCE, przejęcie konta i masowy dostęp do danych. Kolejność
prawdopodobieństwa, że da się to zrobić w miesiąc:

1. **IDOR → masowy odczyt danych** (klasa 03 + 09) w `mwdb` lub `mSzyfr`. Trudność średnia,
   wpływ „masowy” podnosi CVSS do 9+ → 9 000–20 000 zł.
2. **Mass assignment** w rejestracji komunikatora (`role`, `is_admin`, `is_verified`).
   Jedno żądanie, jeśli serwer przyjmie pole — 9 000 zł. Sprawdzać zawsze i wszędzie.
3. **SSRF** w formularzu zgłoszeń (`zglos-dezinformacje.nask.pl` przyjmuje „źródło”).
   Jeśli serwer pobiera link — mamy SSRF; pełny SSRF → RCE = 20 000 zł.
4. **Upload → RCE** też tam, ale wymaga znalezienia wykonania pliku.
5. **RCE/SSTI** — najrzadsze, nie planuj na to miesiąca.

## 3. Tabela EV — kolejność pracy (z `plan.json`)

| host | klasa | tier | nagroda | P(traf) | dni | EV | **EV/dzień** |
|---|---|---|---:|---:|---:|---:|---:|
| `www.gov.pl` | 14-cors | T1 | 4 000 | 15 % | 1 | 330 | **330** |
| `mwdb.cert.pl` | 12-api | T1 | 9 000 | 18 % | 3 | 891 | **297** |
| `komunikator…` | 13-mass-assignment | T1 | 9 000 | 12 % | 2 | 594 | **297** |
| `mwdb.cert.pl` | 09-idor-bac | T1 | 9 000 | 22 % | 4 | 1 089 | **272** |
| `n6portal.cert.pl` | 12-api | T1 | 9 000 | 15 % | 3 | 743 | **248** |
| `incydent.cert.pl`, `moje.cert.pl`, `oad.nask.pl` | 09/12 | T1 | 9 000 | 10 % | 2 | 495 | **248** |
| `zglos-dezinformacje` | 07-upload | T1 | 9 000 | 12 % | 3 | 594 | **198** |
| `komunikator…` | 09-idor-bac | T1 | 9 000 | 18 % | 5 | 891 | **178** |
| `dns.pl` | 03-dane | T1 | 9 000 | 10 % | 3 | 495 | **165** |
| `www.gov.pl` | 08-xss | T1 | 4 000 | 20 % | 3 | 440 | **147** |
| `eobieg.wladyslawowo.pl` | 09-idor-bac | T1 | 2 000 | 25 % | 2 | 275 | **138** |
| `komunikator…` | 02-przejęcie konta | T1 | 20 000 | 6 % | 6 | 660 | **110** |

Pełna tabela: `python3 nask/nask.py plan nask/plan.json`.

**Jak to czytać:** pierwsze trzy dni nie idą na „największą nagrodę”, a na **dwie tanie
weryfikacje** (CORS na www.gov.pl, mass assignment w komunikatorze) i **jeden dzień na
uruchomienie dostępu do kodu mwdb**. Reszta to już praca ciągła nad mwdb.

## 4. „Rust z Rayon wszędzie” — gdzie to naprawdę daje pieniądze, a gdzie nie

To nie jest sprzeciw wobec Rusta, a rozliczenie z limitem z regulaminu:

```
5 req/s × 3600 s = 18 000 żądań na godzinę.
Sprawdzenie 12 domen × 20 ścieżek = 240 żądań = 48 sekund.
Słownik 10 000 ścieżek na jednym hoście = 33 minuty (i WAF i tak odetnie).
```

**Przy 5 req/s szybkość CPU nie jest wąskim gardłem — jest nim decyzja, co wysłać.**
Repo, które ma dziś fuzzer bez limitera (patrz `AUDYT-POPRZEDNIEGO-REPO.md`), przy
16 rdzeniach wygenerowałoby setki req/s, czyli **złamałoby regulamin i unieważniło
wszystkie nagrody**. Rust przyspiesza tam, gdzie nikt nie patrzy na sieć:

| zadanie | język | zysk |
|---|---|---|
| przegląd kodu `mwdb-core` / `n6portal` (offline) | Rust + Rayon **ma sens**: skan AST/regex po tysiącach plików w sekundy | wysoki |
| ekstrakcja endpointów z bundli JS (setki MB po minifikacji) | Rust + Rayon **ma sens** | średni |
| lokalne laboratorium (uruchomienie mwdb-core w Dockerze, dwa konta) | **największy zysk w całym miesiącu** | bardzo wysoki |
| wysyłanie żądań HTTP | Rust **bez znaczenia** — limit 5 req/s | zero |
| łamanie haseł, brute force | **zakazane** (DoS/obciążenie) | ujemny |

Dlatego w tym repo narzędzia są w Pythonie (zero zależności, testy offline, 46/46 zielonych),
a Rust jest zarezerwowany na **jeden** konkretny moduł: skaner reguł bezpieczeństwa po kodzie
`mwdb-core` (zadanie na tydzień 2). Wtedy „Rust + Rayon” jest przewagą, a nie ozdobą.

## 5. Sześć decyzji, które najczęściej decydują o wygranej

1. **Zgłaszać wcześnie.** Nagrody ogłaszane w trakcie miesiąca, duplikat rozstrzyga godzina.
   Dobry raport w dniu 5 bije perfekcyjny raport w dniu 28.
2. **Jedna klasa na raz, do końca.** Skończ mwdb, zanim otworzysz komunikator.
3. **Pisać wpływ, nie tylko błąd.** NASK płaci wg CVSS 4.0. „Odczytałem cudzy obiekt” = 4 000 zł;
   „odczytałem 200 000 rekordów zawierających e-maile i próbki” = 9 000–20 000 zł.
   Ten sam błąd, inny raport, inna kwota.
4. **Dwa własne konta, zawsze.** Bez tego IDOR jest nie do udowodnienia (§6).
5. **Nie zgłaszać wykluczeń.** Jeden raport o brakującym nagłówku HSTS potrafi sprawić, że
   zespół zaczyna traktować kolejne zgłoszenia tego autora jak szum.
6. **Zapis dowodów od pierwszej sekundy.** `tools/fetch.py` loguje każde żądanie z SHA-256 —
   bez tego PoC trzeba odtwarzać od zera (a czasem nie da się odtworzyć).

## 6. Co robię ja, a co Ty

- **Ja:** kod, narzędzia (z limitem i kontrolą zakresu), analiza kodu otwartych źródeł
  `mwdb-core`/`n6portal` offline, triage EV, generator raportów, przegląd dowodów.
- **Ty:** rejestracja własnych kont, wysyłka żądań z Twojej maszyny lub Actions (ja nie mam
  dostępu sieciowego do tych hostów), kliknięcia w przeglądarce tam, gdzie potrzebny jest
  zalogowany użytkownik, i **wysyłka zgłoszeń przez formularz** — to wymaga Twojego konta.

To nie jest podział „dla wygody”: żądania do celów w scope muszą wychodzić z Twojej
infrastruktury i pod Twoim nazwiskiem, bo to Ty jesteś uczestnikiem konkursu (§4).
