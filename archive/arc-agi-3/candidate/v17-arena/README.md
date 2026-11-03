# duck-v17-arena — kandydat lokalny (Arena, 30.10.2026)

**Status: zbudowany i zweryfikowany offline (47/47 kontroli). Nie uruchamiany w Kaggle, nie
wysłany, brak zmierzonego wyniku.** Ten katalog jest samodzielny.

v17-arena = **v13.6-final** (to, co druga sesja uznała za swoje finalne wydanie) **+ jedna
zmienna eksperymentalna**: patch 0010 `ARC3_PRIORITY_DPRIME=1` (priorytet slotu D′).

| warstwa | element | źródło |
|---|---|---|
| baza | v13.6-final, 40 komórek, `PLAN_COMMIT=1`, `CAP=0`, `WINPATH=1`, `DEAD_SKIP=1`, conc=10, playbook 14/14 | Smak `3bf4d3e0` |
| presja na openerach | `ARC3_OPENER_COMMIT_HINT=1` | v13.3-arena |
| spust eskalacji | `ESCALATE_ACTIONS=20` + patch 0009 `ARC3_ESCALATE_SELF_PACE=1` (clamp(1,5×własna mediana, 20, 120), cap 2/poziom) | duck-v16 (Gemma) |
| obserwowalność | sondy rosteru/coverage/baseline, sonda budżetu, żywy instrument `a/call` | v13.4–v13.6 |
| **NOWE (jedna zmienna)** | **patch 0010 `ARC3_PRIORITY_DPRIME=1`** — D′ zamiast fabrycznego `priority_value` | `../v16-arena` |

## Dlaczego baza to v13.6, a nie mój v16-arena

Mój `v16-arena` stoi na v13.4, gdzie eskalację robi patch 0008 przez **względny** baseline.
W trybie submisji `taaf/game.py` podaje `base_actions_per_level = None`, więc 0008 **nie ma
danych** i zjeżdża do reguły absolutnej 20 + cap 2. Zmierzone przeze mnie na r085:
42 nudge / **26 przedwczesnych** (reguła względna liczona na replayu: 8 / 0, ale w submisji
jest bezwładna). Self-pace nie potrzebuje ukrytych danych (bierze własną medianę
`GameRun.actions_per_level`), więc jest jedyną eskalacją, która w biegu, który się liczy,
faktycznie działa inaczej niż „20”. To jest realna przewaga v13.6 nad v13.4 — i dlatego
v17-arena bierze v13.6 jako bazę.

D′ jest ortogonalny wobec self-pace: inny plik (`priority_scheduler.py`), inne pytanie
(*która gra dostaje następny slot*, nie *kiedy nudge*).

## Kill-switche (każdy niezależny)

`"ARC3_PRIORITY_DPRIME": "0"` = dokładnie v13.6-final · `"ARC3_ESCALATE_SELF_PACE": "0"` =
v13.5-consensus · `"ARC3_ESCALATE_RELATIVE": "0"` · `"ARC3_ESCALATE_MAX_PER_LEVEL": "0"` ·
`"ARC3_OPENER_COMMIT_HINT": "0"` · `"ARC3_WINPATH": "0"` · `"ARC3_DEAD_SKIP": "0"` ·
`PLAN_COMMIT = "0"` · `"ARC3_LEVEL_TOKEN_CAP": "45000"`.

## Co robi patch 0010

1. `ProgressPace` dostaje **surowy** pomiar: `total_tokens` i
   `mean_tokens_per_cleared_level()`. Bezwymiarowy `cost_multiplier()` (0,5–2,0) nie może
   udawać tempa tokenów.
2. `priority_scheduler` dostaje `dprime_value()`, `dprime_priority()` i `select_priority()`
   (formuła D′, skala 1000, bez bezwarunkowego pasma „fresh first”). Fabryczne
   `priority_value()` zostaje **nietknięte, bajt w bajt**.
3. Oba miejsca wywołania (`_game_priority`, `_PriorityGate._snapshot_priority`) idą przez
   `select_priority`; `_maybe_handover` podaje zmierzony pace.
4. Gdy włączone `ARC3_PRIORITY_PACE` **lub** D′, pace jest zapisywany przy przejściu poziomu.

Zmierzone wcześniej publiczne drawy D′: 31,54 / 30,74 / 29,05 / 24,77 (średnia ≈29,0, n=4)
wobec porównywalnej linii baseline ≈25,77 (SD ≈3,93). **To słaby, zaszumiony sygnał
(n=4), nie dowód.** Samo włączenie D′ nie daje podstaw twierdzić cokolwiek o 50+.

## Co nowego w logu (0 kosztu GPU)

* **sonda D′ (przed `bm.run`)**: czy przełącznik jest w env i czy patch się załadował,
  czy przy `"0"` `select_priority()` zwraca **dokładnie** `priority_value()`, czy przy `"1"`
  D′ rozróżnia głębokość/taniość gry. Awaria → `skipped`, notebook leci dalej.
* **miernik D′ (po biegu)**: `dprime_metering.jsonl` — na grę: poziomów, akcji, tokenów,
  `actions_per_call`, `tokens_per_cleared_level`, wynik; plus podsumowanie i jawne
  ostrzeżenie, jeśli **żaden** run nie ukończył poziomu (wtedy D′ pracował na referencji
  30k i jego wkład jest efektem ubocznym, nie pomiarem).

## Weryfikacja offline

```
python3 tools/build_v17.py                     # 43 komórki, 764 759 B; powtarzalny bajt w bajt
python3 tools/verify_v17.py                    # 27 kontroli bez drzewa (notebook, switch, playbook, sondy)
python3 tools/verify_v17.py --bundle <r033> --tests   # 47 kontroli: 10 patchy, kompilacja, testy
```

`--bundle` wyciąga **wszystkie 10 patchy z samego notebooka**, aplikuje je w kolejności
notebooka na czyste drzewo `ARC3-Inference` z bundle’a r033, kompiluje i uruchamia na nim
12 testów plan-commit, 5 względnej eskalacji, 21 D′, 11 win-path oraz self-pace
(**22/14 na r085 odtworzone z drzewa po patchach**) i dowodzi, że przy `ARC3_PRIORITY_DPRIME`
unset `select_priority()` == `priority_value()` na 24 kombinacjach snapshotów i argumentów.

Wymagania: `requests`/`PIL` (na offline: `PYTHONPATH=/tmp/shims`) i `R085_BENCH` wskazujący
realny `benchmark.json`. `src/priority_scheduler_v17.py` to zrzut drzewa po patchach —
wejście do replayu bez budowania notebooka.
