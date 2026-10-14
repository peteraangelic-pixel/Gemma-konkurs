# V6.8 — bramki i pre-registracja (zamrożone **przed** jakimkolwiek przebiegiem)

Stan na 2026-10-14 ~18:30 UTC. V6.8 **nie został uruchomiony ani wysłany**. Powstał w oknie
oczekiwania na wynik V5 (ref `57188055`, PENDING) jako trzecia dźwignia sobotniego resetu, metodą
przeniesioną z równoległego projektu Pokemon (patrz `ANALYSIS_2026-10-14_EVOLVED_LOCATOR.md`).

## Czym V6.8 jest

**V6.8 = V6.4 + jedna dźwignia (L5): stałe lokalizatora dopasowane populacyjnie do złotych łatek.**

Baza jest celowo V6.4, jak w V6.6/V6.7: każde ramię zmienia jedną rzecz wobec wspólnego przodka.
Nie ma tu klauzuli V6.5, reguł kontraktu V6.7 ani inline'owego lokalizatora V6.6 — podmienione są
wyłącznie **liczby** w skrypcie lokalizatora oraz cztery zdania, które cytują jego zmierzoną
skuteczność.

| | V6.4 | V6.8 |
| --- | --- | --- |
| artefakt | `submission-v6.zip`, `aaea34e4…`, 13 455 B | `submission-v6.8.zip`, **`8c816fc8…`, 13 307 B** |
| prompt | 17 888 znaków (kopia) | **19 752 znaków** |
| lokalizator | stałe dobrane ręcznie | te same wyrażenia, 10 stałych z wyszukiwania populacyjnego |
| reszta | — | bez zmian (sampling, limity, reguły M1–M4, brak `submit_patch`) |

## Skąd te liczby (offline, CPU, zero GPU)

`tools/evolve_locator.py` — pętla ewolucyjna wzorowana na metodzie sąsiedniego projektu (populacja →
mutacja gaussowska wokół top-3 → selekcja), z **kompozytowym** fitness zapisanym przed przebiegiem:

    F = 0.50*top1 + 0.30*top3 + 0.15*top5 + 0.05*top10

Top-1 dominuje, bo prompt każe przeczytać pierwszego kandydata i edytować do wywołania 4.
Ocena: 48 osobników × 25 pokoleń (1200 ocen, ~13 min na 2 rdzeniach) na 128 opublikowanych zadaniach
dev ze złotymi łatkami; walidacja na 104 zadaniach proxy z czterech repozytoriów spoza zbioru dev
(starlette, click, typer, pydantic).

| zbiór | konfiguracja | fitness | top-1 | top-3 | top-5 | top-10 |
| --- | --- | --- | --- | --- | --- | --- |
| dev (128) | ręczna (V6.4) | 0.5875 | 47,7 % | 66,4 % | 73,4 % | 79,7 % |
| dev (128) | ewoluowana | **0.6297** | **55,5 %** | 67,2 % | 74,2 % | 78,9 % |
| holdout (104) | ręczna | 0.5702 | 44,2 % | 65,4 % | 74,0 % | 83,7 % |
| holdout (104) | ewoluowana | **0.6462** | **51,0 %** | **74,0 %** | **83,7 %** | **87,5 %** |

Zysk na zbiorze odłożonym jest **większy** niż na dev (top-3 +8,6 pp, top-5 +9,7 pp), więc to nie
jest artefakt dostrajania. Koszt: top-10 na dev spada o 1 zadanie (79,7 → 78,9 %).

## Czego pilnują kontrole (dwa błędy złapane i naprawione przed oddaniem)

1. **Martwe pokrętła.** Pierwsza wersja wyszukiwania zmieniała wagi zapytania, których scorer nie
   używał — wypieczony plik realizował inną konfigurację niż zmierzona. Kontrola
   `--selftest --locator … --config …` (porównanie rankingu pliku z rankingiem modelu na prawdziwych
   korpusach) to wykryła. Po naprawie: **15/15 zadań identycznych**.
