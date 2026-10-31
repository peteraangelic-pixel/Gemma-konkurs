# STATUS sesji Gemma (`arena/c4eeb067-gemma-konkurs`) — punkt wejścia dla innych gałęzi

**Ostatnia aktualizacja: 2026-10-31, commit `6200061` (+ `ARC3/duck-v17/`).** Ten plik jest po to, żeby każda inna
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

## NOWE (31.10): `ARC3/duck-v17/` — jedyny artefakt, który warto wziąć

`duck-v17` = **champion v3** (SHA `550eb185…d5fa`, `v3-world-model`, WM=1, zmierzony 26,25)
+ kontroler `template` (ft09: 25 akcji / 3 poziomy) + **guard** z audytu peerów (limit 32
propozycji/poziom przerywa pętlę oscylacyjną, `ARC3_TEMPLATE=0` = zachowanie v3).

- build deterministyczny, `sha256 76b57100…b519795`, 30 komórek, **1 zmieniona**;
- patch: 4 pliki, **arytmetyka liczników hunków walidowana programowo**, `git apply` na czystym drzewie OK;
- **11/11 testów**, ft09 modułem wyjętym z notebooka = 25/3;
- `cap_hits = 0` na 25 grach publicznych → bezpiecznik nic nie psuje, ale też **nic nie dźwignie**;
- **do TOP5 nie wchodzi**: 26,25 + 0,26…2,6 = **26,5–28,9** vs #5 = **51,51** (LB 30.10).

Odpowiedź na audyt per gałąź (6/8 korekt przyjętych, m.in. kontrprzykład pętli 60 akcji)
i arytmetyka TOP5: `REVIEWS/2026-10-31-odpowiedz-na-audyt.md`.

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

## Audyt `duck-v13-7-final` (gałąź `5ed750ef`, commit `de57e4d`) — 2026-10-30

**v13.7 = nasz duck-v16 + patch 0010.** Bajt w bajt na 0006–0009 (`04a91380`, `e891e9bd`, `5c427621`,
`9cdc3c74`), `playbook.json` (`e2d86b1e`), `arc3_winpath.py` (`b8ffedaa`), `base-v11.ipynb`
(`fdaa8b84`), `test_self_pace.py` (`a9fbef41`). Notebook 41 komórek / 758 240 B — zgodne.
Jedyne różnice: 0010, komentarze, własny slug.

0010 przepuszczony przez realne trakty r085 (`local-lab/sim_dyn_budget.py`):

| `ARC3_LEVEL_TOKEN_CAP` | RESET | ABANDON | gry reagujące |
|---|---|---|---|
| `"0"` (to wysyłają) | 0 | 0 | 0/10 |
| `"45000"` | 6 | 0 | 5/10 |
| `"60000"` (proponowane uzbrojenie) | 6 | 0 | 6/10 |

Czyli: dormant jest **naprawdę** dormant (0 decyzji / 2 126 akcji), ABANDON nie odpala ani raz
(warunek: resety wyczerpane **i** spend ≥ 1,5×cap w jednej próbie — gry kończą na zegarze),
a 45k vs 60k to ta sama liczba resetów. Premisa patcha („35–91% tokenów na niekończonym poziomie",
r019) na r085 wynosi **25%** — zmalała, bo gry doszły do 2–5 poziomów.

Sprawdzone dodatkowo (czego ich certyfikat nie obejmował): hook **istnieje i jest wołany**
(`solver.py`: `peek` w `should_stop`, `step` w ścieżce akcji — nie martwy kod), RESET **zachowuje
poziom** (`taaf/game_api.py:221` ustawia `ONLY_RESET_LEVELS="true"` przed budową klienta),
patch 0010 **odwracalny** na ich rekonstrukcji (testy 16/16 badają bajty wysyłkowe), dotyka 1 pliku.

**Bramka a/call — potwierdzona niezależnie.** Zmierzone z logów r085: 481 wywołań / 2 136 akcji
= **a/call 4,441** (ich 4,357, zgodne w 2%). Do 50 pkt brakuje ~1,1 poziomu = +70 akcji/greę,
przy stałej liczbie wywołań → a/call musi dojść do **5,9**. Ich próg **6,0 jest trafny.**

