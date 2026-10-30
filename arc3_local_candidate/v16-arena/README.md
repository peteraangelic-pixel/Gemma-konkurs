# duck-v16-arena — izolowany kandydat lokalny (Arena, 30.10.2026)

**Status: zbudowany i zweryfikowany offline. Nie uruchamiany w Kaggle, nie wysłany, nie ma
zmierzonego wyniku.** Ten katalog jest samodzielny: notebook powstaje z certified v13.4-unified
plus **jedna** zmienna eksperymentalna.

| warstwa | element | źródło |
|---|---|---|
| baza | PLAN_COMMIT=1, CAP=0, WINPATH=1, DEAD_SKIP=1, conc=10, playbook 14/14 | v13.2 |
| presja na openerach | `ARC3_OPENER_COMMIT_HINT=1` | v13.3-arena |
| log replayu | patch 0007 `[arc3-winpath] …` | v13.3-arena |
| spust eskalacji | `ESCALATE_ACTIONS=20` + patch 0008 `ARC3_ESCALATE_RELATIVE=1` (max(20, 1,2×baseline), cap 2/poziom) | v14 (pomiar) + v13.4 (patch) |
| crash-proof + obserwowalność | guard hooka sondy, sonda budżetu, sonda rosteru (`roster_probe_runs.jsonl`) | v14 / v13.4 |
| **NOWE (jedna zmienna)** | **patch 0009 `ARC3_PRIORITY_DPRIME=1`** — priorytet slotu D′ zamiast fabrycznego `priority_value` | ten katalog |

Przy `"ARC3_PRIORITY_DPRIME": "0"` notebook jest **dokładnie v13.4-unified** — to nie jest
deklaracja, tylko test: `select_priority()` wywołuje wtedy `priority_value()` z tymi samymi
argumentami, a `tools/verify_v16.py --bundle … --tests` sprawdza to na świeżo spatchowanym
drzewie (24 kombinacje snapshotów i argumentów, zero rozbieżności).

## Co realnie zmienia patch 0009

1. `ProgressPace` dostaje **surowy** pomiar tempa: `total_tokens` i
   `mean_tokens_per_cleared_level()`. Stary `cost_multiplier()` (bezwymiarowy czynnik 0,5–2,0)
   nie może udawać tempa tokenów — to była najpoważniejsza przeszkoda w poprzednim podejściu.
2. `priority_scheduler` dostaje `dprime_value()`, `dprime_priority()` i `select_priority()`
   z formułą D′ (skala 1000). Fabryczne `priority_value()` zostaje **nietknięte**, bajt w bajt,
   i jest tym, co działa przy wyłączonym przelaczniku.
3. Oba miejsca wywołania (`_game_priority` oraz `_PriorityGate._snapshot_priority`) przechodzą
   przez `select_priority`, a `_maybe_handover` podaje zmierzony pace.
4. Gdy jest włączone `ARC3_PRIORITY_PACE` **albo** D′, pace jest zapisywany przy przejściu
   poziomu — bez tego D′ nie miałby wejścia.

## Kill-switche (każdy niezależny)

`"ARC3_PRIORITY_DPRIME": "0"` = v13.4-unified · `"ARC3_ESCALATE_RELATIVE": "0"` = v14-exact ·
`"ARC3_ESCALATE_MAX_PER_LEVEL": "0"` · `"ARC3_OPENER_COMMIT_HINT": "0"` · `"ARC3_WINPATH_LOG": "0"` ·
`"ARC3_WINPATH": "0"` · `"ARC3_DEAD_SKIP": "0"` · `PLAN_COMMIT = "0"` · `"ARC3_LEVEL_TOKEN_CAP": "45000"`.

## Co nowego w logu (obserwowalność, 0 kosztu GPU)

- `v16 dprime: switch=ON … legacy(mid)=… dprime(mid)=…` — czy przelacznik jest żywy,
- `v16 dprime: switch-off == priority_value: True` — czy eksperyment jest jednozmiennościowy
  (przy `False` log krzyczy `UWAGA`),
