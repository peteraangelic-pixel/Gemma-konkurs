# v18-arena — bezpieczna kompozycja kontrolera szablonowego

Zbudowane i zweryfikowane offline 31.10.2026 na gałęzi `codex/arc-local-lab-v18-20261030`
(Smak, commit `3926007`). Nic nie zostało zgłoszone na Kaggle, nic nie wysłano do cudzego repo.

## Co to jest

Jeden zestaw trzech zmian na module kontrolera szablonowego, każda za przełącznikiem
środowiskowym, każda z pomiarem **neutralności domyślnej** (bez zmiennych środowiskowych
zachowanie jest identyczne z oryginałem, co do decyzji):

| # | zmiana | przełącznik | po co |
|---|---|---|---|
| 0012 | bramka „dokładnie jedna niezgodna komórka" | `ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH=1` | tnie fałszywe rozpoznania o 94–100 % |
| 0013 | strażnik akcji na poziom (z przezbrojeniem) | `ARC3_TEMPLATE_ACTION_GUARD=32` | ucina nieograniczoną pętlę przy przejściowym efekcie kliknięcia |
| 0014 | bezpieczny hook | `ARC3_TEMPLATE_ENABLED=0` (kill-switch) | idempotentny `install()`, `should_stop` oddany oryginałowi |

## Jak używać

```bash
# 1. zbuduj (podmienia tekstowo, każde trafienie musi być dokładnie jedno)
python3 tools/build_v18.py --analysis /ścieżka/arc-agi-3/analysis --out build

# 2. sprawdź (7 kontroli, wszystko offline)
python3 tools/verify_v18.py --analysis /ścieżka/arc-agi-3/analysis --build build
```

`verify_v18.py` kończy się kodem 1, jeśli którakolwiek kontrola nie przejdzie.

## Wynik ostatniego przebiegu

`reports/verify-summary.txt` (pełne wyjście), `reports/v18-arena.diff` (102 linie diffu do przeglądu).

```
[1] NEUTRALNOSC DOMYSLNA   ft09: 0 rozbieznosci | 400 plansz syntetycznych: 0 rozbieznosci
[2] BRAMKA                 copy 149/149 -> 149/149 | rotate 299/18 -> 17/3
                           invert 300/0 -> 0 | random 297/23 -> 8/1
[3] STRAZNIK               bez limitu 120 akcji/240 klatek | limit 32: 32 akcje
                           przezbrojenie po zmianie poziomu: OK
[4] HOOK                   idempotent True | dziala na ft09 True | stop->oryginal True | kill-switch True
[7] KOMPATYBILNOSC         z template_guarded.py: 32 akcje, bez podwojnego liczenia
[6] FT09                   domyslnie/bramka/straznik/oba: (6,39,39) (6,23,17) (6,23,7)
WERDYKT: OK
```

Testy modułu po nałożeniu zmian: **37/37** (`test_template_transfer.py` 35 + `test_template_guarded.py` 2),
w tym przy włączonych przełącznikach.

## Czego tu nie ma i dlaczego

**Detektora zmiany mechaniki.** Zmierzone kontrfaktycznie: mapowanie odtworzone z paneli
poziomu 2 to `{0:9, 2:9}`, a z poziomu 3 `{0:8, 2:8}` — w obu przypadkach **sprzeczne** z modelem
przeniesionym z poziomu 1 (`{2:9, 0:8}`), który dał poprawne akcje `(6,23,17)` i `(6,23,7)`.
Detektor „odrzuć `learned`, gdy bieżąca klatka daje inne mapowanie" **abstyniowałby na obu tych
poziomach**, czyli zamienił 3 ukończone poziomy ft09 na 1 (28,57 → 4,76). Pomysł z mojego
raportu z 31.10 został tym samym odrzucony przez pomiar — nie przez opinię.

**Zmian w `final_score`, transkryptach i scoringu** — v18 nie dotyka niczego poza decyzjami kontrolera.

## Znany konflikt, który ta wersja rozwiązuje

Podklasa `GuardedTemplateTransfer` (peer, `template_guarded.py`) liczy akcje we własnym polu
`level_actions`. Strażnik w klasie bazowej pod tą samą nazwą liczyłby każdą akcję dwa razy i cap 32
zjeżdżałby do 16 — zmierzone. Dlatego pola v18 nazywają się `_arm_*`; kontrola `[7]` pilnuje, że
nałożenie obu strażników daje nadal 32 akcje.
