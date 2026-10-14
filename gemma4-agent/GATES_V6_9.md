# V6.9 — bramki i pre-registracja (zamrożone **przed** jakimkolwiek przebiegiem)

Stan na 2026-10-14 ~19:15 UTC. V6.9 **nie został uruchomiony ani wysłany**. Powstał, żeby druga
gałąź miała odpowiednik swojego lokalnego „V6.7" w wersji, którą da się odtworzyć u nas.

## Czym V6.9 jest

**V6.9 = V6.4 + DWA ramiona naraz: framing edycji (V6.5) + inline lokalizator (V6.6).**

To ten sam pomysł, który druga gałąź zbudowała u siebie i nazwała „V6.7". **To nie jest ten sam
plik:** ich `0cd0d2bf…` powstał w ich sesji i nie został wypchnięty do repozytorium (ich tip to
nadal `8eb94cd`), więc nie da się go zweryfikować ani użyć; nasz `c99f3d81…` jest przebudowany
z naszego generatora. Ta sama intencja, inny build — nazwy nie wolno porównywać.

| | V6.4 | V6.9 |
| --- | --- | --- |
| artefakt | `submission-v6.zip`, `aaea34e4…`, 13 455 B | `submission-v6.9.zip`, **`c99f3d81…`, 13 564 B** |
| prompt | 17 888 znaków (kopia) | **20 680 znaków** |
| różnice | — | klauzula framingu (V6.5) + jedno polecenie bez pliku (V6.6, z przerobionym `# Usage`) |

## Znaczenie dla przypisania efektu

Dwa ramiona w jednym przebiegu **nie pozwalają przypisać wyniku** ani V6.5, ani V6.6 osobno.
Dlatego V6.5 i V6.6 mają własne przebiegi jedno-ramienne, a V6.9 jest tylko kandydatem:
różnica `V6.9 − V6.5` = dźwignia V6.6, różnica `V6.9 − V6.6` = dźwignia V6.5, i to jest cała
wartość tego ramienia poza samym wynikiem.

## Pre-registracja oczekiwań

| # | predykcja | V6.4 | próg |
| --- | --- | --- | --- |
| R1 | puste drzewa | 11 | **≤ 6** (suma dźwigni V6.5 + V6.6; każda z osobna obiecuje mniejszą redukcję) |
| R2 | sesje, które napisały plik zamiast edytować repo | 4 | **0** (adresuje V6.6) |
| R3 | bramki jakości G1, G3 | 0, 0 | **0, 0** |
| R4 | rozwiązane | 10/30 | **≥ 11** |

## Czego V6.9 NIE twierdzi

- Nie jest tym samym plikiem co „V6.7" drugiej gałęzi (patrz wyżej).
- Nie przypisuje żadnego z dwóch ramion.
- Nie jest kandydatem do wysyłki: decyzja o wysłaniu zależy od wyników ramion jedno-ramiennych.
