# Mapa porażek V6.4 (pełny przebieg 30 zadań) — gdzie naprawdę tracimy zadania

Stan: 2026-10-14. Wszystkie liczby pochodzą z zapisanych artefaktów (`agent_benchmark_result.json`,
`traces/trace-operations.json`), nie z osądu. Narzędzia: `tools/audit_failure_taxonomy.py`,
`tools/audit_locator_ranks.py`, `tools/locate_excerpt_coverage.py`. Zero GPU.

## 1. Podział 30 zadań na koszyki

| koszyk | ile | % zadań | co to znaczy |
| --- | --- | --- | --- |
| **P** rozwiązane | 10 | 33 % | — |
| **N** brak jakiejkolwiek zmiany w repo | **11** | **37 %** | `patch_chars = 0` (puste drzewo = pewne zero) |
| **R** edycja dobrego pliku, patch nie przechodzi | **8** | **27 %** | plik ze złotego patcha był dotknięty, testy padły |
| **W** edycja złego pliku | **1** | 3 % | `fastapi_14482` |

**Wniosek 1: lokalizator nie jest głównym wąskim gardłem.** Tylko 1 zadanie z 20 przegranych
poległo na edycji złego pliku. Dwie prawdziwe dziury to „nic nie zrobił" (11) i „zrobił, ale źle" (8).

## 2. Ranking lokalizatora a wynik (prawdziwy join, nie tautologia)

`localized` w wyniku benchmarku to `touched ∩ gold` — czyli **skutek**, nie przyczyna. Rankingi
odtworzyłem offline skryptem, który jedzie w paczce (`submission-v6.6/tools/locate.py`):

| koszyk | gold na #1 | #2–3 | #4–5 | #6–10 | poza top-10 |
| --- | --- | --- | --- | --- | --- |
| P rozwiązane (10) | 7 | 2 | 0 | 1 | 0 |
| **N brak edycji (11)** | **5** | 1 | 1 | 0 | **4** |
| **R zły patch (8)** | **5** | 0 | 1 | 1 | 1 |
| W zły plik (1) | 0 | 0 | 0 | 0 | 1 |

- **5 zadań z koszyka N miało złoty plik na pozycji #1** i sesja nie zmieniła nic.
- 6/11 miało go w top-3. Czyli: dla większości koszyka N to nie jest problem wyszukiwania.
- Rekall lokalizatora na tej próbce: top-1 17/30 (57 %), top-3 20/30 (67 %), miss 7/30 (23 %) —
  zgodne z deklaracją w prompcie (66 % / 73 %).

## 3. Ile kosztuje faza „przed pierwszą edycją"

Z 22 sesji, które w ogóle edytowały (traces):

| miara | wartość |
| --- | --- |
| wywołań przed 1. edycją | mediana **10** (w tym mediana **4 `read_file`**; łącznie 132 `run_command` + 101 `read_file`) |
| czas do 1. edycji | mediana **176 s** z 315 s budżetu; p90 = 265 s |
| edycja w terminie „call 4" | 1/30 |

**Budżet a wynik** (30 zadań, limit 30 wywołań / 315 s):

| pasmo | zadań | rozwiązane |
| --- | --- | --- |
| skończyło przed oboma limitami | 4 | 50 % |
| uderzyło w limit 30 wywołań | 7 | 43 % |
| uderzyło w zegar (≥300 s) | 19 | **26 %** |

**Wniosek 2: połowa budżetu idzie na orientację przed jakąkolwiek zmianą.** Zadanie, które dobija
do zegara, ma potem ~139 s na dopracowanie i weryfikację — i rozwiązuje się 3× rzadziej.

## 4. Co dokładnie robiły sesje bez edycji (koszyk N = 11)

| mechanizm | zadania | uwaga |
| --- | --- | --- |
| napisała **tylko** `/tmp/locate.py` i skończyła | 4 (`fastapi_15588`, `fastapi_15745`, `httpx_3672`, `rich_3043`) | pułapka lokalizatora; **adresuje ją V6.6**; 2 z nich miały gold na #1/#2 |
| nie napisała nic, tylko czytała/komendowała | 4 (`fastapi_14266` 31 wyw., `fastapi_14459` 18, `rich_3934` 11, `rich_3105` 8 w 74 s — koniec z własnej woli) | `rich_3934` miał gold na **#1** i przeczytał cały budżet |
| **pierwsza edycja odrzucona przez sufit 30 wywołań** (2 zadania) | 2 (`fastapi_14851` — próba na wywołaniu 32, `fastapi_14487` — na 31; `fastapi_14953` dostał ten sam błąd dwa razy) | surowy ślad: `{"status": "error", "error_type": "BudgetExceeded", "error_message": "Tool call budget exhausted (30 calls)"}` — to nie jest „edycja nie trafiła w drzewo", tylko edycja **nigdy nie została wykonana** |
| **edycja pliku, który grader odrzuca** (1 zadanie) | 1 (`requests_6757` — dwa udane `edit_file` w `tox.ini`, każde potwierdzone diffem) | `tox.ini` jest resetowane przez grader (prompt mówi to od V6.4), więc udana edycja jest niewidoczna: drzewo zostało puste, a złote pliki to `src/requests/compat.py` i `src/requests/utils.py` |