**ZNANY DEFEKT NASZEJ SONDY:** alarm w `coverage_probe` brzmi `a/call < 1.5`, a dzisiejsza wartość
to 4,44 i próg 50 pkt to ~6,0 — alarm **nigdy by nie zadzwonił**. Poprawka: próg `< 6.0` plus druk
luki (`6.0 - a/call`). Nie naniesione bez GO (zmiana md5 wysyłanego notebooka).

**Werdykt:** nie uzbrajać 0010 (brak dźwigni: 6 decyzji na run; ryzyko niskie, korzyść zerowa).
Na slot iść **jednym** kandydatem — v13.7 (ich slug, ich certyfikat) albo v16 **po** zmianie sluga,
bo zachowanie jest identyczne. Uwaga: nasze slugi v14/v15/v16 celują w ich kernele
(`arc3-duck-v13-2`, `-v13-3-arena`, `-v13-4-unified`) — wysłanie bez zmiany **nadpisze ich artefakt**.

## `v13.7 rev2` (commit `3945d72`) vs nasz v16 — 2026-10-30

rev2 = rev1 (759 109 B vs 758 240 B; różnica to nota i scalone sondy) z **`ARC3_LEVEL_TOKEN_CAP`
nadal `"0"`**, więc **na submisji rev2 ≡ rev1 ≡ nasz v16**. Różnice w artefakcie: kom. 1/2/12/14/33
(nazwy, nota, writer 0010) i scalenie sond 39+40 w jedną kom. 40 z **bezwarunkowym drukiem
`a/call` + bramką 6,0**.

**Dwa defekty po naszej stronie, przyznane:**
1. `if _summary["mean_a_per_call"] < 1.5` w kom. 39 naszego v16 to **martwy próg** (dziś 4,441;
   50 pkt wymaga ~6,0). v13.7 drukuje bezwarunkowo. Do przejęcia.
2. `duck-v16/kernel-metadata.json` → `id = petersharps/arc3-duck-v13-4-unified` = **ich kernel**.
   Wysyłka bez zmiany sluga nadpisałaby cudzy artefakt.

**Arming 20 000 (propozycja rev2 na 1.11) — policzone, `local-lab/arm_cost.py`:**

| cap | Δ r085 | Δ r093 | Δ r110 | Δ r118 | utracone poz. | uwolnione tok |
|---|---|---|---|---|---|---|
| 10 000 | −18,67 | −9,54 | 0,00 | −0,05 | 20/14/0/1 | 2 091k |
| 15 000 | −6,07 | −9,43 | 0,00 | −0,05 | 9/13/0/1 | 1 210k |
| **20 000** | **−4,43** | **−4,82** | 0,00 | −0,05 | **5/9/0/1** | 668k |
| 30 000 / 45 000 | 0,00 | 0,00 | 0,00 | 0,00 | 0/0/0/0 | 0 |

Ich tabela §25 **odtwarza się 1:1** (indeksowanie o jedną akcję dalej: 20k → AB=20 gier,
15 utraconych poziomów, **667 937** uwolnionych tokenów; per-run AB 3/7/0/10). Ale wniosek jest
odwrócony: uwolniony budżet wart jest 3,5 poziomu na r085 i 6,6 na r093 przy **5 i 9 utraconych**
— trzeba by **>100% konwersji** (143% / 136%), żeby wyjść na zero.

Dlaczego konwersja ≈ 0: `solver.py:898` trzyma `asyncio.Semaphore(concurrency=10 = MAXREQ)`
i tworzy zadania dla **wszystkich** gier naraz; zwolniony slot natychmiast dostaje następna gra
z kolejki, więc obciążenie serwera jest stałe, a każda gra ma **własny** cap `532/11 ≈ 48,4 min`.
Uwolniony czas skraca bieg, nie wydłuża cudzego budżetu. (Rozumowanie z kodu, nie z przebiegu
110 gier — niezweryfikowane pomiarem, dlatego przy ewentualnym flipie mierzyć `completed/game`.)

**Werdykt:** nie uzbrajać 20k na 1.11 (arytmetyka, nie ryzyko). Przejąć od rev2 tylko druk `a/call`
z bramką 6,0. Na slot — jeden kandydat, pod własnym slugiem.

## ZMIANA KURSU: prawdziwy rerun v13.7-final = **13,28** (odczyt 31.10)

`own-submissions.csv` (Kaggle API): ref 57811453 = v13.7-final, COMPLETE, **publicScore 13,28**.
Dla porównania v11 = **23,89**, mistrz v3 = **26,25**. Strata 10,61 pkt względem v11.

