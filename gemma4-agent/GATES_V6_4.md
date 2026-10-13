# Bramki V6.4 — zamrożone **przed** jakimkolwiek przebiegiem

**Data zamrożenia:** 2026-10-13, przed pierwszym uruchomieniem. Nic nie zostało uruchomione: żaden
trigger nie istnieje, nie powstał żaden submitter V6.4, GPU nie zostało użyte.

## Czym jest V6.4

V6.3 + **cztery reguły promptu**, każda przypięta do jednego zmierzonego mechanizmu z read-only
diagnozy kerneli V6.3 (`ANALYSIS_V6_3_MECHANISMS.md`):

| reguła | mechanizm, który naprawia | pomiar bazowy (V6.3, pełny przebieg) |
| --- | --- | --- |
| **M1** „No reading without writing” — pierwsze wywołanie po przeczytaniu pierwszego pliku to próba edycji; jeśli do wywołania 6 nie ma edycji, następne wywołanie **musi** być `edit_file`/`write_file` | brak jakiejkolwiek próby edycji | 7/30 sesji bez edycji; jedna zużyła 31 wywołań na `run_command`/`read_file`; dwie skończyły same po 41 s i 108 s; mediana pierwszej edycji 179 s z 315 s |
| **M2** „If an `edit_file` call does not change the file, do not repeat it” — jedna inna kotwica, potem `write_file` całego pliku | pętla nieudanych edycji | `fastapi_15030`: 9 wywołań `edit_file` pod rząd (212–307 s), diff nadal 0 znaków |
| **M3** „`submit_patch()` … at most once” — powtórzenie submitu to sygnał do edycji, nie do ponawiania | pętla submitu zjadająca limit tur | `requests_6757` 48 wywołań, `fastapi_14077` 44, `rich_3894` 42 → wszystkie trzy padły na limicie 60 tur |
| **M4** „Never create a file to help yourself, and never write outside the repository” | zapis poza repozytorium | `fastapi_15745`: `write_file` → `/tmp/locate.py` o 279,8 s; w ścieżkach widać też `/tmp/repro.py` |

**Czego V6.4 NIE zmienia:** budżet 30 wywołań, 60 tur, 150 s na komendę, 5,25 min sesji, timeout
testów 45 s, `thinking_budget` 4096, skrypt lokalizatora. Zmiana budżetu myślenia to osobny
eksperyment (wymóg recenzji) i nie jest tu mieszana.

## Tożsamość artefaktu (weryfikowalna)

| element | wartość |
| --- | --- |
| archiwum | `gemma4-agent/submission-v6.zip`, **13 053 B**, sha256 `3843c8788c756777c6c93e9d9ada81b43ebcca5d2e1c093884a194a831726a89` |
| odtwarzalność | dwa kolejne buildy = ten sam hash (stały znacznik ZIP 1980-01-01); kontrola negatywna: podmiana jednej reguły wywala build |
| prompt | 19 166 znaków (V6.3: 17 603); diff wobec V6.3 = **+4 / −1 linia** (dokładnie cztery reguły; jedna linia zmieniona: „optional” → „optional, and you may call it at most once”) |
| lokalizator | `tools/locate.py` `fe25b200fa52e100…` **bez zmian**, bajt w bajt taki sam w ZIP i w repo |
| zamrożony prompt V6.3 | `gemma4-agent/candidates/v6-3/prompts-system.md` (17 603 znaków, sha256 `423da01cc4ddc019…`) — żeby archiwum V6.3 pozostało audytowalne |
| packer | `build_submission_v6.py` + 4 strażniki reguł i 4 strażniki pomiarów (`31 calls`, `nine consecutive`, `48 times`, `280 s`) |
| notebook | `kaggle_smoke/gemma-agent-benchmark-v6.ipynb` regenerowany dla `3843c878` |

**Uwaga o odtwarzaniu V6.3:** obecny packer egzekwuje reguły V6.4, więc **nie odtworzy** archiwum
V6.3 — to celowe (V6.3 nie jest kandydatem do wysyłki: G2 = 3). Archiwum V6.3 jest zamrożone
w historii (`3ee7dd2`) i nadal zapięte pinem w `submit_kaggle_v63_once.py`; gdyby ktoś odpalił tamten
workflow, uploader odmówi z `archive_hash_mismatch` (exit 2) — czyli bezpiecznie, nie wysyłkowo.

## Bramki (hard — bez zmian wobec V6.3)

- **G1** pliki-śmieci w diffie = 0
- **G2** przedwczesne puste drzewa (patch 0 i sesja < 280 s) = 0
- **G3** diffy wyłącznie dokumentacyjne = 0
- **G4** puste drzewa ≤ 4 — raportowane, **nie** bramkuje

