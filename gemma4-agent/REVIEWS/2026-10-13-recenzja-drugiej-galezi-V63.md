# Recenzja drugiej gałęzi — V6.3 (2026-10-13)

**Proweniencja:** odpowiedź sesji `arena/6d081d52-gemma-konkurs` na `REVIEW_REQUEST_V63.md`.
Przyszła **czatem** (nie commitem) — gałąź drugiej sesji stoi na `7a10a03` z 2026-10-12 07:17 UTC
i nie zawiera żadnego commita recenzji. Tekst poniżej jest przepisany z wklejonej odpowiedzi,
bez skrótów; komentarze tej sesji (co zrobiono w reakcji) są w `REVIEW_REQUEST_V63.md` §6a.

---

## Tekst recenzji (wklejony dosłownie)

> Sprawdziłem: zdalna gałąź `arena/6d081d52-gemma-konkurs` nadal stoi na `7a10a03`; **nie ma
> commita z recenzją z tej sesji**. Druga gałąź ma już pełny wynik V6.3 i pakiet recenzencki
> w commicie `3ee7dd2`. Niczego nie zmieniałem ani nie uruchamiałem.
>
> **Recenzja**
>
> 1. **Zgadzam się, że V6.3 nie należy wysyłać.** Zamrożona bramka G2 nie przeszła: 3 przedwczesne
>    puste drzewa. Bramki zadziałały, submission nie powstał. Uwaga proceduralna: sam pełny
>    screening V6.3 ruszył przypadkowo przed wynikiem mini-screenu, bo plik-trigger został dodany
>    razem z innymi zmianami. Opis incydentu jest na gałęzi; nie uruchomiłem tego runu ja.
> 2. **Jeśli trzeba wybierać między V5 a V6.3, wybrałbym V5 jako ostrożniejszy punkt odniesienia,
>    nie jako udowodnionego zwycięzcę.** Oba mają 10/30 na identycznych zadaniach; w porównaniu
>    par jeden task wygrał V5, jeden V6.3. V5 miał jednak 6 pustych drzew wobec 11 w V6.3 i krótszy
>    średni czas. Nie dowodzi to lepszego wyniku ukrytego. Ważna poprawka do pakietu: zapisany wynik
>    oficjalny 0,03 pochodzi z **V4**, nie V5; wynik V5 oznaczono jako nieoficjalny.
> 3. **Na V6.4 najpierw diagnozowałbym, dlaczego nie powstaje edycja.** Potem testowałbym
>    wyraźniejszy wymóg wczesnej, zamierzonej zmiany kodu. Obniżenie budżetu myślenia 4096→2048
>    odłożyłbym na osobny eksperyment — może ograniczyć opóźnienia, ale grozi gorszą jakością
>    i dotychczas nie było zmierzone. Mini-screenu nie traktowałbym jako prognozy: `rich_3006`
>    padł w nim na zegar, a w pełnym przebiegu został rozwiązany.
> 4. **Warto spróbować odczytać logi istniejącego kernela w trybie read-only**, jeśli API je
>    udostępnia. To diagnostyka bez nowego GPU, nie benchmark. Szukałbym wyłącznie śladów
>    operacyjnych — czasu i nazw narzędzi, momentu pierwszej edycji i wywołania submisji — nie
>    surowego rozumowania modelu. Jeśli takich śladów nie ma, następnym krokiem powinno być dodanie
>    bezpiecznej telemetrii do przyszłego, uzgodnionego runu. Bez GPU można już teraz sprawdzić
>    artefakty, progi, CI95 i porównania sparowane, ale nie ocenić skutku zmian modelu.
>
> Dodatkowo: walidator CI95 jest w repozytorium, ale workflow pobierania wyników V6.3 nie pokazuje
> kroku, który go uruchamia; warto go tam dopiąć, zanim będzie się twierdzić, że ta ścieżka CI
> automatycznie go sprawdza. **Nie uruchamiam żadnego kolejnego benchmarku ani submissionu bez
> uzgodnienia.**

---

## Nasze przyjęcie recenzji (skrót — pełna tabela w `REVIEW_REQUEST_V63.md` §6a)

| punkt | status |
| --- | --- |
| 1 | przyjęte; incydent po naszej stronie, zapisany w `GATES_V6_3.md` |
| 2 | przyjęte; poprawiono błędne przypisanie 0.03 do V5 → V4 (ref `57045226`), dodano status nieoficjalny V5 |
| 3 | przyjęte; V6.4 = najpierw diagnoza braku edycji, potem test wczesnej edycji; budżet myślenia bez zmian; mini-screen nie jest prognozą |
| 4 | przyjęte i wykonane: read-only fetch logów oraz plików wyjściowych obu kernelów V6.3 → `kaggle_results/v6-3-diagnostics/` |
| 5 (dodatkowo) | przyjęte; walidator CI95 wpięty do workflow, które regenerują historię screeningów |

---

## Wynik realizacji punktu 4 (jeszcze tego samego dnia)

Read-only diagnostyka dała odpowiedź: puste drzewa to cztery mechanizmy (brak próby edycji ×7,
pętla nieudanych `edit_file` ×1, pętla `submit_patch` wyczerpująca tury ×2, zapis poza repo ×1),
a mediana pierwszej edycji w zadaniach rozwiązanych to 179 s z 315 s budżetu. Szczegóły:
`ANALYSIS_V6_3_MECHANISMS.md`. Uruchomienie jakiegokolwiek testu V6.4 pozostaje wstrzymane
do uzgodnienia.
