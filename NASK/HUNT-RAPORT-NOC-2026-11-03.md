# Nocny hunt NASK — raport zbiorczy (3/4 listopada 2026)

**Edycja:** hack.cert.pl, program NASK PIB (11/2026), pula 100 000 zł, Tier 1 600–20 000 zł, Tier 2 300–10 000 zł.
**Zasady przestrzegane:** tylko hosty z §5 (`NASK/tools/nasktriage/scope.example.json`), ≤ 2 req/s (regulamin dopuszcza 5), wyłącznie GET, bez logowania, bez ciał żądań, bez brute-force, bez testów obciążeniowych.
**Program Władysławowo:** nietknięty (zgodnie z poleceniem).

## Wynik w jednym zdaniu

**105 żądań, 5 rund, 0 potwierdzonych podatności.** Zmapowano powierzchnię API 9 hostów z zakresu, sfalsyfikowano ~10 hipotez i wskazano 4 miejsca, w których warto kopać dalej — żadne nie daje jeszcze materiału na zgłoszenie.

## Co zostało sprawdzone i z jakim wynikiem

| Host | Powierzchnia | Testy | Wynik |
|---|---|---|---|
| `science.nask.pl` | `/api/downloadFile`, `/api/search`, `/api/media/`, `/api/contact`, `/api/__mp/` | kontrakt `fileId` (potwierdzony), sweep 25 ID, traversal, tablica/typ, SQLi, CORS | **negatyw** — patrz „Słabe punkty” nr 1 |
| `116sos.pl` | `/api/centres-search`, `/api/fetch-cookie-hash`, `/api/announcements`, `/api/og-image` | kształt odpowiedzi, cytat/boolean, `limit`, CORS | **host nieosiągalny od ~23:00** (502 nginx na każdą ścieżkę `/api/*` i na stronę) — testy przerwane, nie zakończone |
| `dns.pl` | `/api/zone-stats`, `/api/count-deleted-domains`, `/api/who-is-xml/`, `/api/domain-browser/`, `/api/funny-name/` | żywotność, parametry, CORS | **negatyw** — 3 z 5 ścieżek z bundle'a to martwe trasy klienta (404) |
| `zglos-dezinformacje.nask.pl` | `/api/sendForm` (POST), catch-all `/api/*` | GET na POST-only, enumeracja innych tras | **negatyw** — 405 na GET, catch-all zwraca identyczny błąd dla każdej ścieżki (brak wycieku tras) |
| `bezpiecznymiesiac.pl` | `_next/image`, `/api/__mp/`, `/api/news/`, `/post-data/` | open-proxy/SSRF w image-proxy, CORS | **negatyw** — `url` param whitelistowany, `/api/news/` i `/post-data/` tylko POST (405) |
| `bezpiecznewybory.pl` | `_next/image`, formularz zgłoszeń | open-proxy z remotePatterns, `@`-bypass | **negatyw** — obrazek z dozwolonego hosta działa, obejście whitelisty nie przechodzi |
| `dataannotation.pllum.org.pl` | `/api/v1/*` (FastAPI/HIVE) | authz na `projects/`, `users/`, 401 vs 405, OpenAPI | **częściowo pozytyw** — API żyje i ma poprawną kontrolę dostępu na poziomie routera; OpenAPI niedostępne |
| `pllum.org.pl`, `secure.edu.pl` | strony statyczne / brak połączenia | fingerprint | brak powierzchni do ataku (pllum: Nuxt statyczny; secure.edu.pl nie odpowiada) |
| `nask.pl` | Next.js CMS + `/api/search` | API wyszukiwarki, `lang`, `perPage`, XSS refleksyjny | patrz „Słabe punkty” nr 3 (uwaga: `www.nask.pl` jest **poza** literałem §5) |

Klasy z §8 przetestowane i **odrzucone**: SSRF (image-proxy, `podglad-pdf`, `og-image`), path traversal/LFI (`/api/media/`, `fileId`), SQLi (boolean + czasowa, WAF ucina payloady), CORS (żadne API nie odbija `Origin`), open redirect, XSS refleksyjny w wyszukiwarce, middleware bypass Next.js (CVE-2025-29927) na 4 hostach, IDOR na `downloadFile`.

## Słabe punkty — ranking do dalszej pracy