## Nowa metryka mechanizmu **M5** (raportowana osobno, **nie** bramkuje wyniku)

- **pokrycie edycji** = zadania z ≥ 1 wywołaniem `edit_file`/`write_file` (liczone read-only
  z `trace-operations.json` po przebiegu). **Baseline V6.3: 23/30. Cel: ≥ 27/30.**
- raportowane razem: mediana czasu pierwszego zapisu (baseline 184,6 s), najdłuższa seria
  `submit_patch` (baseline 48), zapisy o ścieżce absolutnej (baseline `/tmp/locate.py`, `/tmp/repro.py`).

M5 mierzy **mechanizm**, nie wynik; przy n=30 nie uprawnia do twierdzenia o przewadze punktowej.

## Pre-registered oczekiwania (falsyfikowalne — zapisane przed przebiegiem)

1. **E1**: sesji bez jakiejkolwiek próby edycji ≤ 3/30 (baseline 7/30).
2. **E2**: żadna sesja nie wywoła `submit_patch` więcej niż 2 razy (baseline: 44/48/42).
3. **E3**: co najwyżej jedna sesja z serią ≥ 3 nieudanych edycji (baseline: `fastapi_15030`, 9 pod rząd).
4. **E4**: w ścieżkach brak zapisu o ścieżce absolutnej poza repo (baseline: `/tmp/locate.py`).
5. **E5**: mini-screen **nie jest prognozą** wyniku — rozstrzyga pełny przebieg (dowód z V6.3:
   `rich_3006` zginął na zegarze w mini, a w pełnym został rozwiązany).
6. **E6**: jeśli po przebiegu pokrycie edycji nadal wynosi ≤ 23/30, to **reguły promptu nie zmieniają
   zachowania** i następnym dźwigniom (telemetria, parametry, architektura) poświęcamy osobny test —
   bez ponownego „dokładania reguł".

## Plan przebiegów — **wymaga Twojego zatwierdzenia; nic nie zostało uruchomione**

1. **Mini-screen 6 zadań mechanizmowych:** `rich_3105` (M1 szybki), `rich_3043` (M1 średni),
   `fastapi_15030` (M2), `requests_6757` (M3), `fastapi_15745` (M4), `fastapi_14077` (M3 przy
   zadaniu rozwiązanym) — outdir `v6-4-miniscreen`, ~1/5 kosztu pełnego przebiegu.
2. **Pełny screening 30 zadań**, seed `20261009`, ten sam dobór zadań co V3–V6.3 — outdir
   `v6-4-benchmark`; startuje po zaliczeniu G1–G3 w mini-screenie **albo** po wyjaśnieniu porażki,
   nigdy „przy okazji” innego commita.

Reguła operacyjna z 13.10: plik-trigger wyłącznie w osobnym commicie; `git add -A` nigdy nie dotyka
`kaggle_smoke/*.trigger`.

## Reguła decyzyjna o submissji (zamrożona **przed** wynikami)

Submissja V6.4 następuje wtedy i tylko wtedy, gdy: (1) G1–G3 = 0 w **obu** przebiegach; (2) pełny
przebieg ≥ 9/30; (3) slot dzienny wolny; (4) użytkownik wyraźnie zatwierdza. Ponadto:

- **V6.4 nie ma submittera i mieć go nie będzie, dopóki (1) i (2) nie są spełnione.** Bez
  zapiętego pliku nie da się wysłać niczego przypadkiem — to celowe, po dwóch wpadkach z pinem SHA.
- Gdy warunki zajdą, submitter V6.4 (`submit_kaggle_v64_once.py`, pin `3843c878…`, komunikat „V64”,
  bramki `v6-4-miniscreen,v6-4-benchmark`) powstaje **w tym samym commicie co decyzja**, i dopiero
  wtedy `compare_screenings.py` dostaje wiersze `V6.4-mini`/`V6.4` (wcześniej walidator CI95 słusznie
  wymagałby wierszy bez wyników i czerwieniłby repo).

## Uczciwe zastrzeżenie

V6.4 nie obiecuje wyższego wyniku. Testuje cztery mechanizmy, które w V6.3 produkowały
**gwarantowane zera**. Jeśli E1–E4 przejdą, a liczba rozwiązań nie wzrośnie, to nadal użyteczna
wiedza: wiemy, że problem nie leży w regułach promptu. Jeśli E1–E4 nie przejdą, reguły są
nieskuteczne w tej formie i wracamy do projektowania — z tym samym, niemodyfikowanym progiem.
