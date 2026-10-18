# Bramki dla V8 — zapisane PRZED zobaczeniem wyniku (2026-10-18)

Zasada z Pokemon (`BENCH_V2_HARD_REQUESTS.md`): „CI, nigdy punkt" i „żadnej decyzji na małej
próbce". Dlatego progi są zapisane tutaj, zanim ktokolwiek zobaczy liczby, i nie zmieniają się po
fakcie. Wszystko, co nie przejdzie bramki, **nie idzie na slot** — zostaje V5 (0,13).

## Ekran C (concurrency) — 12 zadań sparowanych, seed 20261009

Baseline seryjny, ten sam plik i te same zadania: **5/12 rozwiązanych, 2919 s, 2 puste drzewa**
(`gemma4-agent/kaggle_results/v7-c-benchmark/agent_benchmark_result.json`, pierwsze 12).

| bramka | próg | po co |
| --- | --- | --- |
| **C1 zgodność** | rozwiązane 4–6/12 | concurrency ma być neutralne; wypadnięcie poza ten przedział znaczy, że batching psuje jakość i wszystkie przyszłe ekrany trzeba robić seryjnie |
| **C2 zysk czasu** | wall-clock ≤ 60 % seryjnego | sens istnienia concurrency; przy 3 równoległych sesjach oczekujemy ~2,5× |
| **C3 puste drzewa** | ≤ 2/12 | jeśli kolejka wydłuża sesje, agenci będą kończyć na zegarze z pustym drzewem |
| **C4 brak awarii** | 12/12 zadań z wynikiem | kernel musi dojść do końca; status `error` = ekran nieważny |

C1–C4 są warunkiem wstępnym. Bez C1 i C2 **nie uruchamiamy V8 na 30 zadaniach**, bo nie mamy
taniego pomiaru, a drogi (seryjny) zjada kwotę.

## Ekran V8 — te same 30 zadań, w tej samej kolejności, seed 20261009

Baseline: **10/30** (V5/V7-c; identyczna lista `task_ids`, więc porównanie jest parowane).
Jedyna różnica między archiwami: `prompts/system.md` (pętla weryfikacji po edycji). Budżet, sampling,
model i narzędzia bajt w bajt jak V5.

| bramka | próg | uzasadnienie |
| --- | --- | --- |
| **V1 wygrana** | V8 ≥ 13/30 | +10 pp na ekranie to minimum, przy którym warto zajmować slot |
| **V2 pary niezgodne** | netto ≥ +4 (wygrane−przegrane) | przy 4 parach w jedną stronę test znaku daje p = 0,0625; mniej = szum |
| **V3 puste drzewa** | < 6/30 | pętla weryfikacji ma nie zwiększać liczby sesji bez edycji |
| **V4 czas** | średni ≤ 330 s przy tym samym concurrency | 120 × (330+30) = 12,0 h; wyżej = ryzyko przekroczenia limitu 12 h |
| **V5 uczciwość** | tylko zmiana promptu | jeśli w archiwum zmieniło się cokolwiek jeszcze, ekran jest nieważny |

**Decyzja:** V1 **i** V2 **i** V3 → V8 jedzie na slot (po jawnej zgodzie). Inaczej slot dostaje
**V5** — jedyne archiwum, które zmierzyło 0,13 — a V8 wraca do szuflady jako „zmierzone, bez zysku".

## Czego te bramki nie mówią

- 30 zadań to nadal ±18 pp przy 95 % CI. Nawet 13/30 nie jest dowodem, że oficjalny wynik wzrośnie;
  to jest dowód, że **nie spadnie** i że kierunek jest dodatni. Rozstrzyga urządzenie oficjalne
  (±9 pp przy 58 zadaniach), a nie ekran.
- Czasów z ekranu przy concurrency 3 **nie wolno** wstawiać do arytmetyki 12 h: kolejka zawyża
  per-zadanie. Do arytmetyki liczy się tylko przebieg seryjny (V5: 232,7 s średnio).
- Ekran mierzy 30 publicznych zadań tych samych czterech repozytoriów, na których ćwiczono prompty.
  To nie jest holdout i nie wolno go tak nazywać.
