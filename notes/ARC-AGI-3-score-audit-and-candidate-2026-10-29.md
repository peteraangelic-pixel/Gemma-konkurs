# ARC-AGI-3 — aktualizacja audytu i lokalnego kandydata (29.10.2026)

## Wyniki i identyfikacja submission

Gałąź `peteraangelic-pixel/Smak-Domu-Konkurs@arena/5ed750ef-smak-domu-konkurs` została odświeżona do tipa `491ca44bb1211f8bb6e9632e0daa9ac0d81fe354`.

| Ref | Data UTC | Wariant | Wynik / status |
|---|---|---|---:|
| `#57737623` | 28.10 13:11 | v11 fast line; `PLAN_COMMIT=0`, cap 45k, concurrency fix | **23.89 COMPLETE** |
| `#57752672` | 29.10 00:09 | Tufa stock Qwen3.6-27B-FP8, conc 28, no cap | **1.18 COMPLETE** |
| `#57247568` | 16.10 | duck v3 | **26.25 COMPLETE**, najlepszy znany COMPLETE |

Użytkownik najpewniej wskazuje `#57737623` mówiąc „około 23”, ale `#57752672` jest późniejsza i znacznie słabsza; nie należy łączyć tych wyników w jedną diagnozę.

### Smoke dla osobnej linii 27B

- `r110` (`duck-v13-27b`): 10 gier, 48 min/gra, 0 zwycięstw, 4 poziomy ukończone łącznie; scorecard mean `0.7279912575403615`.
- `r117`: kernel `arc3-duck-v14-27b-long` zakończył się jako `COMPLETE`; sam status nie jest wynikiem LB.
- `r118` output-pick dla v14: 10 gier, 90 min/gra, 0 zwycięstw, 2 poziomy ukończone łącznie; mean `0.2733544355165977`.
- `r118` ma zapisany `benchmark.json`/log, ale nie jest nową competition submission. Nie uruchamiałem Kaggle — tylko odczytałem istniejące artefakty GitHub.

To jest dowód, że 27B stock smoke nie działa dobrze na tych publicznych 10 grach. Różnica 48 vs 90 min nie ma czystej przyczynowości (sampling i pojedyncze runy); nie wyciągać wniosku, że samo wydłużenie czasu obniża wynik.

## Diagnoza 23.89

- Zmienność modelu jest duża: na tej samej bazie Franzen M2 opisano średnią `25.77`, SD `3.93`, wiele drawów od `21.01` do `35.35`. `23.89` samo w sobie nie dowodzi regresji.
- Niezależnie od tej wariancji, v11 używa capu 45k i `min_done=0`; logi opisane w c87 wykazują przedwczesne terminalne `ABANDON`: `g50t` 0/7 poziomów po 1499 s, `cn04` 1/6 po 1609 s, `tn36` 1/7 po 1692 s. Raportowana strata budżetu to ok. 3840 s / 64 min i 243,600 tokenów. To błąd strukturalny, nie twierdzenie o dokładnej liczbie utraconych punktów.
- Uniform allocation jest drugą słabością. W publicznym D′ priorytet jest przeliczany przy zwolnieniu slotu/trimie; nie kończy gry. Zmierzony draw-set D′: `31.54, 30.74, 29.05, 24.77`, średnia `29.025`.
- Nie kopiować całego `duck-v13-mega` bez krytycznej selekcji: jego replay/playbook ma wyniki lokalne na publicznych grach, ale nowsze c87 źródła wskazują brak transferu na hidden. Held-out repo raportuje `0/113` na held-out i `7/70` na dev; offline BFS pierwsza submission dostała `0.20`. Nie jest to droga do 50+.

## Bezpośredni audyt v13 z gałęzi a450 (29.10)

Sprawdzono tip `3782f8c39ede4bdd83888b05d1cb38f5afa3ee3c` oraz notebook, patch 0006, playbook, testy, build/verify i PC-sweep pack. To **lokalny kandydat niezgłoszony do konkursu**; README mówi wprost, że nic nie zostało wysłane.

