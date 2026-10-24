# ARC-AGI-3 (branch `Smak-Domu-Konkurs`, `arena/5ed750ef`): dlaczego nie ma 45+

Recenzja z 2026-10-24. Czytane: `arc-agi-3/STATUS.md`, `README.md`, `STRATEGY.md`, `MY-WORK-STATUS.md`,
`CHAT-LOG-2026-10-14.md`, wyciągi z runów `r019` (10 gier, linia W4A16) i `r050` (1 gra, linia FP8),
źródła TAAF z `r033-recon-bundle` (`benchmark.py`, `game.py`, `run.py`) i notatniki
`duck-original` / `duck-v7` / `their-duck`.

**Konkluzja w jednym zdaniu:** wasz wynik nie zależy od tego, jak *dobrze* agent gra, tylko od tego,
ile poziomów *zdąży ukończyć* — a dzisiaj obie wasze linie dostają **~1 decyzję modelu na minutę na grę**,
czyli ~4× za mało, żeby domknąć grę w oknie 2,2 h. To jedyna dźwignia, która ma zapas.

---

## 1. Wzór, który rozstrzyga wszystko

`taaf/game.py::GameRun._compute_final_score` (skopiowany z `arc_agi.scorecard`, v0.9.8):

```
poziom k (k liczone od 1):  score_k = min(115, (H_k / A_k)² × 100)   jeśli ukończony, inaczej 0
gra:                        score   = Σ_k (w_k · score_k) / Σ_k w_k       przy w_k = k
wynik zgłoszenia:           średnia po grach
```

Trzy konsekwencje, które w waszych dokumentach nie są jeszcze wyciągnięte:

1. **Cap 115 = „lepiej niż człowiek" i jest tani.** Wystarczy A_k ≤ 0,93·H_k.
2. **Nieukończony poziom to nie „niski wynik", tylko zero** — i nadal siedzi w mianowniku.
   Poziom 1 w grze 8-poziomowej to 1/36 = **2,8 %** gry. Poziomy 6-8 to 58 %.
3. **„Szeroko po trochu" jest bezwartościowe.** Ukończenie poziomu 1 we wszystkich grach daje ~2-3 pkt.

## 2. Wasze własne dane: wydajność akcji jest już maksymalna

`r019` (10 gier, 1 pass, 48 min/gra, concurrency 10) — score per poziom policzony z
`base_actions_per_level` i `actions_per_level`:

| gra | ukończone | % wagi | score gry | score per poziom |
|---|---|---|---|---|
| su15 | 7/9 | 62 % | 56,4 | **115,115,115,115,115,115,17,0,0** |
| cn04 | 4/6 | 48 % | 47,6 | **115,76,115,115,0,0** |
| dc22 | 4/6 | 48 % | 44,8 | 104,115,54,111,0,0 |
| sc25 | 4/6 | 48 % | 42,6 | 18,36,115,115,0,0 |
| m0r0 | 3/6 | 29 % | 28,6 | 88,115,115,0,0,0 |
| ka59 | 3/7 | 21 % | 17,8 | 115,115,52,0,0,0,0 |
| s5i5 | 3/8 | 17 % | 16,7 | 64,115,115,0,… |
| g50t | 2/7 | 11 % | 10,7 | 115,115,0,… |
| tn36 | 1/7 | 3,6 % | 3,6 | 115,0,… |
| ls20 | 1/7 | 3,6 % | 3,3 | 92,0,… |
| **średnia** | | | **27,21** | |

**Udział poziomów ukończonych wyjaśnia wynik w 100 %.** Na 27 ukończonych poziomów 17 ma 115
(czyli cap, graliście *szybciej* niż człowiek), 6 ma ≥ 88. Mediana ≈ 110.

To jest odpowiedź na „dlaczego wszystkie dźwignie promptowe dały ±szum": **nie ma już czego poprawiać
w oszczędności akcji.** Jedyne, co zostaje, to liczba ukończonych poziomów.

Skąd 26,25 na LB przy 27,21 w ekranie 10 gier? Bo ekran i rerun mają **ten sam budżet decyzji na grę**
(patrz §3) — a zbiór ukryty jest trochę trudniejszy. To nie regresja, to ta sama liczba.

## 3. Jedna liczba, która rządzi wynikiem: decyzje na minutę

Przeliczone z dwóch waszych własnych przebiegów (oba logi są w repo):

| linia | tok/s na strumień | tokenów na decyzję | **decyzje/min** | ukończone poziomy |
|---|---|---|---|---|
| FP8 Qwen3.6-27B + vLLM (`r050`, 1 gra, 132 min) | **36** | **1 337** | 1,6 | 0/8 na sk48 |
| W4A16 Qwen3.8-Flash-Next + MTP + sglang (`r019`, 10 gier) | **165-180** (accept rate 0,59) | **2 173-9 187** (średnio ~5 000) | **~1,0** | 27 poziomów / 10 gier |

Iloczyn jest ten sam: **~1 decyzja na minutę na grę.** Dlatego dwie kompletnie różne maszyny
dały 24,66 i 26,25 — to nie zbieg okoliczności, to ten sam budżet.

Ile trzeba na całą grę:

```
akcje potrzebne na grę   = Σ H_k        (su15: 361, dc22: 1228, s5i5: 638, mediana ~730)
akcji na decyzję         = 1,8-4,8      (średnio ~3)
decyzji na grę           = 240-300
przy 1 decyzji/min       = 4-5 h        vs cap max_runtime_s_per_game = 7 920 s = 2,2 h
```

**Dostajecie ~40 % potrzebnego czasu decyzji. Stąd 27 % wagi, nie 60 %.** Wynik 45 to ~55-60 %
wagi czyli ~2× więcej ukończonych poziomów, czyli ~2-4× więcej decyzji na grę.

