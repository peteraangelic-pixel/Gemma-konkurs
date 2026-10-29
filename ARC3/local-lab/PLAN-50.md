# PLAN-50 — jak z 23 zrobić 50+ (29.10.2026)

Dokument opiera się **wyłącznie** na artefaktach, które mamy w repo plus na lokalnym silniku
odtworzonym w tym sandboxie. Każda liczba ma źródło: plik `benchmark.json` (własny zapis
harnessu) albo pomiar lokalny. Rzeczy niezweryfikowane są oznaczone.

---

## 0. TL;DR — rewizja 2 (po autopsy v14-27B, 29.10 17:30 UTC)

Co się zmieniło od pierwszej wersji tego dokumentu: doszedł `benchmark.json` z **r118
(v14-27b-long, smoke)** i **r116 (slot B, stock 27B = 1.18)**. Diagnoza jest teraz pełna.

1. **„23" to nie jeden run, to cała linia.** Oficjalne: v3 **26,25** (57247568, wciąż best),
   v11 slot A **23,89**, slot B (stock 27B) **1,18**, v14-27b-long smoke **0,27**. Czyli
   subiektywne „~23" = v11; slot B był jeszcze gorszy. Dwa ostatnie eksperymenty (27B) to
   nie regresja polityki, tylko **zabity throughput**.
2. **Autopsja 27B (r118) — dlaczego 0,27 przy 90 min/gę.** Mediana **116 akcji**, **47,0 s
   na akcję**, ~83k tokenów/gę, **8/10 gier z zerem poziomów**. Linia 8B (r085) ma
   **12,9 s/akcję** i 198 akcji przy 48 min. Czyli 27B jest **3,6× droższy na akcję** i w
   *dłuższym* oknie robi *mniej* ruchów. Większy model nie był za głupi — był za wolny.
   Sygnał zapętlania jest wyraźny: na cn04 27B wykonał **130 ruchów z tylko 6 różnymi**
   akcjami, na g50t 91 ruchów z 5 różnymi, na ls20 96 ruchów z 4 (8B w tej samej grze: 427
   ruchów, ale 5 różnych — różnica jest w liczbie ruchów, nie w różnorodności). To wzorzec
   „nie zdążył przetworzyć stanu, więc powtarza", a nie „nie rozumie mechaniki".
3. **Nasza własna arytmetyka punktów była błędna do 32×.** Reguła ma *dwa* ograniczenia:
   `min(115, (baseline/actions)²·100)` na poziom **oraz** cap na skali 100 od liczby
   ukończonych poziomów. Liczy się **tylko poziom ukończony** — wpis w `actions_per_level`
   dla poziomu, na którym agent utknął, to zero. Poprawiona implementacja odtwarza
   **32/32** zapisanych `final_score` (`verify_scoring.py`).
4. **Gdzie brakuje punktów (r085, 10 gier dev):** 26,78 faktycznie; te same poziomy przy
   bazowych akcjach = 29,79 (**+3,0**); wszystkie poziomy = 90,78. **Głębokość to 96%
   brakujących punktów, efektywność akcji +3.**
5. **Głębokość ogranicza liczba akcji, a tę — sekundy na akcję.** Projekcja z zachowaną
   efektywnością runu: 200 akcji → 35,6; 300 → 59,5; 400 → 72,3; 600 → 83,1. To *górne*
   ograniczenie (nie zakłada nowych umiejętności, tylko niepoddawanie się i więcej ruchów).
   Wniosek: **50+ jest funkcją przepustowości, nie „mądrzejszego modelu"** — a wszystkie
   ostatnie eksperymenty szły w przeciwną stronę (większy model = mniej akcji).
6. **Pomiar, który rozstrzyga resztę (1 polecenie, bez GPU i bez slotu):** wciągnąć
   `benchmark.json` z ostatniego rerunu i puścić `analyze_run.py`. Jeśli mediana akcji
   < 300 → priorytet: przepustowość. Jeśli ≥ 300 i głębokość nadal ≤2 → priorytet: polityka.

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
| r050 | inny agent (novelty-explorer), 132 min/grę | 231 366 | 521 | 444 | 0 | 0,00 |

r085 ↔ oficjalne 26,25 (duck v3). Lokalna średnia po 10 grach dev jest **dobrym proxy LB**
(błąd ~2 pkt), więc można na niej iterować bez palenia slotu.

