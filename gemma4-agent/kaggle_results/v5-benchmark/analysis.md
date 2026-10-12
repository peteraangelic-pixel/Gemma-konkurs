# Wynik prywatnego screeningu V5 (30 zadań, seed 20261009) — analiza

## Wynik

| miara | V4 | **V5** |
| --- | --- | --- |
| rozwiązane | 11/30 (36.7 %) | **10/30 (33.3 %)** |
| CI95 Wilsona | — | [19.2 %, 51.2 %] |
| średni patch (rozwiązane) | — | 823 znaki |
| średni patch (nierozwiązane z patchem) | — | 2 127 znaków |
| puste patche | 6/30 | 6/30 |
| uderzenia w limit wywołań (45) | 0 (cap 35) | 2 |
| średni czas zadania | — | 233 s (cap 315 s) |

**Werdykt: statystyczny remis z V4, nie poprawa.** Przy n=30 różnica 1 zadania jest szumem —
CI95 sięga od 19 % do 51 %, więc ten test nie odróżni 33 % od 37 %. To narzędzie do diagnozy
mechanizmów, nie do ogłaszania zwycięstw (dokładnie tak, jak przy 0.03: publiczne 11/30 nie
przewidziało ukrytego wyniku).

## Co się faktycznie zmieniło (per zadanie)

Tylko 3 zadania zmieniły status względem V4:

| zadanie | V4 | V5 | przyczyna |
| --- | --- | --- | --- |
| `rich_2725` | ✗ (patch 5 654) | **✓ (patch 1 099)** | minimalna edycja wygrała tam, gdzie wielka przegrała |
| `fastapi_14873` | ✓ (patch 1 681) | ✗ (**pusty**) | sesja zginęła bez edycji |
| `fastapi_14851` | ✓ (pusty patch — anomalia V4) | ✗ (pusty) | jak wyżej |

## Zdiagnozowany mechanizm porażki (6 zer)

Wszystkie 6 pustych patchy miało `exit=-1` (żaden test nie ruszył), czyli **w drzewie nie było
żadnej edycji** — mimo reguły „zawsze `submit_patch()`". Z `HARNESS_README.md` (linie 231–235,
346–361, 569–575) wynika dlaczego to nie jest problem z submisją:

- `submit_patch()` **kończy sesję** (patch łapany w momencie wywołania), więc nie da się „wysłać
  wcześnie i pracować dalej",
- harness ma **fallback**: bez `submit_patch()` i tak wyciąga diff drzewa
  (`git add -N . && git diff HEAD`),
- zatem **jedynym gwarantowanym zerem jest drzewo bez edycji**.

Rozkład pustych sesji: 5 z 6 zginęło na zegarze (298–325 s z 315 s capu), 2 uderzyły w limit
45 wywołań; `rich_3934` miało tylko 7 wywołań, ale 227 s — jedno polecenie (najpewniej
nieograniczony `pytest`) zjadło połowę sesji.

Dodatkowy, mocny sygnał: **wszystkie 10 rozwiązanych patchy było < 1 900 znaków** (9/10 < 1 500),
a patche > 2 000 znaków przegrały **0/6**. V5-owa reguła „minimalna edycja" działa — brakowało
reguły „edycja przede wszystkim".

## Co V6 zmienia z tego powodu (poza lokalizatorem)

1. **Twardy deadline edycji**: do 12. wywołania edycja musi leżeć na dysku, do 18. przestań
   szukać, do 24. co najwyżej jeden krótki test i submisja — plus wprost wyjaśnienie, że
   oceniany jest diff drzewa, nie samo wywołanie `submit_patch()`.
2. **Budżet weryfikacji**: `timeout 45` zamiast `timeout 90`, zakaz ponawiania poleceń, które
   przekroczyły limit, i pomijanie weryfikacji po 24. wywołaniu.
3. **Reguła małego patcha**: „rozwiązane sesje < 1 900 znaków, > 2 000 znaków = 0/6" wpisane
   w instrukcję edycji.
4. **Lokalizator jako pierwszy krok** (1 wywołanie, 0.4 s) zamiast 5–10 grepów — odzyskuje
   zarówno czas, jak i wywołania, czyli dokładnie te dwa zasoby, na których V5 ginęło.

Artefakt V6 po tych zmianach: `submission-v6.zip`, SHA-256 `7344f5d806b086746d45f4a389535494f193d25733721d441f08c6540b75942c`.
Benchmark V6 mierzy ten sam zestaw 30 zadań i ten sam seed, więc wynik jest porównywalny 1:1
z V3/V4/V5.
