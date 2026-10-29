# local-lab — ARC-AGI-3 na własnym sprzęcie

Lokalny silnik + dokładna punktacja + analiza runów + wyszukiwanie deterministyczne.
Powstało 29.10.2026 po runie na 23 pkt. Wnioski: **[`PLAN-50.md`](PLAN-50.md)** (czytaj to
najpierw), liczby i tabele: `analyze_run.py`, `verify_scoring.py`, `results/`.

## Co tu jest i po co

| plik | rola | stan |
|---|---|---|
| `lab/engine.py` | bootstrap silnika, `Session` po `game.perform_action`, **dokładna** formuła punktów (taaf + `scorecard` v0.9.8) | 32/32 zapisanych runów odtworzone |
| `lab/fastclone.py` | snapshoty stanu gry: 0,5–8,6 ms zamiast 19 ms, z **samoweryfikacją** per gra | 20/20 gier bit-identyczne z pełnym deepcopy |
| `lab/search.py` | BFS po akcjach, kalibracja klików (efekt, nie piksel), centra blobów, budżety | patrz `results/` |
| `run_lab.py` | sweep po grach na `multiprocessing` (14 workerów = 14 rdzeni) | działa |
| `analyze_run.py` | `benchmark.json` → tabela per gra, rozkład strat, tabela marginalna, projekcja budżetu | to narzędzie odpowiada „dlaczego 23" |
| `verify_scoring.py` | regresja punktacji na zapisanych runach | 32/32 |
| `test_lab.py` | 10 testów (punktacja + silnik), bez pytest | OK |
| `worker.py` | jedna gra → JSON (jednostka pracy dla Rusta) | działa |
| `rust/arc3lab/` | `score` / `alloc` / `sweep` na Rayon | **źródło, niekompilowane tutaj** (brak toolchaina w sandboxie) |

## Uruchomienie

```bash
python3 -m pip install arcengine arc-agi          # lub ARC3_ENGINE_PATHS=<dir z arc_agi>:<dir z arcengine>
export ARC3_GAMES=~/smak/arc-agi-3/games/environment_files

python3 verify_scoring.py                          # 32/32
python3 test_lab.py                                # 10 testów
python3 analyze_run.py ~/r116/benchmark.json --target 50
python3 run_lab.py --games all --levels 3 --nodes 4000 --time-s 120 --workers 14
python3 worker.py --game cn04 --levels 2            # jedna gra, jedna linia JSON
```

## Zmierzone fakty o silniku (sandbox: 2 rdzenie, 3 GB)

- krok: **0,07–2,9 ms**; reset: **0,4–7 ms**; `deepcopy(game)`: **19 ms** → 0,5–8,6 ms po kalibracji
- `wrapper.step()` jest 3–5× droższy od `game.perform_action()` i **dopisuje każdą klatkę do
  historii** (pamięć rośnie bez końca w długim searchu) → sesja chodzi po `_game`
- `GameAction(1)` rzuca `ValueError` (to zwykły `Enum`); id akcji z `available_actions` trzeba
  mapować po wartości — `lab/fastclone.action_enum`
- `fd.frame` to **lista** klatek (animacje); hashować trzeba **ostatnią** + licznik poziomów,
  inaczej ten sam stan haszuje się różnie i deduplikacja przestaje działać
- dzielenie stanu między kopie nie zawsze jest bezpieczne: ls20 mutuje `_clean_levels`,
  więc polityka jest **kalibrowana per gra** i tylko wtedy, gdy jest bit-identyczna

## Czego to nie robi

- Nie rozwiązuje ukrytych gier: 110 gier ocenianych nie ma w notebooku, więc nic nie da się
  „precomputować". Search działa w czasie gry i to on jest produktem, nie jego wynik.
- Nie zastępuje rerunów: `n_passes > 1` jest niedozwolone w bramie konkursowej, tylko lokalnie.
- Nie używa luki `(x=None, y=None)` w kamerze — ryzyko DQ.
