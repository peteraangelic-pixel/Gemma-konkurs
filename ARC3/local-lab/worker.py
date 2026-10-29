#!/usr/bin/env python3
"""One game, one process, one JSON line on stdout - the unit of work for the Rust harness.

Deliberately dumb: the Rust `arc3lab sweep` binary owns the parallelism (Rayon), the
aggregation and the scoring; this process only owns the engine, which has to be Python
because the 25 environments are Python by construction.

    python3 worker.py --game cn04 --levels 2 --nodes 4000 --time-s 120
    {"game":"cn04","levels":1,"level_total":6,"actions":9,"actions_per_level":[9],
     "score":15.87,"policy":"share_levels_and_camera","nodes_per_s":412.0, ...}

Exit code is 0 whenever a measurement was produced, even if zero levels were cleared: a
zero is data. Non-zero only on a broken environment (no games dir, engine missing).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--levels", type=int, default=2)
    ap.add_argument("--nodes", type=int, default=4000)
    ap.add_argument("--time-s", type=float, default=120.0)
    ap.add_argument("--max-clicks", type=int, default=10)
    ap.add_argument("--games-dir", default=os.environ.get("ARC3_GAMES"))
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    from lab.engine import Lab
    from lab.search import node_cost_ms, play_with_search

    t0 = time.time()
    lab = Lab(games_dir=a.games_dir)
    session = lab.session(a.game, seed=a.seed)
    node_ms = node_cost_ms(session)
    stats = play_with_search(
        session, levels_wanted=a.levels, node_budget=a.nodes,
        time_budget_s=a.time_s, max_clicks=a.max_clicks, log=lambda *_: None,
    )
    rep = session.report()
    rep.update({
        "node_ms": round(node_ms, 2),
        "nodes_per_s": round(1000.0 / node_ms, 1) if node_ms else None,
        "search": stats,
        "secs": round(time.time() - t0, 1),
        "baseline": session.meta.baseline_actions if session.meta else None,
        "levels_total": session.meta.n_levels if session.meta else None,
    })
    print(json.dumps(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
