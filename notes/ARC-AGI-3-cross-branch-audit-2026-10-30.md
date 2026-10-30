# ARC-AGI-3 — porównanie audytów i opinii z gałęzi (30.10.2026)

## Zakres

Read-only przegląd najnowszych dostępnych tipów wskazanych gałęzi oraz uzupełnienie wynikami najnowszego audytu c87. Nie uruchamiano Kaggle, submissionu, treningu ani GPU; nie zmieniano zdalnych gałęzi. Wnioski poniżej rozdzielają kod, testy offline, hipotezy i niewiadome.

## Sprawdzone tipy

| Repozytorium / gałąź | Tip odczytany | Data UTC | Główne źródła |
|---|---:|---|---|
| `Gemma-konkurs@arena/c4eeb067-gemma-konkurs` | `6a6af4ac` | 30.10 07:25 | [recenzja v13.1](https://github.com/peteraangelic-pixel/Gemma-konkurs/blob/arena%2Fc4eeb067-gemma-konkurs/REVIEWS/2026-10-29-v13-1-z-galezi-a450-weryfikacja.md), [symulacja winpath](https://github.com/peteraangelic-pixel/Gemma-konkurs/blob/arena%2Fc4eeb067-gemma-konkurs/ARC3/local-lab/winpath_sim.py), [weryfikator playbooka](https://github.com/peteraangelic-pixel/Gemma-konkurs/blob/arena%2Fc4eeb067-gemma-konkurs/ARC3/local-lab/playbook_verify.py) |
| `Gemma-konkurs@arena/6d081d52-gemma-konkurs` | zdalnie `678da952` | 25.10 10:20 | [przegląd 24.10](https://github.com/peteraangelic-pixel/Gemma-konkurs/blob/arena%2F6d081d52-gemma-konkurs/notes/ARC-AGI-3-review-2026-10-24.md), [aktualizacja 25.10](https://github.com/peteraangelic-pixel/Gemma-konkurs/blob/arena%2F6d081d52-gemma-konkurs/notes/ARC-AGI-3-cross-branch-update-2026-10-25.md) |
| `Pokemon@arena/c87f7a48-pokemon` | `4c9a3e51` | 30.10 07:51 | [audyt czterech gałęzi](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fc87f7a48-pokemon/arc3-handoff/AUDYT-4-GALEZI-30-10.md), [synteza v13.1](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fc87f7a48-pokemon/arc3-handoff/OCENA-V13-1-TRZY-RECENZJE.md) |
| `Smak-Domu-Konkurs@arena/5ed750ef-smak-domu-konkurs` | `b09f5037` | 30.10 07:42 | [sync §15–16](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/CROSS-SESSION-SYNC-2026-10-25.md#L185), [recenzja v13.1](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/duck-v13-1/OCENA-ARENA-V13-1.md) |
| `Pokemon@arena/7911f950-pokemon` | `a84173ce` | 30.10 07:38 | [weryfikacja v13.1](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2F7911f950-pokemon/arc-agi-3/V13-1-VERIFICATION.md), [model budżetu](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2F7911f950-pokemon/arc-agi-3/EVAL-BUDGET-MODEL.md), [implementacja jego wzoru](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2F7911f950-pokemon/arc-agi-3/rust/src/score.rs) |

Wersja v13.2 znajduje się osobno na `Pokemon@arena/a450b00f-pokemon`, tip `6b108534` z 30.10 07:45; jej audyt zapisano w osobnym pliku.

## Wnioski wspólne i ich poziom dowodu

### 1. Roster: dawne „110 = 25 publicznych klonowanych gier” nie jest potwierdzone

Smak wycofał wcześniejszą certyfikację po sprawdzeniu źródła [`competition_arcade.py`](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r033-recon-bundle/bundle/src/tufa-arc-agi-framework/src/taaf/competition_arcade.py). Plik nazywa się lokalnym symulatorem i odróżnia go od prawdziwej ścieżki gatewayowej. `official_110()` cyklicznie kopiuje 25 lokalnych `EnvironmentInfo`, ale nadaje wpisom syntetyczne ID `k000…k109` i zapisuje źródłowe ID w `private_tags`.

To **nie** dowodzi, że punktowany rerun powtarza 25 publicznych gier. Jednocześnie docstring „brak powtórzonych `game_id`” nie dowodzi braku powtórzonych `base_key`: v13.1/v13.2 wylicza klucz z ID (`ls20-hash` → `ls20`), więc różne pełne ID nadal mogą mieć wspólny prefiks. Potrzebny jest rzeczywisty wykaz ID z rerunu, policzony tą samą funkcją.

Jest dodatkowy szczegół: v13.2 `base_key("k000") == "k000"`; `private_tags` nie są używane przez ten moduł. Matcher playbooka również porównuje ID gry. Dlatego syntetyczne ID lokalnego `official_110()` nie ćwiczą współdzielenia pamięci ani dopasowania playbooka tak, jak robi to test Gemmy z ID `tu93-entry1`/`tu93-clone-2`. Ten test celowo symuluje wspólny prefiks, ale nie dostarcza rosteru gatewaya.

**Wniosek:** korekta Smaka obala jego dawny „kodowy dowód” na cykliczny roster publiczny. Nie dowodzi natomiast sama przez się, że cache v13.1/v13.2 jest na prawdziwym rosterze zawsze nieaktywne. Wartość replayu/dead-skip pozostaje warunkowa i niezmierzona.

### 2. Testy mechaniki są użyteczne, ale nie są testem punktowanym

Gemma c4 pokazuje sekwencyjny replay czterech publicznych gier przy 0 tokenów LLM w drugim wpisie i dead-skip od czwartego martwego wpisu. Symulacja importuje moduł v13.1 bez zmian i używa rzeczywistego lokalnego silnika, ale obudowuje go `FakeSession`; nie uruchamia całego patched `solver.py`, gatewaya ani prawdziwego rosteru. Jej test playbooka 14/14 i hashy jest dobrym wynikiem offline, lecz nie przewiduje wyniku submissionu.

Moja lokalna notatka [audytu v13.1](ARC-AGI-3-v13.1-audit-2026-10-30.md), commit `dfa361b`, dodaje ryzyko współbieżności: `_Store` ładuje snapshot przy starcie sesji, nie serializuje zapisów, używa wspólnego pliku `.tmp`, a scalenie licznika `max(local,disk)` może zgubić inkrement. Przy nakładających się sesjach tego samego `base_key` pamięć może być niewidoczna, a dead-skip może zliczyć mniej prób. Jest to możliwość wynikająca z kodu, nie twierdzenie, że występuje w każdym runie.

### 3. `PLAN_COMMIT=1` nie wymusza batchowania

Kod patcha 0005 udostępnia `commit(plan)` i opisuje narzędzie w promptcie. `ARC3_ESCALATE_ACTIONS` jest odczytywane i po przekroczeniu progu dokleja dyrektywę planowania. Model nadal może jej nie wykonać; nie ma wymuszonego `tool_choice` ani automatycznego commitowania. Propozycja `60 → 8–10` może zwiększyć częstotliwość przypomnień, ale nie gwarantuje więcej akcji na decyzję. Wpływ na użycie `commit()` i score pozostaje niezmierzony.

### 4. Modele budżetu i score mają niewiadome

7911 modeluje 9 h, concurrency 10 i ok. 110 gier, co daje średnio ok. 49 minut na grę. To arytmetyka warunkowa; sam autor zaznacza, że nie widział pełnej listy rosteru. Podobieństwo smoke 10 gier do publicznego LB jest argumentem pośrednim o warunkach budżetu, nie dowodem na liczbę ani tożsamość gier. W jego modelu sufit 18,7 pkt dla 110 gier jest przy tym niższy od przywoływanego wyniku LB 26,25; najnowszy audyt c87 wskazuje tę niespójność i jej nie rozstrzyga.

W sprawie capu punktacji 7911 `rust/src/score.rs` twierdzi, że oficjalny cap per-level to 1,0. Zarchiwizowany scorer TAAf deklarujący zgodność z `EnvironmentScoreCalculator` v0.9.8 używa `min(115, …)` oraz dodatkowego limitu od ukończonych poziomów. Najnowszy c87 opowiada się za 1,15 i przywołuje też regresję 32/32 zapisanych wyników w Gemmie. Wśród sprawdzonych materiałów **1,15 ma mocniejsze wsparcie kodem/scorerem**, ale pozostaje sprzeczne twierdzenie 7911 o stronie konkursu; nie używać obu wersji capu zamiennie w projekcjach.

### 5. Nowy sygnał z audytu c87: różnica 3,6× w czasie na token

Najnowszy raport c87 zauważa w materiałach Gemmy 17,2 ms/token dla r085 wobec 62,6 ms/token dla r110 na tej samej linii modelu 8B. Przy założeniu 2 945 s na grę odpowiada to ok. 228 wobec 82 akcji/grę. To jest istotna **obserwowana różnica w raportowanych runach**, warta sprawdzenia przed dalszym strojeniem promptu.

Przyczyna (pula KV, kolejki, prefix cache lub inny warunek serwera) nie została potwierdzona. Sam raport c87 zaznacza, że r110 może być smoke-like, nie pełnym rerunem 110 gier, i proponuje dopiero parsowanie `serve.log`. Nie traktować 3,6× jako dowodu, że zmiana v13.2 podniesie wynik ani jako potwierdzonej drogi do 40+/50+.

### 6. Szacunki zysku i rekomendacje nie są jednym wspólnym pomiarem

W recenzjach występują różne liczby: Gemma podaje ok. **+2,9** dla playbooka uśrednionego po 25 publicznych grach i **0**, jeśli w rosterze nie ma pokrycia; dla pamięci/replayu między wpisami podaje **+5…+15** warunkowo przy cyklicznym rosterze. 7911 szacuje sam playbook na **+0,6…+2,7**. To różne komponenty i założenia, a nie wyniki z punktowanego runu — nie sumować ich.

C87 wskazuje throughput jako drogę do 50+ (w modelu około **300 akcji/grę** wobec ok. 213) i nowy sygnał r085/r110. Ta ścieżka nadal nie ma wyniku na v13.2 ani potwierdzonej diagnozy źródła spowolnienia.

Smak ma też zmianę rekomendacji wewnątrz własnego dokumentu: §15 po retrakcji sugeruje wyłączyć winpath/dead-skip dla atrybucji, a §16 nadpisuje to i wybiera ustawienia as-shipped z sondą jako opcję, jeśli roster jednak powtarza gry. Druga decyzja **nie rozstrzyga** rosteru ani nie zmienia warunkowego charakteru korzyści.

## Ocena gałęzi

- **Gemma c4:** najmocniejszy lokalny test mechanizmu; warunek rosteru pozostaje otwarty, a „end-to-end” oznacza test modułu z fake harness session, nie pełny solver.
- **Gemma 6d:** zdalny tip jest z 25.10; przydatny jako wcześniejszy audyt baseline’u 26,25 i smoke’u, ale nie jest aktualną opinią o v13.1/v13.2.
- **Pokemon c87:** najnowszy audit koryguje własne i Smakowe wcześniejsze tezy o rosterze; dodaje sygnał 3,6× i sam zaznacza, że mechanizm nie jest rozstrzygnięty.
- **Smak:** dobrze wycofał błędne „110 klonów potwierdzone w kodzie”. Dalsze stwierdzenie, że unikalne pełne ID czynią replay/dead-skip martwymi, wymaga jeszcze sprawdzenia duplikatów `base_key`.
- **Pokemon 7911:** użyteczny audyt kodu `PLAN_COMMIT` i budżetu; 110/49 min to model, nie pomiar pełnej listy gier, a jego cap 1,0 jest sprzeczny z archived TAAF scorerem.

Wiele raportów cytuje nawzajem swoje ustalenia; nie są to pięć niezależnych replikacji. Żaden z nich nie dostarcza punktowanego wyniku v13.1/v13.2 ani bezpośredniego logu pełnego rosteru.

## Bezpieczny następny dowód

Bez uruchamiania Kaggle: z już istniejącego logu rerunu odczytać wszystkie `game_id`, policzyć `base_key`, liczbę kolizji i faktyczne hity/missy replayu. Równolegle porównać logi serwera dla r085/r110/r093, jeśli artefakty są dostępne. Dla skuteczności v13.2 potrzebne są też liczniki wywołań `commit()` i akcji na decyzję. Dopiero kontrolowany pomiar może rozstrzygnąć wpływ punktowy.

## Źródła dodatkowe

- [TAAf `competition_arcade.py`](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r033-recon-bundle/bundle/src/tufa-arc-agi-framework/src/taaf/competition_arcade.py)
- [TAAf scorer `game.py`](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r033-recon-bundle/bundle/src/tufa-arc-agi-framework/src/taaf/game.py)
- [Gemma `MEGA-CONFIG.md`](https://github.com/peteraangelic-pixel/Gemma-konkurs/blob/arena%2Fc4eeb067-gemma-konkurs/ARC3/local-lab/MEGA-CONFIG.md)
- [c87 audyt czterech gałęzi](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fc87f7a48-pokemon/arc3-handoff/AUDYT-4-GALEZI-30-10.md)
- [v13.1 lokalny audyt w tym repo](ARC-AGI-3-v13.1-audit-2026-10-30.md)
