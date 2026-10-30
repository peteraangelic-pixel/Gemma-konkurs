# STATUS sesji Gemma (`arena/c4eeb067-gemma-konkurs`) — punkt wejścia dla innych gałęzi

**Ostatnia aktualizacja: 2026-10-30, commit `0ef2465`.** Ten plik jest po to, żeby każda inna
sesja mogła w jednym miejscu zobaczyć, co ta gałąź już zrobiła i czego **nie** zweryfikowała.

## Jak to zobaczyć z innej gałęzi

```bash
git fetch origin arena/c4eeb067-gemma-konkurs
git log --oneline origin/arena/c4eeb067-gemma-konkurs -8
git show origin/arena/c4eeb067-gemma-konkurs:ARC3/README.md
```

Ta sesja **nie pushuje na wasze gałęzie** (zakaz mieszania pracy między sesjami) — wszystko
ląduje wyłącznie na `arena/c4eeb067-gemma-konkurs`. Wasze `duck-v15` (`8d96c68`) już zresztą
zmirrorowało moje v14 (`b38b82e`), czyli kanał działa; nowsze rzeczy to `07bf05e` i `0ef2465`.

## Co jest gotowe do wzięcia (stan na `0ef2465`)

| pakiet | commit | co to jest |
|---|---|---|
| **`ARC3/duck-v16/`** | `0ef2465` | **najlepszy**: v13.4-unified (8 patchy) + **patch 0009 self-pace** + **sonda pokrycia** |
| `ARC3/duck-v15/` | `07bf05e` | v13.3-arena + eskalacja 20 + sondy (7 patchy) |
| `ARC3/duck-v14/` | `b38b82e` | v13.2 + eskalacja 20 + sondy + guard (6 patchy) |
| `REVIEWS/` | j.w. | 8 recenzji: v13, v13.1, v13.2, v13.3-arena, v13.4+v15, wcześniejsze |

## Liczby, które warto powtórzyć, a nie cytować

Populacja: r085, 10 gier / **32 ukończone poziomy** (ta sama, której wszyscy używali dla @10/@60).

| próg eskalacji | nudge | przedwczesnych | działa w rerunie? |
|---|---|---|---|
| 10 (v13.2, v13.3) | 154 | 31/32 | tak |
| 20 (v14) | 67 | 26/32 | tak |
| 20 + cap 2 (v13.4) | 42 | 26/32 | tak |
| 0008 relatywny (v13.4, duck-v15 `8d96c68`) | 8 | 0/32 | **nie** — `base_actions_per_level is None` w trybie submisji |
| **0009 self-pace (v16)** | **22** | **14/32** | **tak** — kalibruje na `GameRun.actions_per_level` (nasz rekord) |

Reguła punktacji: `score = min(Σ s·w / Σ w, 100 × pokrycie)` — **wynik nigdy nie przekroczy
100 × pokrycia**. Dziś pokrycie ≈ 29% → ≈ 29 pkt; do 50 brakuje **+1,1 poziomu na grę**.

## Czego ta gałąź NIE zweryfikowała (nie dziedziczcie tego jako pewnika)

- **Smoke'a z GPU nie było** — wszystko powyżej jest offline: prawdziwy silnik, prawdziwe
  dane runów, `git apply`, testy. `a/call` po włączeniu opener-hinta **nie został zmierzony**.
- **Sonda rosteru nigdy nie wróciła z prawdziwego submitu** — czy roster powtarza gry, nadal
  jest założeniem, nie pomiarem.
- **Sweep playbooka na niepokrytych grach: 0 trafień** (3 gry × 60 s BFS). Podłoga to nadal
  2,90, nie więcej.
- **`plan_commit` / `commit(plan)`** — mechanizm jest opisany i uzbrojony, ale nie zmierzony.

## Audyt `duck-v17-action-efficiency` (gałąź `5ed750ef`, commit `283a36b`) — 2026-10-30

Paczka jest w repo (nie tylko w czacie). Odtworzone: `test_layer.py` **7/7**, `run_eval.py 12`
→ **RHAE 40,06 ± 0,00**. **Ale:** `agent.py` i `run_eval.py` nie importują
`action_efficiency_layer.py` ani razu — 40,06 mierzy `PlannerAgent` (model przejść + BFS),
a trzy mechanizmy mają **zero pomiarów** poza testami jednostkowymi. „12 seedów" = 12 powtórzeń
jednej deterministycznej populacji (`_make_level()` nie używa seeda → σ = 0,00).

Na naszym prawdziwym r085 (`local-lab/leverage.py`, scorowisko zgodne z harnessem 34/34):

| wariant | Δ score |
|---|---|
| cięcie akcji −30% (bez nowych poziomów) | **+2,05** |
| cięcie akcji −70% | +3,00 |
| **+1 poziom na grę** | **+16,42** |
| +2 poziomy na grę | +32,89 |

5 z 10 gier jest ograniczonych pokryciem → w nich cięcie akcji daje **dokładnie 0**.
Do 50 pkt samą efektywnością trzeba by uciąć **99%** akcji.

**Werdykt: nie nakładać na v16, nie robić v18.** Sensowne użycie: te 166 akcji/greę (78% puli),
które palimy na poziomach już ukończonych, **przekierować** na nieukończone — cięcie 30% oddaje
~11 min = ~1,2 poziomu/greę ≈ **+19 pkt**. Z mechanizmów v17 wart zachowania jest tylko
`ConvergedGuard` (pętle dłuższe niż okno; u nas `ARC3_REPEAT_STATE_GUARD` istnieje, ale jest
domyślnie wyłączony) — jako backlog **po** 2 XI. `AVX512/` jest poza konkursem i nie wchodzi
do żadnej paczki. Szczegóły: `REVIEWS/2026-10-30-v17-action-efficiency-audyt.md`.

## Zasady, których ta sesja się trzyma (i wam proponuje)

1. Nic na Kaggle bez GO użytkownika; żadnych GPU-runów bez pytania.
2. Każdy patch: `git apply --check` na **czystym r033**, potem `cmp` z plikiem, na którym
   przeszły testy — „testy zielone przy martwej funkcji" już nas raz kosztowały.
3. Domknięcie w notatniku: `\`%%writefile` bez końcowego `\n` daje **corrupt patch** —
   zapisywać patche zawsze z newline.
4. Liczby z cudzych README traktować jak hipotezy; przy każdej okazji przeliczać na r085.
