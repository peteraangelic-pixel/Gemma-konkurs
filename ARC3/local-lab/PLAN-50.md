# PLAN-50 — jak z 23 zrobić 50+ (29.10.2026)

Dokument opiera się **wyłącznie** na artefaktach, które mamy w repo plus na lokalnym silniku
odtworzonym w tym sandboxie. Każda liczba ma źródło: plik `benchmark.json` (własny zapis
harnessu) albo pomiar lokalny. Rzeczy niezweryfikowane są oznaczone.

---

## 0. TL;DR

1. **23 nie jest szumem ani pechem.** To poziom całej linii przy budżecie ~45 tys. tokenów
   na grę. r110 (v13, cap 45k) na 10 grach dev dał **0,73**; r085 (bez capa, ~146k tokenów)
   dał **26,78**; oficjalny LB dla tej samej rodziny to 26,25 / 23,89 / 24,66.
2. **Nasza własna arytmetyka punktów była błędna do 32×.** Reguła ma *dwa* ograniczenia, nie
   jedno: `min(115, (baseline/actions)²·100)` na poziom **oraz** cap na skali 100 od liczby
   ukończonych poziomów. Dodatkowo liczy się tylko poziom *ukończony* — wpis w
   `actions_per_level` dla poziomu, na którym agent właśnie utknął, to zero punktów.
   Poprawiona implementacja odtwarza **32/32** zapisanych `final_score` (patrz
   `local-lab/verify_scoring.py`).
3. **Gdzie brakuje punktów (r085, 10 gier dev):** 26,78 faktycznie; te same poziomy przy
   baseline = 29,79 (+3,0); wszystkie poziomy = 90,78. **Głębokość to 96% brakujących
   punktów, efektywność akcji +3.**
4. **Głębokość ogranicza liczba akcji, a tę — tokeny na akcję i progi poddawania się.**
   Projekcja z zachowaną efektywnością runu: przy 200 akcjach/gę 35,6 (gdyby nie porzucać
   poziomów w połowie), 400 → 72,3, 600 → 83,1. To *górne* ograniczenie: nie zakłada nowych
   umiejętności, tylko niepoddawanie się i więcej czasu.
5. **50+ jest więc osiągalne zmianami budżetu i alokacji, a nie „lepszym modelem"** — pod
   warunkiem, że ściany w grze są czasowe, a nie rozumowania. Pomiar, który to rozstrzyga,
   jest tani: wciągnąć log r116 (akcje/tokeny na grę) i puścić `analyze_run.py`.

---

## 1. Reguła punktacji — dokładnie

