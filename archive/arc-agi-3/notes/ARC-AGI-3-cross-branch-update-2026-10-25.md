# ARC-AGI-3 — aktualizacja z gałęzi Pokemon (2026-10-25)

> **Ta notatka koryguje** wcześniejszy przegląd [`ARC-AGI-3-review-2026-10-24.md`](ARC-AGI-3-review-2026-10-24.md). W szczególności wcześniejsze wskazanie „efektywność ruchów” jako głównego ograniczenia jest zbyt mocne po uwzględnieniu nowych pomiarów z gałęzi Pokemon.

## Gałęzie i stan prac

- `peteraangelic-pixel/Pokemon`, `arena/c87f7a48-pokemon`, tip `6c53d13bfbc0d7805936cf8faf5be03ea66dc9b5` (2026-10-24 21:56 UTC): offline'owy search/playbook, kalibracja kliknięć, analiza budżetu oraz korekta wcześniejszych, zbyt optymistycznych prognoz.
- `peteraangelic-pixel/Pokemon`, `arena/a450b00f-pokemon`, tip `33a9f7e5b428992a8048f67cbca18f9e2ad5f536` (2026-10-24 20:42 UTC): prototyp Duck v8 z rejestrowaniem i replayem rozwiązanych poziomów; poprawiony test integracyjny 10/10.
- To są **postępy offline i inżynieryjne**, nie nowy wynik Kaggle. V8 replay ma testy jednostkowe/integracyjne, lecz jego dokumentacja wyraźnie mówi, że nie ma jeszcze smoke'u ani pomiaru punktowego.

## Najważniejsza korekta diagnozy: liczy się głębokość

Z `arc3-handoff/FAKTY-I-POMIARY.md` i `results/playbook.json` na c87 wynika wzór zgodny co do setnej z danymi `r019`:

- poziom ukończony: `min(115, (baseline/actions)^2 * 100)`; nieukończony: `0`;
- poziomy mają wagę rosnącą z numerem (`w_k = k+1`), mianownik zawiera wagi wszystkich poziomów, a wynik ma dodatkowy cap zależny od ukończonych poziomów;
- test na `tn36` (1/7 poziomów → 3,57) i `ls20` (1/7 → 3,27) odtwarza wyniki z r019.

W konfiguracji r019 większość ukończonych poziomów już trafia w cap 115. Sufit z samej głębokości smoke'u to 29,0 pkt wobec zmierzonych 27,21, czyli cała strata przypisana dalszej poprawie efektywności ruchów wynosi około **1,75 pkt** na tym zestawie. Zatem wcześniejsza rada, by przede wszystkim „zmniejszać liczbę ruchów”, nie jest właściwym celem. Oszczędność ma znaczenie, jeśli pozwala ukończyć **dodatkowy poziom** albo uwalnia przepustowość innym graczkom; nie daje dużego zysku sama w sobie po osiągnięciu capu.

**Cel techniczny to ukończenie więcej ważonych poziomów**, a nie poprawienie ruchów na poziomach, które już punktują na capie.

## Co faktycznie zadziałało w offline searchu

`arc3-handoff/arc3_search.py`, `results/playbook.json` i `PATCH-0004-I-SEARCH.md` raportują sześć przebiegów CPU-only, bez tokenów LLM. Najlepszy scalony playbook ma **11/25 gier, 16 poziomów i 3,18 pkt dolnego ograniczenia**; każda sekwencja została odtworzona na świeżej instancji gry. To użyteczny, zmierzony składnik, ale nie podstawa do obietnicy +14–37 pkt ani 45+.

Najbardziej transferowalny wynik metodyczny to **kalibracja kliknięć po zaobserwowanym efekcie**, zamiast wyznaczania klików z centroidów blobów. Skan siatki, reset poziomu i grupowanie klików po hashu nowej ramki dodały rozwiązania `ar25`, `cn04` i `ft09`; `ft09` przeszła z pustego searcha do ukończenia pierwszego poziomu w 4 akcjach. To konkretna metoda warta zachowania dla dalszego searcha. Wewnętrzne `_get_valid_actions()`/`_score`/`_win_score` zostały w audycie oznaczone jako niedozwolone w submissionie; używać publicznego API i kalibracji po skutku.

