#!/usr/bin/env python3
"""Ile kosztuje UZBROJENIE patchu 0010 (dyn-level-budget) — na zapisanych traktach.

Dla każdego capa karmi prawdziwy `LevelBudget.step()` per-akcję (jak solver.py:711)
i liczy trzy rzeczy, których nikt wcześniej nie policzył razem:

  * `utracone poz.`  — poziomy ukończone w trakcie PO punkcie ABANDON. Strata PEWNA.
  * `uwoln. tok`     — tokeny wygenerowane po tym punkcie. Zysk WARUNKOWY.
  * `Δ score (0%)`   — zmiana wyniku przy ZEROWEJ konwersji uwolnionych tokenów
                       (scorer zgodny z harnessem: local-lab/verify_scoring.py 34/34).
  * `zysk (100%)`    — ile poziomów wart jest uwolniony budżet przy DOSKONAŁEJ
                       konwersji po średnim koszcie poziomu w tym runie. Jeśli to
                       mniej niż `utracone poz.`, patch jest stratny nawet wtedy,
                       gdy uwolnione tokeny w całości się przekonwertują.

    BUDGET_MODULE=<ścieżka do arc3_level_budget.py> python3 arm_cost.py <benchmark.json>...
"""
import importlib.util
import json
import os
import sys

CAPS = (10_000, 12_000, 15_000, 20_000, 30_000, 45_000)


def load(path):
    spec = importlib.util.spec_from_file_location("arc3_level_budget", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _score(done, tot, apl, base):
    """Ten sam wzór co harness: min(raw, 100*pokrycie)."""
    weight = tot * (tot + 1) / 2.0 or 1.0
    raw = 0.0
    for k in range(min(done, len(apl))):
        raw += min(115.0, (base[k] / max(1, apl[k])) ** 2 * 100.0) * (k + 1)
    raw /= weight
    cap = 100.0 * (done * (done + 1) / 2.0) / weight
    return min(raw, cap)


def _level_of_action(game, n_actions):
    """Poziom, w którym leży każda akcja (z actions_per_level)."""
    out = []
    for k, n in enumerate(game["actions_per_level"]):
        out.extend([k] * n)
    return out + [game["levels_completed"]] * (n_actions - len(out))


def sweep(mod, game, cap):
    """(abandon_level|None, utracone poziomy, uwolnione tokeny)."""
    budget = mod.LevelBudget.from_env()
    toks = [e.get("generated_tokens", 0) for e in game["history"]]
    levels = _level_of_action(game, len(toks))
    cum = 0
    for i, t in enumerate(toks):
        cum += t
        # +1: hook woła peek PRZED akcją, po księgowaniu poziomu (solver.py:679)
        lv = levels[min(i + 1, len(levels) - 1)]
        if budget.step(generated_tokens=cum, levels_completed=lv) == mod.ABANDON:
            return lv, max(0, game["levels_completed"] - lv), sum(toks[i + 1:])
    return None, 0, 0


def main(argv):
    mod = load(os.environ.get("BUDGET_MODULE", ""))
    runs = []
    for path in argv[1:]:
        data = json.load(open(path))
        runs.append((path.split("/")[-3].split("-")[0], data["game_runs"]))
    print(f"{'cap':>7}" + "".join(f"{r + ' Δ/utr/uwoln':>22}" for r, _ in runs)
          + f"{'':>3}{'Δ śr (0%)':>11}{'płaci?':>10}")
    for cap in CAPS:
        os.environ["ARC3_LEVEL_TOKEN_CAP"] = str(cap)
        cells, deltas = [], []
        for _name, games in runs:
            s0 = s1 = 0.0
            lost = freed = 0
            for g in games:
                base, tot, apl = g["base_actions_per_level"], g["number_of_levels"], g["actions_per_level"]
                s0 += _score(g["levels_completed"], tot, apl, base)
                lv, l, f = sweep(mod, g, cap)
                new_done = g["levels_completed"] if lv is None else min(g["levels_completed"], lv)
                s1 += _score(new_done, tot, apl, base)
                lost += l
                freed += f
            n = len(games)
            d = (s1 - s0) / n
            deltas.append(d)
            cells.append(f"{d:+7.2f}/{lost:3}/{freed // 1000:5}k")
        mean_d = sum(deltas) / len(deltas)
        pays = "TAK" if all(d >= 0 for d in deltas) else "NIE"
        print(f"{cap:7}" + "".join(f"{c:>22}" for c in cells)
              + f"{'':>3}{mean_d:+11.2f}{pays:>10}")
    print("\nΔ = zmiana score przy zerowej konwersji uwolnionych tokenów; utr = utracone")
    print("poziomy; uwoln = uwolnione tokeny. 'płaci?' = czy Δ ≥ 0 we WSZYSTKICH runach.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv)
