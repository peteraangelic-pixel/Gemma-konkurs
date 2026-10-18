# V8 — pętla weryfikacji NIE pomaga; ekran jest teraz 2,8× tańszy (2026-10-18)

Uruchomienie: kernel `petersharps/gemma-agent-benchmark-c32a37dc-20261018-120239`, start 12:02 UTC,
koniec 13:04 UTC. Archiwum `c32a37dc…` = V5 bajt w bajt (budżet 150 s / 45 wywołań / 80 tur /
5,25 min, sampling, model, narzędzia) **plus jedna zmiana**: krok 5 promptu wymaga uruchomienia
własnej zmiany i poprawienia tego, co pokaże; krok 4 zakazuje kończenia na edycji pliku, który grader
wyrzuca. Te same 30 zadań, ten sam seed, porównanie parowane z V5/V7-c (10/30).

## Wynik: 9/30, netto −1

| bramka (`GATES_V8.md`) | próg | zmierzone | werdykt |
| --- | --- | --- | --- |
| **V1 wygrana** | ≥ 13/30 | **9/30** (0,30) | ❌ |
| **V2 pary niezgodne** | netto ≥ +4 | **−1** (1 wygrana, 2 przegrane) | ❌ |
| **V3 puste drzewa** | < 6/30 | **11/30** | ❌ |
| **V4 średni czas** | ≤ 330 s | 248,8 s | ✅ |
| **V5 uczciwość** | tylko prompt | tylko `prompts/system.md` | ✅ |

Zmiany statusu: V8 **wygrał** `rich_3882` (0 → 503 znaków patcha, 486 s → 106 s) i **przegrał**
`fastapi_14851` oraz `rich_3718` — dwa zadania, które V5 rozwiązywało tanio (109 s, 10 wywołań),
a V8 przepalił do 276 s i zegara.

## Dlaczego przegrał — mechanizm widać w czasach

**Czternaście z 30 zadań V8 stanęło na 313–326 s**, czyli dokładnie na zegarze 5,25 min (315 s + narzut).
U V5 takich sesji było 3/30. Pętla weryfikacji zużyła budżet, którego nie było: dopisanie repro,
uruchomienie go, przeczytanie błędu i druga poprawka to 4–6 dodatkowych wywołań przy średniej 21,
a sesja i tak kończy się na zegarze, nie na limicie wywołań. Puste drzewa wzrosły z 6 do 11, bo
sesja, która w V5 zdążyłaby coś zapisać, w V8 kończyła się w środku własnej weryfikacji.

To jest ta sama lekcja, którą dał V6.12 (0,08 przy 244 linijkach promptu) i V7-c (8 minut zegara
kupuje +28 s i zero rozwiązań), tylko tym razem zmierzona na parowanych zadaniach: **model jest na
granicy budżetu, a nie na granicy wiedzy**. Każda instrukcja, która dodaje pracę bez skracania
poszukiwań, oddaje zadania zegarowi.

## Co ten przebieg jednak udowodnił: concurrency działa

| miara | wartość |
| --- | --- |
| suma czasów zadań | 7 464 s |
| wall clock całego przebiegu | **2 651 s** |
| przeplot | **2,8×** |
| concurrency w wyniku | 3 |

Po poprawce `gather` (i po teście na CPU, który sprawdza semafor, zachowanie wiersza błędu
i zapis po każdym zadaniu) 30 zadań trwa **44 min zamiast ~2,1 h**. To jest realna naprawa pomiaru:
od dziś ekran 30 zadań kosztuje ~1,5 h kwoty, a nie ~4,2 h.

Sam przeplot nie zmienia werdyktów: przy **tym samym archiwum** trzy przebiegi (2 seryjne, 1 z flagą
concurrency 3) dały 5/12 i 12/12 identycznych werdyktów per zadanie. Podzbiór kontrolny tego
przebiegu to **3/12**, ale to jest efekt promptu V8, nie batchingu — i to on jest częścią wyniku,
a nie artefaktem pomiaru.

## Decyzja

- **V8 nie jedzie na slot.** Archiwum zostaje w repo jako zmierzone i odrzucone (`submission-v8.zip`,
  sha `c32a37dc…`), z liczbami w `GATES_V8.md`.
- **V5 (0,13) pozostaje jedynym kandydatem.** Żadna z pięciu prób (V6.12, V7-b, V7-c, V8, zegar)
  nie pobiła go poza szumem; trzy z nich były gorsze, a żadna różnica nie przekroczyła ±9 pp.
- **Wniosek na przyszłość:** dopóki budżet per zadanie zostaje na 5,25 min, każda zmiana promptu musi
  **skracać** pracę, nie dodawać. Kandydaci, którzy dodają kroki (pętla, locator, analiza), muszą
  iść w parze z podniesieniem zegara — a to jest osobna dźwignia, której V7-c nie uzasadnił.

## Koszt dnia (wall clock kerneli GPU)

| kernel | czas | wynik |
| --- | ---: | --- |
| dud (NameError) | 14 min | 0 |
| ekran 12 zadań, seryjny | 41 min | 5/12 |
| ekran 12 zadań, „concurrency 3" (flaga bez efektu) | 43 min | 5/12 |
| LoRA canary (wystrzelony przypadkiem przez `git add -A`) | 31 min | error |
| **V8, 30 zadań, concurrency 3** | **62 min** | **9/30** |
| razem | **~3,2 h** | |
