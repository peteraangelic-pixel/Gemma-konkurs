# Dlaczego sesje kończą się bez edycji — diagnoza operacyjna V6.3 (read-only, bez GPU)

**Pytanie recenzenta (2026-10-13):** najpierw diagnoza, dlaczego nie powstaje edycja; dopiero potem
testy. Ten dokument jest tą diagnozą. Wszystko pochodzi z **już zakończonych** kerneli V6.3,
odczytanych przez API Kaggle w trybie tylko-do-odczytu (`kaggle kernels logs`, `kaggle kernels
output`) — bez nowego GPU, bez nowego benchmarku, bez submissji.

## Metoda i materiał

| element | gdzie | rozmiar |
| --- | --- | --- |
| log kernela pełnego przebiegu | `kaggle_results/v6-3-diagnostics/v63-full-excerpt.txt` (ekscerpt operacyjny) | 1799 linii → 514 dopasowań |
| log mini-screenu | `kaggle_results/v6-3-diagnostics/v63-mini-excerpt.txt` | 178 linii → 59 dopasowań |
| ścieżki wykonania per zadanie (30 + 4) | `kaggle_results/v6-3-diagnostics/traces/trace-operations.json` | 34 ścieżki, 0 błędów parsowania |
| spis schematu ścieżek | `kaggle_results/v6-3-diagnostics/traces/trace-schema-census.md` | klucze i typy, **bez tekstu modelu** |
| lista plików wyjściowych kerneli | `kaggle_results/v6-3-diagnostics/outputs-listing.md` | 84 pliki z hashami |

**Ograniczenie etyczne, które sami narzuciliśmy:** recenzent prosił o ślady operacyjne, nie
o surowe rozumowanie. Surowych plików `trace_*.json` (50–177 KB każdy, zawierają pełne odpowiedzi
modelu) **nie wgraliśmy do repozytorium**. Ekstraktor `tools/summarize_agent_traces.py` zapisuje
wyłącznie nazwy narzędzi, czasy, cele wywołań `edit_file`/`write_file` i liczbę fragmentów
tekstowych (bez treści); test na syntetycznej ścieżce potwierdził, że w artefakcie nie ma ani znaku
tekstu modelu.

**Uczciwa uwaga o rozbieżności czasów:** czas w ścieżce to rozpiętość sesji agenta, a
`duration_seconds` w wyniku zadania obejmuje też sandbox i uruchomienie testów — dla 6 zadań różnica
wynosi 26–43 s. Wniosek: sesja kończy się wcześniej, niż kończy się zadanie; próg 315 s dotyczy
całego zadania.

## Cztery różne mechanizmy pustego drzewa (11 zadań)

| mechanizm | zadania | co dokładnie zaszło |
| --- | --- | --- |
| **M1 — brak jakiejkolwiek próby edycji** (7) | `rich_3105` 41 s · `rich_3043` 108 s · `rich_3934` 286 s · `fastapi_14459` 282 s · `fastapi_14851` 304 s · `fastapi_14487` 311 s · `httpx_3672` 293 s | wyłącznie `run_command` i `read_file` (od 9 do 31 zdarzeń). Pięć z siedmiu mieliło cały zegar; dwa skończyły same (41 s i 108 s). Ani razu `edit_file`/`write_file`. |
| **M2 — pętla edycji, która nie zapisuje** (1) | `fastapi_15030` 307 s | **9 wywołań `edit_file` pod rząd** na `fastapi/responses.py` (co ~9 s: 212, 222, 255, 264, 272, 281, 289, 297, 307 s) i diff nadal 0 znaków. Edycje nie trafiały w cel, model ponawiał bez zmiany strategii. |
| **M3 — pętla `submit_patch` zjada budżet tur** (2) | `requests_6757` 210 s · `fastapi_14266` 314 s | `requests_6757`: 48 wywołań `submit_patch` (co ~0,7 s!), pierwsza i jedyna edycja o 102,8 s w `tox.ini`, sesja ubita przez limit 60 tur. `fastapi_14266`: pierwsza edycja dopiero o 297,7 s (4 s przed końcem) + 5 wywołań `submit_patch`. |
| **M4 — zapis poza repozytorium** (1) | `fastapi_15745` 280 s | `write_file` → **`/tmp/locate.py`** o 279,8 s. Agent „tworzył" skrypt lokalizatora zamiast naprawiać zadanie; w drzewie roboczym zero zmian. |