Pomiar 60k węzłów rozwiązał dodatkowo `s5i5`, ale dalsze zwiększenie capa do 200k nie dodało poziomów: `ka59` wyczerpała frontier, a `re86` pozostała ograniczona capem. Wniosek: przed wydaniem CPU/GPU rozpoznawać przyczynę zatrzymania:

- `node_cap_cut` → większy cap może pomóc, ale trzeba ograniczyć pamięć frontieru;
- `time_cut` → sprawdzić sekundy na węzeł; sam limit czasu nie pomoże, gdy silnik utknął na wolnej animacji;
- `frontier_exhausted` → zwiększanie budżetu nie pomoże, trzeba poprawić generator ruchów lub heurystykę czytającą planszę.

Dla BFS pamięć frontieru jest realnym ograniczeniem: pomiar `re86` wynosił około 0,190 MB na stan; `--frontier-cap` zapobiegł scenariuszowi OOM. Nie uruchamiać równoległego BFS bez limitu frontieru.

## Ważne korekty wcześniejszych hipotez

- **Nie sumować hipotetycznych zysków.** Najnowszy commit c87 (`6c53d13`) wycofuje prognozę +7–17 pkt z level-cap/ABANDON: poziomy są sekwencyjne, a `ABANDON` kończy grę, nie przenosi budżetu na jej kolejny poziom. Uwolnienie slotu SGLang może pomóc innym grom w puli, ale ten efekt jest niezmierzony.
- **RESET_LEVEL** jest jedynym wskazanym tam kandydatem per-gra na dodatkową próbę od czystej klatki przy zachowaniu poziomu (`ONLY_RESET_LEVELS=true`). Jest darmowy w tokenach LLM, lecz jego wpływ na ukończone poziomy pozostaje niezmierzony.
- Budżet około 208 akcji na grę jest tylko oszacowaniem z r019. Przy tym założeniu wszystkie poziomy mieszczą się w budżecie tylko w `cd82` i `ft09` — już obecnych w playbooku; najbliżej są `sb26` i `r11l`. Dla większości gier „+1 poziom w każdej” to sufit arytmetyczny, nie plan wykonawczy.
- **`game_weights` nie realokuje budżetu gry** w sprawdzonym kodzie — wpływa na diagnostykę/agregację. `n_passes` jest nadpisywane do 1 w komórce 14 notebooka.
- Nie ma podstaw, by poprawiać rzekomy brak pamięci lub limit historii jako główny problem bez ponownego sprawdzenia konfiguracji: c87 potwierdza, że kompakcja pamięci istnieje, jest wyłączana przez `ARC3_MEMORY_SECTIONS=off`, a efektywny `ARC3_HISTORY_ASSISTANT_TURNS` w tej konfiguracji wynosi 150, nie domyślne 30.

## Duck v8 replay z a450: co jest, a czego jeszcze nie dowodzi

`arc-agi-3/duck-v8/` dostarcza sensowny prototyp record/replay. Po teście integracyjnym poprawiono dwa rzeczywiste błędy okablowania (utrata pierwszej akcji segmentu i off-by-one `prev_level/consumed`); wynik testów to 7 jednostkowych + 3 integracyjne, **10/10**. To potwierdza logikę na atrapie środowiska, **nie** zachowanie w Kaggle ani zysk punktowy.

`RESET-VERDICT.md` zaznacza, że wcześniejszy test resetu nie ustawił `ONLY_RESET_LEVELS=true` przed budową klienta, podczas gdy notebook konkursowy ustawia ten pin. Replay nie powinien więc być uznany za główną dźwignię bez sprawdzenia konfiguracji rzeczywistego harnessa. Dodatkowo patch c87 o numerze `0004` i replay patch a450 `0004-solved-level-replay.patch` są różnymi zmianami; nie składać ich w jeden łańcuch z tym samym numerem ani nie zakładać, że ich hunki się stosują. c87 raportuje, że jego standalone level-cap ma **zastąpić** stary patch 0003, a nie być dokładany po 0003b.

## Blokery operacyjne i konkursowe

