# ARC-AGI-3 v13 „MEGA" z gałęzi `arena/a450b00f-pokemon` — co jest prawdą, a co nie zadziała

**Recenzja z 2026-10-29** (sesja Gemma, `arena/c4eeb067`). Czytane: gałąź
`arena/a450b00f-pokemon` @ **`3782f8c`** (`ARC-AGI-3 duck-v13 MEGA: win-path memory + verified
replay (patch 0006), playbook 14 poziomów/9 gier…`). Klon: `/tmp/pk-a450`.
Weryfikacja **na prawdziwym kodzie gier** silnikiem z `ARC3/local-lab`, nie na opisie.

---

## 0. Wniosek w trzech zdaniach

1. **Playbook jest prawdziwy i mocny:** 14/14 poziomów, **184/184 hashy klatek** zgadza się
   na prawdziwym silniku, także przy seedach 1, 2, 7, 42. Format jest w 100% zgodny
   z `arc3_winpath._replay_once`, więc wchodzi bez zmian.
2. **Ale wart jest mniej, niż sugeruje README:** to 72,6 pkt sumarycznie na 9 grach =
   **średnio 2,90 na 25 grach publicznych** (8,07 na grach pokrytych). Na rosterze
   prywatnym, jeśli nie ma w nim gier publicznych — **0**. Widełki „35–50+" z README nie
   mają pokrycia w artefaktach.
3. **Dwie z trzech „dźwigni" patcha 0006 są w konfiguracji submisyjnej martwe:** pamięć
   poziomów wygranych w trakcie runu i `ARC3_DEAD_SKIP`. Żyje tylko część playbookowa.
   Powód jest arytmetyczny i sprawdzalny w kodzie (poniżej), nie „może zadziała".

---

## 1. Co dokładnie zawiera paczka

| plik | zawartość |
|---|---|
| `arc3-duck-v13.ipynb` | 35 komórek; plan-commit ON, `ARC3_LEVEL_TOKEN_CAP=0`, `ONLY_RESET_LEVELS=true`, `concurrency=10` |
| `src/arc3_winpath.py` | 389 linii: magazyn ścieżek, `maybe_replay`, `dead_skip`, zapis/odczyt `playbook.json` |
| `patches/0006-winpath-replay.patch` | wpięcie w `solver.py`: `maybe_replay` na początku pętli prób, `dead_skip`, `record_action` w `_execute_action` |
| `playbook.json` | 9 gier, 14 poziomów, 184 akcje, każda z hashem klatki |
| `tools/verify_v13.py`, `tests/{test_winpath,test_plan_commit}.py` | 6/6 patchy + 18 testów (ich deklaracja) |
| `../pc-sweep-pack/` | `sweep2.py` + `RUN-NA-PC.md` (BFS na PC, cap 600–1200 s) |

`ANALIZA-23.md` w paczce zgadza się z moją diagnozą w dwóch z pięciu punktów (cap 45k
kosztuje; brak pamięci między passami). Różnica: ja mam **dowód**, że rozcieńczenie tokenów
to nie „mniej czasu na grę" (bo cap 532 min nie wiąże), a **sekundy na akcję** — patrz §4.

---

## 2. Weryfikacja playbooka — REPRODUKUJĘ 14/14

Metoda: `ARC3/local-lab/playbook_verify.py`. Dla każdego (gra, poziom): sprawdzam hash
startowy, wykonuję akcje po kolei, porównuję hash każdej klatki **ich schemą**
(`sha256(repr(grid))[:16]`), potem sprawdzam, że `levels_completed` wzrosło.

```
cn04   1 poziom  14 akcji  hashe 13/13  PASS      m0r0  2 poziomy 39 akcji  PASS/PASS
ft09   1         5         4/4     PASS      sp80  1         28         28/28  PASS
lp85   1         6         5/5     PASS      tu93  4         65         4/4    PASS
ls20   1        14        13/13    PASS      vc33  2         15         2/2    PASS
                                            cd82  1          5         5/5    PASS
=== 14/14 poziomów odtwarza się na prawdziwym kodzie gier (184 akcje)
=== seed 1 / 2 / 7 / 42: również 14/14 (gry są deterministyczne względem seeda)
```

To jest **mocniejszy wynik niż ich własne `verify_v13.py`**, bo oni sprawdzali, że patch
się aplikuje i testy przechodzą; ja sprawdziłem, że **sekwencje naprawdę kończą poziomy**.
Playbook jest też odporny na dopasowanie id: `_norm()` + prefiks w obie strony trafia
w klonowane id (`tu93-abc123` → `tu93`), więc `official_110()` go nie rozłączy.

## 3. Ile to jest warte — dokładnie

Punkty z samych ścieżek playbooka, przy założeniu, że model nie zrobi już nic więcej
(liczone formule taaf, `analyze_run`-em):

| gra | poziomy z playbooka | pkt (z 100) |
|---|---|---|
| tu93 | 1–4 | **22,22** |
| m0r0 | 1–2 | 14,29 |
| vc33 | 1–2 | 10,71 |
| cd82 / cn04 / ft09 / sp80 | 1 | po 4,76 |
| lp85 | 1 | 2,78 |
| ls20 | 1 | 3,57 |
| **razem** | 14 | **72,61** |

Suma 72,6 wzięła się stąd, że wszystkie 14 poziomów jest **szybszych niż baseline**
(1,06–11,00× baseline, mediana 1,79), więc każdy jest przy capie 115 pkt.

**Normalizacja do średniej, która jest wynikiem w konkursie:**
- po 25 grach publicznych: **2,90**;
- po 9 grach pokrytych: 8,07;
- po 110 grach, jeśli roster jest w pełni prywatny: **0,00** (playbook nie trafi).

