# ARC-AGI-3 (Smak-Domu)

> **Punkt wejścia dla innych gałęzi: [`STATUS.md`](STATUS.md)** — stan na commit `0ef2465`,
> łącznie z listą rzeczy, których ta sesja **nie** zweryfikowała.



| katalog | co to jest |
|---|---|
| `local-lab/` | nasze lokalne narzędzia: silnik, playbook (14/14), audyty runów (`analyze_run.py`), symulator pamięci win-path, audyt eskalacji. Nic z tego nie idzie na Kaggle. |
| `duck-v14/` | pakiet z `duck-v13-2`: eskalacja 20 + dwie sondy + guard (bez opener-hinta). Wariant zapasowy, gdyby batch okazał się ślepy. |
| `duck-v15/` | `duck-v13-3-arena` (opener-hint + log replayu) + eskalacja 20 + obie sondy. 7 patchy. |
| `duck-v16/` | **najlepszy pakiet**: `duck-v13-4-unified` (8 patchy: hint + log + eskalacja relatywna) **+ patch 0009 self-pace** (eskalacja na własnym tempie — działa w rerunie, gdzie ludzki baseline jest `None`) **+ sonda pokrycia**. `README.md` w środku. |

Stan wiedzy (liczby, nie opinie):

- playbook 14 poziomów / 9 gier = **2,90** średniej na 25 grach publicznych, 184/184 hashy na prawdziwym silniku;
- pamięć win-path między wpisami rosteru działa mechanicznie (0 tokenów), ale płaci **tylko** gdy roster powtarza bazowe kody gier — stąd sonda rosteru w v14;
- jedyna dźwignia z sufitem >50 to `commit(plan)`: do 40 akcji na turę modelu, ~0,3 s każda zamiast ~12,9 s;
- eskalacja: @10 = 154 nudge'ów na 32 poziomach (15,3% puli, 31/32 przedwczesnych), @20 = 67 (42 z capem), próg relatywny 0008 = 8/0 ale **w rerunie martwy** (baseline `None`), **0009 self-pace = 22/14 i działa w rerunie**;
- `score ≤ 100 × coverage`: dziś pokrycie ~29% → ~29 pkt; do 50 brakuje **+1,1 poziomu na grę**.
