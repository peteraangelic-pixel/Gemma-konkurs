# V6.4 pełny przebieg — wynik i werdykt (2026-10-13, 15:18 UTC)

Kernel `petersharps/gemma-agent-benchmark-aaea34e4-20261013-122940`, archiwum `aaea34e4…`
(zgodne z `run.json`), te same 30 zadań i seed `20261009` co V3–V6.3, 169 min, średnio 298,4 s na zadanie.
Dane: `kaggle_results/v6-4-benchmark/{agent_benchmark_result.json,run.json,traces/}`.

## Wynik: V6.4 jest repliką V6.3 na tej próbce

| miara | V6.3 | V6.4 | zmiana |
| --- | --- | --- | --- |
| rozwiązane | **10/30** | **10/30** | **+0 / −0 parami — ten sam zbiór zadań** |
| CI95 (Wilson) | [19,2; 51,2] | [19,2; 51,2] | — |
| puste drzewa (G4) | 11 | **11** | 0 (wymiana: `fastapi_15030` naprawione, `fastapi_15588` zepsute) |
| G1 pliki-śmieci | 0 | 0 | — |
| **G2 przedwczesne puste** | 3 | **3** | 0 (inne zadania: `fastapi_14487`, `rich_3105`, `fastapi_15588`) |
| G3 tylko dokumentacja | 0 | 0 | — |
| średni czas zadania | 252,7 s | 298,4 s | +45,7 s (dłużej, bez zysku) |

**Werdykt mechaniczny pre-rejestracji S1–S3 z tej sesji:**

- **S1** (≥ 10/30): **spełnione** — 10/30, ale to *równość*, nie poprawa.
- **S2** (puste ≤ 8): **NARUSZONE** — 11, tyle samo co V6.3.
- **S3** (G1 = G3 = 0 i G2 ≤ 1): **NARUSZONE** — G2 = 3.

→ **V6.4 nie spełnia warunku submissji.** Zgodnie z zamrożoną regułą: nie wysyłamy.

## E6 i E7: czy reguły w ogóle zmieniły zachowanie?

Z pełnych śladów operacyjnych (30 zadań, `traces/trace-operations.json`):

| metryka M5 | V6.3 | V6.4 | ocena |
| --- | --- | --- | --- |
| pokrycie zapisów (dowolny `edit_file`/`write_file`) | 23/30 | **26/30** | lekka poprawa zachowania |
| pokrycie edycji **w repo** (ścieżka względna) | 22/30 | **22/30** | **bez zmian** |
| mediana wywołania pierwszego zapisu | call 10 | call 10 | bez zmian |
| pierwsza edycja w repo **w call 4** | 1/30 | **1/30** | **E7 (cel ≥ 12/30) — OBALONE** |
| wywołania `submit_patch` | dziesiątki | **0** | M3: naprawione strukturalnie |
| najdłuższa seria `submit_patch` | 48 | **0** | — |
| najdłuższa seria edycji | — | **9** | nowa pętla do zbadania |
| zapisy poza repo | `/tmp/locate.py`, `/tmp/repro.py` | `/tmp/locate.py`, `/tmp/repro.py`, **`/tmp/issue.txt`** | M4: wariant „tylko skrypt" nadal żyje |

