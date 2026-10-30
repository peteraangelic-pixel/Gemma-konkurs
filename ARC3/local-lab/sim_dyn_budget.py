#!/usr/bin/env python3
"""Przepuść zapisane trakty runu przez moduł budżetu poziomu (patch 0010 / v13.7).

Odpowiada na pytanie "co ten patch w ogóle zdecyduje na NASZYCH danych", bez GPU:
bierze `benchmark.json` (per-akcja `generated_tokens` + `actions_per_level`),
karmi `LevelBudget.peek/step` tak, jak robi to hook w solver.py, i liczy decyzje.

    python3 sim_dyn_budget.py <benchmark.json> <ścieżka/do/arc3_level_budget.py> [cap ...]

Domyślnie cap = 0 (dormant), 45000 i 60000 (proponowane uzbrojenie).
"""
import json
import os
import sys


def load_budget(path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("arc3_level_budget", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_game(mod, game):
    """Decyzje modułu na jednej grze; generuje (akcja, poziom) z actions_per_level."""
    budget = mod.LevelBudget.from_env()
    toks = [e.get("generated_tokens", 0) for e in game["history"]]
    apl = game["actions_per_level"]
    total = sum(apl)
    cum = 0
    i = 0
    counts = {}
    first = None
    levels = list(range(len(apl))) + [game["levels_completed"]] * max(0, len(toks) - total)
    for lv, n in ((lv, n) for lv, n in enumerate(apl)):
        for _ in range(n):
            if i >= len(toks):
                break
            cum += toks[i]
            i += 1
            dec = budget.step(generated_tokens=cum, levels_completed=lv)
            counts[dec] = counts.get(dec, 0) + 1
            if dec != mod.KEEP_GOING and first is None:
                first = f"lvl {lv + 1}, tok={cum} -> {dec}"
    while i < len(toks):
        cum += toks[i]
        i += 1
        dec = budget.step(generated_tokens=cum, levels_completed=game["levels_completed"])
        counts[dec] = counts.get(dec, 0) + 1
        if dec != mod.KEEP_GOING and first is None:
            first = f"lvl {game['levels_completed'] + 1} (nieuk.), tok={cum} -> {dec}"
    return counts, first


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    bench, module = argv[1], argv[2]
    caps = argv[3:] or ["0", "45000", "60000"]
    mod = load_budget(module)
    data = json.load(open(bench))
    for cap in caps:
        os.environ["ARC3_LEVEL_TOKEN_CAP"] = cap
        print(f"\n=== ARC3_LEVEL_TOKEN_CAP={cap}")
        print(f"{'gra':6}{'decyzje':>34}   pierwszy sygnał")
        total = {}
        for g in data["game_runs"]:
            counts, first = run_game(mod, g)
            for k, v in counts.items():
                total[k] = total.get(k, 0) + v
            summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()) if k != mod.KEEP_GOING) or "brak"
            print(f"{g['game_id'][:4]:6}{summary:>34}   {first}")
        print(f"  RAZEM: " + ", ".join(f"{k}={v}" for k, v in sorted(total.items())))


if __name__ == "__main__":
    main(sys.argv)
