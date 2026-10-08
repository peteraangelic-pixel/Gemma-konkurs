# Submission log

Wyniki leaderboardu i logi z Kaggle dopisujemy tutaj po każdym teście użytkownika. Hipoteza powinna być zapisana przed obejrzeniem wyniku.

| Data UTC | Wersja | Co zmieniono | Hipoteza | Wynik |
|---|---|---|---|---|
| 2026-10-08 | v1 MVP | Pierwszy scaffold: root fixer + read-only analyzer, nawigacja po grafie, dwa skills, prompt read→plan→edit→test→submit; bez LoRA/treningu. | Graf i małe patche ograniczą błędy lokalizacji; test celowany przed submission chroni wynik. | Zbudowany ZIP; YAML sparsowany, układ sprawdzony; smoke testy obu skryptów przeszły. Wynik Kaggle oczekuje. |
| 2026-10-08 | v1 spec reconciliation | Po wskazaniu źródeł GitHub sprawdzono `HARNESS_README.md` i `sample_submission` z `origin/main` (`813b3d072b909918a6cee72060b0cc85c1874cf8`). Dodano `eval_config.yaml` (4 min / 35 narzędzi / 60 tur / 180 s komenda), poprawiono `search_similar_code` na zapytania nazwą symbolu, doprecyzowano `get_status` (per-task), resetowanie testów/configów, cache cleanup i `submit_patch()` jako ostatnie narzędzie; sampling dostosowano do przykładowej konfiguracji. | Twardy task-local cap zostawi globalne 12 h na sandbox setup i dalsze zadania; symbol-keyed graph lookup i harness-aware testy zmniejszą jałowe wywołania oraz patch’e odrzucane w Phase 2. | ZIP przeszedł porównanie kontraktu z README/sample, parsowanie YAML i strukturalne sprawdzenie. Skill smoke: 1 pytest test zaliczony, diff validator clean. Pełny `swegemma eval` nieuruchomiony: brak `snapshots/`, runtime package/harnessu, Docker i modelu w dostępnym workspace/GitHub podzbiorze; Kaggle score oczekuje. |

## Kontrakt kolejnych iteracji

- Przed zmianą zapisz hipotezę; zmieniaj jeden główny czynnik naraz, jeśli to możliwe.
- Dopisz datę UTC, pliki/konfigurację, dokładny wynik i decyzję (zachować/cofnąć).
- Zachowuj otrzymane logi walidacji i dokładny komunikat Kaggle; nie przypisuj wyniku zmianie, jeśli w tej samej iteracji zmieniło się kilka niezależnych rzeczy.
