# Przegląd 6 gałęzi zespołu — co przyjmuję, co odrzucam, co zweryfikowałem sam
**Data:** 4.11.2026 · **Sesja:** `arena/c4eeb067-gemma-konkurs` (Gemma-B)
**Zakres przeglądu:** `Pokemon@c87f7a48`, `Pokemon@7911f950`, `Pokemon@a450b00f`, `Gemma-konkurs@6d081d52`, `Smak-Domu-Konkurs@5ed750ef`, `NASK@a29ca234` + `NASK@codex/*`.

Zasada, którą stosowałem czytając cudze prace: **każde twierdzenie jest hipotezą, dopóki nie powtórzę go własnym żądaniem.** Poniżej trzy kolumny: przyjęte bez zastrzeżeń, przyjęte warunkowo, odrzucone — plus to, co znalazłem tylko ja.

---

## 1. PRZYJMUJĘ (to realnie przyspiesza pracę)

| Co | Skąd | Dlaczego to zmienia grę |
|---|---|---|
| **Kontrakt `POST /api/sendForm`**: multipart, pola `accept` (wym.), `email`, `file` (png/jpeg ≤20 MB), `reason` ≤250 zn., `urls` (wym., do 50 linków, po jednym w linii), `g-recaptcha-response` (v3) | Smak `5ed7` (z bundla) | Jedyne miejsce w całym zakresie, gdzie **serwer robi coś z treścią podaną przez atakującego**: pobiera linki i przyjmuje pliki. To jest dokładnie klasa §8.5 (SSRF) i §8.6 (upload). Bez tego kontraktu nie dało się nawet zaplanować sondy. |
| **`/download-file/?fileUrl=` na `bezpiecznymiesiac.pl`** — endpoint, którego **nie było w naszej mapie** | c87 + Smak | Nasz `naskmap` znalazł tylko `/api/*`; ten endpoint żyje poza `/api`, na innym poziomie routingu. To luka w naszym narzędziu, nie w ich wiedzy. |
| **Reguła „odejmij catch-all hostu”** | 7911, Smak, c87 (niezależnie, trzy sesje) | U nich 200 → 12 „trafień” w jednym przebiegu, które okazały się przekierowaniami. U nas reguła „200+JSON = kandydat” dawała ten sam szum (runda 3–5). **Wdrożone w kod** — patrz §4. |
| **Jeden skok na przekierowanie same-origin (308/307)** | 7911 (`measure()` + hop) | Frameworki kanonizują ścieżki (`/api` → `/api/`, `/wp-json/` → `/wp-json`). Przy `redirects(0)` te sondy były **ślepe**. Wdrożone. |
| **`dns.pl` = Drupal, żywe tylko `zone-stats` i `registrars-services`** | Smak (bieg 4–5) + nasza runda 6 | Zgadza się z naszym pomiarem (3 z 5 ścieżek to martwe trasy klienta). Zamyka temat. |
| **`_next/image` nie jest SSRF na żadnym hoscie** | wszyscy + nasza runda 5 | Zbieżność 4 niezależnych pomiarów. Definitywnie zamknięte. |
| **Wytyczna prawna: regulamin usługi `moje.cert.pl` (część IV pkt 4.2) zakazuje testowania mimo programu bug bounty** | a450 | To nie jest drobiazg — to potencjalna dyskwalifikacja. **Nie dotykamy** do pisemnego wyjaśnienia organizatora. |

## 2. PRZYJMUJĘ WARUNKOWO (wymaga weryfikacji, zanim zbuduję na tym plan)