2. **Model ≠ artefakt.** Wersja deweloperska lokalizatora (`tools/locator.py`) ma akronimy i bramkę
   złożonych literałów, których **shippowany** plik nie ma; dodatkowo mój czytnik korpusu pomijał
   inne katalogi niż `collect()` artefaktu, co przesuwało idf. Po przepisaniu ekstrakcji cech na
   `collect()` artefaktu kontrola przechodzi w 100 %.

## Wpływ na 30 zadań, których wyniki znamy (join z koszykami V6.4)

`tools/screen_locator_impact.py`, `analysis/locator-evolve/screen-impact.json`:

- **7 zadań w górę, 2 w dół, 21 bez zmian** (ranga pierwszego złotego pliku).
- największe skoki: `fastapi_14266` (koszyk N: 97 → 36), `fastapi_15030` (R: 32 → 12),
  `fastapi_14482` (W: 63 → 48), `rich_3006` (P: 10 → 4), `rich_3043` (N: 14 → 9).
- złoto w top-3: N 6 → 7, R 5 → 5, P 9 → 9, W 0 → 0.
- pogorszenia: `fastapi_14487` (N: 16 → 23), `rich_3105` (N: 37 → 41).

To miara pomocnicza, nie forecast: poprawa jest skoncentrowana, a 21/30 zadań nie zmienia rangi,
bo złoty plik i tak był wysoko albo pozostaje poza rankingiem.

## Pre-registracja oczekiwań (zapisana przed przebiegiem)

Przebieg: workflow `gemma-kaggle-v68-benchmark.yml` (gotowy), ten sam zestaw 30 zadań i seed
`20261009` co V3–V6.4. Start po pushu `gemma4-agent/kaggle_smoke/v68-benchmark.trigger`.

| # | predykcja | V6.4 | próg dla V6.8 |
| --- | --- | --- | --- |
| R1 | rozwiązane zadania | 10/30 | **≥ 12** (dźwignia jest zmierzona, więc wymaganie jest ostrzejsze niż w V6.7) |
| R2 | sesje edytujące plik z koszyka R, które przegrały | 8 | **≤ 6** |
| R3 | bramki jakości G1, G3 | 0, 0 | **0, 0** |
| R4 | bramka G2 | 3 | **≤ 1** |
| R5 | ranga złota w surowych śladach nowego przebiegu | jak V6.4 | **mediana lepsza o ≥ 2 pozycje** |

R1 jest celowo ostrzejsze: V6.7 tylko usuwa marnotrawstwo, V6.8 poprawia wskazywanie pliku, więc
jeśli różnica nie pojawi się w rozwiązanych zadaniach, dźwignia nie działa tak, jak zapowiada
pomiar offline. R5 mierzy to samo na nowych śladach (wymaga uruchomienia diagnostyki na nowym
kernelu, jak przy V6.4).

## Czego V6.8 NIE twierdzi

- Nie jest zmierzony w żadnym przebiegu agentowym; to ramię na reset 2026-10-17.
- Poprawa lokalizacji **nie musi** przełożyć się 1:1 na score: w V6.4 5 z 11 sesji koszyka N miało
  złoto już na #1 i mimo to nie wykonało żadnej edycji.
- Ranking lokalizatora to sugestia, nie werdykt — prompt nadal każe czytać przed edycją.

## Odtworzenie

```
python3 gemma4-agent/tools/evolve_locator.py --selftest --count 8          # model == shippowany plik
python3 gemma4-agent/tools/evolve_locator.py --build-cache --split dev
python3 gemma4-agent/tools/evolve_locator.py --build-cache --split holdout
python3 gemma4-agent/tools/evolve_locator.py --evolve --pop 48 --gens 25
python3 gemma4-agent/tools/evolve_locator.py --validate
python3 gemma4-agent/tools/evolve_locator.py --bake \
    --base gemma4-agent/submission-v6.4/tools/locate.py \
    --out gemma4-agent/submission-v6.8/tools/locate.py
V6_VARIANT=v68 python3 gemma4-agent/tools/make_v6_prompt.py
python3 gemma4-agent/build_submission_v6.py --source-dir gemma4-agent/submission-v6.8
python3 gemma4-agent/tools/negative_controls_v6.py --variant v68
python3 gemma4-agent/tools/screen_locator_impact.py
```
