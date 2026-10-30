# ARC3 Duck v15

**Lineage:** v13.2 (Pokemon `6b10853`) → v13.3-arena (Smak `5548d35`) → **v15** (tutaj).
v13.3-arena jest w tym pakiecie nietknięte w `src/base-v13-3-arena.ipynb`; builder dokłada
cztery zmiany i nic więcej.

## 0. Co v15 ma, a czego nie ma żaden z poprzedników

| | v13.2 | v13.3-arena | **v14** (moje) | **v15** |
|---|---|---|---|---|
| batch na openerze (`ARC3_OPENER_COMMIT_HINT=1`) | – | **+** | – | **+** |
| log zdarzeń win-path (patch 0007) | – | **+** | – | **+** |
| `ESCALATE_ACTIONS` | 10 | 10 | **20** | **20** |
| sonda rosteru (czy gry się powtarzają) | – | – | **+** | **+** |
| sonda budżetu (cap vs uczciwy udział) | – | – | **+** | **+** |
| guard hooka c45 (wyjątek nie zabija notebooka) | – | – | **+** | **+** |
| łańcuch patchy | 6 | 7 | 6 | **7** (zweryfikowany przez v13.3) |
| playbook | 14 poz. | 14 poz. | 14 poz. | 14 poz. |

v15 = v13.3-arena + trzy rzeczy z v14, które są **env-only albo read-only**. Nie ma tu ani
jednego nowego patcha, więc certyfikacja v13.3 (7/7 na czystym r033, 11/11 winpath,
standalone == patched, playbook 14/14 na silniku) przenosi się bez zmian.

Diff v15 vs v13.3 to **dokładnie** komórki 1 (nazwa wariantu), 2 (`ESCALATE_ACTIONS = 20`
+ komentarz), 26 (guard sondy c45), 30 (sonda budżetu), nowa 37 (sonda rosteru). Nic więcej.

## 1. Dlaczego 20, a nie 10

`ESCALATE_ACTIONS` steruje jedną dyrektywą promptu (540 znaków ≈ 146 tokenów): „stop probing
by hand → napisz model → `check_model()` → `plan()` → `commit()`". Zmierzone na r085
(32 ukończone poziomy, `ARC3/local-lab/escalation_audit.py`):

| próg | wstrzyknięć | % puli gry | odpala **przed** ludzkim baseline'em |
|---|---|---|---|
| 10 (v13.2/v13.3) | 154 | 15,3% | 31/32 poziomów |
| **20 (v15)** | 60 | 6,0% | ~25/32 |
| `max(20, 1,2 × baseline[poziom])` | 8 | 0,8% | 0/32 |

Przykłady z v13.2/v13.3: `cn04/4` dostaje „przestań próbować" po 41 akcjach, gdy człowiek
potrzebuje 300; `cn04/5` po 52 przy 208; `m0r0/3` po 94 przy 203.

To ma znaczenie **szczególnie teraz**, bo v13.3 dokłada hint „batchuj". Dwa naciski naraz:
„wykonuj więcej akcji na turę" i „przestań działać, zbuduj model" — przy progu 10 drugi
wygrywa na pierwszych ~10 akcjach każdego poziomu. Przy 20 hint ma czas zadziałać.

**Kill-switch:** `ESCALATE_ACTIONS = 10` w komórce 2 odtwarza v13.3 co do zachowania.

## 2. Co mierzą sondy (i czego nie da się zmierzyć offline)

**Sonda budżetu** (komórka 30, przed `bm.run`): liczba gier, `n_passes`, concurrency, budżet
notebooka, uczciwy udział na grę, skonfigurowany cap i iloraz → `/kaggle/working/budget_probe.json`.

Podstawa: we wszystkich trzech zapisanych runach **każda gra kończy się dokładnie na capie**
(`max(final_wallclock_seconds) == min(...) == 48/48/90 min`). Gra nie zatrzymuje się sama, więc
cap jest przydziałem akcji. W prawdziwym rerunie cap = 532 min, a uczciwy udział przy 110
grachach ≈ 48 min → **11,04×**. Czy priority scheduler i tak pilnuje sprawiedliwego podziału —
tego nikt nie loguje; sonda rozstrzyga po jednym przebiegu.