| Twierdzenie | Kto | Mój wynik weryfikacji |
|---|---|---|
| „`/admin/logs` na HIVE ma guardy **tylko klienta**” (H10, 4 500–10 000 zł) | Smak | **Niepotwierdzone.** Moje `GET /admin/logs` ląduje na `/login` (formularz), a `GET /api/v1/admin/logs` → weryfikacja w rundzie 7. SPA React Routera odpowiada 200 na **wszystko** (catch-all 713 B) — bez nagranego statusu surowego ten „guard kliencki” może być zwykłym 200 na nieistniejącej trasie. Za mało, by planować na tym budżet. |
| „H9: `downloadFile` → enum po własnym uploadzie, 2 000–4 500 zł” | Smak | **Już sfalsyfikowane — przez nas** (runda 6): gęsty sweep 60 ID wokół realnych załączników dał wyłącznie publiczne zdjęcia. Ich wersja („enum po własnym uploadzie”) jest ciekawa, ale wymaga uploadu = żądanie zapisujące = Twoja zgoda. |
| „`sendForm`: 50 linków × walidacja SSRF” | c87 / Smak | Kontrakt zgadza się z naszym `MAP`. Nietknięte, bo to POST tworzący prawdziwe zgłoszenie u operatora rządowego. **Czeka na Twoje GO.** |
| „`x-original-url` / `x-forwarded-prefix` zmienia odpowiedź na `moje.cert.pl` i `incydent.cert.pl`” | Gemma-A (`6d08`) | **Nie do sprawdzenia z naszego środowiska** — te hosty zrywają połączenie (status 0). Dodatkowo `moje.cert.pl` ma zakaz z regulaminu usługi. Odkładam. |

## 3. ODRZUCAM / KORYGUJĘ (żeby nie tracić na to czasu)

| Twierdzenie | Problem |
|---|---|
| „116sos.pl leży od ~23:00, 502 nginx” (powtarzane w 4 raportach) | **Nieaktualne.** Dziś host odpowiada 200 na `/api/centres-search` i `/api/fetch-cookie-hash`. Awaria minęła — cztery sesje zapisały ją jako trwały stan. |
| „`fetch-cookie-hash` to potencjalnie dane sesji” | **Zamknięte.** Wartość `6a9963b75ab63` jest **identyczna** wczoraj i dziś, dla dwóch różnych żądań bez ciasteczka → to stała (cache-buster/asset hash), nie pochodna sesji. |
| „`q` w `centres-search` filtruje wyniki, więc `q=Warszawa'` różni się od `q=Warszawa`” | **Błędne założenie.** `q` jest **ignorowane** — `q=zzzzqqqxxx` zwraca tę samą pełną bazę ośrodków. Wszystkie nasze testy SQLi na tym parametrze mierzyły szum, nie bazę. Poprawna kontrolą jest porównanie z `q=` pustym. |
| „`www.nask.pl` jest w zakresie, bo §5 mówi `nask.pl`” | **Ryzyko odrzucenia.** To inna nazwa hosta. Zgłoszenie z `www` może zostać odrzucone jako poza zakresem — a po trzech odrzuceniach pod rząd platforma może zablokować wysyłkę. **Pytanie do organizatora przed jakimkolwiek testem.** Nasz `naskhunt` **nie wykonuje** skoku `nask.pl` → `www.nask.pl` (porównanie hosta jest twarde), więc nie wychodzimy z zakresu przez przypadek. |
| „`hack.cert.pl` ma trasy `/users/$userId/view` i `/users/me/profile/payout` — IDOR na IBAN” | **Nie nasz program.** `hack.cert.pl` należy do programu **CERT Polska**, nie NASK. Nasz wybrany program ma 12 innych domen. Mieszanie programów w jednym rejestrze zgłoszeń to prosta droga do odrzucenia. |
| Zbiorcze „0 podatności u wszystkich” jako wniosek strategiczny | Zgoda co do faktu, ale nie co do wniosku: to nie znaczy „powierzchnia wytarta”, tylko **„powierzchnia bezstanowa jest wytarta”**. Różnica jest cała w tym, że klasa 9 (IDOR/BAC) i 7 (upload) wymagają konta, którego nikt z nas nie ma. |

