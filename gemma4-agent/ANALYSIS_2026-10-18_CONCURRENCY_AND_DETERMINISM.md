# 2026-10-18 — concurrency i determinizm harnessu: co dziś naprawdę zmierzono

Dzień miał dwa cele: (1) napprawić pomiar, żeby ekran był tańszy, (2) zmierzyć pętlę weryfikacji
(V8). Cel (2) nie został zmierzony — kolejka GPU i trzy błędy własnego narzędzia zjadły dzień.
Poniżej dokładnie co wiemy, a czego nie.

## 1. Trzy martwe gałki, wszystkie w tym samym miejscu

| # | defekt | objaw | jak go złapano |
| --- | --- | --- | --- |
| 1 | `_excluded` czytane w `persist_results()`, nigdy nie zdefiniowane | kernel `907b8648…091416` padł na NameError po pierwszym zadaniu (14,5 min, status ERROR) | przegląd wygenerowanego notebooka |
| 2 | `concurrency` nie trafiało do `TASK_SELECTION` w notebooku | `--concurrency 3` dawało `concurrency: 1` w wyniku | test `build_notebook()` w pamięci |
| 3 | CLI nie przekazywało `concurrency=`/`excluded_repos=` do `build_notebook()` | **dwa** kernele „concurrency 3" biegły seryjnie, a `run.json` raportował 3 | odczyt wynikowego JSON: `concurrency: 3`, ale wall == suma czasów |

Każdy z nich jest niewidoczny dla `ast.parse` launcher-a, bo notebook jest **stringiem**.
`gemma4-agent/tools/check_notebook_names.py` buduje notebook i sprawdza: nazwy czytane i nigdzie
nie związane, składnię wygenerowanego kodu, klucze `TASK_SELECTION`, których launcher nie forwarduje,
oraz keywordy, których CLI nie przekazuje do `build_notebook()`. Na starym launcherze zgłasza
defekty 1–3; na nowym przechodzi. Jest twardym krokiem workflow przed każdą premierą GPU.

## 2. Concurrency: neutralne dla jakości, ale flaga sama nic nie dawała

Ten sam archiwum (`907b8648…`, V5 + zegar 8 min), te same 12 zadań, ten sam seed:

| przebieg | concurrency | rozwiązane | suma czasów | wall clock | średni czas zadania | puste |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| #1 seryjny (V7-c) | 1 | **5/12** | 2 919 s | 2 919 s | 232,7 s* | 2 |
| #2 seryjny (powtórka) | 1 | **5/12** | 2 436 s | 2 437 s | 203,0 s | 2 |
| #3 „concurrency 3" | 3 (flaga) | **5/12** | 2 572 s | 2 573 s | 214,3 s | 3 |

\* średnia z 30 zadań całego przebiegu V7-c; dla samych 12 nie była raportowana.

Dwa wnioski, oba ważne:

- **Jakość: zero różnicy.** 12/12 zadań z identycznym werdyktem w każdym z trzech przebiegów, także
  tam, gdzie treść patcha się różniła (`rich_3894` 790→595 znaków, `fastapi_14266` 0→2704 znaków —
  werdykt bez zmian). Batching nigdy nie był włączony, więc to nie jest jeszcze test batchingu;
  to test **powtarzalności**.
- **Czas: brak zysku, i wiemy dlaczego.** `wall == suma czasów`, bo nasza pętla w notebooku czekała
  na `evaluate_task` po kolei — semafor w `EvalConfig` nigdy nie miał drugiego zadania do przepuszczenia.
  Poprawka: `asyncio.gather` po tych samych korutynach, które zbiera własny batch-path harnessu
  (`swegemma_source.txt` L3945–3995), z semaforem, przy zachowanym zapisie wyniku po każdym zadaniu.
  Ścieżka seryjna (`concurrency == 1`) została nietknięta.

## 3. Determinizm harnessu — najważniejsza liczba dnia

Trzy niezależne kernele, to samo archiwum, ten sam seed, te same 12 zadań: **5/12 za każdym razem,
12/12 identycznych werdyktów per zadanie**. Czas i treść patchy pływają (203–232 s średnio, ±17 %
wall clocku), werdykty nie.

Co to znaczy dla metody:

- **Pomiar parowany nie jest szumem.** Jeśli V8 przewróci zadanie, które V5 rozwiązało (albo
  odwrotnie), to jest efekt zmiany, a nie losowość przebiegu. To dokładnie ta „pula ważona, nie
  mieszanie maszyn" z Pokemon — tyle że u nas determinizm jest zmierzony, nie założony.
- **Niepewność ekranu leży w doborze zadań, nie w przebiegu.** 12 zadań to 12 punktów danych o
  *tych* 12 zadaniach; ekstrapolacja na oficjalne 58 zadań zostaje szeroka (±9 pp) i żadna liczba
  z ekranu tego nie zmieni.
- **Powtórka tego samego archiwum nie kupuje informacji.** Drugi przebieg dał identyczny wynik za
  0,8 h kwoty — to był koszt błędu, nie eksperymentu.

## 4. Czego NIE zmierzono

- **V8 (pętla weryfikacji) — zero danych.** Archiwum zbudowane i spakowane
  (`submission-v8.zip`, sha `c32a37dc…`), ekran przygotowany na 30 sparowanych zadań
  (`screen-v8c-verify.json`, bramki w `GATES_V8.md`), ale żaden przebieg nie wystartował.
- **concurrency > 1 z prawdziwym `gather`** — kod gotowy, niesprawdzony na GPU.
- **repo holdout** (`--exclude-repos`) — kod poprawiony, niesprawdzony; parametr nadal nie został
  użyty w żadnym przebiegu.

## 5. Koszt dnia

| pozycja | wall clock | uwaga |
| --- | ---: | --- |
| kernel-dud (NameError) | 14,5 min | spalone na defekt 1 |
| ekran 12 zadań + powtórka seryjna | 54 min | 5/12, 12/12 identycznych |
| ekran 12 zadań „concurrency 3" | 44 min | flaga bez efektu, 5/12 |
| **razem** | **~1,9 h** | ≈ 3,8 h kwoty przy rozliczeniu ×2 |

Do tego — niespodziewanie — przycisk „uruchom LoRA SFT": commit `c6a1479` zawierał przez
`git add -A` plik `gemma4-agent/kaggle_smoke/v2-benchmark.trigger`, który wyzwolił workflow SFT
(`39123433910`, start 11:29 UTC). Kernel canary zajął slot GPU i zablokował dwie próby ekranu
(„Maximum batch GPU session count of 2 reached"). **Zasada: w tym repo nigdy `git add -A`; tylko
jawne ścieżki.** Plików `*.trigger` nie wolno dotykać nawet usunięciem — usunięcie też wyzwala.