Warto zauważyć, że `r019` (10 gier równolegle, 48 min) i rerun (25 gier, concurrency 28, 2,2 h)
dają ten sam iloczyn: concurrency nie zmienia sumy tokenów, tylko dzieli ją inaczej. **Dłuższy cap
na grę w niczym nie pomógł, bo wąskim gardłem nie jest zegar, tylko tokeny/s na GPU.**

## 4. Wniosek: jest dokładnie jedna dźwignia z zapasem

```
decyzje/min na grę  =  (tok/s na strumień)  ÷  (tokenów na decyzję)
```

- **tokeny/s** — jest x5 na stole: wasza linia W4A16+MTP robi 165-180 tok/s, linia FP8 36 tok/s.
- **tokenów na decyzję** — jest x3,7 na stole: 1 337 vs 5 000.

Każda z tych dwóch rzeczy osobno zjadana jest przez drugą (dlatego oba wyniki są identyczne).
**Razem dają 5-6×.** To jest jedyna droga z 26 do 45+.

Konkretnie: **silnik z `duck-v7` (Flash-Next W4A16 + MTP drafter, sglang, 180 tok/s) + twardy cap
outputu ~1 000-1 500 tokenów na decyzję** (`LOCAL_ANALYZER_MAX_OUTPUT`, który już macie w patchach,
plus `ARC3_PRESERVE_THINKING=0`). Przy 180 tok/s i 1 200 tokenach: **~9 decyzji/min → ~450 decyzji
w 48-minutowej grze** zamiast 78. To jest różnica między 27 a 50+.

Nie trzeba nowego promptu, nowej architektury ani nowego modelu — trzeba *tego samego mózgu
na szybkim silniku z krótką odpowiedzią*. Wasz `v7` był już w połowie drogi: miał szybki silnik,
ale „brain = v2-think-less" (czyli nadal długie myślenie) i padł po 25 min, a jego log (`r061`)
nigdy nie dotarł do repo.

## 5. Co zrobić w najbliższych dwóch dniach

**Dzień 1 — odzyskać kanał i zabić 400.**
1. `r061` (log v7) + `r062` (submissions) — sprawdzić, czy w ogóle się wykonały. W repo nie ma
   wyników po `2026-10-21 21:07`; auto-łańcuch stoi od 3 dni. To pierwsza rzecz do naprawy,
   bo bez kanału każdy pomysł jest niesprawdzalny.
2. **Bisekcja 400** (bo 400 nie pali slotu — to wasza własna empiria): push trywialnego kernela
   (placeholder parquet, bez pinu, bez `machine_shape`, bez modelu) i submit. Jeśli przejdzie →
   wina jest w notatniku/środowisku; jeśli nie → wina konta/limitu. 5 minut, zero GPU.
3. Dopiero potem push `v8` (silnik v7 + cap outputu) jako smoke 1 gry i **submit** — nie kolejny
   „save-run na zapas".

**Dzień 2 — zmierzyć decyzje, nie wynik.**
W `summary.txt` / `benchmark.json` liczyć dwie rzeczy i wpisać je do nagłówka raportu:
`decyzje/min` i `ukończone_poziomy / 100 decyzji`. Score z 1-3 gier to szum; te dwie liczby nie są.

**Czego nie robić:**
- żadnych kolejnych dźwigni promptowych — cap 115 dowodzi, że nie mają zapasu;
- nie podnosić `max_runtime_s_per_game` (7900 s to nie ograniczenie);
- nie ruszać promptu i silnika w jednym przebiegu (jedna dźwignia na pomiar);
- nie traktować „smoke 10 gier" jako prognozy LB (kalibracja −3…−6,7 pp jest już zmierzona).

## 6. Uczciwa ocena, czy 45+ jest realne

- **45+ to top-3.** Próg nagrody to 40,97 (NVARC3), mediana pola ~38. Wasze 26,25 to dolna ćwiartka.
- Dźwignia z §4 jest realna i zmierzona w waszych logach, ale ma **jeden warunek: cap nie może
  zepsuć jakości decyzji.** Przy 1 000 tokenach model może przestać pisać BFS-a w Pythonie —
  a to jedyne, co w `r050` realnie zawodziło (173 tury i ani jednego poziomu na sk48: model
  po raz setny przepisywał ten sam opis planszy zamiast policzyć ścieżkę).
- Realny pas przy udanym rerunie: **35-50**. 45+ tylko jeśli cap trafi w sweet spot i rerun
  faktycznie wstanie. Twierdzenie „45+ po samych poprawkach infrastruktury" byłoby nieprawdą.
- **Data:** `STATUS.md` mówi entry 26 X, finał **2 XI**. Jeśli „2 dni" znaczą 26 X (entry), to
  termin zgłoszeń, nie walki o punkty — jeśli to jest wasz twardy koniec, to priorytetem nie jest
  45+, tylko to, żeby jakikolwiek rerun się przyjął i zapisał wynik.

## 7. Co z tego przenosi się do Gemma-4 (ta sesja)

Dwie rzeczy, niezależnie od ARC:

1. **Cap metryki zabija klasę dźwigni.** U was `min(115, …)` powoduje, że optymalizacja oszczędności
   akcji nie ma już gdzie rosnąć — i wszystkie „inteligentniejsze" prompty wracają jako szum.
   U nas ten sam wzorzec to V8: dodanie pracy (verify-loop) przy stałym budżecie = −1.
   Zanim dodasz mechanizm, sprawdź, **czy metryka ma w ogóle zapas** w tym wymiarze.
2. **Jedna liczba rządzi wynikiem.** U was: decyzje/min. U nas: akcje do limitu czasu.
   W obu przypadkach kolejne warianty promptu bez tej liczby to loteria.