Wniosek: playbook to **gwarantowana podłoga na grach publicznych**, a nie droga do 50.
Nawet gdyby cały roster był publiczny, 2,90 to nie 35–50.

## 4. Dlaczego „35–50+" z README nie ma podstaw — arytmetyka submitu

README zakłada, że replay „zamienia najdroższe poziomy w niemal darmowe" w wielu passach.
W konfiguracji submisyjnej (cell 21 notatnika):

```python
bm.n_passes = 4
if TRUE_SUBMISSION:
    bm.n_passes = 1                                   # <-- passów jest JEDEN
    bm.solver.concurrency = 10
    bm.solver.max_runtime_s_per_game = 532*60         # nigdy nie wiąże
```

- **budżet notatnika**: 32 400 s; **roster** 110 gier; **concurrency** 10
  → 11 fal → **2 945 s (49 min) na grę**. Cap 532 min nie jest ograniczeniem.
- `s/akcja` jest liniowe w `tok/akcja` (r = 0,99–1,00), a nachylenie zależy od silnika:
  **17,2 ms/token** (r085, 8B) vs **62,6** (r110, ten sam 8B) vs **63,1** (r118, 27B).
  Stąd akcje/gę: **228 / 82 / 63**.

Czyli dźwignią jest **sekundy na akcję** (tokeny/akcję × jakość silnika), nie liczba passów
ani okno. A `n_passes > 1` nie jest alternatywą: 440 runów = 44 fale = 12 min/gę.

## 5. Co z patcha 0006 realnie działa w submisie

| mechanizm | działa? | dowód |
|---|---|---|
| **playbook** (wpisy `src: offline-sweep`) | **TAK** | `_merge_playbook` wgrywa je przy starcie sesji; `maybe_replay` odpala się w pierwszej iteracji pętli, zanim padnie decyzja LLM; strażnik `init` hash + weryfikacja klatka-po-klatce |
| **pamięć poziomów wygranych w trakcie runu** (`record_action`) | **NIE** | wpis powstaje po ukończeniu poziomu k, a `_replay_once` szuka wpisu **dla bieżącego poziomu**. Wrócić do ukończonego poziomu można tylko pełnym resetem; z `ONLY_RESET_LEVELS=true` RESET po śmierci cofa **do początku bieżącego poziomu**, a `n_passes=1` nie daje drugiego przejścia |
| **`ARC3_DEAD_SKIP`** | **NIE** | wymaga `pass_index >= 4` i `passes_completed >= 3`; przy jednym passie oba są 0 |
| **reset poziomu z budżetu (patch 0004)** | **NIE** | `enabled` tylko gdy `ARC3_LEVEL_TOKEN_CAP > 0`, a v13 ustawia `0` |

To nie jest błąd, który psuje run — wszystko jest w `try/except` i degraduje się cicho do
stockowego zachowania. Ale README sprzedaje trzy dźwignie, z których **dwie są inertne**,
a trzecia (playbook) jest warta 2,90 na grach publicznych.

**Naprawa, jeśli chcesz, żeby pamięć w-run działała:** ustawić `ONLY_RESET_LEVELS=false`
(wtedy RESET po śmierci wraca do poziomu 1 i wtedy replay wpisów `src: run` faktycznie
odpala). To jest *jedna* zmiana, mierzalna, i warto jej nie łączyć z niczym innym.
Uwaga: z `ONLY_RESET_LEVELS=false` tracisz darmowe resety poziomu z patcha 0004 — przy
`cap=0` i tak są nieaktywne, więc koszt jest zerowy.

## 6. Rekomendacja na slot 30.10

| zmiana | ryzyko | spodziewany efekt |
|---|---|---|
| push v13 **jak leży** | niskie (playbook + cap-off + plan-commit) | +2 do +5 pkt na grach publicznych; ~0 jeśli roster prywatny |
| `ARC3_LEVEL_TOKEN_CAP=0` — zostawić | niskie | zmierzone +0,4…+2,2 vs 45k |
| `ONLY_RESET_LEVELS=false` | średnie (zmienia zachowanie resetów) | włącza pamięć w-run; +EV tylko przy 2+ poziomach na grę |
| `n_passes>1` | wysokie | nie: 44 fale × 12 min = mniej akcji na grę, nie więcej |

Nie wysyłać z nadzieją na 50+. Realistycznie: **28–31**, czyli tyle, ile daje c45 bez
regresji + playbook. Żeby ruszyć w stronę 50, trzeba podnieść **akcje na grę z ~228 do
400–600** przy 8B-owym silniku, czyli zejść z ~650 do ~230–370 tok/akcję — to jest
`PLAN-50.md` §4 M1/M3 i `MEGA-CONFIG.md` §1–§3.

## 7. Ograniczenia tej recenzji

- Playbook sprawdzony na **25 grach publicznych** i seedach 0–42; na rosterze reruna nie
  da się sprawdzić bez wejścia w run (a wtedy dowód przestaje być darmowy).
- „Dwie dźwignie inertne" wynika z kodu (`_replay_once` + ustawienia z cell 21). Jeśli
  harness w którymś miejscu wywołuje RESET na początku nowego poziomu, wniosek o pamięci
  w-run trzeba złagodzić — nie znalazłem takiego wywołania, ale nie mam logu z rerunu.
- Nie uruchamiałem `verify_v13.py` ani `sweep2.py` (wymagają bundle r033 / Kaggle);
  sprawdziłem to, co dało się sprawdzić lokalnie: **czy poziomy naprawdę się kończą**.