**Korekta 2026-10-14 (surowy ślad wywołań, `analysis/diagnostics-2026-10-14/v64-raw-calls.md`).**
Pierwsza wersja tej tabeli opierała się na parowaniu wywołanie→wynik, które przesuwało się
o jeden przy każdym zdarzeniu bez wywołania narzędzia; dlatego edycja w `requests_6757`
wyglądała na zwróconą przez `grep`, a `fastapi_14851` na cudzy odczyt pliku. Po naprawie
parowania (`ffbc55e`) trzy mechanizmy okazały się dwoma innymi niż opisane powyżej
(wiersze zaktualizowane) — w tym dwa, których żaden wcześniejszy przebieg nie nazwał:
sufit wywołań **odrzuca** pracę zamiast ostrzegać, a udana edycja pliku resetowanego
przez grader jest niewidoczna. Oba mają reguły w V6.7 (`GATES_V6_7.md`).

## 5. Wynik negatywny, który zaoszczędził slot GPU (dźwignia L3, odrzucona)

Pomysł: lokalizator wypisuje **wycinki kodu** wokół dopasowanych linii dla top-2 kandydatów, żeby
pierwsza edycja była wykonalna bez fazy czytania. Zmierzone offline na 128 zadaniach
(`tools/locate_excerpt_coverage.py`, ranking identyczny z wersją shippowaną):

| miara | wynik |
| --- | --- |
| złoty plik w top-2 | 66/128 |
| z tego: wycinek zawiera **choć jedną** linię z hunka złotego patcha | 30/66 (45 %) |
| pełne pokrycie linii hunka | **1/56** |
| mediana pokrycia | **0 %** |
| rozmiar wyjścia lokalizatora (8 kandydatów) | mediana ~2,0 tys. znaków, max 3,3 tys. |

**Powód:** miejsce naprawy zwykle **nie leży tam, gdzie dosłownie występują słowa z issue**
(słowa trafiają w importy, sygnatury i wzmianki). Wycinek „wokół dopasowań" nie dowozi kodu do
edycji, więc **nie wysyłamy tego jako osobnego ramienia na GPU**.

## 6. Ryzyko systemowe: arytmetyka 12 godzin

Reguły: 12 h na **wszystkie** zadania, łącznie z setupem sandboxa; split testowy ~120 zadań
(podział public/private po ~60). Nasze zmierzone: średnio **298 s** na zadanie przy limicie 5,25 min.

| liczba zadań | 5,25 min + ~30 s setup | margines do 12 h |
| --- | --- | --- |
| 120 | ~11,0 h | ~1,0 h |
| 130 | ~11,9 h | ~0,1 h |
| 140 | ~12,8 h | **przekroczone** |

Przekroczenie 12 h oznacza, że końcowe zadania nie dostają w ogóle patcha. Nie zmieniamy limitów
bez dowodu, ale to jest kandydat na dźwignię **parametryczną** (np. 5,0 min), gdyby pomiar na
V6.5/V6.6 pokazał, że zadania ginące na zegarze i tak nie są rozwiązywane (26 % vs 50 %).

## 7. Gdzie jest następna dźwignia (kolejność wg dowodów)

1. **Koszyk N (11 zadań)** — V6.5 (framing decyzji) i V6.6 (lokalizator bez pliku) są zbudowane i
   czekają na sobotni reset kwoty; 4 z 11 to dokładnie pułapka `/tmp/locate.py`.
2. **Koszyk R (8 zadań)** — nikt tego nie adresuje. 5/8 miało złoty plik na #1. Bez tekstu patchy
   nie wiadomo, czy to zły hunk, niepełna naprawa, czy brak weryfikacji → **pobieramy surowe ślady
   z kernela V6.4 (workflow `gemma-kaggle-v64-diagnose.yml`), żeby zobaczyć konkretne edycje.**
3. **Mechanizm „pusty diff mimo `edit_file`" (3 zadania)** — dodać do kroku edycji tani dowód, że
   zmiana jest na dysku (`git diff --stat`) — o ile diagnostyka potwierdzi cichy błąd edycji.
4. **Rekall lokalizatora (7/30 miss)** — realny, ale najmniejszy z czterech; wraca na stół po
   diagnozie R.

## 8. Czego ta analiza nie twierdzi

- Nie mówi, że którykolwiek z powyższych mechanizmów *powoduje* porażkę — to współwystępowanie na
  n=30; rozstrzygnięcie przyniesie porównanie parami po sobotnich przebiegach.
- Nie zmienia zamrożonych progów R1–R4 ani decyzji o submissji V5 (już wysłanej, ref `57188055`).
- Publiczny screening 30 zadań nadal nie jest prognozą wyniku ukrytego (`screening_history.md` §„Uczciwe ramy").
