# Hipotezy ZAMKNIĘTE — nie testować ponownie

Ten plik istnieje, żeby nikt (ja za tydzień, Ty za rok, ani kolejny agent) nie powtarzał
pracy, która już została wykonana i **dała wynik negatywny z dowodem**. Każdy wpis ma:
co sprawdzono, jak szeroko, jaki był wynik i gdzie leży surowy dowód.

Zasada: wpis trafia tutaj **tylko z dowodem**, nie z opinii. „Nie znaleźliśmy" ≠ „nie ma";
„nie ma czego testować" ≠ „nie umiemy testować".

| # | Hipoteza | Zakres testu | Wynik | Dowód |
|---|---|---|---|---|
| 1 | Path traversal w `bezpiecznymiesiac.pl/download-file/?fileUrl=` | 20 wariantów: `/etc/passwd`, `/proc/version`, `../../..`, `%2e%2e%2f`, `..%2f`, `%252e%252e`, `....//`, `..%5c` (Windows), `file://`, ścieżka absolutna, URL-e zewnętrzne i ich kodowania | **ZAMKNIĘTE** — filtr dekoduje wartość **przed** sprawdzeniem, odrzuca schematy i `..` w każdym kodowaniu (400), ścieżki absolutne bez kropek → 404 (wartość doklejana do katalogu mediów) | `Pokemon/7911f950: nask/research/02-SONDY-004-006.md` §1 |
| 2 | SSRF przez `/_next/image?url=` (optymalizator obrazów Next.js) | 7 hostów: `oad`, `zglos-dezinformacje`, `dyzurnet`, `science`, `bezpiecznymiesiac`, `116sos`, `bezpiecznewybory` + warianty `@`-bypass | **ZAMKNIĘTE** — 403 (brzeg), 404 (brak trasy), 400 (odrzucony), 308→400. Na `bezpiecznymiesiac` optymalizator istnieje i **odrzuca zdalny URL** → `remotePatterns` ograniczone | `Pokemon/7911f950` §3; `Gemma-konkurs/c4eeb067: NASK/HUNT-RAPORT-NOC` |
| 3 | CORS — odbicie obcego `Origin` | 8 endpointów API + wszystkie moje 15 hostów (`Origin: https://evil.example` i `nask.pl.evil.example`) | **ZAMKNIĘTE** — żadne API nie zwróciło `ACAO` równego wysłanemu Origin. Jedyny `ACAC: true` (HIVE, 404) występuje **bez** `ACAO` = bezużyteczny. Same `ACAO: *` bez credentials są wprost wykluczone (§8 poz. 5.6) | `Pokemon/7911f950` §4; moje `hunt.json` przebieg 3 |
| 4 | Obejście middleware Next.js (CVE-2025-29927) | 4 hosty (gałąź B) + moje 6 ścieżek na 15 hostach, nagłówek `x-middleware-subrequest: middleware×5` | **ZAMKNIĘTE** — brak przypadku „zablokowane → odblokowane". Zaobserwowane różnice to WAF (403 z innym nonce) i rate-limit (429) | `Gemma-konkurs/c4eeb067`; moje `hunt.json` przebiegi 1–3 |
| 5 | Nagłówki omijające proxy (`X-Original-URL`, `X-Rewrite-URL`, `X-Forwarded-Prefix`) | 6 ścieżek × 3 nagłówki × 15 hostów | **ZAMKNIĘTE jako obejście** — serwer reaguje, ale **odmową** (`moje.cert.pl` → 403, `incydent.cert.pl` → 429). To utwardzenie, nie luka | moje `hunt.json` przebieg 3 + testy regresyjne |
| 6 | IDOR na `science.nask.pl /api/downloadFile?fileId=` | Kontrakt ustalony (`fileId` liczbowe, `18864` → 200 `image/png` 2,2 MB), walidacja (`-1`, `18864abc`, `fileId[]` → 400), sweep 25 ID, potem **gęsty sweep 60 ID** w 4 przedziałach | **ZAMKNIĘTE** — wszystkie 200 to **publiczne zdjęcia z aktualności**, dostępne też przez `/api/media/`. Endpoint nadmiarowy wobec publicznego, brak dowodu obejścia | `Gemma-konkurs/c4eeb067: NASK/HUNT-RAPORT-NOC` §„Słabe punkty 1" |
| 7 | XSS refleksyjny w `nask.pl /api/search` | `?lang=pl`, `perPage`, `page`, `query`; refleksja w HTML | **ZAMKNIĘTE** — brak refleksji parametru. API zwraca obiekty WP (autor, ID mediów) = wyciek metadanych, wykluczony (§8 poz. 2.3) | `Gemma-konkurs/c4eeb067` §„Słabe punkty 3" |
| 8 | IDOR/BAC w HIVE (`dataannotation.pllum.org.pl`) **bez konta** | `/api/v1/projects/`, `/api/v1/users/`, `/api/v1/users/1`, OpenAPI, rejestracja | **ZAMKNIĘTE bez konta** — 401 na routerze, 405 na `users/1` (trasa istnieje), **rejestracja nie istnieje** (`/register` → 404). Kontrola działa na poziomie routera → IDOR wymaga konta, a konta nie ma jak zdobyć (regulamin: NASK nie daje kont testowych) | `Gemma-konkurs/c4eeb067` §„Słabe punkty 4" |
| 9 | Wyciek `.git/HEAD` i `.env` przez HTTP | 24 hosty × 2 ścieżki + kontrole, 1 req/s, bez podążania za przekierowaniami | **ZAMKNIĘTE** — 0 kandydatów; 9 odpowiedzi 200 dało wynik negatywny, 11 nierozstrzygający, reszta 403 | `NASK/codex/multi-program-lab: research/night-operation-2026-11-03.md` |
| 10 | Fuzzing ścieżek paneli administracyjnych słownikiem | Świadomie **nie wykonane** | **WYKLUCZONE PRZEZ REGULAMIN** — raport ze skanera bez ręcznego potwierdzenia = §8 poz. 14.4. Nie robimy tego, nawet gdyby coś „wyszło" | `SCOPE.md` §4 |
| 11 | SQLi przez GET na hostach NASK | `' OR 1=1`, boolean, czasowe | **NIESKUTECZNE** — WAF ucina payloady (status 0 / reset połączenia). Nie „brak podatności", a **brak możliwości pomiaru tą drogą** | `Gemma-konkurs/c4eeb067` §„Wnioski metodologiczne 3" |
| 13 | **XSS w atrybutach Rich na `mwdb.cert.pl` (poprawka #1272/#1274)** | Sonda S8: `GET /api/server` → `server_version` | **ZAMKNIĘTE 04.11, przebieg 4** — produkcja stoi na **2.20.0**, czyli poprawka **jest wdrożona**. Temat zamknięty bez potrzeby zakładania konta | `nask/findings/hunt.json` (S8) |
| 14 | IDOR/niezabezpieczone `/users/{id}/…` na `hack.cert.pl` **bez sesji** | Sonda S7: 4 trasy z bundla × 2 identyfikatory × 2 prefiksy (`""`, `/api/v1`) | **ZAMKNIĘTE bez sesji** — żadna trasa nie zwróciła 2xx z danymi. To oczekiwane (API wymaga tokenu), ale zamyka wariant „anonimowy odczyt cudzego profilu". Wariant **z sesją pozostaje otwarty** i wymaga konta | `nask/findings/hunt.json` (S7) |
| 15 | Wagtail/Django `/api/v2/documents` na `moje.cert.pl`, `nask.pl`, `science.nask.pl` | Sonda S9: 3 trasy, odpalana tylko przy wykryciu Django | **ZAMKNIĘTE** — brak odpowiedzi JSON z `items`; endpoint nie istnieje lub nie jest wystawiony | `nask/findings/hunt.json` (S9) |

| 16 | SSRF/odczyt przez `oad.nask.pl/podglad-pdf?url=` | Parametr `url` + wartości: `http://169.254.169.254/`, `https://example.com/x.pdf`, ścieżki spoza prefiksu `/media/` | **ZAMKNIĘTE** — serwer waliduje **prefiks `/media/`**; wartość spoza prefiksu → **500 bez danych**, brak pobierania po stronie serwera, pobranie odbywa się po stronie klienta. Martwe | `Pokemon/c87f7a48: nask/REJESTR-LEADS-20261104.md` (L6) |
| 17 | Path traversal na `science.nask.pl` mierzony **surowym gniazdem TCP** (nie klientem HTTP) | 7 wariantów `%2e%2e`, `%252e%252e`, `....//`, ścieżki absolutne; pomiar status/rozmiar/sha256 | **ZAMKNIĘTE, powtarzalne 7/7** — identyczne statusy/rozmiary/sha256; `%2e` normalizowane przez nginx **przed** aplikacją, `%252e%252e` → 404 (brak podwójnego dekodowania). To nie „nie dało się zmierzyć" — to negatyw zmierzony poprawnym klientem (poprzedni pomiar reqwestem był nieważny: normalizował `../`) | `Pokemon/c87f7a48: nask/lab/RAWPATH-001..003` |
| 18 | Bundle `mSzyfr` (`komunikator.narodowy.gov.pl`) do analizy offline | 3 próby pobrania `.js` curl-em | **NIE DO ZMIERZENIA AUTOMATEM** — brama zwraca **catch-all 200 HTML** dla `.js` poza przeglądarką. Ograniczenie metody, nie negatyw: bundle jest osiągalny tylko z DevTools. Wpis NIE zamyka hosta — zamyka wariant „maszynowy" | `Pokemon/c87f7a48`; `HIVE`/mSzyfr notatki sesji 5ed750ef |
| 19 | Wyciek `.git/HEAD` i `.env` — **pomiar z parami kontrolnymi** (uzupełnienie #9) | 24 dokładne hosty × 2 ścieżki + **2 adresy kontrolne na host**, 1 req/s, bez przekierowań, hashe 4 regulaminów sprawdzone **przed** ruchem | **ZAMKNIĘTE** — 75 żądań, 68 odpowiedzi, 9× 403, 0× 429, min. odstęp 1,000082 s; z 20 zachowanych treści: 9 negatywów, 11 nierozstrzygniętych, **0 kandydatów**. Mocniejszy dowód niż #9 (kontrola parami) | `NASK/codex/multi-program-lab: research/night-operation-2026-11-03.md`, przebieg `41734282345` |
| 12 | `zglos-dezinformacje.nask.pl /api/sendForm` (SSRF, upload) | Kontrakt ustalony z bundle'a, GET → 405 (POST-only) | **NIEROZSTRZYGNIĘTE — wymaga człowieka.** reCAPTCHA v3 wykonywana w przeglądarce; brak tokenu kończy żądanie **przed** wysłaniem. Automat nie może tego sprawdzić | `Pokemon/7911f950: nask/research/01-RUN-003-WYNIKI.md` §3 |

## Czego ta lista NIE mówi

1. **Nie mówi „nie ma luk".** Mówi: te jedenaście dróg sprawdzono i albo dały wynik
   negatywny, albo nie da się ich zmierzyć tym klientem, albo wyklucza je regulamin.
2. **Nie zwalnia z myślenia.** Nowa luka może być w funkcji, której nikt z nas nie
   zobaczył: eksport CSV z danymi osobowymi, „udostępnij raport linkiem", reset hasła
   przez token w URL, panel moderatora z IDOR-em. Tego nie ma na żadnej liście powyżej.
3. **Nie obejmuje żadnej powierzchni zalogowanej** — a tam jest wszystko, co zostało.

## Jak dopisywać nowe wpisy

Wymagane trzy rzeczy: **szerokość testu** (ile wariantów, jakie kodowania), **surowy
wynik** (statusy, rozmiary, treści) i **ścieżka do dowodu** w repo. Bez tego wpis jest
opinią i nie ma prawa blokować czyjejś przyszłej pracy.
