# V6.10 — bramki i pre-registracja (zamrożone **przed** jakimkolwiek przebiegiem)

Stan na 2026-10-14 ~19:15 UTC. V6.10 **nie został uruchomiony ani wysłany**.

## Czym V6.10 jest

**V6.10 = V6.4 + TRZY dźwignie: reguły kontraktu narzędzi (V6.7) + ewoluowany lokalizator (V6.8)
+ inline dostarczanie lokalizatora (V6.6).**

To **ramię-kandydat**. Każda z trzech dźwigni jest zmierzona osobno (V6.7: 9/9 odrzuconych zapisów;
V6.8: dev 0,5875→0,6297 i holdout 0,5702→0,6462; V6.6: usunięcie trybu awarii przez konstrukcję),
a kombinacja istnieje, bo w tym konkursie rzadkim zasobem jest **slot dobowy na zgłoszenie**
(1/dzień, weryfikacja 22–46 h), nie godzina GPU.

| | V6.4 | V6.10 |
| --- | --- | --- |
| artefakt | `submission-v6.zip`, `aaea34e4…`, 13 455 B | `submission-v6.10.zip`, **`523d43fb…`, 14 385 B** |
| prompt | 17 888 znaków (kopia) | **22 501 znaków** (limit packera 24 000) |
| lokalizator | ręczne stałe, plik `/tmp` | stałe z wyszukiwania, uruchamiany bezpośrednio (bez pliku scratch) |
| reguły | M1–M4 | M1–M4 + 7 reguł kontraktu (odrzucenie przez sufit, komentarze, wymyślone zakresy linii, `write_file` poza repo, `tox.ini`, „dokończ zgłoszenie") |

## Pre-registracja oczekiwań

| # | predykcja | V6.4 | próg |
| --- | --- | --- | --- |
| R1 | rozwiązane | 10/30 | **≥ 13** (kandydat musi być wyraźnie lepszy niż suma pojedynczych ramion, inaczej kombinacja się nie broni) |
| R2 | odrzucone zapisy poza repo (surowy ślad) | 9 | **0** |
| R3 | puste drzewa | 11 | **≤ 5** |
| R4 | bramki jakości G1, G3 | 0, 0 | **0, 0** |
| R5 | ranga złota w surowych śladach (mediana) | jak V6.4 | **lepsza o ≥ 2 pozycje** |

## Czego V6.10 NIE twierdzi

- Nie jest zmierzony; to jedno z ramion sobotniego resetu.
- Trzy dźwignie naraz: jeśli przebieg wypadnie słabo, nie wiadomo która zaszkodziła (dlatego
  ramiona jedno-ramienne V6.7 i V6.8 są w tym samym planie).
- Próg R1 = 13/30 jest **wyższy** niż dla pojedynczych ramion celowo: kandydat ma zarabiać na
  kombinacji, a nie tylko jej nie psuć.
