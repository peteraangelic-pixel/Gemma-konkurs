# V6.12 — artefakt zgłoszeniowy na noc 15/16 X 2026 (bramki zamrożone przed wysyłką)

Stan na 2026-10-15 ~20:20 UTC. V6.12 **nie został wysłany**. Nic się nie stanie, dopóki nie
zostanie wypchnięty `gemma4-agent/kaggle_smoke/official-submit-v612.trigger` (albo workflow nie
zostanie uruchomiony ręcznie z wyborem artefaktu).

## Czym V6.12 jest

**V6.12 = V6.10 (kontrakt V6.7 + ewoluowany lokalizator V6.8 + inline V6.6) + trzy reguły konwersji
z V6.11, w kopercie budżetowej V5** (jedynej, która ukończyła oficjalny przebieg).

| | V5 (0,13) | V6.10 | V6.11 (sobotnie ramię) | **V6.12 (dzisiejsza noc)** |
| --- | --- | --- | --- | --- |
| wywołania / tury | 45 / 80 | 30 / 60 | 45 / 80 | **45 / 80** |
| limit czasu zadania | 5,25 min | 5,25 min | **8,0 min** | **5,25 min** |
| lokalizator | pierwszy grep | ewoluowany, inline | ewoluowany, inline | ewoluowany, inline |
| reguły kontraktu V6.7 | — | ✓ | ✓ | ✓ |
| reguły konwersji („kończ po edycji", ratunek przed pustym drzewem, higiena edycji) | — | — | ✓ | **✓** |
| artefakt | `282b1446…` | `523d43fb…` | `7b2beec1…` | **`5381ae17…`, 15 137 B, prompt 23 405 znaków** |

Cztery zdania dopisane wobec V6.10: deklaracja budżetu 45 wywołań z uczciwym zdaniem „the clock,
not the cap, is what ends most sessions"; „**finish as soon as your intended edit is on disk**";
ratunek przed pustym drzewem po wywołaniu 8; reguła higieny edycji z cudzego pomiaru (105/524
odrzuconych wywołań, 47 przez utratę granic długiego argumentu).

## Dlaczego NIE wysyłamy V6.11 (8 minut) — arytmetyka, nie preferencja

Limit 12 h obejmuje **cały** przebieg i jego przekroczenie **zeruje całą submisję** (HOST, `743063`).
Bezpieczna jest **średnia**, nie cap:

    120 zadań × (średnia 3,9 min + ~0,5 min setup) = ~8,8 h   <- średnia V5 w naszym ekranie
    120 zadań × (cap   5,25 min + 0,5 min setup)  = 11,5 h    <- najgorszy przypadek, który V5 przeżył
    120 zadań × (cap   8,0  min + 0,5 min setup)  = 17,0 h    <- V6.11; wymaga zmierzonej średniej

Nasze ekrany pokazują, że sesje dobijają do ~95 % capa (V6.4: średnia 4,97 min przy capie 5,25),
więc podniesienie zegara podnosi średnią, dopóki reguła „kończ po edycji" nie zostanie zmierzona.
V6.11 ma to zmierzyć w sobotę (bramka S1: średnia ≤ 5,0 min); **dopóki S1 nie przejdzie, 8 minut nie
idzie do Kaggle**, bo scenariusz porażki to nie „niższy wynik", tylko „brak wyniku".

## Weryfikacja przed wysyłką (wszystko wykonane dziś)

| kontrola | wynik |
| --- | --- |
| packer (zamknięty zbiór 5 plików, model, narzędzia, brak `submit_patch`, YAML, !include) | PASS |
| kontrole negatywne V6.12 | **1 pozytywna + 15 negatywnych, wszystkie się zapalają** (w tym: wpisanie „8-minute window" do promptu jest odrzucane, a `max_time_minutes` ≠ 5,25, `max_tool_calls` ≠ 45 i `max_turns` ≠ 80 są odrzucane w `eval_config.yaml`) |
| selftest łańcucha strażników wysyłki (`tools/selftest_submit_guard.py`) | **7/7** — zły hash, duplikat komunikatu, slot dzienny, okno 24 h, nieparsowalna data, czysta wysyłka, zgodność pinu SHA z realnym archiwum |
| odtworzenie wszystkich ramion z drzewa źródłowego | bajt w bajt (v6.5 `cb847599`, v6.6 `b6686c53`, v6.7 `df7364e2`, v6.8 `8c816fc8`, v6.9 `c99f3d81`, v6.10 `523d43fb`, v6.11 `7b2beec1`, v6.12 `5381ae17`) |
| workflow wysyłki | YAML parsuje się; nazwa obecna; identyfikator zadania `submit-next` **bez kropki** (incydent fantomowych przebiegów z 2026-10-15) |

## Łańcuch strażników wysyłki (co się stanie po wypchnięciu triggera)

1. Archiwum musi mieć **dokładnie** `5381ae17…` — jeśli plik w repo się zmienił, wysyłka się nie odbędzie.
2. Komunikat `V6.12` nie może już istnieć w historii konkursu (ochrona przed ponowieniem po utracie odpowiedzi).
3. Żadna submisja nie może być z **dzisiaj** ani z ostatnich **24 h** (reguła konkursu: 1/dzień).
   Stan na teraz: ostatnia to V5 z 2026-10-14 15:58:54 UTC — o 00:0x UTC 16 X obie kontrole przechodzą.
4. Po wysyłce skrypt **odczytuje historię** i zapisuje paragon (`kaggle_results/v612-official-submission.json`);
   surowe wyjście CLI nie jest nigdzie zapisywane, tokena nie dotyka.
5. Job kasuje zużyty trigger i commituje paragon na tę gałąź.

## Pre-registracja odczytu wyniku oficjalnego

Kontekst szumu (publicznie, ten sam pakiet 4×): **0,17 / 0,15 / 0,13 / 0,15**; LB publiczna = 58 zadań,
więc 1 zadanie ≈ 0,017. Pojedynczy wynik **nie** rozstrzyga o pojedynczej dźwigni.

| wynik V6.12 | odczyt | co dalej |
| --- | --- | --- |
| **≥ 0,16** | dźwignie konwertują (kontrakt + lokalizator + reguły konwersji na budżecie V5) | sobota: powtórzyć na V6.12/V6.11, wybrać kandydata do finałów |
| **0,12–0,15** | nieodróżnialne od V5 (szum ±0,02) | nie zmieniamy nic na podstawie tego wyniku; rozstrzyga sobota (V6.11 vs V6.10) i droga SFT |
| **≤ 0,09** | regresja: kombinacja kontrakt+lokalizator+inline szkodzi | wrócić do konfiguracji klasy V5 i przescrenować przed kolejną wysyłką |

**Czego V6.12 nie twierdzi:** nie jest zmierzony na GPU w żadnym przebiegu; nie jest „lepszą wersją
V5" — to **tania informacja** (slot i tak przepada), a nie zapowiedź skoku. Kaggle ocenia na swoich
GPU, więc nie kosztuje to naszej kwoty.

## Kalendarz (dlaczego ta noc nie psuje soboty)

- Wysyłka ~00:05 UTC 16 X → scoring 22–46 h → wynik między 22:05 UTC 16 X a 22:05 UTC 17 X.
- Sobotni reset GPU: **2026-10-17 00:00 UTC** (nasze notebooki benchmarkowe, nie kolidują ze scoringiem).
- Reguła 24 h i limit oczekującej submisji zwalniają się najpóźniej w sobotę rano, czyli **nie
  blokują** zgłoszenia zwycięzcy sobotnich ramion (pierwsze ramię V6.11 kończy się ~03:00 UTC).
- Kolejność sobota: `v611-benchmark.trigger` → `v610-benchmark.trigger` → decyzja o zgłoszeniu.

## Odtworzenie

```
V6_VARIANT=v612 python3 gemma4-agent/tools/make_v6_prompt.py
python3 gemma4-agent/build_submission_v6.py --source-dir gemma4-agent/submission-v6.12
python3 gemma4-agent/tools/negative_controls_v6.py --variant v612
python3 gemma4-agent/tools/selftest_submit_guard.py
```