**Sonda rosteru** (komórka 37, po biegu): czyta `bm.game_runs`, pisze `roster_probe.jsonl`
i drukuje werdykt o powtarzalności bazowych kodów gier — czyli czy pamięć win-path jest warta
**0** czy **+5…15**. Dodatkowo alarm: `actions_per_call < 1,5` → batch pressure nie działa.

## 3. Bramka GO/NO-GO (jeden slot pomiarowy)

Z komórki 35 (metering v11) + dwóch sond:

| liczba | próg | co znaczy |
|---|---|---|
| `actions_per_call` | **≥ 1,8** (v13.2: ~1,0–4,4) | hint faktycznie batchuje; bez tego cała dźwignia `tok/akcję` nie istnieje |
| `tok_per_action` | **spada** względem poprzedniego slotu | mechanizm działa dokładnie tak, jak zakłada model budżetu |
| `score` | **nie spada** przy rosnącym `a/call` | batch nie jest ślepy (inaczej „więcej akcji" ≠ „więcej poziomów") |
| `duplicate_bases` | cokolwiek | 0 → `ARC3_WINPATH` to 2,90 i koniec; >0 → +5…15 |

Jeśli `a/call` rośnie, a `score` spada — hint batchuje za agresywnie; wtedy `ARC3_OPENER_COMMIT_HINT=0`
i wracamy do v13.2 z eskalacją 20 (to jest dokładnie v14, jest w `ARC3/duck-v14/`).

## 4. Prognoza

- Podłoga bez zmian: **2,90** (playbook, 14 poziomów, 184/184 hashy).
- v15 nie obiecuje 50. Obiecuje **zmierzenie** jedynej drogi do 50: `tok/akcję`.
  Kierunkowo: `a/call` 4,36 → 6,5 przy stałym budżecie tokenów na wywołanie ≈ +50% akcji na grę.
- Rerun: **26–34** (v13.3-arena sama szacuje 28–38 dla pary slotów; ja nie doliczam pamięci,
  dopóki sonda nie powie, że roster się powtarza).

## 5. Budowa i testy

```bash
cd ARC3/duck-v15
python3 tools/build_v15.py             # -> arc3-duck-v15.ipynb (37 komórek), deterministyczny
python3 tools/test_probes.py           # sondy na stubach (budżet, roster, wyjątki)
python3 -m pytest -q tests/test_v15_package.py    # 3/3 niezmienników łańcucha/playbooka
PYTHONPATH=<arcengine> python3 -m pytest -q tests/test_winpath.py   # 11/11 (ich własne)
```

`tests/test_plan_commit.py` wymaga `inference.utils.plan_commit` ze scaffoldu (nie z pakietu) —
uruchamia się tylko na spatchowanym drzewie r033, tak jak w `tools/verify_v13.py`.

## 6. Jeden eksperyment, który bym zrobił jako następny (nie teraz)

`natężenie` = `tok/akcję`. Skoro czas na akcję to ~85% generowane tokeny, najmocniejszą
następną dźwignią jest **skrócenie historii asystenta**, ale nie tak, jak napisano w
`OCENA-ARENA-V13-3-ARENA.md`: tam „150 → 48" jest odwrócone, bo **domyślna wartość to 30**
(`_persistent_history_assistant_turns()` → `_get_env_int("ARC3_HISTORY_ASSISTANT_TURNS", 30)`).
Sensowny test to 30 → 18, jeden slot, z jawnym ryzykiem: mniej pamięci poziomu = gorsze
decyzje na trudnych poziomach. Warunek wejścia: najpierw zmierzyć `a/call` i `tok/akcję`
w v15, żeby wiedzieć, ile w ogóle zostało do wycięcia.
