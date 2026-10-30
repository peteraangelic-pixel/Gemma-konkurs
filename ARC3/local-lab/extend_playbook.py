#!/usr/bin/env python3
"""Extend a v13 playbook deeper: replay the known prefix, then search for the next levels.

Why this is the only part of the playbook worth growing: the existing 14 entries are all
shallow (mostly level 1, deepest level 4) and the LLM already solves level 1 on most games.
Level k pays k units, so a level 5 entry is worth five level-1 entries of the same game.

Output is a drop-in replacement for `playbook.json` in the same format - including the
package's own hash scheme (sha256 of repr(tuple-of-tuples of the last frame), first 16 hex),
so `arc3_winpath._replay_once` will accept every new entry without changes.

    python3 extend_playbook.py playbook.json --games tu93,vc33,m0r0 --levels 1 --time-s 300 \
        --out playbook-extended.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab.search import find_next_level, replay_verify  # noqa: E402


def grid_key(frame) -> str:
    a = np.asarray(frame)
    while a.ndim > 2:
        a = a[-1]
    grid = tuple(tuple(int(c) for c in row) for row in a.tolist())
    return hashlib.sha256(repr(grid).encode()).hexdigest()[:16]


def replay_prefix(session, entry: dict) -> bool:
    """Play a stored level entry on a live session, verifying every frame."""
    if entry.get("init") and entry["init"] != grid_key(session.last.frame):
        return False
    for i, act in enumerate(entry["actions"]):
        name = act["name"]
        data = act.get("data") or None
        try:
            session.step(int(name.replace("ACTION", "")), data)
        except Exception:
            return False
        stored = (entry.get("hashes") or [None] * (i + 1))[i]
        if stored and stored != grid_key(session.last.frame):
            return False
    return True


def search_level(session, node_budget, time_s, max_clicks):
    """BFS for the next level, then record it in playbook format."""
    init = grid_key(session.last.frame)
    level = session.levels_completed
    start_actions = session.total_actions
    hist = []

    # Wrap step so every executed action is captured with the frame it produced.
    orig_step = session.step

    def recording_step(action, data=None):
        fd = orig_step(action, data)
        name = f"ACTION{action}"
        hist.append({"name": name, "data": dict(data or {}), "hash": grid_key(fd.frame)})
        return fd

    session.step = recording_step
    try:
        path, stats = find_next_level(session, node_budget=node_budget,
                                      time_budget_s=time_s, max_clicks=max_clicks)
        if not path:
            return None, stats
        before = session.levels_completed
        for cand in path:
            session.step(cand.action, cand.data)
        if session.levels_completed <= before:
            return None, {**stats, "verify_failed": True}
    finally:
        session.step = orig_step
    entry = {
        "actions": [{"name": h["name"], "data": h["data"]} for h in hist],
        "init": init,
        "hashes": [h["hash"] for h in hist],
        "n": len(hist),
        "src": "offline-sweep-ext",
    }
    stats["actions_used"] = session.total_actions - start_actions
    return entry, stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("playbook")
    ap.add_argument("--games", default="all", help="'all' or comma list")
    ap.add_argument("--levels", type=int, default=1, help="how many NEW levels per game")
    ap.add_argument("--nodes", type=int, default=200000)
    ap.add_argument("--time-s", type=float, default=300.0)
    ap.add_argument("--max-clicks", type=int, default=12)
    ap.add_argument("--games-dir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only-covered", action="store_true",
                    help="extend only games already in the playbook")
    a = ap.parse_args(argv)

    from lab.engine import Lab

    book = json.loads(Path(a.playbook).read_text())
    lab = Lab(games_dir=a.games_dir)
    games = list(book["games"]) if a.only_covered else (lab.slugs() if a.games == "all"
                                                       else [g.strip() for g in a.games.split(",")])
    if a.games != "all" and a.only_covered:
        games = [g for g in games if g in book["games"]]

    added = 0
    for slug in games:
        if slug not in lab.slugs():
            print(f"{slug}: not in this game set, skipped")
            continue
        t0 = time.time()
        session = lab.session(slug)
        known = (book["games"].get(slug) or {}).get("levels") or {}
        prefix_ok = True
        for lvl in sorted(known, key=int):
            if not replay_prefix(session, known[lvl]):
                prefix_ok = False
                print(f"{slug}: stored prefix diverged at level {lvl}; rerun "
                      f"build_playbook.py for this game")
                break
        print(f"{slug}: prefix {len(known)} level(s) -> at level {session.levels_completed}"
              f"{'' if prefix_ok else ' (BROKEN)'}, searching {a.levels} more")
        for _ in range(a.levels):
            entry, stats = search_level(session, a.nodes, a.time_s, a.max_clicks)
            if entry is None:
                print(f"  level {session.levels_completed}: not found ({stats})")
                break
            lvl = str(session.levels_completed - 1)
            book["games"].setdefault(slug, {"levels": {}})["levels"][lvl] = entry
            added += 1
            print(f"  level {int(lvl) + 1}: FOUND in {entry['n']} actions "
                  f"({stats.get('nodes')} nodes, {stats.get('secs')}s)")
        print(f"  {slug} done in {time.time() - t0:.0f}s, score now {session.score():.2f}")

    out = a.out or str(Path(a.playbook).with_name("playbook-extended.json"))
    Path(out).write_text(json.dumps(book, indent=1))
    tot = sum(len(v["levels"]) for v in book["games"].values())
    print(f"\nadded {added} levels; playbook now {tot} levels / {len(book['games'])} games -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
