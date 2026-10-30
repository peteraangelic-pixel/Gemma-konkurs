#!/usr/bin/env python3
"""Try to solve level 1 of the public games the shipped playbook does not cover.

The playbook is the only part of the score that does not depend on the model: a stored
sequence replays on real game code for 0 tokens and banks `levels` weight. The shipped one
covers 9 of the 25 public games; this sweep tries the other 16 with plain BFS from a cold
start and writes any hit in the package's own format (same `init`/`hashes` scheme, so
`arc3_winpath._replay_once` accepts it unchanged).

    python3 sweep_uncovered.py playbook.json --out playbook-plus.json --time-s 120 --jobs 12
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def grid_key(frame) -> str:
    a = np.asarray(frame)
    while a.ndim > 2:
        a = a[-1]
    grid = tuple(tuple(int(c) for c in row) for row in a.tolist())
    return hashlib.sha256(repr(grid).encode()).hexdigest()[:16]


def state_key(session) -> str:
    """Hash of the session's current frame, in the playbook's own scheme."""
    return grid_key(session.last.frame)


def solve_one(args: tuple[str, float, int]) -> dict:
    slug, time_s, max_clicks = args
    # imports inside the worker: one engine per process
    sys.path.insert(0, str(HERE))
    from lab.engine import Lab
    from lab.search import find_next_level

    lab = Lab(games_dir=os.environ.get("ARC3_GAMES"), engine_paths=os.environ.get("ARC3_ENGINE_PATHS"))
    s = lab.session(slug)
    init = state_key(s)
    path, stats = find_next_level(s, time_budget_s=time_s, max_clicks=max_clicks)
    if not path:
        return {"game": slug, "found": False, **stats, "init": init}
    # replay from a cold start, recording the hash before every action
    s2 = lab.session(slug)
    hashes, actions = [], []
    for cand in path:
        actions.append({"name": getattr(cand.action, "name", str(cand.action)),
                        "data": dict(cand.data or {})})
        s2.step(cand.action, cand.data)
        hashes.append(state_key(s2))
    ok = s2.levels_completed > 0
    return {
        "game": slug, "found": True, "verified": ok, "init": init,
        "levels_completed": s2.levels_completed,
        "actions": actions, "hashes": hashes, **stats,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("playbook")
    ap.add_argument("--out", default=str(HERE / "playbook-plus.json"))
    ap.add_argument("--time-s", type=float, default=120.0)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--max-clicks", type=int, default=10)
    ap.add_argument("--games", default="", help="comma list; default = uncovered")
    args = ap.parse_args()

    pb = json.loads(Path(args.playbook).read_text())
    covered = set(pb["games"])
    env = Path(os.environ.get("ARC3_GAMES") or "")
    all_games = sorted(p.stem for p in env.iterdir() if p.is_dir()) if env else []
    todo = [g.strip() for g in args.games.split(",") if g.strip()] or [g for g in all_games
                                                                     if g not in covered]
    print(f"sweep: {len(todo)} gier bez wpisu, {args.time_s:.0f}s każda, {args.jobs} procesów", flush=True)

    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(solve_one, (g, args.time_s, args.max_clicks)): g for g in todo}
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception as exc:  # noqa: BLE001
                r = {"game": futs[f], "found": False, "error": repr(exc)}
            results.append(r)
            mark = "OK " if r.get("found") and r.get("verified") else "-- "
            print(f"{mark}{r['game']:6} found={r.get('found')} "
                  f"depth={r.get('depth')} nodes={r.get('nodes')} secs={r.get('secs')}"
                  f"{' ERR ' + r['error'][:60] if r.get('error') else ''}", flush=True)

    hits = [r for r in results if r.get("found") and r.get("verified")]
    for r in hits:
        pb["games"].setdefault(r["game"], {"levels": {}})["levels"]["0"] = {
            "actions": r["actions"], "init": r["init"], "hashes": r["hashes"],
            "n": len(r["actions"]), "src": "bfs-uncovered",
        }
    Path(args.out).write_text(json.dumps(pb, indent=1, ensure_ascii=False))
    n_levels = sum(len(g["levels"]) for g in pb["games"].values())
    print(f"\nsweep: {len(hits)}/{len(todo)} nowych poziomów w {time.time() - t0:.0f}s; "
          f"playbook teraz {len(pb['games'])} gier / {n_levels} poziomów -> {args.out}")


if __name__ == "__main__":
    main()
