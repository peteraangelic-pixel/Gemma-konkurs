# V6.1: 6/30 — regresja i jej dokładna przyczyna (pomiar per zadanie)

## Wynik

| kandydat | rozwiązane | puste patche | śmierci na zegarze (≥315 s) | zanieczyszczone diffs |
| --- | --- | --- | --- | --- |
| V3 | 11/30 | — | — | — (brak diagnostyki) |
| V4 | 11/30 | 6 | — | — |
| V5 | 10/30 | 6 | 9 | — (brak diagnostyki) |
| **V6.1** | **6/30** | **7** | **17** | **9** |

Zmiany statusu V5 → V6.1: **0 popraw, 4 regresje** (`rich_3518`, `rich_3894`, `rich_3043`, `rich_3882`).
CI95 Wilsona dla 6/30 to [9.5 %, 37.3 %].

## Przyczyna (z nowej diagnostyki per zadanie)

Nowe pola (`touched_files`, `localized`, `tasks_with_empty_patch`) pokazały mechanizm, którego
nie widzielibyśmy bez nich:

1. **Krok lokalizatora kazał agentowi zapisać issue i skrypt przez `write_file`.** Agent
   podawał **gołe nazwy plików** (`issue.txt`, `locate.py`), a te są rozwiązywane **wewnątrz
   `/workspace`** — więc zamiast do `/tmp` trafiały do ocenianego diffu.
2. **9 z 30 zadań** miało w diffie pliki robocze; w **7 z nich nie było ŻADNEJ edycji kodu**,
   a „patch" to 7.7 KB skryptu lokalizatora plus treść issue — łącznie **61 008 znaków śmieci**.
3. Śmieci **unieważniły ochronę przed pustym diffem**: harness nie widział pustego patcha, więc
   nie próbował niczego ratować, a grader dostawał wyłącznie plik tekstowy.
4. Dodatkowe zapisy i czytanie top-8 zjadły czas: **śmierci na zegarze 17/30** (V5: 9/30),
   średni czas zadania 275 s (V5: 233 s). Uwaga na interpretację: sama śmierć na zegarze nie
   przekreśla zadania (V3: 16/30 śmierci i 11/30 rozwiązanych), bo oceniany jest diff drzewa —
   przekreśla ją śmierć **bez edycji kodu na dysku**, a takich V6.1 miał 7.

Zadania zanieczyszczone: `rich_3934`, `rich_3894`, `rich_3043`, `fastapi_14873`, `fastapi_15588`,
`fastapi_14459`, `fastapi_14262`, `fastapi_14482`, `fastapi_15745`.
Tylko śmieci (zero edycji kodu): `rich_3934`, `rich_3894`, `fastapi_14873`, `fastapi_15588`,
`fastapi_14459`, `fastapi_14482`, `fastapi_15745`.

Wniosek: **lokalizator nie zawiódł — zawiodło jego okablowanie.** Pomiar lokalizacji mówi
15/30 zadań dotknęło naprawialnego pliku ze złotego patcha (`localization_hits: 15`), a mimo to
rozwiązanych było 6, bo połowa sesji zapisywała śmieci zamiast naprawiać kod.

## Co zmienia V6.2 (wdrożone, screening w toku)

1. **Zero `write_file`**: skrypt i treść issue jadą w JEDNYM `run_command` z dwoma heredocami
   (`cat > /tmp/locate.py <<'LOCATE_PY'`, `python3 /tmp/locate.py --root . --top 8 <<'ISSUE_EOF'`),
   a lokalizator czyta issue ze **stdin** (`--issue-file -`). Do `/workspace` nie trafia nic.
2. **Zakaz tworzenia plików roboczych w `/workspace`** — wprost, z liczbami szkód z V6.1.
3. **Obowiązkowy strażnik higieny** przed submisją: `git status --porcelain`, a jeśli lista
   zawiera cokolwiek poza zamierzonymi plikami źródłowymi — `rm -f` w tym samym wywołaniu.
4. **`max_tool_calls` 45 → 30**: darmowe `budget_warning` harnessu przychodzi przy 20. wywołaniu
   zamiast 35. (Sesje giną na zegarze 315 s, nie na budżecie wywołań — rozwiązane sesje miały
   średnio 15 wywołań.)
5. **Twarde deadline'y**: edycja na dysku do 8. wywołania, koniec szukania na 14., submisja na 18.

Weryfikacja przed wypchnięciem: blok heredocowy **wyciągnięty z wygenerowanego promptu** uruchamia
się i rankuje poprawnie; packer nie przepuści builda, jeśli zniknie któraś z instrukcji
higieny/plumbing. Artefakt V6.2: `submission-v6.zip`,
SHA-256 `8c1ea5b71a61b4d58a6b023596761abb9af37908af6d0ef441347353a2f860b8`.
