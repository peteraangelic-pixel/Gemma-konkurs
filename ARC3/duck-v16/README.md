# ARC3 Duck v16 — najlepsze z czterech gałęzi + jedna rzecz, której nie miała żadna

**Lineage:** v13.2 (Pokemon `6b10853`) → v13.3-arena (`5548d35`) → v13.4-unified (Smak, best-of) →
**v16** (tutaj) — plus pomiar z `arena/7911f950-pokemon` (`V16-PLAN.md`) i `duck-v15` z
`arena/a450b00f-pokemon` (`8d96c68`).

## 1. Co sprawdziłem na tych gałęziach (wyniki, nie cytaty)

| sprawdzane | wynik |
|---|---|
| **v13.4-unified**, 8 patchy na czystym r033 | **wszystkie 8 wchodzą czysto** — odtworzyłem to sam z bundle'a r033, wyciągając patche z komórek notebooka |
| patch **0008** (eskalacja relatywna) na r085 | **8 nudge'ów / 0 przedwczesnych** — potwierdzone własnym uruchomieniem funkcji z patcha na 32 poziomach |
| **v13.4 twierdzi „fallback na 20 przy braku baseline'u"** | prawda, ale to **cały** efekt w rerunie: `taaf/game.py` mówi wprost *„base_actions_per_level is None when the engine hides baselines (e.g. submission mode)"*. W submisji 0008 **nic nie robi** |
| **duck-v15** (Pokemon): patch 0007 = próg względny na `base_actions_per_level` | ten sam problem: w rerunie degraduje do 20 + cap 2. Ich własne README to przyznaje („measurable win is local/smoke") |
| **v16-plan** (7911f950) | słuszna reguła `score ≤ 100 × coverage` i uczciwy rejestr błędów, ale **warstwa analityczna nie jest w żadnym pakiecie** — nie ma czego wysłać, jest tylko dokument |
| poprawione liczby @20 | **67 nudge'ów** na r085 (42 z capem 2/poziom), nie 60 — v14 zaokrągliła interpolacją |
| sweep niepokrytych gier (playbook) | 3 gry × 60 s: **0 trafień** (BFS 528–990 węzłów, level 1 nie wpada). Nie obiecuję punktów, których nie ma |

## 2. Co ma v16, a czego nie ma żadna inna gałąź: **patch 0009 — eskalacja na własnym tempie**

Problem, który wszystkie cztery sesje przeoczyły, choć każda go widziała w kodzie:
**w rerunie ludzkiego baseline'u nie ma**, więc:

- `ESCALATE_ACTIONS=10` (v13.2/13.3) → 154 nudge'ów, 15,3% puli, 31/32 przedwczesnych;
- `=20` (v14) → 67 / 42 z capem;
- `0008` relatywny (v13.4, duck-v15) → **w rerunie identyczny z 20**, bo baseline `None`;
- **`0009` self-pace** → próg z **naszych własnych** ukończonych poziomów w tej grze:

```
threshold = clamp(1.5 × mediana(actions_per_level[:levels_completed]), 20, 120)
            + max 2 nudge'e na poziom
```

`GameRun.actions_per_level` to **nasz** rekord — nie jest ukrywany w żadnym trybie. Zmierzone
na r085 (32 ukończone poziomy, ta sama populacja, na której wszyscy liczyli @10/@60):

| próg | nudge | przedwczesnych (przed ludzkim baseline'em) | działa w rerunie? |
|---|---|---|---|
| @10 (v13.2/13.3) | 154 | 31/32 | tak |
| @60 (v13.1) | 12 | 7/32 | tak |
| @20 (v14) | 67 | 26/32 | tak |
| @20 + cap 2 (v13.4) | 42 | 26/32 | tak |
| 0008 relatywny (v13.4, duck-v15) | 8 | 0/32 | **nie — baseline = None** |
| **0009 self-pace (v16)** | **22** | **14/32** | **tak** |

Czyli: przy tym samym budżecie „przestań próbować" trafia w poziom, który **ta** gra realnie
przegrywa (np. `ls20` poziom 3: 222 akcje, mediana ukończonych 96 → nudge dopiero po ~144), a nie w każdy poziom po 20 akcjach.
Patch jest env-gated (`ARC3_ESCALATE_SELF_PACE=0` → dokładnie v13.4) i **nie zmienia niczego,
gdy baseline jest widoczny** (wtedy wygrywa relatywny z 0008 — test to sprawdza).

## 3. Co v16 dziedziczy (i czego nie rusza)

| element | źródło | stan |
|---|---|---|
| `ARC3_OPENER_COMMIT_HINT=1` (batch na otwarciu tury) | v13.3 | jedyna dźwignia `tok/akcję`, nietknięta |
| patch 0007 log `[arc3-winpath]` (replay: start/ok/abort+powód) | v13.3 | nietknięty |
| `ESCALATE_ACTIONS=20` | v14 (moje) | nietknięty, podłoga progu |
| guard hooka sondy c45 | v14 | nietknięty |
| sonda budżetu (cap vs uczciwy udział) | v14 | nietknięta, `cap_over_fair` = 11,04× przy 110 grach |
| sonda rosteru → `roster_probe_runs.jsonl` | v13.4 | nietknięta |
| **sonda pokrycia** (`baseline=yes|no`, `coverage`, `a/call`) | **v16 (nowe)** | patrz §4 |
| playbook 14 poziomów / 9 gier (2,90 średniej) | v13.2 | bajt w bajt, md5 `e2d86b1e07fe` |
| `src/arc3_winpath.py` standalone | v13.3 | bajt w bajt (`b8ffedaa…`) |

## 4. Sonda pokrycia — cztery liczby, które kończą zgadywanie

Po biegu, tylko odczyt `bm.game_runs` → `/kaggle/working/coverage_probe.json`:

```
v16 coverage: {"games":110,"mean_coverage":29.3,"mean_score":27.1,
               "baseline_available":0,"mean_a_per_call":1.0,"mean_tok_per_action":853}
```

- **`coverage`** — reguła `score ≤ 100 × coverage` (zweryfikowana 30/30 przez 7911); pokrycie
  **jest** prognozą wyniku. Dziś 29% → 29 pkt. Do 50 brakuje **+1,1 poziomu na grę**.
- **`baseline=yes|no`** — rozstrzyga na żywo, czy 0008 w ogóle się włączył (spodziewam się `no`
  na 110 grach; wtedy 0009 jest jedynym progiem, który tam działa).
- **`a/call`** — czy hint batchuje. Jeśli `< 1,5`, dźwignia `tok/akcję` nie zadziałała i cała
  droga do 50 leży odłogiem.
- **`tok_per_action`** — spadek = mechanizm działa (`akcje/grę = 2945 s ÷ (tok/akcję × ms/tok)`).

## 5. Prognoza i bramka

- Podłoga: playbook **2,90** (rośnie tylko nowymi poziomami; sweep 3 gier dał 0 — nie obiecuję).
- Pamięć win-path: **0 albo +5…15**, zależnie od sondy rosteru.
- Rerun: **26–31**. v16 nie obiecuje 50 — obiecuje, że po jednym przebiegu będzie wiadomo,
  **które** z trzech ograniczeń trzeba ruszyć:

| obserwacja po biegu | co robić dalej |
|---|---|
| `mean_a_per_call < 1,5` | batch nie działa → wymusić `action(actions)` w pętli, nie w promptcie |
| `mean_a_per_call ≥ 2`, `coverage` stoi | model batchuje ślepo → zejść z hintem, wrócić do v14 |
| `baseline_available > 0` | 0008 żyje → podnieść `ARC3_ESCALATE_RATE` / zdjąć cap |
| `cap_over_fair > 1,3` i gry kończą na capie | głodzenie rosteru → `max_runtime_s_per_game` = uczciwy udział |

## 6. Budowa, testy, weryfikacja

```bash
cd ARC3/duck-v16
python3 tools/build_v16.py                    # -> arc3-duck-v16.ipynb (41 komórek), deterministyczny
python3 -m pytest -q tests/test_v16_package.py tests/test_self_pace.py tests/test_coverage_probe.py
PYTHONPATH=<arcengine> python3 -m pytest -q tests/test_winpath.py    # 11/11
```

Stan: **7/7 testów pakietu + 11/11 winpath + sondy na stubach** — wszystko zielone lokalnie.
`tests/fixtures/tool_agent_0009_{pre,post}.py` to wycinki z prawdziwego spatchowanego drzewa;
`test_v16_package.py` sprawdza, że `diff pre post` **równa się** patchowi 0009 (żadnego
„testuję coś innego, niż wysyłam").

Patch 0009 sam w sobie sprawdzony: **`git apply` czysto** na łańcuchu 8 patchy, wynik **bajt w
bajt** równy plikowi, który przeszedł testy, i `compileall` bez błędów.

## 7. Czego tu nie ma (świadomie)

- **Nie ruszam** `bm.n_passes`, `max_runtime_s_per_game` ani `soft_end_time` — sonda najpierw.
- **Nie ruszam** trimmingu historii (`ARC3_HISTORY_ASSISTANT_TURNS`, domyślnie **30**, nie 150 jak
  podaje OCENA v13.3) — to następny eksperyment, ale po pomiarze `a/call`.
- **Nie dokładam** nowych poziomów do playbooka bez trafienia (sweep: 0/3).
- **Nie wysyłam** nic na Kaggle bez GO.