### 1. `science.nask.pl /api/downloadFile?fileId=<ID>` — pobieranie po numerze ID (poz. 8.9)
Kontrakt ustalony jednoznacznie: parametr to **`fileId`**, wartość liczbowa; `fileId=18864` zwraca `200 image/png` 2 210 114 B z `Content-Disposition: attachment; filename="Designer-11.png"`. Walidacja jest twarda (`-1`, `18864abc`, `fileId[]` → `400 Invalid file id`; traversal → reset WAF), a sweep 25 ID w przedziale 100–20 000 dał 404 poza dwoma realnymi.
**Dlaczego nadal warto:** endpoint serwuje pliki wyłącznie z witryny `sites/4`. Jeśli w mediach tej witryny istnieje załącznik niepubliczny (wersja robocza wpisu, plik z `post_status=private`), jego ID wystarczy do pobrania. Brakuje **jednego** ID niepublicznego pliku — zdobycie go to cała robota.
**Następny krok:** pozyskać ID z osi czasu (media dodawane w tym samym dniu co wpisy robocze) i sprawdzić, czy dla danego ID `/api/downloadFile` zwraca 200, gdy `/api/media/wp-content/...` zwraca 404/403.

### 2. `zglos-dezinformacje.nask.pl /api/sendForm` — jedyny realny wektor z potencjałem na wyższą półkę
POST-only (405 na GET), FormData + `g-recaptcha-response`, pole „link” i załącznik. Niesprawdzone: typy plików (upload → RCE/filter bypass, poz. 8.6), walidacja URL (SSRF), propagacja treści do panelu analityka (stored XSS).
**Blokada:** to żądanie **zapisujące** (tworzy zgłoszenie u operatora rządowego) i wymaga przejścia captchy. Nie wykonane bez zgody użytkownika — przygotowany plan i payloady czekają w `NASK/IDEAS`.

### 3. `nask.pl /api/search` — CMS-owe API listujące treści
`?lang=pl` zwraca pełne obiekty WP (autor, ID mediów, taksonomie) i paginację 73 stron; `perPage`, `page`, `query` są ignorowane lub walidowane (`400 Query must be at least 3 characters`). Brak refleksji parametru w HTML → brak XSS.
**Uwaga formalna:** §5 wymienia literał `nask.pl`; `www.nask.pl` to inna nazwa hosta. Zanim cokolwiek zgłosisz z tego hosta, potwierdź interpretację zakresu z organizatorem — inaczej ryzykujesz odrzucenie.

### 4. `dataannotation.pllum.org.pl /api/v1/*` — aplikacja FastAPI (HIVE)
`/api/v1/projects/` i `/api/v1/users/` → `401 {"detail":"Not authenticated"}`; `/api/v1/users/1` → `405` (trasa istnieje dla innych metod). Kontrola dostępu działa na poziomie routera, więc IDOR wymaga konta. Rejestracja publiczna nie istnieje (`/register`, `/api/v1/register` → 404).
**Następny krok (za zgodą):** konto testowe od organizatora albo własne, jeśli gdzieś jest zaproszenie — dopiero wtedy BAC/IDOR na `users/{id}`, `projects/{id}`, `annotations`.

### Obserwacja operacyjna
`116sos.pl` od ~23:00 zwraca `502 Bad Gateway` (nginx) na wszystkie ścieżki, także na stronę główną — to awaria, nie wynik testu. Dostępność nie jest w §8, więc nie nadaje się na zgłoszenie; wróć tam, gdy wstanie, bo `centres-search` i `fetch-cookie-hash` pozostają niesprawdzone do końca.

## Wnioski metodologiczne (żeby nie tracić czasu drugiej nocy)

1. **Runner GitHub Actions nie jest dobrym punktem startowym dla `cert.pl`** — `hack.cert.pl`, `cert.pl`, `moje.cert.pl`, `incydent.cert.pl`, `mwdb.cert.pl`, `ctf.hack.cert.pl` zrywają połączenie z runnera (WAF blokuje chmurę). Hosty te trzeba testować z sieci domowej albo przez proxy tekstowe (GET-only).
2. **Fałszywe „KANDYDACI”**: reguła „200 + JSON = kandydat” generowała szum — usunięta z `naskhunt` w tej rundzie. Werdykt ma wynikać z sygnału (odbity Origin, różnica wobec baseline), nie z kodu odpowiedzi.
3. **WAF NASK ucina payloady** (status 0 / reset) dla `' OR 1=1`, `pg_sleep`, `../` w ścieżce. Testy iniekcji przez GET są tu praktycznie nieskuteczne — zostają żądania z ciałem i nagłówkami.

## Artefakty

- `NASK/hunt/report-*.{md,json}`, `NASK/hunt/MAP-*.md` — surowe wyniki 5 rund (każde żądanie z statusem, czasem, nagłówkami).
- `NASK/tools/naskhunt/checks-round{1..4}.json` — archiwum zestawów sond (audytowalne, co dokładnie wysłano).
- `NASK/tools/naskhunt/checks.json` — bieżący zestaw.
- `NASK/tools/nasktriage/` — strażnik zakresu i limiter tempa (12 testów, clippy czysty).