- **Korekta:** v13 ma włączony pewien slot-priority scheduler (`USE_PRIORITY_SCHEDULING=True`, 10 aktywnych strumieni, refresh kolejki). Nie jest więc poprawne powiedzieć, że v13 używa wyłącznie czystego FIFO/equal slots. To jednak **nie jest opublikowana formuła D′**: włączony patch używa innego `priority_value`; `ARC3_PRIORITY_PACE=0`, a kod D′ z publicznego referencyjnego notebooka nie występuje. Moja poprzednia rekomendacja D′ pozostaje osobną zmianą do sprawdzenia, nie opisem tego, co już robi v13.
- **Twarda sprzeczność passów:** notebook ustawia `bm.n_passes=1` w gałęzi competition i także `=1` w smoke. `dead_skip()` wymaga `pass_index >= 4` i trzech wcześniejszych ukończonych passów, zatem `ARC3_DEAD_SKIP=1` jest w rzeczywistym v13 **nieosiągalny/no-op**. Również marketing „replay w passach 2–20” nie opisuje tego notebooka w competition. Replay może zadziałać przy ponownym wejściu do poziomu w tej samej sesji albo dla dopasowanego playbooka, ale skuteczność tego nie została zmierzona.
- **Playbook:** w repo jest 9 publicznych ID i 14 poziomów. Runtime dopasowuje ID po exact/prefix-normalizacji i sprawdza hash planszy początkowej oraz kolejne hashe; przy niezgodności wraca do LLM. To sensowny fail-safe, ale nie dowód pokrycia ukrytego rosteru. PC pakiet przeszukuje publiczne pliki gier; surowe pliki wynikowe sweepów nie są w katalogu, więc nie da się odtworzyć 14/14 wyłącznie z commita.
- **Zakres testów:** niezależnie uruchomiono `verify_v13.py` w trybie bez bundle: 35 komórek, 20 komórek kodu, przełączniki, metadane, 6 patchy wyekstrahowanych i zgodność playbooka 9/14 — **ALL CHECKS PASSED**, ale patch-chain tests zostały jawnie pominięte (`SKIP patch-chain checks`, brak bundle r033). `test_winpath.py` używa jawnie `FakeSession`/toy game, więc to nie test gatewaya ani ukrytej gry. README/commit deklarują też osobne pełne testy na czystym bundle; tych tutaj nie uruchamiałem.
- **Stack bez izolacji:** `PLAN_COMMIT=1`, cap-off, winpath/playbook i dead-skip ustawiono razem; brak oficjalnego score v13 i brak izolowanego pomiaru tych zmian. Część cap-off ma sens jako naprawa udokumentowanego `ABANDON`, ale nie dowodzi wartości pozostałych elementów.
- **`ANALIZA-23.md` jest częściowo starsza niż dane:** jej hipoteza o wysłanym v12-plan nie pasuje do r116, który identyfikuje `#57737623` jako v11 z `PLAN_COMMIT=0`. Dla 23.89 należy używać późniejszej diagnozy c87: wariancja jest realna, a błąd capa jest niezależny.

Wniosek: v13 zawiera przydatny cap-off i bezpieczne mechanizmy sprawdzania replay, ale te fakty nie uzasadniają zakresu 35–50+. **Nie traktować go jako zweryfikowanego kandydata 50+ ani utożsamiać jego scheduler’a z D′.** Pakiet PC sam używa Python multiprocessing (`--workers 14`), nie Rust/Rayon; jego cel to budowa publicznego playbooka.

## Rekomendacja kandydata

Powstał izolowany pakiet `arc3_local_candidate/` z:

- implementacją formuły D′ w `dprime.py` (priorytet, bez interakcji z Kaggle);
- niezależnym scorecardem RHAE i CLI audytu `benchmark.json`;
- testami `unittest` oraz etapowym manifestem `candidate.json`.

Etapy są celowo rozdzielone:

1. cap-off safe control na tym samym modelu/serwingu, bez `ABANDON`;
2. dopiero potem D′ jako jedyna zmiana schedulera.

Nie włączono win-path replay, memory, offline playbook, dead-skip, plan-commit ani zmian serwingu; część tych pomysłów jest niezmierzona lub odrzucona, a nałożenie ich uniemożliwiłoby diagnozę. Nie utworzono pełnego notebooka, bo aktywna gałąź to `Gemma-konkurs`, a ARC bundle/runner jest w innym repo — nie zmieniano żadnej gałęzi zdalnej.

**Rust+Rayon pominięto świadomie:** wcześniejsze pomiary segmentacji `0.178 ms` vs ok. `6077 ms` na wywołanie LLM (ok. 1:34,142) nie wskazują bottlenecku. Szybszy search po publicznych grach nie rozwiązuje hidden games. Pakiet jest Python stdlib, właściwy do integracji z istniejącym Python runnerem. Nie uruchamiałem testów na fizycznym Ryzenie użytkownika ani nie twierdzę, że lokalny smoke prognozuje LB.

## Wykonane testy lokalne

```bash
python3 -m unittest discover -s arc3_local_candidate/tests -t . -v
python3 -m compileall -q arc3_local_candidate
```

Wynik: **19/19 testów zaliczonych**, kompilacja modułów OK. Niezależny audyt dwóch istniejących artefaktów z GitHuba dokładnie odtworzył zapisane scorecardy (`0` rozbieżności): r110 mean `0.727991`, r118 mean `0.273354`. To waliduje implementację scorecardu, nie transfer strategii ani wynik LB.

Brak Kaggle runu, Kaggle submission, GPU/treningu, pushu lub commitu kandydata. Każdy z tych kroków wymagałby osobnej zgody użytkownika.

## Źródła

- Smak r116: https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena/5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r116-submissions/SUMMARY.md
- Smak r110 output-pick: https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/tree/arena/5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r110-kernel_output_pick/output-pick
- Smak r117: https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena/5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r117-kernel-status/SUMMARY.md
- Smak r118: https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena/5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r118-kernel_output_pick/SUMMARY.md
- c87 diagnoza: https://github.com/peteraangelic-pixel/Pokemon/blob/arena/c87f7a48-pokemon/arc3-handoff/DIAGNOZA-23-89-I-PLAN.md
- a450 lokalny v13 (wartościować krytycznie): https://github.com/peteraangelic-pixel/Pokemon/tree/arena/a450b00f-pokemon/arc-agi-3/duck-v13-mega
- D′ source/research: https://github.com/mayankraj4728/ARC-AGI-3-2026
- Held-out evaluation summary: https://github.com/rasagyavatsal/arc-prize-2026-arc-agi-3
- Ocena kosztu segmentacji vs LLM: https://github.com/peteraangelic-pixel/Pokemon/blob/arena/c87f7a48-pokemon/arc3-handoff/OCENA-RUST-BENCH.md
