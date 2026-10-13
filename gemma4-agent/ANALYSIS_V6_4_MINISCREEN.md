# V6.4 mini-screen — wynik i werdykt (2026-10-13, ~12:05 UTC)

Przebieg: kernel `petersharps/gemma-agent-benchmark-aaea34e4-20261013-111908` (L4x4), archiwum
`aaea34e4…` (13 455 B, sha zgodny z `run.json`), 6 zadań mechanizmowych, 12:03 UTC, 45 min,
średnio 289,9 s na zadanie. Pre-rejestracja: `GATES_V6_4.md`, sekcja „Pre-rejestracja mini-screenu
V6.4" — zapisana **przed** wypchnięciem triggera.

## Wynik w jednym akapicie

**Nie zdobyliśmy ani jednego rozwiązania i nie straciliśmy żadnego.** Dwa z czterech mechanizmów
zostały naprawione **na poziomie zachowania**: pętla nieudanych edycji (M2) zniknęła, a pętla
`submit_patch` (M3) nie może już wystąpić, bo narzędzia nie ma — oba zadania, które w V6.3 kończyły
puste, **teraz zostawiają patch** (0 → 1348 B i 0 → 377 B). Nie udało się natomiast ruszyć
**terminu pierwszej edycji** (0/6 w call 4, dokładnie tyle samo co baseline) ani trzech sesji, które
w ogóle nie edytują, mimo że V6.3 miało ich pięć. Bramka jakości G2 pękła na jednym zadaniu, więc
zgodnie z zamrożoną regułą decyzyjną **V6.4 nie może zostać wysłany** — i nie zmieniam tego po
zobaczeniu wyniku.

## Liczby: V6.3 → V6.4 na tych samych 6 zadaniach

| zadanie | patch V6.3 | patch V6.4 | zmiana | mechanizm V6.3 | co się stało |
| --- | --- | --- | --- | --- | --- |
| `rich_3105` | 0 | 0 | — | M1 szybki (43 s, 7 wywołań) | 107 s, **15 × `run_command`**, zero edycji — sesja sama kończy, nie zabija jej zegar |
| `rich_3043` | 0 | 0 | — | M1 średni | 322,7 s, 8 × `run_command` + 4 × `read_file`, zero edycji |
| `fastapi_15030` | 0 | **1348** | **M2 naprawiony** | 9 edycji pod rząd, 212 s | edycja w repo w call 8, najdłuższa seria **2** |
| `requests_6757` | 0 | **377** | **M3 naprawiony** | 48 × `submit_patch` | 0 wywołań `submit_patch`; patch na `setup.py` (zły plik, nie rozwiązany) |
| `fastapi_15745` | 0 | 0 | M4 częściowo | tylko `/tmp/locate.py` o 279,8 s | **żadnego zapisu poza repo** (10 × `read_file fastapi/routing.py`), ale nadal zero edycji |
| `fastapi_14077` | 2443 **PASS** | 2443 **PASS** | kontrola OK | 44 × `submit_patch`, zadanie rozwiązane | 0 × `submit_patch`, **nadal rozwiązany** (241 s) |
| **razem** | **1/6** | **1/6** | +0 / −0 | 5 pustych drzew | 3 puste drzewa |

## Nowa, ostrzejsza diagnoza: sesje „uwięzione w rozpoznaniu"

Trzy zadania, które nadal kończą puste, mają wspólny wzorzec i **nie jest to brak reguły**:

- `rich_3105`: 15 wywołań `run_command` w 107 s, potem koniec sesji — **nie na zegarze** (limit to
  315 s), lecz z własnej decyzji modelu;
- `rich_3043`: 8 × `run_command` + 4 × `read_file` w 322,7 s — koniec na zegarze, bez edycji;
- `fastapi_15745`: 10 × `read_file fastapi/routing.py` + 8 × `run_command` w 336,7 s — koniec na
  zegarze, bez edycji.

Prompt zawierał jawny, liczbowy termin („an intended edit must exist on disk by call 4; stop searching
by call 14") i **został zignorowany**: mediana pierwszej edycji w repo to wywołanie **7** (baseline
dla tych zadań: 8), w terminie call 4 zmieściło się **0/6**. To dokładnie ta klasa porażki, o której
mówi E6: kolejne reguły promptu nie zmieniają zachowania, bo model nie „nie wie", że ma edytować —
on **wybiera dłuższe rozpoznanie**, aż skończy się czas.

Różnica wobec V6.3 jest jednak realna i warta odnotowania: `rich_3105` w V6.3 kończyło po 43 s
**przedwczesną submissją** (7 wywołań), a `fastapi_15745` pisało `/tmp/locate.py` i to był jego cały
wkład. W V6.4 obie te patologie zniknęły — zostało to samo jądro problemu: **brak edycji**.

## Bramki jakości (pre-registered, liczone z JSON-a, nie z narracji)

