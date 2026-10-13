# V6.5 — bramki i pre-registracja (zamrożone **przed** jakimkolwiek przebiegiem)

Stan na 2026-10-13 ~13:00 UTC. V6.5 **nie został uruchomiony**; powstaje, gdy równolegle trwa
informacyjny przebieg V6.4 na 30 zadaniach (`38397663860`).

## Czym V6.5 jest, a czym nie jest

**V6.5 = V6.4 + jedna dźwignia.** Wszystkie reguły M1-M4, brak narzędzia `submit_patch`, termin
call 4 z zakazem atrapy, sampling, limity i lokalizator — **bez zmian**. Zmienia się wyłącznie
**framing decyzji o pierwszej edycji**.

| | V6.4 | V6.5 |
| --- | --- | --- |
| artefakt | `submission-v6.zip`, `aaea34e4…`, 13 455 B | `submission-v6.5.zip`, `cb847599…`, 13 782 B |
| prompt | 19 310 znaków | 20 221 znaków |
| różnica w treści | — | dwa zdania: pozwolenie + granica intencja/dokładność, plus dowód z V6.4 |

## Dlaczego ta dźwignia (dowód, nie intuicja)

Mini-screen V6.4 dał twarde liczby:

1. **Termin „edytuj do call 4" był w prompcie i został zignorowany w 6/6 zadań** — edycja w repo
   w terminie: **0/6**, mediana na wywołaniu **7** (baseline dla tych zadań: 8). Kolejne zdanie
   o terminie nic nie zmieniło, więc samo „przypominanie" nie jest dźwignią.
2. **Trzy sesje kończyły puste, żadna nie z powodu zegara**:
   `rich_3105` 15 × `run_command` w 107 s i **koniec z własnej woli** (limit 315 s),
   `rich_3043` 322,7 s, `fastapi_15745` 10 × `read_file` jednego pliku w 336,7 s.
3. **Każda sesja, która edytowała, zostawiła patch** (`fastapi_15030` 1348 B, `requests_6757`
   377 B, `fastapi_14077` PASS) — czyli problemem nie jest jakość edycji, tylko jej brak.
4. Hipoteza: sesje czekają z edycją, aż będą pewne. Prompt wzmacniał to zakazem („never create a
   dummy edit"), a pozwolenie było podrzędne. V6.5 odwraca proporcję: **pierwsza edycja ma powstać
   nawet bez pewności**, a granica między edycją zamierzoną a atrapą jest nazwana wprost
   („intent, not accuracy").

## Dźwignie rozważone i **odrzucone** (z zapisanym powodem)

| pomysł | dlaczego odrzucony |
| --- | --- |
| skrócenie `evaluation.timeout_seconds` (150 → 45-60 s) | na 30 zadaniach V6.3 puste drzewa mają średnio 1,55 luk >30 s, zadania z patchem 0,84, a maksymalne luki są niemal identyczne (48,8 s vs 46,3 s) — sygnał za słaby, żeby na nim budować |
| usunięcie `run_command` („wymusi edycję") | nie wymusi: model nadal może czytać pliki bez końca (`fastapi_15745` zrobił 10 czytań, 0 komend mu nie brakowało), a tracimy lokalizator i weryfikację |
| obniżenie `max_tool_calls` (30 → 14-18) | nie zamienia zera w edycję — sesja, która nie edytuje przy 30 wywołaniach, nie edytuje i przy 14; oszczędza tylko GPU |
| obniżenie `thinking_budget` 4096 → 2048 | odrzucone wcześniej (recenzja: nie łączyć z inną zmianą), a bez thinkingu ablation kolegi spadł o ~22 punkty |

## Strażniki artefaktu (7 kontrolek negatywnych, wszystkie wywalają build)

1. usunięcie klauzuli pozwolenia;
2. usunięcie granicy „intent, not accuracy";
3. zastąpienie granicy tekstem czekania na pewność („wait until you are sure");
4. usunięcie dowodu „15 `run_command` calls in 107 s";
5. usunięcie dowodu „336.7 s";
6. usunięcie **dziedziczonej** reguły M2 (każdy strażnik V6.4 działa na V6.5);
7. **tekst V6.5 w archiwum V6.4** — wersje nie mogą się wymieszać (i odwrotnie).

Dodatkowo: build deterministyczny (dwa buildy = jeden hash), a V6.4 po zmianach generatora nadal
daje `aaea34e4…` (sprawdzone regresyjnie).

## Plan przebiegu i reguły decyzyjne (zamrożone)

**Krok 1 — mini-screen V6.5 na tych samych 6 zadaniach** (`rich_3105`, `rich_3043`,
`fastapi_15030`, `requests_6757`, `fastapi_15745`, `fastapi_14077`), seed `20261009`, outdir
`v6-5-miniscreen`, archiwum `submission-v6.5.zip`. Porównanie **parami** z V6.4 (te same zadania,
ten sam kernel-shape). Uruchomienie wymaga Twojej zgody i wolnego slotu L4x4 (dziś: 2/2 użyte).

**Kryteria (falsyfikowalne, zapisane przed przebiegiem):**

- **Q1**: ≥ **4/6** zadań ma edycję **w repo** (baseline V6.4: 3/6).
- **Q2**: puste drzewa ≤ **1/6** (baseline V6.4: 3/6; cel: `rich_3105`/`rich_3043`/`fastapi_15745`
  któraś zaczyna edytować).
- **Q3**: brak regresji — `fastapi_14077` nadal rozwiązany i `fastapi_15030`/`requests_6757` nadal
  zostawiają patch (baseline V6.4: 1348 B i 377 B).
- **Q4**: G1 = G2 = G3 = 0 (twarde bramki jakości, definicje jak w `GATES_V6_4.md`).
- **Falsyfikacja**: jeśli Q2 nie spadnie (puste drzewa ≥ 2/6), to **framing decyzji nie jest
  dźwignią** i następny krok musi być **architektoniczny lub parametryczny**, nie tekstowy —
  konkretnie: przebudowa kolejności ról w sesji (np. lokalizator → obowiązkowa edycja → weryfikacja
  wymuszona strukturą promptu i budżetem) albo zmiana budżetu wywołań, testowane jako osobne ramię.
- **E5 obowiązuje**: mini-screen nie jest prognozą wyniku.

**Krok 2 — pełny przebieg 30 zadań** startuje tylko wtedy, gdy Q1-Q4 są spełnione; wtedy
porównanie z V6.3/V6.4 na tych samych 30 zadaniach i decyzja o submissji wg reguły z
`GATES_V6_4.md` (G1-G3 = 0 w **obu** przebiegach ∧ ≥9/30 ∧ wolny slot ∧ Twoja zgoda).

**V6.5 nie ma submittera** — zgodnie z regułą z V6.4 powstanie on dopiero w commicie z decyzją
o wysłaniu, z pinem `cb847599…`, żeby nie dało się wysłać niczego przypadkiem.
