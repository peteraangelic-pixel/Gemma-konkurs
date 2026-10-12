# Historia screeningów: co każdy wynik zmienił

Te same 30 zadań i seed 20261009 w każdym przebiegu. Kolumny diagnostyczne istnieją tylko
dla przebiegów po dodaniu diagnostyki per zadanie (V6.1, V6.2).

| kandydat | rozwiązane | puste drzewa (zero edycji) | śmierci na zegarze | zadania z plikami-śmieciami | w tym TYLKO śmieci | trafienia lokalizatora | średni czas |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V3 | **11/30** | 6 | 16 | 0 | 0 | — | 261.3 s |
| V4 | **11/30** | 6 | 12 | 0 | 0 | — | 233.8 s |
| V5 | **10/30** | 6 | 9 | 0 | 0 | — | 232.7 s |
| V6.1 | **6/30** | 7 | 17 | 9 | 7 | 15/30 | 275.4 s |
| V6.2 | **9/30** | 8 | 17 | 0 | 0 | 20/30 | 272.4 s |

## Zmiany statusu między kolejnymi kandydatami

- V3 → V4: +0 (—), -0 (—)
- V4 → V5: +1 (rich_2725), -2 (fastapi_14851, fastapi_14873)
- V5 → V6.1: +0 (—), -4 (rich_3043, rich_3518, rich_3882, rich_3894)
- V6.1 → V6.2: +4 (fastapi_14873, rich_3518, rich_3882, rich_3894), -1 (rich_3006)

### V6.1: zadania z plikami-śmieciami w diffie

- wszystkie: rich_3934, rich_3894, rich_3043, fastapi_14873, fastapi_15588, fastapi_14459, fastapi_14262, fastapi_14482, fastapi_15745
- **bez żadnej edycji kodu: rich_3934, rich_3894, fastapi_14873, fastapi_15588, fastapi_14459, fastapi_14482, fastapi_15745**

### V3: puste drzewa (6)

- fastapi_14851, rich_3105, fastapi_14186, requests_6757, fastapi_14262, fastapi_15745

### V4: puste drzewa (6)

- fastapi_14851, rich_3105, fastapi_15030, fastapi_14186, requests_6757, fastapi_15745

### V5: puste drzewa (6)

- rich_3934, fastapi_14851, fastapi_14266, rich_3105, fastapi_14873, fastapi_15745

### V6.1: puste drzewa (7)

- fastapi_14851, fastapi_14266, rich_3518, rich_3105, fastapi_14186, rich_3882, requests_6757

### V6.2: puste drzewa (8)

- rich_3934, fastapi_14851, fastapi_14266, rich_3105, rich_3006, fastapi_14186, requests_6757, fastapi_15745

## Reguły interpretacji (wyuczone na tych przebiegach)

1. **Śmierć na zegarze nie przekreśla zadania** — oceniany jest diff drzewa roboczego, także gdy
   sesja padnie przed `submit_patch()` (dowód: V3 miał 16/30 takich sesji i 11/30 rozwiązanych).
2. **Przekreśla ją brak użytecznej edycji** — V5 (6 pustych drzew) i V6.1 (7 drzew bez edycji kodu,
   bo diff wypełniły pliki robocze) to dwa różne objawy tej samej przyczyny.
3. **Publiczny screening 30 zadań nie przewiduje ukrytego wyniku** (V3/V4/V5: 10–11/30 przy
   oficjalnym 0.03), ale z diagnostyką per zadanie niezawodnie wskazuje mechanizmy porażek.
