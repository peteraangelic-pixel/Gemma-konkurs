# V6.2: 9/30 — naprawa regresji potwierdzona, dwa nowe wzorce porażki

## Wynik na tym samym zestawie 30 zadań i seedzie 20261009

| kandydat | rozwiązane | puste drzewa | śmierci na zegarze | pliki-śmieci w diffie | trafienia lokalizatora | średni czas |
| --- | --- | --- | --- | --- | --- | --- |
| V3 | 11/30 | 6 | 16 | — | — | 261 s |
| V4 | 11/30 | 6 | 12 | — | — | 234 s |
| V5 | 10/30 | 6 | 9 | — | — | 233 s |
| V6.1 | 6/30 | 7 | 17 | **9** (7 tylko śmieci) | 15/30 | 275 s |
| **V6.2** | **9/30** | **8** | 17 | **0** ✅ | **20/30** ✅ | 272 s |

**Naprawa regresji V6.1 potwierdzona**: 9/30 zamiast 6/30, **zero** zadań z plikami-śmieciami
(`locate.py`, `issue.txt`, `repro.py`), trafienia lokalizatora 15 → **20/30**. Trzy z czterech
regresji V6.1 wróciły (`rich_3518`, `rich_3894`, `rich_3882`), jedna nadal spada (`rich_3043`),
doszło jedno nowe rozwiązanie (`fastapi_14873`, patch 1 291 znaków, 27 wywołań).

Wynik nadal **nie bije V5 (10/30)**. Przy n=30 różnica 1 zadania to szum (CI95 dla 9/30 to
[16.7 %, 47.9 %], zgodnie z `agent_benchmark_result.json`), więc ten przebieg trzeba czytać mechanicznie, nie rankingowo.

## Pierwszy dowód end-to-end, że lokalizacja ma znaczenie

| grupa | rozwiązane |
| --- | --- |
| zadania z `localized=True` (patch dotknął naprawialnego pliku ze złotego patcha) | **8/20 (40 %)** |
| zadania z `localized=False` | **1/10 (10 %)** |

To korelacja, nie dowód przyczynowy (lokalizacja i łatwość zadania są skorelowane), ale jest to
pierwszy pomiar, który łączy ranking lokalizatora z wynikiem na prawdziwym harnessie.

## Wzorzec 1 (nowy): `submit_patch()` bez edycji = przedwczesny koniec sesji

`submit_patch()` **kończy sesję** (HARNESS_README, l. 346–348) i to liczy się także wtedy, gdy w
drzewie nie ma żadnej zmiany. W V6.2 dwa z ośmiu pustych drzew to nie śmierć na zegarze, tylko
**przedwczesna submisja**:

| zadanie | czas | wywołania | co się stało |
| --- | --- | --- | --- |
| `rich_3105` | 119 s | 5 | sesja skończona w 1/3 budżetu, zero edycji |
| `rich_3934` | 266 s | 10 | sesja skończona przed limitem, zero edycji |

Reguła „zawsze `submit_patch()`" z V5/V6 prowokuje ten błąd: agent wolał złożyć pusty patch niż
ryzykować brak submisji. Poprawka do zaproponowania w V6.3: **`submit_patch()` wolno wywołać
tylko wtedy, gdy `git status --porcelain` nie jest pusty** — a strażnik higieny ma zaczynać się od
tego sprawdzenia.

## Wzorzec 2 (znany, nierozwiązany): 6 śmierci na zegarze

`fastapi_14851` (30 wywołań — uderzenie w nowy cap), `fastapi_14266`, `rich_3006` (4 wywołania w
318 s!), `fastapi_14186`, `requests_6757`, `fastapi_15745`. Przypadek `rich_3006` pokazuje, że
problemem nie jest liczba wywołań, a **czas pojedynczego wywołania** (średnio 80 s przy 4
wywołaniach): długie myślenie i/lub długie wyjścia narzędzi. Kandydaci na V6.3: niższy
`thinking_budget` (4096 → 2048), twardsze „pierwsza edycja do 6. wywołania" i `timeout 30`.

## Reguła małego patcha potwierdzona trzeci raz

- rozwiązane V6.2: 458, 503, 529, 595, 609, 767, 1 291, 1 361, 1 855 znaków — **wszystkie < 1 900**,
- nierozwiązane z patchem: 509 … 2 292 znaki, w tym 6 patchy > 1 500.

## Nowy, tani sygnał: edycje dokumentacji

`fastapi_14487` (patch 731 znaków) zmienił **`docs/en/docs/tutorial/handling-errors.md`** — plik,
który nie może zmienić wyniku testów. Warto dopisać jedną regułę: *edycja `docs/`/`docs_src/`
nigdy nie naprawia testów; jeśli kandydat z rankingu jest dokumentacją, wybierz następny plik
źródłowy*.

## Stan infrastruktury

- Wynik V6.2 wrócił na gałąź przez `gemma-kaggle-v62-fetch-results.yml` (pobranie outputu
  **zakończonego** kernela przez API Kaggle — zero pracy GPU, brak submissji), bo commit w
  workflow benchmarku padł. `run.json` jest jawnie oznaczony jako rekonstrukcja z metadanych
  kernela (`run_json_source`), a pełna tabela per zadanie leży w `fetch_summary.txt`.
- Krok commitu w workflow benchmarku przepisany na `git reset --soft origin/<branch>` (bez
  `pull --rebase --autostash`), żeby kolejne przebiegi nie padały w ten sam sposób.
- Artefakt, który wygenerował te wyniki: `submission-v6.zip`,
  SHA-256 `8c1ea5b71a61b4d58a6b023596761abb9af37908af6d0ef441347353a2f860b8` — nie zmieniam go,
  żeby wyniki pozostały przypisane do dokładnie tego pliku.
