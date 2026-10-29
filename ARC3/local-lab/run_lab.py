#!/usr/bin/env python3
"""Run the local ARC-AGI-3 lab: search the public games and report the exact RHAE.

Usage (on the 5950X: --workers 14, leave two cores for the model if you also run vLLM):

    python3 run_lab.py --games all --levels 2 --nodes 4000 --workers 14
    python3 run_lab.py --games cn04,ls20,ar25 --levels 3 --nodes 8000 --time-s 120
    python3 run_lab.py --score-only --from results/lab-....json     # re-score a saved run

What it answers: how many levels can a *deterministic* searcher clear per game, at what
action cost, and what that is worth in score. Anything it clears is free for the model in
the real run - that is the point, not the score of the play-through itself.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab.engine import Lab, game_score  # noqa: E402
from lab.search import play_with_search  # noqa: E402

_LAB = None


def _init(games_dir, engine_paths):
    global _LAB
    _LAB = Lab(games_dir=games_dir, engine_paths=engine_paths)


def _work(job):
    slug, levels, nodes, secs, seed = job
    t0 = time.time()
    session = _LAB.session(slug, seed=seed)
    stats = play_with_search(
        session,
        levels_wanted=levels,
        node_budget=nodes,
        time_budget_s=secs,
        log=lambda *_a, **_k: None,
    )
    rep = session.report()
    rep["search_stats"] = stats
    rep["secs"] = round(time.time() - t0, 1)
    rep["baseline"] = _LAB.meta[slug].baseline_actions if slug in _LAB.meta else None
    rep["tags"] = _LAB.meta[slug].tags if slug in _LAB.meta else []
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", default="all", help="'all' or comma-separated slugs")
    ap.add_argument("--levels", type=int, default=2, help="stop after this many cleared levels")
    ap.add_argument("--nodes", type=int, default=4000, help="node budget per level")
    ap.add_argument("--time-s", type=float, default=60.0, help="wall budget per level")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--games-dir", default=None)
    ap.add_argument("--engine-paths", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    probe = Lab(games_dir=args.games_dir, engine_paths=args.engine_paths)
    slugs = probe.slugs()
    if args.games != "all":
        want = [g.strip() for g in args.games.split(",") if g.strip()]
        missing = [g for g in want if g not in slugs]
        if missing:
            raise SystemExit(f"unknown games {missing}; known: {slugs}")
        slugs = want
    del probe

    jobs = [(s, args.levels, args.nodes, args.time_s, args.seed) for s in slugs]
    t0 = time.time()
    with mp.Pool(args.workers, initializer=_init, initargs=(args.games_dir, args.engine_paths)) as pool:
        rows = pool.map(_work, jobs, chunksize=1)
    wall = time.time() - t0

    rows.sort(key=lambda r: (-r["levels"], r["actions"]))
    print(f"\n{'game':8}{'lvl':>6}{'actions':>9}{'score':>8}{'secs':>7}  tags")
    for r in rows:
        print(f"{r['game']:8}{str(r['levels'])+'/'+str(r['levels_total'] or '?'):>6}"
              f"{r['actions']:9}{r['score']:8.2f}{r['secs']:7.0f}  {','.join(r['tags'])}")
    mean = sum(r["score"] for r in rows) / len(rows)
    solved = sum(1 for r in rows if r["levels"] > 0)
    levels = sum(r["levels"] for r in rows)
    print(f"\nmean score {mean:.2f} over {len(rows)} games | {solved} games with >=1 level "
          f"| {levels} levels total | wall {wall/60:.1f} min on {args.workers} workers")

    out = args.out or f"results/lab-{time.strftime('%Y%m%dT%H%M%S')}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({
        "config": vars(args), "wall_secs": round(wall, 1),
        "mean_score": round(mean, 3), "levels_total": levels, "rows": rows,
    }, indent=2))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
