# Audyt `duck-v17-action-efficiency` — czy bije v16 i czy to nakładać? (2026-10-30)

**Materiał:** `arc3_duck-v17-action-efficiency.zip` (44 KB), znaleziony na gałęzi
`arena/5ed750ef-smak-domu-konkurs`, commit `283a36b` („Add files via upload") —
czyli paczka **jest** w repo, mimo że sesja, która ją zrobiła, nie miała poświadczeń GitHuba.
Zawartość: `ARC3/duck-v17-action-efficiency/` (9 plików), `ARC3/REVIEWS/2026-10-30-audyt-galezi-i-duck-v17.md`,
`AVX512/` (5 plików C + raport), `PUSH_INSTRUCTIONS.md`, `README.md`.

**Wniosek w trzech zdaniach:** wszystkie twierdzenia liczbowo się odtwarzają
(`test_layer.py` 7/7, `run_eval.py` RHAE 40,06), ale **40,06 nie jest zasługą tej warstwy** —
`run_eval.py` porównuje dwa *agenty* (`ReactiveAgent` vs `PlannerAgent` z modelem przejść i BFS),
a `action_efficiency_layer.py` nie jest importowany przez `agent.py` ani `run_eval.py` ani razu.
Wzięte na naszych prawdziwych danych (r085) *jakiekolwiek* cięcie akcji jest warte **+2,05 pkt
za −30%** i **dokładnie 0** na 5 z 10 gier, bo wiąże pokrycie, nie efektywność. **Nie nakładać,
nie robić v18.**

---

## 1. Co odtworzyłem (i czym)

| twierdzenie v17 | wynik u mnie | jak |
|---|---|---|
| `test_layer.py` → 7/7 | **7/7 PASS** | `python3 test_layer.py` (82 ms) |
| `run_eval.py 12` → RHAE 40,06 | **40,06 ±0,00** | `python3 run_eval.py 12` (24 s) |
| REACTIVE (baseline) 3,80; 1 337 akcji/poziom | **3,80; 1 337** | to samo wyjście |
| deterministyczne | **tak** | powtórka identyczna co do 0,01 |
| 2 z 4 gier na 0,00 | **potwierdzone** (switchorder, colorclicks) | j.w. |

Warstwa jest czystym Pythonem, bez zależności, więc to się uruchamia w 25 s. Do tego stopnia
paczka jest **rzetelna** — liczby nie są zmyślone.

## 2. Blocker: 40,06 mierzy coś innego, niż twierdzi README

```
$ grep -rln "action_efficiency_layer" .
./README.md  ./RAPORT.html  ./STATUS.md  ./test_layer.py      # i nic więcej
```

`agent.py` (12 832 B) nie ma ani jednego odwołania do `PlanCache`, `ConvergedGuard`,
`BudgetLedger` czy `HarnessHook`. `run_eval.py` importuje `from agent import ReactiveAgent,
PlannerAgent` i mierzy **te dwa agenty**. Czyli tabela „RHAE 3,80 → 40,06" pokazuje, ile daje
**model przejść + BFS + inferencja celu**, a nie ile daje warstwa action-efficiency.

Warstwa jest sprawdzona tylko przez `test_layer.py` — 7 testów jednostkowych na **sztucznych
wejściach** (`PlanCache()` z ręcznie wstrzykniętymi kluczami, `ConvergedGuard(repeat_threshold=3)`,
`BudgetLedger(total_actions=1000)`). Żaden z nich nie dotyka gry, agenta ani licznika RHAE.

To jest **dokładnie ten wzorzec, który ta sama sesja wytknęła innym** w swoim audycie
(„testy 6/6 zielone przy martwej funkcji"). Tutaj wersja łagodniejsza, ale ta sama klasa błędu:
zielone testy + liczba w nagłówku, które **nie są połączone**. Uczciwie: `STATUS.md` §5 mówi
„nie ma modelu w pętli", ale nie mówi „warstwa nie jest w pomiarze" — a to jest różnica
między „zmierzone offline" a „niezmierzone".

**Konsekwencja:** zdanie z `README.md` pkt 2 („trzy mechanizmy + **zmierzony** wynik offline:
RHAE 3,80 → 40,06") jest nieprawdziwe w tej jednej rzeczy, która ma znaczenie. Poprawna wersja:
„trzy mechanizmy + planista, którego wynik zmierzono; **wpływ samych mechanizmów = 0 pomiarów**".

## 3. „12 seedów" to w praktyce n = 1

`sim.py`: konstruktor zapisuje `random.Random(seed*1000+level)`, ale **`_make_level()` go nie
używa** — poziom losowany jest z `random.Random(level*77+5)` (i `level*31+11`). Dlatego
`game_score_stdev` = **0,00 dla wszystkich 4 gier i 12 seedów**. Seed nie zmienia świata,
tylko `rng` agenta, którego `PlannerAgent` przeważnie nie używa.

Więc „12 seedów, deterministyczne" = **jedna populacja, powtórzona 12 razy**. To nie jest
zarzut o fałsz — to zarzut o **brak pokrycia**: 4 deterministyczne mikro-gry nie mówią nic
o 10 grach ARC-AGI-3, z których każda jest inna.

## 4. Czy warto w ogóle gonić akcje? Nasze prawdziwe dane mówią: prawie nie

To jest najważniejsza część audytu, bo dotyczy **każdej** warstwy action-efficiency, także
poprawnej. Policzmy na r085 (`kaggle/ops/results/r085-kernel_output_pick/output-pick/benchmark.json`)
skorowiskiem, które wcześniej odtworzyło `final_score` harnessu w **34/34** przypadkach
(`local-lab/verify_scoring.py`):

| gra | lvl | raw | cap | score | co wiąże |
|---|---|---|---|---|---|
| tn36 | 1/7 | 4,1 | 3,6 | 3,6 | pokrycie |
| m0r0 | 4/6 | 46,3 | 47,6 | 46,3 | efektywność |
| cn04 | 5/6 | 79,9 | 71,4 | 71,4 | pokrycie |
| dc22 | 3/6 | 27,7 | 28,6 | 27,7 | efektywność |
| ka59 | 5/7 | 49,9 | 53,6 | 49,9 | efektywność |
| sc25 | 3/6 | 17,1 | 28,6 | 17,1 | efektywność |
| s5i5 | 2/8 | 9,2 | 8,3 | 8,3 | pokrycie |
| ls20 | 3/7 | 8,8 | 21,4 | 8,8 | efektywność |
| su15 | 3/9 | 15,3 | 13,3 | 13,3 | pokrycie |
| g50t | 3/7 | 24,0 | 21,4 | 21,4 | pokrycie |

**Średnio 26,78.** Pięć gier jest ograniczonych pokryciem — w nich cięcie akcji daje
**dokładnie zero** (cap `100·Σk/Σk_max` nie zależy od akcji). W pozostałych pięciu sufituje
`min(·, 115)` na poziom.

| wariant | score | Δ |
|---|---|---|
| dziś | 26,78 | — |
| cięcie akcji **10%** | 27,89 | +1,11 |
| cięcie akcji **20%** | 28,38 | +1,60 |
| cięcie akcji **30%** | 28,83 | **+2,05** |
| cięcie akcji **50%** | 29,34 | +2,56 |
| cięcie akcji **70%** | 29,79 | +3,00 |
| **+1 poziom na grę** | 43,20 | **+16,42** |
| **+2 poziomy na grę** | 59,67 | **+32,89** |
| +1 poziom i cięcie 30% | 44,59 | +17,81 |

Żeby **samą** efektywnością, bez ani jednego nowego poziomu, dojść do 50 pkt, trzeba by
uciąć **99%** akcji na ukończonych poziomach. Jedna dodatkowa akcja mniej jest warta tyle,
ile ~1/8 poziomu.

**Ale jest drugi odczyt, i to jest jedyna użyteczna rzecz z v17.** Na r085 zużywamy średnio
213 akcji na grę, z czego **166 (78%) na poziomach już ukończonych**. Cięcie 30% właśnie tam
oddaje ~50 akcji/greę = przy 12,9 s/akcję **+11 min** = **~1,2 poziomu/greę** = **+19 pkt**.
Czyli: akcje są warte nie jako *mnożnik*, tylko jako **paliwo do przekierowania na poziomy
nieukończone**. v17 mówi „cięcia akcji to dźwignia" — precyzyjniej: cięcia akcji to **budżet**,
a dźwignią jest pokrycie. To nie unieważnia ich mechanizmów, ale odwraca priorytet.

## 5. Co z tego jest naprawdę nowe (i warte zachowania na później)

| mechanizm v17 | mamy odpowiednik? | ocena |
|---|---|---|
| `PlanCache` | **tak** — playbook (9 gier / 14 poziomów, 184 hashe) | zero wartości dodanej: sweep na nowych grach **0/3**. Cache planów nie generalizuje, co do tego mamy własny pomiar negatywny. |
| `ConvergedGuard` | częściowo — `ARC3_NOOP_REPEAT_GUARD` / `ARC3_REPEAT_STATE_GUARD`, kluczowane po `(plansza, akcja)`, ale **domyślnie wyłączone** i tylko w obrębie jednego snippetu | **jedyne realnie nowe**: pętla dłuższa niż okno (ich test: cykl 6-krokowy). Maszyna stanów już u nas jest (`state_key` = hash planszy), więc to ~20 linii włącznika, nie nowy moduł. Do przetestowania offline na zapisanych śladach z r085 — ale nie przed 2 XI. |
| `BudgetLedger` | nie — mamy próg 0009 self-pace *w obrębie* gry | ciekawe **tylko jeśli** harness pozwala wybierać, której grze dać następną akcję. Tego nie wiemy (niezweryfikowane: kolejność gier w submicie). `priority = completed/(actions+200)` to sensowna forma, ale nasze dane mówią, że problemem są *przedwczesne nudge'e*, a nie zły wybór gry. |
| `AVX512/` | nie dotyczy | wątek sprzętowy, ortogonalny do konkursu. Nie weryfikowałem (C + raport HTML); **nic z tego nie wchodzi do paczki** i nie ma wpływu na wynik. Wspominam tylko, żeby nikt tego nie policzył jako „postęp". |

## 6. Werdykt na trzy pytania

**(a) Czy to bije v16?** Nie, i nie jest to pytanie „czy". To nie jest wersja ducka: nie ma
modelu (Gemma), nie ma harnessu, nie ma bramki. Liczba 40,06 pochodzi z 4 mikro-gier z
„ludzkim" budżetem akcji zdefiniowanym w `sim.human_actions()`, więc **nie jest porównywalna
z naszym 26,78** na 10 prawdziwych grach. Porównywanie ich byłoby tym samym błędem, który
ta sesja wytknęła innym (replay ≠ gateway). Jako *wersja* — 0:1 dla v16, bo v16 przynajmniej
istnieje w formie, którą można wysłać.

**(b) Czy nałożyć na v16 i mierzyć medianę akcji na ukończony poziom (Δ > 0 inaczej nie wysyłać)?**
Reguły nie da się dziś wykonać **uczciwie**: nie ma GPU, nie ma bramki, a „przed/po" na r085
wymagałoby dwóch pełnych submisji. A z tabeli w §4 wiemy z góry, czego szukać: nawet
**prawdziwe** −30% daje **+2,05**, czyli ~1/8 tego, co daje jeden poziom w jednej grze.
Mediana akcji na poziom to dobra metryka *diagnostyczna*, ale próg „Δ > 0" przepuści szum.
**Rekomendacja: nie nakładać. Zamrozić v16 na submisję, resztę czasu wydać na pokrycie.**

**(c) Czy tworzyć v18?** Nie. Zgadzam się z ich własną rekomendacją („nie twórzcie v18"),
i dodaję mocniejszy powód niż oni: v18 zbudowane z tej warstwy mierzyłoby co najwyżej +2 pkt,
a każda iteracja notatnika to ryzyko regresji w 34 patchach, które już przeszły `git apply`.

## 7. Trzy zdania do poprawienia, jeśli ktoś będzie to cytował

1. „Trzy mechanizmy + zmierzony wynik 40,06" → „planista: 40,06; mechanizmy: 0 pomiarów".
2. „RHAE rośnie kwadratowo ze spadkiem akcji — jedyna dźwignia" → „…ale sufituje na
   `min(·, 1,15)` i na capie pokrycia; w naszej submisji warte +2 pkt za −30%".
3. „12 seedów" → „12 powtórzeń jednej deterministycznej populacji (σ = 0,00)".

## 8. Reprodukcja

```bash
# 1. paczka drugiej sesji (jest w repo, nie tylko w czacie)
git clone -b arena/5ed750ef-smak-domu-konkurs https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs.git /tmp/smak
cd /tmp/smak && python3 -c "import zipfile; zipfile.ZipFile('arc3_duck-v17-action-efficiency.zip').extractall('/tmp/v17')"
cd /tmp/v17/ARC3/duck-v17-action-efficiency && python3 test_layer.py && python3 run_eval.py 12

# 2. kto importuje warstwę
grep -rln "action_efficiency_layer" .        # -> tylko README/RAPORT/STATUS/test_layer

# 3. ile warte są akcje w PRAWDZIWYM zgłoszeniu
cd /home/user/Gemma-konkurs/ARC3/local-lab
python3 verify_scoring.py /tmp/smak/arc-agi-3/kaggle/ops/results   # 34/34 zgodne z harnessem
python3 leverage.py /tmp/smak/arc-agi-3/kaggle/ops/results/r085-kernel_output_pick/output-pick/benchmark.json
```
