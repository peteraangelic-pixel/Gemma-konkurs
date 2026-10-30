# duck-v17-arena-dyn — najlepszy kandydat lokalny (Arena, 30.10.2026)

**Status: zbudowany i zweryfikowany offline — 54/54 kontroli. Nie uruchamiany w Kaggle,
nie wysłany, brak zmierzonego wyniku.** Katalog samodzielny.

Podstawa: **v13-7-final** (Smak, `arena/5ed750ef-…`, katalog `arc-agi-3/duck-v13-7-final`,
zweryfikowany przeze mnie w `notes/ARC-AGI-3-ocena-v13-7-final-2026-10-30.md`)
**+ jedna żywa zmienna: D′ (`ARC3_PRIORITY_DPRIME=1`, patch 0011)**.

| warstwa | element | źródło |
|---|---|---|
| baza | v13-7-final, 41 komórek, `PLAN_COMMIT=1`, `CAP=0`, `WINPATH=1`, `DEAD_SKIP=1`, conc=10, playbook 14/14 | Smak `3bf4d3e0`/`de57e4d8` |
| eskalacja | patch 0009 `ARC3_ESCALATE_SELF_PACE=1` — clamp(1,5×własna mediana, 20, 120), cap 2/poziom; r085 **22/14** (vs 42/26 dla 20+cap2) | Gemma duck-v16 |
| budżet poziomu | patch 0010 `dyn-level-budget` — **DORMANT** (`ARC3_LEVEL_TOKEN_CAP="0"`), uzbrajany jedną wartością | handoff „strategia" |
| obserwowalność | sondy rosteru/coverage/baseline, sonda budżetu, żywy instrument `a/call` | v13.4–v13.7 |
| **NOWE (jedna żywa zmienna)** | **patch 0011 `ARC3_PRIORITY_DPRIME=1`** — D′ zamiast fabrycznego `priority_value` | `../v16-arena` |

Przy `"ARC3_PRIORITY_DPRIME": "0"` notebook jest **dokładnie v13-7-final** — `select_priority()`
wywołuje wtedy `priority_value()` z tymi samymi argumentami, co sprawdza
`verify_v17_dyn.py` na świeżo spatchowanym drzewie (24 kombinacje snapshotów i argumentów,
zero rozbieżności).

## Dlaczego akurat to zestawienie

1. **v13.7 jest lepszą bazą niż v13.4** (na której stoi mój `v16-arena`): eskalacja względna
   (0008) jest w submisji bezwładna — `taaf/game.py` podaje `base_actions_per_level = None` —
   a self-pace (0009) nie potrzebuje ukrytych danych i faktycznie działa: 22 zamiast 42
   wtrąceń, 14 zamiast 26 przedwczesnych na r085.
2. **D′ jest ortogonalny** wobec eskalacji i budżetu: inny plik (`priority_scheduler.py`),
   inne pytanie (która gra dostaje następny slot). Pliki 0010 i 0011 są rozłączne —
   sprawdzone: łańcuch v13.7 + D′ aplikuje się na czysty r033 i kompiluje.
3. **Dwie dźwignie, ale jedna włączona.** W tym buildzie żyje tylko D′; budżet poziomu jest
   zapakowany i wyłączony, więc eksperyment pozostaje jednozmiennościowy.

## Jeśli kiedyś uzbrajać 0010 — NISKO, nie 60000

Reguła to `cap = clamp(max(static_cap, mediana(koszty ukończonych) × 4), cap_min, 150k)`.
Wartość uzbrojenia jest **jednocześnie podłogą**, więc przy 60000 reguła **tylko poluzowuje**.
Na moim korpusie 40 gier (r085/r093/r110/r118), przy uzbrojeniu 60000:

* reguła włącza się w **16/40** gier (tylko tam, gdzie ≥2 ukończone poziomy), w nich
  **15/16 luźniej, 0/16 ciaśniej**, mediana capa 128 612;
* gry, które palą 100% tokenów na poziomie, którego nie kończą (24/40), **w ogóle nie są
  dotknięte** — nie mają historii;