**To unieważnia moją wcześniejszą rekomendację.** v13.7 = v13.4-unified + 0009 + 0010(dormant);
**duck-v16 jest z tej samej linii**, więc jego oczekiwany wynik to ≈13, nie ≈26. Zdanie
„v16 jest najlepszą z czterech gałęzi" było oparte na testach offline, a obala je jedyny
prawdziwy pomiar. **Nie wysyłać v16 ani niczego z linii v13.x bez wyjaśnienia spadku.**

Mapa różnic wobec mistrza (bez wskazywania winnego — ich zasada „nie przypisujemy bez dowodów"
jest słuszna): v3 miał `ARC3_WORLD_MODEL=1` i tylko patche 0001+0002; v13.7 ma WM=0, cap
wyłączony (0), PLAN_COMMIT=1, win-path/dead-skip/opener-hint/relative+self-pace, 10 patchy.

**Smoke nie prognozuje rerunu w żadną stronę:** v11 smoke 18,54 → 23,89 (+5,4);
v13.7 smoke 22,59 → 13,28 (−9,3). Reguła „GO przy smoke ≥ 26" jest zawodna przy n=1 na wersję.

## Audyt kontrolera `template` (gałąź `codex/arc-local-lab-v18`, `3926007e`) — 31.10

Odtworzone **niezależnie na prawdziwym silniku** (arcengine 0.9.3 + arc-agi 0.9.9, 25 gier z repo):
SHA256 notebooka zgodny, moduł i hook w notebooku bajt w bajt z plikami, 52/52 testy,
**3 poziomy ft09 w 25 akcjach, per-level [4,7,14], wszystkie 25 kliknięć identyczne z zapisem**,
abstynencja na 24 pozostałych grach. Zero identyfikatorów gier / współrzędnych / dostępu do silnika.

- **Pułapka odtwarzania:** po level-upie `fd.frame` ma 2 klatki; `frame[0]` to animacja
  (`[0 2 4 5 8 9 11 12]`), `frame[-1]` to plansza (`[0 2 4 9 12]`). Kto bierze `frame[0]`,
  dostaje 1 poziom / 4 akcje i „obala" prawdziwy wynik. Obserwacja = **ostatnia** klatka.
- **Wartość:** jedna gra ⇒ sufit **+0,26 pkt** (28,57 / 110 gier). „28,5714 RHAE" = sufit
  pokrycia `100×6/21`, nie efektywność.
- **Bramka zastosowania:** motyw (≥3 panele odniesienia + 1 z obwódką) musi być na **pierwszej**
  planszy. Zmierzone: 5/25 gier ma strukturę paneli, ale tylko ft09 ma motyw; lf52/tu93 mają
  1 panel, sc25/tn36 — 0.
- **Izolacja pamięci:** kontroler per `state_path` na instancji ToolAgent — działa; ale przy
  `n_passes>1` ta sama ścieżka wraca i stan (`learned`) **nie jest resetowany**. W submicie
  `n_passes=1`, więc dziś nie boli.
- **`a/call`:** wycofuję swoje „6,0 = 50 pkt". Akcje płacą tylko, gdy kupują poziom
  (`score = min(raw, 100×pokrycie)`); `a/call` to przepustowość, nie prognoza.
- **Niezweryfikowane:** Rust/Rayon 33,4× (brak `cargo`; to kernel prostokątów, nie wynik),
  hybryda z Qwenem (brak modelu lokalnie; ślad sprawdzony).

Narzędzia: `local-lab/template_replay.py`, `local-lab/template_stage_probe.py`,
kopie kodu autora w `local-lab/template-audit/`. Pełna recenzja:
`REVIEWS/2026-10-31-template-hybrid-audyt.md`.

## Zasady, których ta sesja się trzyma (i wam proponuje)

1. Nic na Kaggle bez GO użytkownika; żadnych GPU-runów bez pytania.
2. Każdy patch: `git apply --check` na **czystym r033**, potem `cmp` z plikiem, na którym
   przeszły testy — „testy zielone przy martwej funkcji" już nas raz kosztowały.
3. Domknięcie w notatniku: `\`%%writefile` bez końcowego `\n` daje **corrupt patch** —
   zapisywać patche zawsze z newline.
4. Liczby z cudzych README traktować jak hipotezy; przy każdej okazji przeliczać na r085.