| bramka | V6.4 mini | V6.3 mini | V6.3 pełny | werdykt |
| --- | --- | --- | --- | --- |
| **G1** pliki-śmieci w diffie = 0 | **0** | 0 | 0 | PASS |
| **G2** przedwczesne puste drzewa = 0 | **1** (`rich_3105`, 106,9 s) | 0 | 3 | **FAIL** |
| **G3** diffy wyłącznie dokumentacyjne = 0 | **0** | 0 | 0 | PASS |
| **G4** puste drzewa ≤ 4 (nie bramkuje) | **3** | 0 | 11 | raportowane |

Uwaga o G1: `requests_6757` dotknęło `setup.py`, ale to **prawdziwy plik repozytorium `requests`**,
nie plik roboczy — automatyczna heurystyka w moim skrypcie oznaczyła go jako podejrzany, ręczna
weryfikacja to odrzuca. Zero plików-śmieci.

**Skutek zamrożonej reguły decyzyjnej:** submissja wymaga G1–G3 = 0 w **obu** przebiegach.
Mini-screen ma G2 = 1 → **V6.4 nie może zostać wysłany**, niezależnie od wyniku pełnego przebiegu.
Reguła zadziałała zgodnie z projektem (tak samo jak przy V6.3) i nie ruszam jej po fakcie.

## Werdykt mechaniczny P1–P5 (wygenerowany skryptem, nie przepisany ręcznie)

# V6.4 mini-screen — wynik wobec pre-rejestracji (P1-P5)

| zadanie | patch | PASS | 1. edycja w repo | plik | czas | seria edycji | submit | zapisy /tmp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rich_3105` | 0 | nie | **brak** | — | — | 0 | 0 | — |
| `rich_3043` | 0 | nie | **brak** | — | — | 0 | 0 | — |
| `fastapi_15030` | 1348 | nie | 8 | fastapi/responses.py | 181.4 | 2 | 0 | — |
| `requests_6757` | 377 | nie | 7 | setup.py | 188.7 | 3 | 0 | — |
| `fastapi_15745` | 0 | nie | **brak** | — | — | 0 | 0 | — |
| `fastapi_14077` | 2443 | TAK | 7 | pyproject.toml | 42.2 | 6 | 0 | — |

## Werdykt mechaniczny

- **P1**: NARUSZONE — edycja w repo w terminie call 4: 0/6 (cel >= 4/6, baseline 0/6)
- **P2**: NARUSZONE — puste drzewa: 3/6 (cel <= 1/6, baseline 5/6)
- **P3**: SPEŁNIONE — wywołania submit_patch: 0 (cel 0, baseline dziesiątki)
- **P4**: SPEŁNIONE — fastapi_15030 najdłuższa seria edycji: 2 (cel < 3, baseline 9)
- **P5**: SPEŁNIONE — fastapi_14077 rozwiązany: True (cel PASS, baseline PASS)

> **FALSYFIKACJA (E6):** P1 <= 2/6 lub P2 > 1/6 — reguły promptu **nie zmieniają zachowania**; następne dźwignie (telemetria, parametry, architektura) dostają osobny test, bez dokładania reguł.

- edycja w repo: pokrycie 3/6, w terminie call 4: 0/6
- puste drzewa: 3/6 = rich_3105, rich_3043, fastapi_15745
- rozwiązane: 1/6

## Co to znaczy dla następnego kroku (E6)

Trzy mechanizmy z czterech **zmieniły zachowanie** (M2, M3, częściowo M4), ale dwa cele
pre-rejestrowane **nie zostały osiągnięte** (P1, P2), więc klauzula falsyfikacji zadziałała i nie
wolno mi twierdzić, że „reguły promptu naprawiły problem". Uczciwy wniosek jest węższy:

1. **Reguły promptu naprawiają pętle** (M2: 9 → 2 kolejne edycje; M3: 48 wywołań → 0), bo pętla to
   wzorzec, który da się nazwać i zakazać.
2. **Reguły promptu nie naprawiają decyzji o rozpoznaniu.** Termin „edytuj do call 4" był w prompcie
   i został zignorowany w 6/6 zadań. To nie jest problem wiedzy, tylko wyboru kolejności działań.
3. Dlatego następna dźwignia musi być **inna niż kolejna reguła** — tak jak mówi E6: mechanizm
   wymuszający edycję (architektura: kolejność/budżet narzędzi), parametr (budżet myślenia, limit
   wywołań, tak by ostrzeżenie `budget_warning` odpalało się wcześniej) albo telemetria, która
   pokaże, ile z 315 s zjada rozpoznanie.

Zapisane w `GATES_V6_4.md`: V6.4 nie jest kandydatem do wysłania, ale jego reguły M2/M3 są
**zmierzone jako skuteczne** i wchodzą do V6.5.
