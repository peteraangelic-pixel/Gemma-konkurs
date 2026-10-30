# ARC-AGI-3 (Smak-Domu): dwa katalogi

| katalog | co to jest |
|---|---|
| `local-lab/` | nasze lokalne narzędzia: silnik, playbook (14/14), audyty runów (`analyze_run.py`), symulator pamięci win-path, audyt eskalacji. Nic z tego nie idzie na Kaggle. |
| `duck-v14/` | **gotowy pakiet do submitu**: notebook + patche + playbook, zbudowany z `duck-v13-2` z trzema mierzalnymi poprawkami. `README.md` w środku. |

Stan wiedzy (liczby, nie opinie):

- playbook 14 poziomów / 9 gier = **2,90** średniej na 25 grach publicznych, 184/184 hashy na prawdziwym silniku;
- pamięć win-path między wpisami rosteru działa mechanicznie (0 tokenów), ale płaci **tylko** gdy roster powtarza bazowe kody gier — stąd sonda rosteru w v14;
- jedyna dźwignia z sufitem >50 to `commit(plan)`: do 40 akcji na turę modelu, ~0,3 s każda zamiast ~12,9 s;
- eskalacja (`ESCALATE_ACTIONS`) jest absolutna i przy 10 odpala 154× na 32 poziomach (15,3% puli) — v14 ustawia 20 i mierzy resztę.