## 4. CO WDROŻYŁEM W KODZIE (trwałe, nie jednorazowe)

`NASK/tools/naskhunt` — trzy zmiany, wszystkie z cudzych błędów:

1. **Catch-all na hosta.** Przed pierwszą sondą narzędzie pobiera losową nieistniejącą ścieżkę i zapamiętuje odpowiedź. Jeśli sonda zwraca to samo (status + długość ±48 B), werdykt to `czysto`, nie `KANDYDAT`. To likwiduje klasę fałszywych trafień, która w trzech sesjach zjadła po kilkanaście „odkryć”.
2. **Jeden skok same-origin.** `308`/`307`/`301`/`302` z `Location` na **ten sam host** i `https` jest rozwiązywany dodatkowym żądaniem (liczonym osobno w limiterze). `http://` i obce hosty — odrzucane. Porównanie nazwy hosta jest twarde, więc `nask.pl → www.nask.pl` **nie** zostanie wykonane.
3. **Werdykt bez fałszywej reguły.** Usunięte „200 + JSON = kandydat”. Zostały wyłącznie sygnały mierzalne: odbity `Origin` z credentials, różnica wobec baseline, różnica wobec catch-all.

Dodatkowo: `checks-round{1..6}.json` to archiwum kompletnych zestawów sond — każdy przebieg jest odtwarzalny co do żądania.

## 5. CO ZNALAZŁEM TYLKO JA (i czego nikt inny nie sprawdził)

- **`science.nask.pl/api/downloadFile?fileId=` — kontrakt złamany**, parametr to `fileId`. Nikt inny go nie ustalił (cztery sesje pisały „Invalid file id” i zgadywały `file`, `name`).
- **Gęsty sweep 60 ID** wokół realnych załączników: wszystkie trafienia to publiczne zdjęcia z aktualności. Hipoteza IDOR zamknięta **pomiarem**, nie opinią.
- **`pllum.org.pl/api/_content/query`** — Nuxt Content. Filtr `_draft=true` zwraca `[]` → wersje robocze **nie** wyciekają. Zamknięte.
- **`q` ignorowane w `centres-search`** — patrz §3.

## 6. NASTĘPNY RUCH (kolejność wg realnej wartości, nie wg kolejności w cudzych planach)

1. **Twoje GO na rundę zapisującą** — `sendForm` z własnym kontrolerem podglądu (żeby sprawdzić, czy serwer pobiera link). To jedyne miejsce z szansą na klasę 5/7, czyli 4 000–9 000 zł. Bez zgody tego nie ruszam.
2. **Pytanie do organizatora** (jedno, trzy wątki): zakres `www.nask.pl`; zakaz z regulaminu `moje.cert.pl`; możliwość konta testowego w HIVE. Odpowiedź odblokowuje albo zamyka trzy ścieżki naraz.
3. **Runda 7 (już w CI):** nowe sondy na `/download-file` (bezpiecznymiesiac), weryfikacja `/admin/logs`, stabilność `cookieHash`, drafty Nuxt. Bez powtarzania tego, co zamknięte.
4. **Reszta czeka na konto.** IDOR bez dwóch kont jest nie do udowodnienia — §6 regulaminu wymaga PoC, a PoC na cudzych danych jest niedozwolone. To nie jest „brak pomysłu”, to twarda bariera.

## 7. Stan techniczny

Kod i dokumenty zacommitowane i wypchnięte. Push był chwilowo zablokowany po stronie sieci sandboxa (`gnutls_handshake() failed`, `curl https://github.com/` → `000` przy działającym `registry.npmjs.org`), przez co runda 7 nie wystartowała od razu; po przywróceniu łączności trafiła do CI.

Pełny inwentarz tego, co przejęte z innych gałęzi (z proweniencją commit→plik i statusem weryfikacji): **`NASK/PRZEJETE-Z-GALEZI-2026-11-04.md`**.
