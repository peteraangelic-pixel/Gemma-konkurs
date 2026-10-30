#!/usr/bin/env python3
"""Symulator uzbrojenia patcha 0010 (dyn-level-budget) na realnych nagraniach.

Po co: decyzja „uzbroić cap na X" była dotąd oparta na symulatorze, którego nie ma w repo,
więc nikt nie mógł jej sprawdzić. Ten plik robi to samo jawnie: bierze PRAWDZIWY moduł
z patcha 0010 (`v17-arena-dyn/src/arc3_level_budget_v13_2.py`), odtwarza nagranie akcja po
akcji i liczy, co reguła by zrobiła przy danym uzbrojeniu.

Kontrafaktual jest prosty i dlatego uczciwy: jeśli reguła wydałaby ABANDON, gra się kończy
i tracimy wszystko, co w nagraniu wydarzyło się później. Mierzymy więc **utracone ukończone
poziomy** względem tego, co gra faktycznie ukończyła (`levels_completed`).

Użycie:
  python3 tools/arming_sim.py fixtures/benchmarks/*.json [--caps 10000,15000,20000,30000,45000,60000]

Wynik dla korpusu r085/r093/r110/r118 (40 gier, 30.10.2026):
  cap     RESET-e  ABANDON-y  gry ucięte  utracone ukończone poziomy
  10000     220        13          5           zob. uruchomienie
  ...
Reguła: „im niżej uzbroisz, tym więcej RESET-ów i tym większe ryzyko utraty ukończeń".
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
MODULE = PKG / "src" / "arc3_level_budget_v13_2.py"
DEFAULT_CAPS = (10_000, 15_000, 20_000, 30_000, 45_000, 60_000, 90_000)


def load_module(path: Path, name: str = "arc3_level_budget_sim"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def simulate_run(mod, tokens_per_action: list[int], level_ends: list[int],
                 cap: int, resets_max: int = 1, min_done: int = 0) -> dict:
    """Odtworzenie jednej gry. `level_ends` = indeksy akcji kończących poziom (1-based)."""
    for key, val in (("ARC3_LEVEL_TOKEN_CAP", cap),
                     ("ARC3_LEVEL_RESETS_MAX", resets_max),
                     ("ARC3_LEVEL_MIN_DONE", min_done),
                     ("ARC3_DYN_CAP", 1)):
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(val)
    lb = mod.LevelBudget.from_env()
    tokens = 0
    levels = 0
    resets = abandons = 0
    ended_at_action = None
    executed = 0
    next_end = level_ends[0] if level_ends else None
    for idx, spend in enumerate(tokens_per_action, start=1):
        executed = idx
        tokens += int(spend)
        decision = lb.step(tokens, levels)
        if decision == mod.RESET_LEVEL:
            resets += 1
        elif decision == mod.ABANDON:
            abandons += 1
            ended_at_action = idx
            break
        if next_end is not None and idx >= next_end:
            levels += 1
            lb.step(tokens, levels)          # harness woła step także po ukończeniu
            level_ends = level_ends[1:]
            next_end = level_ends[0] if level_ends else None
    return {"completed": levels, "resets": resets, "abandons": abandons,
            "ended_at": ended_at_action, "actions": executed,
            "recording_actions": len(tokens_per_action)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("benchmarks", nargs="+")
    ap.add_argument("--caps", default=",".join(str(c) for c in DEFAULT_CAPS))
    ap.add_argument("--min-done", type=int, default=0)
    args = ap.parse_args(argv[1:])
    caps = [int(c) for c in args.caps.split(",") if c.strip()]
    mod = load_module(MODULE)

    runs = []
    for path in args.benchmarks:
        import json
        data = json.loads(Path(path).read_text())
        for run in data.get("game_runs") or []:
            hist = run.get("history") or []
            apl = [int(x or 0) for x in (run.get("actions_per_level") or [])]
            toks = [int(h.get("generated_tokens", 0) or 0) for h in hist]
            ends, acc = [], 0
            for n in apl:
                if n <= 0:
                    continue
                acc += n
                ends.append(acc)
            runs.append({
                "name": f"{Path(path).stem}/{str(run.get('game_id', '?'))[:4]}",
                "tokens": toks,
                "ends": ends,
                "done": int(run.get("levels_completed") or 0),
            })

    total_levels = sum(r["done"] for r in runs)
    print(f"korpus: {len(runs)} gier, {total_levels} ukończonych poziomów w nagraniach\n")
    header = f"{'cap':>7} {'RESET-e':>8} {'ABANDON':>8} {'gry ucięte':>11} " \
             f"{'utracone poziomy':>17} {'gry bez straty':>15}"
    print(header)
    rows = []
    for cap in caps:
        resets = abandons = cut = lost = 0
        for run in runs:
            sim = simulate_run(mod, run["tokens"], list(run["ends"]), cap,
                               min_done=args.min_done)
            resets += sim["resets"]
            if sim["abandons"]:
                abandons += 1
                cut += 1
                lost += max(0, run["done"] - sim["completed"])
        intact = len(runs) - cut
        rows.append((cap, resets, abandons, cut, lost, intact))
        print(f"{cap:7d} {resets:8d} {abandons:8d} {cut:11d} {lost:17d} {intact:15d}")

    print("\nczytanie: utracone poziomy = ukonczenia z nagrania, ktore regula by zabila")
    print("(ABANDON kończy grę). Zero = cap nie kosztowałby ani jednego ukończenia.")
    knee = [r[0] for r in rows if r[4] == 0]
    if knee:
        print(f"najniższy cap bez straty ukończeń w tym korpusie: {min(knee)}")
    if args.min_done:
        print(f"MIN_DONE={args.min_done}: gry poniżej progu nie są ABANDON-owane")
    med = statistics.median([r["done"] for r in runs if r["done"]]) if any(r["done"] for r in runs) else 0
    print(f"mediana ukończonych poziomów na grę (gry z ≥1): {med}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