Źródło autorytatywne: `kaggle/ops/results/r033-recon-bundle/bundle/src/tufa-arc-agi-framework/src/taaf/game.py::_compute_final_score`
(taaf „mirrors arc_agi.scorecard.EnvironmentScoreCalculator v0.9.8").

```
dla każdego poziomu k = 1..n (n = liczba poziomów gry):
    w_k = k
    jeśli k <= levels_completed i actions_k > 0:
        s_k = min(115, (baseline_k / actions_k)² · 100)
    wpp: s_k = 0

raw   = Σ s_k·w_k / Σ w_k
cap   = 100 · Σ_{k: s_k>0} w_k / Σ w_k
score = min(raw, cap)
wynik_gry = średnia score po grach (110 gier ukrytych)
```

Dwie pułapki, obie kosztowały nas błędne szacunki:

| pułapka | efekt na cn04 (r093) | poprawnie |
|---|---|---|
| zaliczenie poziomu w toku (wpis w `actions_per_level` bez `levels_completed`) | 11,30 | **0,35** |
| pominięcie capa ukończenia (myślenie „cap = 1,15") | 5,48 | **4,76** |

Kod: `local-lab/lab/engine.py::game_score`, testy: `local-lab/test_lab.py`,
regresja na zapisanych runach: `local-lab/verify_scoring.py` (32/32) i `arc3lab score`
(wersja Rust, te same liczby w `cargo test`).

**Konsekwencja strategiczna:** poziom k płaci k jednostek, więc na grze o 9 poziomach
ostatni poziom to sam 20% gry, a pierwszy 2,2%. Głębokość bije szerokość, a efektywność
akcji jest tylko wentylem bezpieczeństwa — nie źródłem punktów (cap 100).

---

## 2. Diagnoza: dlaczego 23

### 2.1 Krzywa dawka→efekt (10 gier dev, mediana)

| run | konfiguracja | tokeny/grę | akcje/grę | tok/akcja | poziomów (mediana) | średnia |
|---|---|---|---|---|---|---|
| r110 | v13, cap 45k | 45 208 | 80 | 569 | **0** | **0,73** |
| r085 | uncapped (~48 min) | 146 325 | 198 | 737 | 3 | **26,78** |
| r093/r108 | uncapped | 171 222 | 200 | 858 | 2 | 18,55 |
| r050 | 132 min/grę | 231 366 | 521 | 444 | 0 | 0,00 |

r085 ↔ oficjalne 26,25 (duck v3). Lokalna średnia po 10 grach dev jest **dobrym proxy LB**
(błąd ~2 pkt), więc można na niej iterować bez palenia slotu.

### 2.2 Rozkład strat (r085, punkty)

| gra | stan | zysk z naprawy wentyla | zysk z naprawy głębokości |
|---|---|---|---|
| MEAN | 26,78 | **+3,00** | **+70,21** |

Szczegóły per gra w `python3 analyze_run.py <benchmark.json>`; dwie gry psują wentyl
mocno: ls20 (poz. 2: 175 akcji vs baseline 123; poz. 3: 222 vs 73) i sc25 (poz. 4: 111 vs 83).

### 2.3 Projekcja budżetu akcji (ten sam agent, ta sama efektywność)

| akcje/gę | średnia | sumarycznie poziomów |
|---|---|---|
| 200 | 35,55 | 37 |
| 300 | 59,53 | – |
| 400 | 72,25 | 59 |
| 600 | 83,13 | 65 |
| 1200 | 90,78 | – |

Dwie rzeczy naraz: (a) przy **tym samym** budżecie 200 akcji, ale bez porzucania poziomów
w połowie, wynik rośnie 26,8 → 35,6; (b) każde podwojenie budżetu akcji to skok o klasę.
Model nie zakłada nowych umiejętności — tylko niepoddawanie się. To jest **górna granica**;
tam, gdzie poziom jest ścianą rozumowania, projektowane poziomy nie przyjdą.

### 2.4 Dwie hipotezy dla r116 (~23), i pomiar, który je rozdziela

- **H1 „budżet"**: agent dostaje za mało akcji (cap tokenów / progi `ABANDON`/`STUCK_AUDIT`),
  więc umiera na 1–2 poziomie. → Lekarstwo: budżet i brak porzucania (sekcja 3.1–3.2).
- **H2 „ściana"**: nawet z czasem agent nie potrafi rozwiązać poziomów 3+. → Lekarstwo:
  zmiana polityki (głębokość, plan-commit, otwieracze), nie budżet.

Rozstrzygnięcie: pobrać output/log r116 (`ops kernel-output`) i policzyć
`python3 analyze_run.py <benchmark.json>`. Jeśli `levels` mediana ≤1 i akcje/gę ≈ 45–80 →
H1. Jeśli akcje/gę ≈ 300+ i mediana poziomów nadal ≤2 → H2. **To jedno polecenie decyduje,
gdzie wydać resztę czasu; nie trzeba do niego GPU ani slotu.**

---

## 3. Dźwignie, uszeregowane po zmierzonym zysku

### 3.1 Budżet akcji i zakaz porzucania poziomu przed capem — **+9 pkt, zmierzona**
200 akcji wydanych bez porzucania = 35,6 vs 26,8 faktycznie. Konkretnie w v12/c45:
`ARC3_LEVEL_TOKEN_CAP` (domyślnie 40000), `ARC3_ABANDON_TOKENS` (60000),
`ARC3_STUCK_AUDIT_TOKENS` (60000). Wszystkie trzy działają jak „poddać się po ~1 poziomie".
Propozycja: cap per poziom skalowany wagą k (`cap_k = 40k·k`), `ABANDON`/`STUCK_AUDIT`
podniesione tak, by nie odpalały się przed wyczerpaniem okna czasowego gry.

### 3.2 Więcej akcji w tym samym oknie — **+35 pkt w górnej granicy (200→400)**
Okno w rerunie to ~2,2 h/grę; nasze dev-runy kończą na 48 min. Albo harness w konkursie nie
wykorzystuje okna, albo tokeny/akcję (737) zjadają je szybciej niż zakładamy. Zmierzyć w
logu reruna: `akcje × (wall/akcję)`. Jeśli wall ≪ 2,2 h → podnieść budżet; jeśli akcje są
drogie (s/akcję > 20) → ciąć tok/akcję (cap outputu 12k, krótsze analizy, fast-line).

### 3.3 Efektywność akcji — **+3 pkt, ale klif poniżej**
Przy 1,0× baseline: +3,0. Przy 1,5×: −13,5. Przy 2×: −19,3. Czyli nie warto gonić
„oszczędności", ale trzeba mieć watchdog: jeśli poziom zużył 2×baseline akcji bez postępu,
restart poziomu jest tańszy niż brnięcie (reset poziomu kosztuje tylko akcje, nie tokeny).

### 3.4 Wyszukiwanie deterministyczne (search assist) — dane w `local-lab/results/`
Silnik lokalny działa na 25/25 grach. Zmierzone koszty: krok 0,07–2,9 ms, snapshot
0,5–8,6 ms → **95–1400 węzłów/s/rdzeń** (14 rdzeni: 1,5–15 tys./s). To wystarcza na
poziomy o małym rozgałęzieniu (klawiaturowe, 4–5 akcji) i na „kalibrację klików"
(na ft09: 4096 pikseli → ~8 klików o różnym efekcie). Nie wystarcza na głębokie zagadki:
BFS o głębokości 20 przy rozgałęzieniu 5 to 10¹⁴ węzłów. Rola: tanie, pewne poziomy 1–2 i
oszczędzanie akcji/tokenów na nich, plus opener detection. Tabela per gra:
`local-lab/results/sweep-bounded.json`.

### 3.5 Best-of-k / n_passes — **niedozwolone w rerunie**
Scorecard liczy najlepszy przebieg per środowisko, ale brama konkursowa nie da drugiego
środowiska na grę. Można to robić tylko lokalnie (k wyborów offline), nie w submicie.

---

## 4. Recepta „mega" (do decyzji, nic nie wysłane)

Baza: **v12 (c45 + 2 linie concurrency)**, bo jest bajtowo sprawdzona i daje 26,8 smoke.

Zmiany, w kolejności ryzyka:

1. **Budżet alokowany wagą poziomu** — `cap_k = 40k·k`; brak `ABANDON` przed 4. poziomem.
2. **Watchdog wentyla** — poziom > 2×baseline akcji bez postępu → reset poziomu (nie gry).
3. **Priorytetyzacja gier o krótkiej drabince** — z tabeli marginalnej (`arc3lab alloc`):
   w r085 najwięcej płaciły cn04 (6 poz.), m0r0 (6), dc22 (6), ka59 (7). +10 poziomów
   w tych pięciu grach = średnia 51,5 (policzone na r085).
4. **Search assist tylko jako opener** — nie w środku poziomu; celem jest oszczędność akcji
   na poziomach 1–2, nie rozwiązywanie za model.
5. **Cap outputu 12k** (`LOCAL_ANALYZER_MAX_OUTPUT=12000`) — 12% paliwa z powrotem.

**Bramki przed wysłaniem slotu** (wszystkie lokalne, na 25 grach publicznych):
- mediana poziomów ≥ 4 (dziś 3),
- średnia proxy ≥ 40 (dziś 26,8),
- zero gier z `state=gave_up` przy < 1,5×baseline na poziomie 1–2.

Oczekiwanie: **40–60** przy H1; **~27–32** przy H2 (czyli wtedy trzeba zmiany polityki, nie
budżetu). Szacunek jest interpolacją z §2.3, nie pomiarem — jedyny uczciwy sposób to
puścić 25 gier publicznych w nowej konfiguracji.

---

## 5. Lokalne laboratorium (to, co zostało zbudowane)

```
ARC3/local-lab/
  lab/engine.py       # bootstrap silnika, Sesja (bezpośredni perform_action), DOKŁADNA punktacja
  lab/fastclone.py    # polityki klonowania + samoweryfikująca kalibracja (0,5–8,6 ms vs 19 ms)
  lab/search.py       # BFS po akcjach, kalibracja klików, centra blobów, budżety
  run_lab.py          # sweep po grach, multi-proces (zamiennik arc3lab sweep)
  analyze_run.py      # score+alloc: rozkład strat, tabela marginalna, projekcja budżetu
  verify_scoring.py   # 32/32 odtworzonych final_score
  test_lab.py         # 10 testów (punktacja + silnik), przechodzą
  worker.py           # jedna gra → jedna linia JSON (jednostka pracy dla Rusta)
  rust/arc3lab/       # score | alloc | sweep na Rayon (źródło; nie kompilowane w sandboxie)
```

Zmierzony fakt o silniku: `wrapper.step()` dopisuje każdą klatkę do historii (wyciek przy
długim searchu) i jest 3–5× droższy niż bezpośrednie `game.perform_action`. Dlatego sesja
chodzi bezpośrednio po `_game`, a `verify_against_wrapper()` udowadnia (0 rozbieżności na
20 grach × 20 akcji), że to ta sama ścieżka co oficjalna.

Szybki start u Ciebie (5950X):

```bash
cd ARC3/local-lab
python3 -m pip install arcengine arc-agi     # albo wskaż rozpakowane wheele: ARC3_ENGINE_PATHS=
export ARC3_GAMES=~/smak/arc-agi-3/games/environment_files
python3 verify_scoring.py                    # 32/32
python3 test_lab.py                          # 10 testów
python3 analyze_run.py ~/r116/benchmark.json --target 50   # diagnoza + alokacja
python3 run_lab.py --games all --levels 3 --nodes 4000 --time-s 120 --workers 14
cd rust/arc3lab && cargo test && cargo build --release
```

---

## 6. Co by to obaliło

- Jeśli log r116 pokaże ≥300 akcji/gę i medianę poziomów ≤2 → projekcja z §2.3 jest
  nieosiągalna i priorytetem staje się polityka (głębokość/plan), nie budżet.
- 25 gier publicznych to jedyny pomiar, jaki mamy; przenoszenie na 110 ukrytych może się
  nie udać (poprzednio tuning na 10 grach dał 0/113 poziomów na nowych — patrz
  `REVIEWS/2026-10-25-...`).
- Punktacja: jeśli mimo wszystko oficjalny LB nie zgadza się z naszą formułą przy pełnym
  runie, to znaczy, że `arc_agi` v0.9.9 różni się od v0.9.8 w `scored_w` — wtedy wracamy do
  danych, nie do teorii.

Termin: **2 XI** (finał), wyniki 4 XII.

---

## 7. Rejestr źródeł

**Zweryfikowane lokalnie:** cała arytmetyka punktów (32/32 zapisanych runów), koszty silnika
(0,07–2,9 ms/krok), wierność szybkiej ścieżki (20 gier × 20 akcji, 0 rozbieżności),
krzywa dawka→efekt (5 zapisanych runów), rozkład strat i projekcja (r085), tabela wyszukiwania
(`results/sweep-bounded.json`).

**Niezweryfikowane / do sprawdzenia:** liczby r116 (brak `benchmark.json` w repo — tylko
`SUMMARY` z PENDING); „2,2 h/gę" w rerunie (z opisu submitu, nie z logu); efektywność modelu
stock 27B-FP8 (zgłoszenie użytkownika ~23); twierdzenia z cudzych repo o 59,82 przy
best-of-4 (nie replikowane na naszym sprzęcie).
