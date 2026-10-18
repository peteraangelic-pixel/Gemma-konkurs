# Pomiar, który potrafi przegrać z własnym szumem — czego nauczyły gałęzie Pokemon

**Data:** 2026-10-17. Przejrzane: `arena/a450b00f-pokemon` (659 commitów) i `arena/c87f7a48-pokemon`
(264 commity) w `peteraangelic-pixel/Pokemon`. Nie kopiujemy kodu — kopiujemy rygor pomiaru.

## Co tam znaleźliśmy, w ich własnych liczbach

1. **Twierdzenie na małej próbce nie replikuje się.** Ich `v58b`: „0,40 vs Shaun @30 g" → **0,255 @600 g**
   (baseline 0,213). To nie była pomyłka w kodzie, to był szum 30 gier. U nas to samo: ekran 30 zadań
   obiecuje 0,33, oficjalnie wychodzi 0,10–0,13.
2. **Cudza tabela wyników może być artefaktem harnessu.** Spór o ligę c87: ich 300 gier dało
   „v71 0,533 vs v67", trzy niezależne replikacje po 1200 gier dały **0,462 / 0,491 (pooled 0,477)** —
   czyli v71 jest *gorsza*. Wniosek zapisany u nich wprost: „tabela ligi to artefakt ich harnessu".
   U nas odpowiednik: nasz ekran i oficjalny LB to dwa różne harnessy i **nie wolno ich mieszać**.
3. **Twarde żądania benchu** (`BENCH_V2_HARD_REQUESTS.md`, dosłownie):
   - „Selekcja na szumie H2H — żadnej decyzji <10-20k gier per matchup, CI nie punkt."
   - „Parowanie seedów — te same seedy per (our, opp, game_idx)."
   - „Pula ważona pool-v3 — ważona live-meta, wersjonowana, nie mieszać maszyn."
4. **Hard bench bije regresję.** Ich commit: „hard bench overrides regress" — jeśli twardy test mówi
   „nie", miękki wskaźnik nie ratuje paczki. Decyzja: „not submittable".
5. **Forensyka porażek zamiast zgadywania.** `analyze_live_losses.py` czyta *tylko własne* wpisy z
   replayów (bo mieszanie siedzeń psuje statystyki końcowe), klasyfikuje przyczynę przegranej i
   pokazuje, które matche są naprawdę psute, a które są szumem („SPREAD to szum (lokalnie 0,99)").
6. **Zbieżna diagnoza dwóch niezależnych gałęzi = sygnał.** Obie doszły do „Kyo4 wallfix"
   niezależnie — to podniosło zaufanie bardziej niż jakikolwiek pojedynczy wynik.

## Co z tego wchodzi do naszego projektu (i co już weszło)

| zasada | u nas | stan |
| --- | --- | --- |
| CI, nigdy punkt | każdy ekran raportuje `score_ci95_wilson`; w analizach piszemy przedział, nie liczbę | ✅ od V7-b |
| parowanie | ten sam `seed` i **te same `task_ids`** dla porównywanych wariantów (`--task-ids`) | ✅ istnieje |
| brak decyzji na małej próbce | próg: zmiana musi być > szerokości CI albo mierzymy więcej | ✅ zapisane w `GATES_V7_B.md` |
| twardy test bije miękki | `G-holdout` dla LoRA; holdout repo dla ekranu | ⚠️ w trakcie |
| forensyka porażek | 30 zadań V7-c sklasyfikowane (patrz niżej) | ✅ pierwszy przebieg |
| pula ważona, nie mieszanie maszyn | jeden harness, jeden seed, jedna paczka na przebieg | ✅ |

## Forensyka V7-c — pierwszy wynik tej metody

30 zadań, 10 rozwiązanych. Pozostałe 20 w trzech kategoriach:

| kategoria | ile | co to znaczy |
| --- | --- | --- |
| **`edited_gold_file_no_fix`** | **13** | agent trafił w plik, który naprawia błąd, i napisał patch, który nie naprawia. Wszystkie z `test_exit_code` 1–2. |
| `empty_tree` | 6 | zero edycji = gwarantowane zero |
| `wrong_file` | 1 | patch w plik spoza złotego zestawu |

To jest najważniejsza liczba w całym projekcie: **13 z 20 porażek to „wiem gdzie, nie umiem naprawić"**.
Do tego z trajektorii V6.4: **6/30 sesji kończy się edycją, po której nie następuje już żadna komenda**
— czyli agent nie sprawdza, czy jego własna zmiana cokolwiek naprawiła.

Wniosek: następna dźwignia to nie lokalizacja i nie zegar, tylko **pętla: napisz → uruchom test →
przeczytaj błąd → popraw**. I musi być mierzona na tych samych zadaniach (parowanie), z CI.

## Co to znaczy dla kolejnych decyzji

- **Ekran musi być tańszy**, inaczej nie zbierzemy n na parowane porównanie: `concurrency`
  (jeden serwer vLLM obsługuje wszystkie sesje) + holdout całych repozytoriów
  (`--exclude-repos`), żeby mierzyć transfer, a nie pamięć promptu.
- **Żadnej decyzji o wysyłce na różnicy mniejszej niż CI.** 0,08/0,10/0,13 to jedna liczba;
  następna paczka idzie na slot tylko wtedy, gdy ekran pokaże różnicę większą niż jego własny
  przedział.
- **Porażki klasyfikujemy zawsze**, zanim zmienimy cokolwiek w prompcie — inaczej „poprawiamy" to,
  co nie jest zepsute (jak zegar w V7-c).

## Drugi pomiar tej samej metody: co odróżnia sesję rozwiązaną od przegranej (V6.4, 30 zadań)

Te same 30 zadań, dla których mamy pełne trajektorie (`kaggle_results/v6-4-benchmark/traces/`).
Pytanie: czy po edycji agent sprawdził, co zrobił?

| stan po ostatniej edycji | rozwiązane | przegrane |
| --- | ---: | ---: |
| **po edycji uruchomił cokolwiek** | **10** | 10 |
| edycja i ani jednej komendy po niej | **0** | 6 |
| żadnej edycji w pliku źródłowym | **0** | 4 |

To nie jest dowód przyczynowy (sesja, która ma dobry pomysł, częściej go też sprawdza), ale jest to
jedyne miejsce w naszych danych, gdzie jedna obserwowalna czynność dzieli zbiór na 50 % i 0 %.
Dlatego V8 nie dokłada wiedzy o repozytoriach — dokłada **obowiązek uruchomienia własnej zmiany**
i poprawienia tego, co pokaże. Bramki: `GATES_V8.md`.

Trzecia liczba z tej samej tabeli: **3/30 pierwszych zapisów trafiło w plik, który grader wyrzuca**
(`pyproject.toml`, `docs/en/...md`, `tox.ini`) — dwa z nich skończyły się pustym drzewem mimo
potwierdzonej edycji. To nie jest problem rozumowania, to problem celu; w V8 jest osobne zdanie,
że diff confined to tests/config/docs nie jest fixem.