- `v16 dprime: depth order deep>mid=… cheap>pricey=…` — czy formuła rozróżnia gry,
- `v16 dprime: UWAGA … nieaktywny` — bieg bez D′ nie może przemknąć jako „v16”,
- po biegu `dprime_metering.jsonl` + `v16 dprime metering: {...}` — zmierzony
  `tokens_per_cleared_level`, `actions_per_call`; brak ukończonych poziomów jest jawnie nazwany.

## Weryfikacja offline (wynik tej sesji)

```
python3 tools/build_v16.py            # 42 komórki, 755 857 B, przebudowa bajt-identyczna
python3 tools/test_v16_probes.py      # 7/7 sond na stubach
python3 tools/verify_v16.py --bundle <r033> --tests
  # ALL CHECKS PASSED:
  #  42 komórki, 24 komórki kodu się kompilują, wszystkie 8 cech v13.4 nadal obecne,
  #  9/9 patchy wyciągniętych z notebooka i nałożonych w kolejności na czysty r033,
  #  drzewo się kompiluje, 12 plan-commit + 6 escalate-relative + 21 D′ + 11 winpath,
  #  playbook wbudowany == certified playbook.json (9 gier / 14 poziomów),
  #  switch-off == priority_value na spatchowanym drzewie.
```

Testy D′ (`tests/test_priority_dprime.py`, 21) obejmują m.in. zgodność z referencją
repozytoryjną `arc3_local_candidate/dprime.py`, wartość policzoną ręcznie, kolejność
głębsza>płytsza, tańszy>droższy pace, NaN/inf/None, agenta odpiklowanego bez nowego pola
i kontrakt keywordów obu miejsc wywołania.

## Diagnostyka offline: czy D′ w ogóle coś zmienia?

`tools/dprime_ordering_replay.py` odtwarza z zapisanych benchmarków to, co D′ widzi, i porównuje
rankingi (szczegóły: `reports/ordering-replay-summary.json`):

| nagranie | próbki | identyczny top-3 | korelacja rank. z realnym wynikiem: legacy / D′ |
|---|---:|---:|---|
| r085 (48 min) | 8 | 1 | +0.22 / +0.18 |
| r093 (48 min) | 9 | 0 | −0.09 / −0.07 |
| r110 (48 min) | 9 | 1 | +0.37 / +0.32 |
| r118 (90 min) | 17 | 0 | +0.27 / +0.36 |
| **razem** | **43** | **2 (5%)** | **+0.19 / +0.20** |

Wniosek: **przelacznik jest żywy** (zmienia top-3 w 41/43 próbek), ale ten test **nie daje
dowodu, że ranking D′ jest lepszy** — korelacja z realnym wynikiem jest praktycznie taka sama.
To nie jest wynik konkursowy i nie może nim być: wyniki w nagraniach powstały przy starej
alokacji. Pozytywnym dowodem pozostają tylko publikowane drawy (średnia ~29,0 vs ~25,8,
n=4, SD ~3,9) — mały, zaszumiony sygnał.

## Jak by to uruchomić (NIE zrobione, wymaga osobnego GO)

Ten katalog nie zawiera `kernel-metadata.json` i nie jest przygotowany do `kaggle kernels push`.
Aby z niego skorzystać, trzeba by: przenieść `arc3-duck-v16.ipynb` do pakietu Smak-Domu-Konkurs
jako nowy `duck-v16-arena/` z metadanymi, dodać `patches/0009-priority-dprime.patch` i testy do
drzewa, powtórzyć `verify_v13.py` w ichniejszym układzie. **Żaden z tych kroków nie został
wykonany i nie należy go wykonywać bez wyraźnej zgody.** Zero wywołań Kaggle API w tej sesji.

## Uczciwe granice

- Brak zmierzonego wyniku. Przewidywanie „26–31” z dokumentów v13.4/v15 to projekcja, nie pomiar.
- D′ nie jest zintegrowany z runnerem Smak-Domu-Konkurs; kolejność patchy jest zweryfikowana
  tylko względem r033.
- D′ ignoruje `endgame` poza wyborem φ; przy braku wspólnego zegara (φ=None) gasi bonus
  rozwojowy zamiast przełączać fazę jak stary kod. To świadoma decyzja, nie przeoczenie.
- Sam D′ nie tworzy informacji o ukrytych grach: zmienia kolejność dostępu do modelu,
  nie mechanikę rozgrywania poziomów.