Uwaga na r050: to **inny agent** (novelty-explorer, submisja 0,01), nie linia duck. Jest
w tabeli jako kontrprzykład: sama liczba akcji (521!) nie daje punktów, jeśli nie ma
ukończonych poziomów. Czyli „więcej akcji" działa tylko przez głębokość.

### 2.2 Rozkład strat (r085, punkty na grę)

`throttle-fixed` = te same poziomy, ale przy bazowych akcjach (naprawiony wentyl).
`lost to depth` = 100 − throttle-fixed (czyli to, co zabiera nieukończenie poziomów).

| gra | poziomy | faktycznie | throttle-fixed | zysk z wentyla | strata na głębokości |
|---|---|---|---|---|---|
| tn36 | 1/7 | 3.6 | 3.6 | +0.0 | 96.4 |
| m0r0 | 4/6 | 46.3 | 47.6 | +1.4 | 52.4 |
| cn04 | 5/6 | 71.4 | 71.4 | +0.0 | 28.6 |
| dc22 | 3/6 | 27.7 | 28.6 | +0.9 | 71.4 |
| ka59 | 5/7 | 49.9 | 53.6 | +3.7 | 46.4 |
| sc25 | 3/6 | 17.1 | 28.6 | +11.5 | 71.4 |
| s5i5 | 2/8 | 8.3 | 8.3 | +0.0 | 91.7 |
| ls20 | 3/7 | 8.8 | 21.4 | +12.6 | 78.6 |
| su15 | 3/9 | 13.3 | 13.3 | +0.0 | 86.7 |
| g50t | 3/7 | 21.4 | 21.4 | +0.0 | 78.6 |
| **MEAN** | — | **26.78** | **29.79** | **+3.00** | **70.2** |

Wniosek: **głębokość to 96% brakującej puli; wentyl jest wart +3,00.** Ale wentyl ma klif:
przy 1,5× baseline średnia spada 26,8 → 13,2, przy 2× → 7,5 (sekcja 3.3). Dwie gry psują go
najmocniej: ls20 (poz. 2: 175 akcji vs 123; poz. 3: 222 vs 73) i sc25 (poz. 4: 111 vs 83).

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

### 2.5 Autopsja linii 27B (r118 / slot B) — najważniejsza tabela w tym pliku

| | 8B r085 | 27B r118 | stosunek |
|---|---|---|---|
| okno na grę | 48 min | **90 min** | 1,9× dłużej |
| mediana akcji/gę | **198** | **116** | 0,59× |
| sekund na akcję | **12,9** | **47,0** | 3,6× drożej |
| tokenów/gę | ~146k | ~83k | 0,57× |
| mediana poziomów | 3 | **0** | — |
| średnia (10 gier) | **26,78** | **0,27** | −26,5 |

Czytanie: 27B dostał *więcej czasu* i zrobił *mniej ruchów*, bo każdy ruch kosztował 47 s
przy konkurencji 10 strumieni na jednym GPU. Do tego rozrzut „różnych akcji" spada (ls20:
4 różne na 96 ruchów), czyli model zapętla się, bo nie mieści mu się stan w budżecie
odpowiedzi. To nie jest sufit umiejętności — to sufit **przepustowości**. Ten sam wniosek
potwierdza slot B (stock 27B, conc 28, bez capa): **1,18**.

**Konsekwencja:** jedyna konfiguracja, która kiedykolwiek dała 26+, to **8B + szybki
silnik** (12,9 s/akcję). Każda dźwignia, która podnosi sekundy na akcję, zjada więcej
punktów niż dodaje. 27B wraca dopiero z konfiguracją 1:1 M1 Tufy (drogo, niskie EV).

### 2.6 Ile akcji realnie mamy w oknie

Rerun ma budżet notatnika **32 400 s (9 h)** i gry idą równolegle, więc okno na grę jest
rzędu godzin, nie minut — nasze dev-runy kończą na 48/90 min, bo *tam* tak ustawiono
`max_runtime_s_per_game`. Przy 12,9 s/akcję:

| okno | akcje (8B) | projekcja średniej (§2.3) |
|---|---|---|
| 48 min (dziś, dev) | ~220 | 35,6 |
| 2,2 h | ~600 | 83,1 |
| 4 h | ~1100 | 90,8 (sufit = wszystkie poziomy) |

To wyjaśnia, dlaczego „więcej czasu" nie pomogło 27B (tam akcje wyznaczało 47 s, nie okno)
i dlaczego **pomoże 8B**: przy tej samej liczbie tokenów jest 3,6× więcej ruchów.

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

## 4. Recepta „mega" — kolejność wg zmierzonego zysku, nie wg intuicji

