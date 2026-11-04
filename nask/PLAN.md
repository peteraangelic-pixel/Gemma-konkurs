# Plan na 28 dni (03.11 – 30.11.2026)

Zasada: **jeden cel na raz, każdego dnia coś, co da się pokazać w raporcie.**

> **KOREKTA po nocy 03/04.11** (dane w `WYNIKI-NOCY.md`): kolejność się zmienia.
> 1. `hack.cert.pl` — awans z dalszego miejsca na **pierwsze**: bundel ujawnia trasy
>    `/users/{id}/view`, `/users/{id}/email`, `/users/me/profile/payout` i `/auth/session/activity`.
>    To sama platforma, Tier 1, dane wypłat. Konkurencja patrzy na programy, nie na nią.
> 2. `mwdb.cert.pl` — najpierw **jedno żądanie**: `/api/server`. Wersja < 2.20.0 znaczy,
>    że poprawka XSS w atrybutach Rich nie jest wdrożona; wersja ≥ 2.20.0 zamyka temat.
> 3. IDOR w `mwdb` schodzi na dalszy plan — przegląd kodu pokazał poprawną, wspólną
>    ścieżkę `access_object → Object.access`.
> 4. `eobieg.wladyslawowo.pl` — **wypada całkowicie** (decyzja użytkownika).
> Konkret do wykonania rano: `DO-ZROBIENIA-RANO.md` (15 minut, trzy kryteria tak/nie).

## Tydzień 1 (3–9.11) — dostęp i dwie tanie weryfikacje

| dzień | zadanie | wynik, który ma zostać |
|---|---|---|
| 1 | przegląd scope + rejestracja kont (mSzyfr, mwdb, moje.cert.pl, n6portal) | konta działają; `nask/nask.py scope --list` zgodny z platformą |
| 2 | **mwdb**: uruchomienie `mwdb-core` lokalnie (Docker) i przegląd kodu pod kątem `get()` bez sprawdzenia właściciela | lista 5–15 miejsc do sprawdzenia na produkcji |
| 3 | **CORS** na `www.gov.pl` (1 dzień, EV/dzień najwyższe) | raport TAK/NIE — jeśli TAK, zgłoszenie tego samego dnia |
| 4 | **mass assignment** w komunikatorze: rejestracja, próba `role`/`is_admin`/`is_verified` | raport TAK/NIE |
| 5 | weryfikacja hipotez z dnia 2 na `mwdb.cert.pl` (własne konto, dwa obiekty) | pierwszy kandydat IDOR albo dowód „nie ma” |
| 6–7 | **`incydent.cert.pl` / `moje.cert.pl`** — IDOR na zgłoszeniach i koncie (wolimy to od gminy: 9 000 zł zamiast 4 000 zł za tę samą pracę) | raport |

**Kamień milowy tygodnia 1: co najmniej jedno zgłoszenie wysłane.** Nie „prawie gotowe”.

## Tydzień 2 (10–16.11) — mwdb do końca + narzędzie w Rust

- dokończenie przeglądu `mwdb-core`: uprawnienia grup, share linki, eksporty, upload/parsery.
- **jedyny moduł w Rust + Rayon**: skaner reguł po kodzie źródłowym (szuka `Objects.get`
  bez `access_control`), uruchamiany na pełnym drzewie repo w sekundy.
- `n6portal.cert.pl`: riznice uprawnień między rolami, endpointy API.
- każde znalezisko → `nask/findings/registry.jsonl` + `evidence.jsonl`.

## Tydzień 3 (17–23.11) — komunikator i serwisy NASK

- `komunikator.narodowy.gov.pl`: IDOR na wiadomościach/urządzeniach, sesje, urządzenia.
  To najcenniejszy cel (20 000 zł), ale i najbardziej prawdopodobny duplikat — dlatego
  nie jako pierwszy, a jako trzeci.
- `zglos-dezinformacje.nask.pl`: SSRF w polu źródła + upload załączników.
- `dns.pl`: dane abonenta w whois, możliwy IDOR.

## Tydzień 4 (24–30.11) — domknięcie i raporty

- odpowiedzi na pytania weryfikatora (to podnosi szanse na wyższą kategorię);
- drugi przebieg po miejscach oznaczonych „prawdopodobne, brak dowodu”;
- **nic nowego nie zaczynać po 27.11** — raport musi zdążyć przed 30.11.

## KOREKTA 2 (po przeglądzie 6 równoległych gałęzi, 04.11)

Wszystkie gałęzie razem: **~2 900 żądań, 0 potwierdzonych podatności**. Publiczna
powierzchnia NASK jest utwardzona na wszystko, co da się sprawdzić bez konta.
Szczegóły i dowody: `PRZEJALEM-Z-GALEZI.md`, `HIPOTEZY-ZAMKNIETE.md`.

**Zostają trzy drogi i wszystkie wymagają zalogowanej przeglądarki, nie narzędzia:**

| # | droga | dlaczego | co blokuje | stawka |
|---|---|---|---|---|
| 1 | `hack.cert.pl` — `/users/{id}/view`, `/email`, `/role`, `/me/profile/payout`, awatar | Tier 1, sama platforma, dane wypłat; konkurencja patrzy na programy, nie na platformę | konto + 2 sesje | 9 000–20 000 zł |
| 2 | `zglos-dezinformacje` — upload (SVG z JS → stored XSS w panelu moderatora) | treść od niezaufanego użytkownika ogląda pracownik | reCAPTCHA v3 = tylko przeglądarka | 4 000–9 000 zł |
| 3 | `mwdb.cert.pl` — XSS w atrybutach Rich, **jeśli wersja < 2.20.0** | mamy kod i znamy wektor | `curl /api/server` | 4 000–9 000 zł |

**Wypadają** (z dowodami w `HIPOTEZY-ZAMKNIETE.md`): HIVE (rejestracja nie istnieje →
IDOR bez konta niemożliwy), `moje.cert.pl` do czasu wyjaśnienia konfliktu regulaminów,
Władysławowo (decyzja użytkownika), cała powierzchnia bezstanowa.

**Reguła na resztę miesiąca:** nie uruchamiamy kolejnego przebiegu sieciowego bez
nowej hipotezy. Kolejne 700 żądań po tej samej powierzchni nie zmieni wyniku —
zmieni go jedna funkcja, której jeszcze nie widzieliśmy, albo jedno konto.

## Reguły, których nie łamiemy nigdy

1. Tylko hosty z `nask/tools/scope.py`. Wątpliwość = `nask.py scope <host>`.
2. ≤ 5 req/s, w praktyce 4,5 (limiter odmawia startu powyżej).
3. Zero testów obciążeniowych, zero DoS, zero spamu powiadomieniami.
4. Tylko własne konta.
5. Żadnych danych innych użytkowników w dowodach — dowodem jest **metadane i dwa własne
   obiekty**, nie zrzut cudzych rekordów. Odczyt cudzych danych ograniczamy do minimum
   niezbędnego do udowodnienia (i to opisujemy w raporcie).

## Definicja sukcesu (realistyczna)

- **minimum:** 1 zgłoszenie, kompletne, z PoC → 600–4 000 zł i wpis w rankingu.
  (Realistycznie: 600–9 000 zł. Władysławowo dawało maks. 4 000 zł i dlatego wypadło.)
- **dobry scenariusz:** 1 × IDOR/BAC (9 000 zł) + 1 × mała (600–1 000 zł).
- **bardzo dobry:** 1 × klasa 03/09 masowy odczyt (9 000–20 000 zł).
- **porażka, której unikamy:** 20 „potencjalnych” zgłoszeń bez PoC → odrzucone, zero wiarygodności.