Potwierdzenie z logu harnessu (niezależne od ścieżek): 14 × „agent timed out", 3 × „agent exceeded
**turns budget**" (dokładnie `rich_3894`, `requests_6757`, `fastapi_14077` — wszystkie trzy mają
pętle `submit_patch`: 42, 48, 44 wywołań) i 9 × „completed without explicit submit_patch call and no
working tree modifications".

## Liczby, które ustawiają priorytety V6.4

1. **Pierwsza edycja przychodzi w połowie budżetu.** Mediana dla 10 rozwiązanych zadań: **179 s**
   (min 43 s, max 225 s); dla wszystkich 23 z jakąkolwiek edycją: **185 s**. Przy budżecie 315 s na
   zadanie zostaje ~135 s na edycję → test → poprawkę.
2. **7/30 zadań nigdy nie próbuje edycji.** Puste drzewo = gwarantowane zero punktów, niezależnie
   od jakości analizy. To najdroższa pojedyncza klasa.
3. **Pętla `submit_patch` to zmierzona przyczyna wyczerpania 60 tur** (3 zadania, w tym jedno puste).
   `submit_patch` może być wołany wielokrotnie, a harness tego nie blokuje — model się zapętla.
4. **Sama wczesna edycja nie wystarcza, ale późna kosztuje.** `fastapi_14303` napisał o 37,7 s
   i nie rozwiązał zadania; `rich_3006` napisał dopiero o 233,8 s i **rozwiązał** — więc zależność
   jest statystyczna (n=30), nie deterministyczna. Uczciwie: to korelacja, nie dowód przyczynowy.
5. **`write_file` poza repo i edycje „donikąd" są wykrywalne** — oba przypadki widać w ścieżce po
   samym celu wywołania, więc przyszła telemetria nie musi czytać rozumowania, żeby je złapać.

## Wnioski dla V6.4 (do zatwierdzenia, nic nie zostało uruchomione)

Cztery zmiany, każda przypięta do zmierzonego dowodu powyżej; **budżet myślenia 4096 i limit czasu
45 s pozostają nietknięte** (zgodnie z recenzją — to osobny eksperyment, nie mieszamy zmiennych):

1. **Wymuszony wczesny zapis (M1).** Instrukcja: „jeśli po ~8 wywołaniach nie masz edycji na dysku,
   przestań czytać i zapisz najlepszą hipotezę poprawki; dopracujesz ją potem". Dowód: mediana 179 s
   i 7 zadań bez edycji.
2. **`submit_patch` co najwyżej raz (M3).** „Jeśli `submit_patch` zgłosi brak zmian, nie ponawiaj —
   najpierw zapisz edycję". Dowód: 48/44/42 wywołań i trzy wyczerpane budżety tur.
3. **Reguła upadku edycji (M2).** „Jeśli `edit_file` nie zadziała dwa razy na tym samym pliku,
   przepisz plik przez `write_file` w całości". Dowód: `fastapi_15030`, 9 nieudanych edycji.
4. **Zakaz zapisu poza drzewem repo (M4).** „Nigdy nie zapisuj plików poza katalogiem zadania;
   lokalizator to skrypt do uruchomienia, nie plik do napisania". Dowód: `fastapi_15745`.

Zamrożone bramki G1–G3 zostają bez zmian; **nową metryką mechanizmu (nie bramką wyniku) proponujemy
„udział zadań z jakąkolwiek edycją"** — dziś 23/30, cel ≥ 27/30. Ta metryka nie zastępuje liczby
rozwiązanych zadań i musi być raportowana osobno, tak jak G1–G3.
