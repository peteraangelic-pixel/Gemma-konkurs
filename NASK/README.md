# NASK / hack.cert.pl — projekt (start 2026-11-03)

Katalog nowego projektu. ARC-AGI zamknięty: `../ARC3/CLOSING-2026-11-03.md`.

## Co to jest

Platforma bug bounty CERT Polska / NASK, **5 równoległych programów**, edycja **3–30.11.2026**.
Nagroda za *potwierdzoną* podatność: Tier 1 **600 / 4 000 / 9 000 / 20 000 zł** (niska → krytyczna),
Tier 2 **300 / 2 000 / 4 500 / 10 000 zł**. Pula edycji na program: **100 000 zł**.
Płacą **w trakcie** edycji, ale „kto pierwszy, ten lepszy” — duplikat = 0.

## Zanim cokolwiek zrobisz

1. Konto na <https://hack.cert.pl> (Login.gov.pl), akceptacja regulaminu platformy **i** programu.
2. Przeczytaj `PLAN-30-DNI.md` §0 — tam są cztery zasady, których złamanie = dyskwalifikacja
   albo brak wypłaty (limit 5 req/s, własne konta, tylko domeny z §5, PoC obowiązkowe).
3. Ten katalog **nie zawiera** żadnych danych uwierzytelniających, ciasteczek ani zrzutów
   z cudzymi danymi. Zrzuty HAR trzymaj lokalnie, w `private/` (ignorowanym przez git).

## Stan wiedzy z innych sesji (nie duplikować!)

Praca nad tym konkursem istnieje już w trzech miejscach — **czytaj, zanim napiszesz nowe**:

| gdzie | co tam jest | ocena |
|---|---|---|
| `peteraangelic-pixel/NASK` @ `arena/a29ca234-nask` | `STRATEGIA.md`, `nask-codex/research/*`, `python/jsminer.py`, `python/ffi_native.py`, szablony raportów | dobry materiał strategiczny; **kod Rust nie kompiluje się**, narzędzia nie mają limitera ani guardu zakresu |
| `peteraangelic-pixel/NASK` @ `codex/multi-program-lab-20261103` | porównanie **wszystkich 5 programów**, regulaminy PDF+TXT, `tools/recon` (Rust+Python FFI) | najlepsze źródło faktów o zakresach i stawkach; testy offline |
| Google Drive `1tWcRm79xe…` | `00`–`12`: strategia, rekonesans 12 domen, plan, rejestr zgłoszeń, szablon raportu, generator | rekonesans **pasywny** (204 żądania, 0 ekspozycji); najbliższy realnej robocie |

Ten katalog dodaje to, czego tam **nie ma**:

1. `PLAN-30-DNI.md` — plan z **bramkami decyzyjnymi** i budżetem godzin, nie lista życzeń.
2. `IDEAS.md` — pomysły policzone **wartością oczekiwaną na godzinę**, z jawnym „tego nie zrobię”.
3. `tools/nasktriage/` — narzędzie w **Rust + Rayon**, które robi jedną rzecz, której nie robi
   żadne z istniejących: **offline'ową analizę różnicową zrzutów HAR z dwóch własnych kont**
   (IDOR / asymetria uprawnień / token w URL) + twardy limiter i guard zakresu jako biblioteka.
   Testy w CI, zero ruchu sieciowego w kodzie.
4. `PRZEGLAD-KODU.md` — co dokładnie jest zepsute w istniejących narzędziach i w jakiej kolejności
   to naprawiać.

## Zasada, która decyduje o wszystkim

W tym konkursie **wąskim gardłem nie jest moc obliczeniowa, tylko czyjaś głowa**.
Limit 5 żądań/s oznacza, że 100 000 żądań to 5,5 godziny — a i tak nic nie znajdą, jeśli nie ma
hipotezy. Rust i 16 rdzeni pomagają **offline** (analiza JS, klastrowanie odpowiedzi, haszowanie
tysięcy zrzutów) i tam są użyte. Nie pomogą w wymyśleniu, że w formularzu zgłoszeń jest IDOR.