**E6 w brzmieniu z bramek** („jeśli pokrycie edycji nadal ≤ 23/30, reguły promptu nie zmieniają
zachowania"): pokrycie *dowolnych zapisów* wzrosło 23 → 26, więc warunek **formalnie nie zachodzi**;
ale pokrycie *edycji w repo* stoi w miejscu (22/30), a termin call 4 został zignorowany niemal
dokładnie tak samo jak przed dodaniem reguły (1/30 vs 1/30). Uczciwy wniosek: **reguły zmieniły
zachowanie brzegowe (mniej pętli, zero submissji), ale nie przesunęły momentu ani faktu edycji.**

## Nowa diagnoza: 11 pustych drzew i trzy różne mechanizmy

| mechanizm | zadania | co pokazuje ślad |
| --- | --- | --- |
| **A. brak jakiegokolwiek zapisu** (4) | `fastapi_14266` (31 wyw., 16 czytań), `fastapi_14459` (18), `rich_3105` (8 wyw., koniec po 80 s), `rich_3934` (11) | sesja czyta i uruchamia, nigdy nie edytuje; `rich_3105` kończy dobrowolnie po 80 s |
| **B. tylko skrypt lokalizatora** (4) | `fastapi_15745` (3 wyw.!), `fastapi_15588` (3 wyw.!), `httpx_3672`, `rich_3043` | sesja pisze `/tmp/locate.py` i **kończy się bez edycji** — 3 wywołania w 244–341 s |
| **C. edycja wywołana, diff pusty** (3) | `fastapi_14851` → `fastapi/routing.py` (33. wywołanie, 255,6 s), `fastapi_14487` → `docs/…handling-errors.md`, `requests_6757` → `tox.ini` ×2 | **nie wiemy, czy edycja się powiodła** — ślady operacyjne nie zapisują wyników narzędzi (ani błędu „old_string not found", ani faktu resetu plików przez harness) |

**Mechanizm B to najważniejsze odkrycie dnia.** Cztery zadania (13 %) zużyły sesję na przygotowanie
skryptu lokalizatora i nigdy nie doszły do edycji — a w V3/V4/V5 (bez kroku lokalizatora) pustych
drzew było **6**, nie 11. Czyli architektura „lokalizator najpierw" dodaje nowy sposób na zero,
którego wcześniejsze wersje nie miały. Uwaga: to nie znaczy, że lokalizator jest bezużyteczny —
był walidowany offline (73 % top-5), ale online **nie przekłada się na rozwiązania** (10/30 jak V5)
i wprowadza własną porażkę.

**Bramka G2 nigdy nie została spełniona przez żadną wersję** — ani przez V4, jedyną z oficjalnym
wynikiem 0,03:

| wersja | rozwiązane | G1 | G2 | G3 | puste | oficjalnie |
| --- | --- | --- | --- | --- | --- | --- |
| V3 | 11/30 | 0 | 2 | 0 | 6 | — |
| **V4** | **11/30** | 0 | **1** | 0 | 6 | **0,03** |
| V5 | 10/30 | 0 | 1 | 0 | 6 | — |
| V6.1 | 6/30 | 9 | 1 | 0 | 7 | — |
| V6.2 | 9/30 | 0 | 2 | 1 | 8 | — |
| V6.3 | 10/30 | 0 | 3 | 0 | 11 | — |
| V6.4 | 10/30 | 0 | 3 | 0 | 11 | — |

Wniosek strategiczny: **próg G2 = 0 jest ostrzejszy niż jakość wersji, która realnie zdobyła 0,03.**
Utrzymywanie go jako twardego warunku oznacza, że nie wysłalibyśmy nawet V4.

## Co z tego idzie do V6.5 i dalej

1. **V6.5 (jutro, zaplanowany):** dźwignia „pierwsza edycja bez pewności" trafia dokładnie w mechanizm
   A/B — sesje, które czytają i nie edytują. Mini na 6 najtrudniejszych zadaniach, potem pełny.
2. **Kandydat V6.6 — lokalizator jednym wywołaniem bez pliku:** zamiast
   `cat > /tmp/locate.py <<'LOCATE_PY' … python3 /tmp/locate.py` (2 wywołania + plik, który stał się
   nośnikiem zera w 4/30 zadań) uruchamiać ten sam skrypt przez heredoc do `python3 -` — **jedno
   wywołanie, zero plików**. To usuwa mechanizm B konstrukcyjnie, nie instrukcją.
3. **Diagnostyka do domknięcia:** mechanizm C (edycja wywołana, diff pusty) wymaga zajrzenia w wyniki
   narzędzi (status/„old_string not found") — to dane operacyjne, nie rozumowanie modelu, ale
   `extract_operational_trace.py` ich dziś nie zapisuje. Do rozstrzygnięcia przed V6.6.
