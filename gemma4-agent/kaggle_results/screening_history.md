# Historia screeningów: co każdy wynik zmienił

## Screeningi prywatne (te same 30 zadań i seed 20261009)

| kandydat | rozwiązane | puste patche | śmierci na zegarze (≥315 s) |
| --- | --- | --- | --- |
| V3 | 11/30 | 6/30 | 16/30 |
| V4 | 11/30 | 6/30 | 12/30 |
| V5 | 10/30 | 6/30 | 9/30 |
| V6.1 | 6/30 | 7/30 | 17/30 |

- **V5 = 10/30**, CI95 [19.2 %, 51.2 %] — remis z V4 (11/30); mechanizm porażki: 6 pustych
  diffów, 5 z nich zginęło na zegarze. Analiza: `kaggle_results/v5-benchmark/analysis.md`.
- **V6.1 = 6/30** — regresja wprowadzona przez okablowanie lokalizatora (agent zapisywał
  `issue.txt`/`locate.py` do `/workspace`, więc 9/30 diffów to śmieci, 7 bez żadnej edycji kodu;
  śmierci na zegarze wzrosły do 17/30). Analiza: `kaggle_results/v6-1-benchmark/analysis.md`.
- **V6.2** (w toku) usuwa **wszystkie** zapisy `write_file` (heredoc do `/tmp` + czytanie issue
  ze stdin), dodaje obowiązkowy strażnik `git status --porcelain` przed submisją, obniża limit
  wywołań 45 → 30 i ustawia twarde deadline'y edycji. Artefakt: `submission-v6.zip`,
  SHA-256 `8c1ea5b71a61b4d58a6b023596761abb9af37908af6d0ef441347353a2f860b8`.

**Korekta ważnej hipotezy:** sama śmierć na zegarze (≥315 s) **nie** jest fatalna — V3 miał
16/30 takich sesji i rozwiązał 11/30, bo harness ocenia diff **drzewa roboczego**, także gdy
sesja padnie przed `submit_patch()`. Fatalna jest śmierć **bez użytecznej edycji na dysku**:
V6.1 miał 7 takich zadań („patch" = pliki robocze) i rozwiązał 6/30. Dlatego reguła V6.2 to nie
„mniej czytać", a „**edycja na dysku najpóźniej w 8. wywołaniu**, reszta jest opcjonalna".

Wniosek metodologiczny: **publiczny screening 30 zadań nie przewidzi wyniku na ukrytym zbiorze**
(przy 0.03 mieliśmy 10-11/30), ale z pełną diagnostyką per zadanie niezawodnie wskazuje
mechanizmy porażek — czego Kaggle nie raportuje wcale.