* przy uzbrojeniu **20000** produktywne gry i tak dostają `mediana×4` = 46k–150k, a gry bez
  historii tną się na ~20k (+1 darmowy RESET ≈ 40k).

Dlatego wariant zostaje `"ARC3_LEVEL_TOKEN_CAP": "0"`, a rekomendacja armingu to **20000**.
Komórka „v17 levers" liczy to po biegu z jego własnych danych (`levers.jsonl`) — decyzja
o uzbrojeniu ma być pomiarem z tego biegu, nie z cudzego.

## Kill-switche (każdy niezależny)

`"ARC3_PRIORITY_DPRIME": "0"` = dokładnie v13-7-final · `"ARC3_LEVEL_TOKEN_CAP": "20000"` =
uzbrojenie 0010 · `"ARC3_DYN_CAP": "0"` = wierny statyczny 0004 (kontrola A/B) ·
`"ARC3_ESCALATE_SELF_PACE": "0"` = v13.5 · `"ARC3_ESCALATE_RELATIVE": "0"` ·
`"ARC3_ESCALATE_MAX_PER_LEVEL": "0"` · `"ARC3_OPENER_COMMIT_HINT": "0"` · `"ARC3_WINPATH": "0"` ·
`"ARC3_DEAD_SKIP": "0"` · `PLAN_COMMIT = "0"` · `"ARC3_LEVEL_TOKEN_CAP": "45000"`.

## Co nowego w logu (0 kosztu GPU)

* **sonda D′ (przed `bm.run`)**: czy przełącznik jest w env i czy patch się załadował, czy przy
  `"0"` `select_priority()` zwraca **dokładnie** `priority_value()`, czy przy `"1"` D′ rozróżnia
  głębokość i taniość gry. Awaria → `skipped`, notebook leci dalej.
* **miernik D′ (po biegu)**: `dprime_metering.jsonl` — poziomów, akcji, tokenów, `a/call`,
  tokenów na ukończony poziom, wynik; jawne ostrzeżenie, jeśli **żaden** run nie ukończył
  poziomu (wtedy D′ pracuje na referencji 30k i jego wkład jest efektem ubocznym).
* **raport dźwigni (po biegu)**: `levers.jsonl` — co dałby 0010 przy 20000 vs 60000, ile gier
  w ogóle uruchamia regułę, ile tokenów idzie na poziomy nieukończone.

## Weryfikacja offline

```
python3 tools/build_v17_dyn.py --prev src/base-v13-7-final.ipynb   # 45 komórek, 783 407 B; powtarzalny bajt w bajt
python3 tools/verify_v17_dyn.py                                    # 30 kontroli bez drzewa
python3 tools/verify_v17_dyn.py --bundle <r033> --tests            # 54 kontrole
```

`--bundle` wyciąga **wszystkie 11 patchy z samego notebooka**, aplikuje je w kolejności
notebooka na czyste drzewo `ARC3-Inference` z r033, kompiluje i uruchamia: 12 plan-commit,
5 względnej eskalacji, 21 D′, **16 dyn-budget** (na bajtach wysyłkowych), self-pace
(**22/14 na r085 z drzewa po patchach**), 11 win-path; dodatkowo `cmp` obu rekonstrukcji
(`src/priority_scheduler_v17.py`, `src/arc3_level_budget_v13_2.py`) z drzewem po patchach oraz
dowód, że przy `ARC3_PRIORITY_DPRIME` unset `select_priority() == priority_value()`.

Wymagania: `requests`/`PIL` (offline: `PYTHONPATH=/tmp/shims`) i `R085_BENCH` na realny
`benchmark.json`.

## Czego ten katalog NIE twierdzi

* Brak zmierzonego wyniku. Jedyne liczby o D′ to 4 publiczne drawy 31,54 / 30,74 / 29,05 /
  24,77 (średnia ≈29,0) wobec porównywalnej linii ≈25,77 (SD ≈3,93) — **n=4, szum**.
* Bazowe, zmierzone wyniki tej linii: 1,18 / 23,89 / 26,25. Nic tu nie daje podstaw do 50+.
