# ARC-AGI-3 — przegląd wyników i priorytety (2026-10-24)

## Zakres i wniosek

Przegląd read-only zdalnej gałęzi `arena/5ed750ef-smak-domu-konkurs` repozytorium `peteraangelic-pixel/Smak-Domu-Konkurs` (tip `97fe3602af4a30065a7b16cc418358cffca0b0e9`). Mimo nazwy repozytorium analizowany projekt to ARC-AGI-3.

**Wniosek:** w sprawdzonych artefaktach nie ma wyniku 45+. Najlepszy zapisany oficjalny wynik konta to **26,25**. To nie wygląda na pojedynczy błąd promptu; dane wskazują przede wszystkim na nieefektywność agenta na trudnych poziomach oraz zbyt mało wiarygodnych, pełnych pomiarów kolejnych kandydatów.

## Wyniki zapisane w repozytorium

Raport `arc-agi-3/kaggle/ops/results/r062-submissions/SUMMARY.md`, wygenerowany 2026-10-24 13:48 UTC, podaje:

| Submission | Wariant | Status | Wynik |
|---|---|---|---:|
| `57247568` | duck v3 | COMPLETE | **26,25** |
| `57125322` | v2-think-less | COMPLETE | 24,66 |
| `57201063` | v5-world-model-stuck | COMPLETE | 23,94 |

`r062` jedynie sprawdził listę submissionów; nie zawiera nowszego wyniku. Wariantu v5 nie należy traktować jako poprawy nad v2. V3 jest najlepszym potwierdzonym punktem odniesienia, ale nadal brakuje mu 18,75 pkt do celu 45.

## Co prawdopodobnie ogranicza wynik

1. **RHAE mocno karze nieefektywne ruchy.** W `arc-agi-3/rust/src/score.rs` wynik poziomu jest proporcjonalny do `min(H/A, 1.15)^2`, gdzie `H` to ruchy człowieka, a `A` — agenta; późniejsze poziomy ważą więcej. Zwiększenie samego budżetu myślenia nie gwarantuje poprawy. Liczą się postęp i oszczędność ruchów, szczególnie na dalszych poziomach.
2. **Dolny ogon gier jest bardzo słaby.** Smoke `r019` na 10 grach miał średnią 27,21, medianę 23,21 i nie ukończył żadnej całej gry. `ls20` uzyskało 3,27 pkt (1/7 poziomów; 227 ruchów na drugim), `tn36` 3,57 (1/7; 124 ruchy na drugim), `g50t` 10,71, a `ka59` 17,85. Wysokie wyniki niektórych gier nie kompensują tych zastojujących.
3. **Występują kosztowne utknięcia.** Smoke `r050` dla `sk48` zakończył się po 2 h 12 min z 521 ruchami, 231 366 wygenerowanymi tokenami i wynikiem 0/8 ukończonych poziomów. Log potwierdza załadowanie `vrfai/Qwen3.6-27B-FP8`; w tym konkretnym przebiegu bardziej widoczny jest brak postępu niż błąd ładowania modelu. To pojedynczy smoke, nie wynik konkursowy.
4. **Smoke’y zawyżają wiarygodność prognoz.** Zapisane porównania to: v2 `30,54 → 24,66` (−5,88), v5/v6 `27,21 → 23,94` (−3,27), v3 `29,02 → 26,25` (−2,77). Wartości smoke nie są więc substytutem pełnego rerunu. Prognozy tokenowe w `PLAN-GENIUS.md` (np. 300k → 45,7) pozostają estymatami, a nie potwierdzonym wynikiem Kaggle.
5. **Eksperymentowanie blokowały też problemy operacyjne.** Historia odnotowuje błędne submissiony, błędy/limity pushy i problemy środowiska. Do 24 października nie pojawił się nowy oceniony wariant po submissionie z 16 października, co ograniczyło liczbę użytecznych iteracji.

## Priorytety na dalszą pracę

1. Zachować duck v3 (`26,25`) jako baseline; nie promować zmian tylko na podstawie smoke’u.
2. Najpierw analizować zastoje w `ls20`, `tn36`, `g50t`, `ka59` i `sk48`. Najbardziej obiecująca szybka hipoteza to wykrywanie braku zmiany stanu/powtarzających się akcji i wymuszenie jakościowo nowej strategii przed spaleniem dużej części budżetu. W repo istnieją już detektory powtórzeń w warstwie replay.
3. Porównywać kandydatów z v3 na tym samym, możliwie reprezentatywnym zbiorze; nie wyciągać wniosków o 45+ z 10 gier ani z jednego przebiegu. Do oficjalnego Kaggle benchmarku/submissionu potrzebna jest osobna zgoda.
4. Jeśli celem jest 45+, samo strojenie promptu nie ma potwierdzonej skali. Potrzebny byłby większy, zmierzony zysk w rozwiązywaniu trudnych poziomów lub legalnie używalny, dokładnie odtworzony mocny baseline. Nie ma podstaw, by obiecywać 45+.

Nie należy naprawiać jako głównego problemu „braku pamięci między passami” we własnym `llm-agent`: korekta w `MY-WORK-STATUS.md` mówi, że ta hipoteza dotyczyła Duck harness, a własny agent wykonuje jeden pass na grę i resetuje pamięć między grami.

## Terminy i ograniczenia danych

`STATUS.md` w repo odnotowuje, że udział został zaakceptowany, deadline zgłoszenia udziału przypada 26 października, a finałowe submission — 2 listopada 2026. Wobec daty tego przeglądu oznacza to około dwóch dni do pierwszego terminu i około dziewięciu do finałowego.

Zapisany plik public leaderboardu jest z 11 października. Wartość 45,00 w tym snapshotcie nie potwierdza aktualnego progu ani aktualnej pozycji. `r062` odświeżył wyniki własnych zgłoszeń, nie publiczny leaderboard.

## Źródła w analizowanej gałęzi

- `arc-agi-3/kaggle/ops/results/r062-submissions/SUMMARY.md` — status zgłoszeń na 24 października.
- `arc-agi-3/kaggle/ops/results/r019-kernel-output/output/summary.txt` i `benchmark.json` — smoke 10 gier oraz wyniki per gra/poziom.
- `arc-agi-3/kaggle/ops/results/r050-kernel-output/output/summary.txt` i `benchmark.json` — smoke `sk48`.
- `arc-agi-3/rust/src/score.rs` — implementacja metryki RHAE.
- `arc-agi-3/PLAN-GENIUS.md` oraz `arc-agi-3/CHAT-LOG-2026-10-14.md` — hipotezy, kalibracja smoke→LB i historia prób.

Ten dokument zapisuje wnioski z audytu; podczas jego tworzenia nie uruchomiono Kaggle API, benchmarku, treningu/GPU ani submissionu, i nie zmieniono zdalnej gałęzi ARC-AGI-3.