- `WERYFIKACJA-INNYCH-GALEZI.md` na c87 wskazuje prawdopodobny błąd w auto-submit: `ops.py:459` przekazuje domyślnie ścieżkę, podczas gdy CLI oczekuje nazwy pliku `submission.parquet`. W raporcie 12 prób ze ścieżką kończyło się błędem, a dwie z samą nazwą pliku przeszły; zastrzeżenie: nieudane wersje miały też status `ERROR`, więc do rozstrzygnięcia testować naprawę na wersji `COMPLETE`. Nie testowałem ani nie zmieniałem zdalnego kodu.
- c87 opisuje także martwy guard `soft_end` i run-killer: patch 0003 nie aplikuje się po patchu Franzena w kolejności z notebooka. Te elementy trzeba naprawić przed następnym pomiarem, inaczej nie będzie wiarygodnego submissionu.
- Według odczytu oficjalnej strony Kaggle zapisanego w c87 24 października, deadline 26 X dotyczy entry/team merger, a finałowe submission jest 2 XI; w repo odnotowano, że entry już spełniono (6 punktowanych submissionów). Live top-5 wynosił wtedy **49,85**, więc 45+ nie oznaczało nagrody. To snapshot z 24 X, nie nowy odczyt wykonany w tej sesji; leaderboard i próg są dynamiczne. C87 podaje też, że publiczny leaderboard stanowi około połowę testu, a nagroda wymaga publicznego, permisywnie licencjonowanego rozwiązania — potwierdzić warunki przed finałem.
- `PLAN-V8.md` w a450 wskazuje wariant Franzen M2 z Qwen3.8-Flash-Next W4A16 + MTP/SGLang jako potencjalny większy skok. Ta notatka **nie potwierdza niezależnie** wyniku tego wariantu; traktować go jako kierunek do weryfikacji, z dokładnym modelem, checkpointem i konfiguracją, nie jako gwarantowany wynik.

## Priorytety, które wynikają z obu gałęzi

1. Wspólny punkt odniesienia to ostatni potwierdzony wynik z repo ARC: duck v3 `26,25`; nie mylić go z niezmierzonymi patchami z Pokemon.
2. Przed kolejnym oficjalnym pomiarem usunąć blokery wyjścia/submissionu i błędny łańcuch patchy; testować na wersji `COMPLETE`.
3. Zachować i rozwinąć **effect-based calibration + offline playbook** jako realnie zmierzony komponent (3,18 pkt podłogi), a kolejne CPU-searchy dobierać po `failure_mode`, nie po samym typie gry czy intuicji.
4. Największy potencjał niepotwierdzony: RESET_LEVEL/ponowna hipoteza bez utraty poziomu, szybszy model/serwer lub integracja playbooka z LLM. Każdy to osobna hipoteza; nie sumować zysków i nie używać Kaggle slotu bez testu.
5. Nie stawiać na replay, `game_weights`, większą liczbę passów ani samo skracanie akcji jako rozwiązanie 45+/50. Dla replaya istnieje dobry test software'owy, ale nie ma pomiaru score'u i aktualna konfiguracja może nie uruchamiać mechanizmu.

W tej sesji tylko odczytano repozytoria przez GitHub API. Nie wykonano Kaggle API, smoke/benchmarku, treningu/GPU ani submissionu; nie zmieniono gałęzi Pokemon.

## Źródła

- c87: [README/handoff](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fc87f7a48-pokemon/arc3-handoff/README.md), [DIAGNOZA-45plus](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fc87f7a48-pokemon/arc3-handoff/DIAGNOZA-45plus.md), [FAKTY-I-POMIARY](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fc87f7a48-pokemon/arc3-handoff/FAKTY-I-POMIARY.md), [PATCH-0004-I-SEARCH](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fc87f7a48-pokemon/arc3-handoff/PATCH-0004-I-SEARCH.md), `arc3-handoff/results/{playbook.json,budget_triage.tsv}`.
- a450: [PLAN-V8](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v8/PLAN-V8.md), [INTEGRATION-RESULTS](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v8/INTEGRATION-RESULTS.md), [RESET-VERDICT](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v8/RESET-VERDICT.md), [DEEPSEEK-REVIEW-VERDICT](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v8/DEEPSEEK-REVIEW-VERDICT.md).