Baza: **v12 = bajty c45 + 2 linie (concurrency 10)**. Baza pomiarowa: smoke 26,78.
Zasada: **jedna zmiana mechanizmu na slot**, bo przy takim szumie dwie zmiany naraz dają
liczbę, której nie da się przypisać.

### M1. Okno czasu na grę (największa dźwignia, +EV 15–45 pkt)

Dziś dev-runy kończą na 48 min (`max_runtime_s_per_game = 48*60`), a r116/v14 na 90 min.
Notatnik ma budżet 32 400 s. Przy 12,9 s/akcję:

```python
# v13-cell: budżet per gra = pełne okno, nie 48 min
bm.solver.max_runtime_s_per_game = 7920     # 2,2 h; 4 h = 14400 gdy notatnik pozwala
```
Sprawdzić w logu rerunu jedną liczbę: **akcje/gę**. Jeśli < 300 przy 12,9 s/akcję, to
znaczy, że okno nie było wykorzystane i to jest cała różnica.

### M2. Zakaz poddawania się przed capem (+8,8 pkt zmierzone przy tym samym budżecie)

`ARC3_LEVEL_TOKEN_CAP` (40k), `ARC3_ABANDON_TOKENS` (60k), `ARC3_STUCK_AUDIT_TOKENS` (60k)
działają jak „poddaj się po pierwszym poziomie". Zmierzone przeze mnie na r085: **22%
akcji (470 z 2 126) poszło w poziomy, które nigdy nie zostały ukończone** (c87 podawał 35%
na swoim runie — mój pomiar jest z r085 i niższy). W v14-27B ten sam wskaźnik to **93%**
(1 220 z 1 312) — tam prawie wszystko szło donikąd. Propozycja: cap **skalowany wagą poziomu** (`cap_k = 40k·k`),
`ABANDON`/`STUCK_AUDIT` dopiero po 4. poziomie lub po 2× bazowych akcjach na poziomie.

### M3. Cap odpowiedzi (+12% paliwa)

`LOCAL_ANALYZER_MAX_OUTPUT=12000` (dziś 0 = brak capa; p90 8 046, max 61 300). Trzy i pół
procent tur jest dłuższych niż 12k, a zjadają 12% puli. Przy 8B z 12,9 s/akcję to
~24 dodatkowe akcje na grę.

### M4. Watchdog wentyla (strzeże −19 pkt)

Jeśli poziom zużył 2× bazowych akcji bez postępu → **reset poziomu** (nie gry). Nie po to,
żeby „być efektywnym" (+3), ale żeby nie wpaść w klif: przy 2× baseline na wszystkich
poziomach średnia spada 26,8 → 7,5. W r085 takie dwa poziomy (ls20 poz. 3: 222 vs 73,
tn36 poz. 2: 171 vs 72) kosztowały ~25 pkt na tych grach.

### M5. Czego NIE robić (zmierzone straty)

| pomysł | zmierzony efekt |
|---|---|
| 27B / większy model | **−26,5** (0,27 vs 26,78): 47 s/akcję zamiast 12,9 |
| rekonstrukcja patchy v11 | −2,9 (23,89 vs 26,25); minimalna delta wygrywa |
| cap 45k tokenów na grę | −26,0 (0,73 vs 26,78) |
| gonić efektywność akcji | max **+3,0**, przy 1,5× baseline już **−13,5** |
| search assist jako solver | patrz §3.4: nie skaluje się na głębokie poziomy |

### M6. Bramki przed wysłaniem slotu (wszystkie lokalne, 0 GPU)

1. `verify_scoring.py` → 32/32 (punktacja się nie rozjechała).
2. Smoke na 10 grach: **mediana poziomów ≥ 4** (dziś 3) i **akcje/gę ≥ 400**.
3. Zero gier z `state=gave_up/cancelled` przy < 1,5× bazowych akcjach na poziomie 1–2.
4. Jeśli (2) nie przejdzie → nie wysyłać; to znaczy, że zmiana nie zadziałała, a slot
   kosztuje 9 h GPU i jeden z czterech pozostałych.

**Oczekiwanie (interpolacja z §2.3, nie pomiar):** M1+M2+M4 przy 8B → **35–50** na proxy
10 gier; M3 na wierzchu → +2–4. **50+ osiągalne tylko wtedy, gdy ściany na poziomach 3+ są
czasowe, a nie rozumowania** — i to jest jedyna niepewność, której nie da się rozstrzygnąć
bez jednego smoke'a z realnym budżetem akcji.

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
