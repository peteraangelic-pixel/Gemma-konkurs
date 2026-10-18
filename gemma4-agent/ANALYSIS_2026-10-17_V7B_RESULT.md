# V7-b = 0,10 — i to nie jest osobny wynik, to ten sam wynik co 0,13 i 0,08

**Data:** 2026-10-17 · ref `57290417` (V7b), `SubmissionStatus.COMPLETE`, public **0,10**.

## Wynik

| submisja | ref | public | rozwiązane zadania (z 58) |
| --- | --- | --- | --- |
| V4 | 57045226 | 0,03 | ~1,7 |
| V6.12 | 57247888 | 0,08 | ~4,6 |
| **V7-b** | **57290417** | **0,10** | **~5,8** |
| V5 | 57188055 | 0,13 | ~7,5 |

V7-b spadł o **1,7 zadania** względem V5. Przy 58 zadaniach publicznych jedno zadanie = 1,7 punktu.

## Dlaczego to nie jest „regresja", tylko szum

Przedział ufności 95 % dla proporcji przy n = 58:

| wynik | 95 % CI |
| --- | --- |
| 0,08 | [0,01 – 0,15] |
| 0,10 | [0,02 – 0,18] |
| 0,13 | [0,04 – 0,22] |

Wszystkie trzy przedziały zawierają się wzajemnie. **Trzy ostatnie submisje to statystycznie jedna
liczba** — nie da się z nich odczytać, czy jakakolwiek zmiana w prompcie pomogła, zaszkodziła, czy
nic nie zrobiła. Pre-registrowana drabinka (`GATES_V7_B.md`) zakładała rozdzielczość ±0,02, której
ten przyrząd nie ma.

Wniosek operacyjny: **każda kolejna „jedna dźwignia w prompcie" to spalanie slotu na pomiar szumu.**
Dwie z trzech ostatnich paczek (V6.12, V7-b) różniły się od V5 o jeden akapit i obie wylądowały
w paśmie V5.

## Co naprawdę jest nie tak — trzy liczby

1. **Ekran nie przewiduje oficjalnego wyniku.** Ekran V5: 10/30 = 0,33. Oficjalnie: 0,10–0,13.
   Rozjazd 2,5–3×. Ekran losuje z tych samych czterech publicznych repozytoriów, na których pisany
   był prompt; oceniany zbiór to prywatne repozytoria. Ekran mierzy transfer tam, gdzie go nie ma.
2. **Zadania nie giną na zegarze, tylko na decyzji.** W V7-c 7/30 sesji dało puste drzewo, ale
   mediana czasu **pustych** to 388 s, a **z łatką** 241 s — puste trwają *dłużej*. Cztery z siedmiu
   skończyły się długo przed limitem. Zegar (V7-c: 8 min) nie był ograniczeniem i nie pomógł.
3. **Odnalezienie pliku już działa, zawodzi sama poprawka.** Z 23 sesji, które w ogóle coś napisały,
   13 nie przeszło testu, ale **12 z tych 13 trafiło dokładnie w złoty plik**. Mamy lokalizację, nie
   mamy działającej naprawy.

## Co z tego wynika

- Dźwignie do przełączenia to **jakość poprawki** (weryfikacja po edycji: uruchom test, przeczytaj
  błąd, popraw) i **dopasowanie modelu** (LoRA — dziś udowodnione, że montuje się w harnessie), a nie
  kolejne zdania w prompcie.
- Pomiar trzeba naprawić, zanim wydamy kolejny slot: **holdout całych repozytoriów** (leave-one-repo-out)
  zamiast losowania zadań z tych samych czterech repo.
- Kwota: ekran 30 zadań z `--concurrency 3` to ~1–1,5 h zamiast ~10 h, czyli 3–4 warianty do
  przetestowania w tym, co zostało.

## Czego NIE wolno wyciągnąć z 0,10

Nie wolno powiedzieć „zdanie o pustym drzewie zaszkodziło" — 1,7 zadania to poniżej rozdzielczości
przyrządu. Nie wolno też mówić „V5 = 0,13" — to górna krawędź szumu; uczciwa ocena naszej pozycji to
**~0,10–0,11**, czyli tuż pod medianą tablicy (mediana 0,13, p25 0,08, p75 0,17, 2 240 z 3 084
zespołów ma ≥ 0,10).
