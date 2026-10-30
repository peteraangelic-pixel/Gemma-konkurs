#!/usr/bin/env python3
"""Replay a v13-mega playbook against the real game code, action by action.

Why: the v13 package claims "14 levels / 9 games, each sequence re-validated on the real
game code". That claim decides whether playbook+replay is a real lever or a nice story, so
it gets reproduced here on our own verified engine rather than trusted.

Contract checked per (game, level):
  * the stored `init` hash must equal the frame hash at the moment the level starts --
    this is exactly the guard v13's `_replay_once` uses, so a pass here means the replay
    would have fired in the notebook too;
  * every action's resulting frame must match the stored hash;
  * `levels_completed` must actually rise.

Hash scheme is copied from the package (`arc3_winpath.grid_key_of_grid`):
sha256(repr(tuple(tuple(row) for row in last_frame)))[:16]. Using their scheme instead of
ours is the point: it makes our engine and their recorder comparable number for number.

    python3 playbook_verify.py /tmp/pk-a450/arc-agi-3/duck-v13-mega/playbook.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))


def grid_of(frame) -> tuple:
    """Last frame as a tuple of tuples of ints - the package's `_grid_of`."""
    a = np.asarray(frame)
    while a.ndim > 2:
        a = a[-1]
    return tuple(tuple(int(c) for c in row) for row in a.tolist())


def key(grid: tuple) -> str:
    return hashlib.sha256(repr(grid).encode()).hexdigest()[:16]


def key_of(frame) -> str:
    return key(grid_of(frame))


def action_id(name: str):
    from lab.engine import action_enum  # noqa: PLC0415

    return action_enum(int(name.replace("ACTION", ""))) if name.startswith("ACTION") else action_enum(0)


def verify_game(lab, slug: str, levels: dict, verbose: bool = False, seed: int = 0) -> dict:
    session = lab.session(slug, seed=seed)
    results = []
    for lvl_key in sorted(levels, key=int):
        entry = levels[lvl_key]
        lvl = int(lvl_key)
        want_init = entry.get("init")
        got_init = key_of(session.last.frame)
        state = {
            "game": slug, "level": lvl, "n": entry.get("n"), "src": entry.get("src"),
            "started_at_level": session.levels_completed,
            "init_match": (want_init == got_init) if want_init else None,
            "actions_ok": 0, "hash_ok": 0, "hash_bad": 0, "completed": False,
            "note": "",
        }
        if session.levels_completed != lvl:
            state["note"] = f"not at level {lvl} (at {session.levels_completed}); skipped"
            results.append(state)
            continue
        if want_init and want_init != got_init:
            state["note"] = f"init hash differs: stored {want_init[:8]} vs now {got_init[:8]}"
            results.append(state)
            continue
        for i, act in enumerate(entry["actions"]):
            name, data = act.get("name"), act.get("data") or {}
            try:
                session.step(int(name.replace("ACTION", "")), dict(data) if data else None)
            except Exception as exc:
                state["note"] = f"exception on action {i} ({name}): {exc!r}"[:120]
                break
            state["actions_ok"] += 1
            stored = (entry.get("hashes") or [None] * (i + 1))[i]
            if stored is None or key_of(session.last.frame) == stored:
                state["hash_ok"] += 1
            else:
                state["hash_bad"] += 1
                if verbose:
                    print(f"      action {i} {name}: hash {key_of(session.last.frame)[:8]} != stored {stored[:8]}")
        state["completed"] = session.levels_completed > lvl
        if not state["completed"] and not state["note"]:
            state["note"] = "sequence finished but the level did not complete"
        results.append(state)
    return {"game": slug, "levels": results, "final_levels": session.levels_completed,
            "actions": session.total_actions, "score": round(session.score(), 2)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("playbook")
    ap.add_argument("--games-dir", default=None)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args(argv)

    from lab.engine import Lab

    book = json.loads(Path(a.playbook).read_text())
    lab = Lab(games_dir=a.games_dir)
    known = set(lab.slugs())

    out, ok_levels, tot_levels, actions_used = [], 0, 0, 0
    for slug, payload in book["games"].items():
        if slug not in known:
            print(f"  {slug}: NOT IN THIS GAME SET")
            continue
        r = verify_game(lab, slug, payload["levels"], a.verbose, a.seed)
        out.append(r)
        print(f"\n{slug}: final {r['final_levels']} level(s), {r['actions']} actions, "
              f"score {r['score']:.2f}")
        for s in r["levels"]:
            tot_levels += 1
            ok = s["completed"] and s["hash_bad"] == 0
            ok_levels += ok
            actions_used += s["actions_ok"] if ok else 0
            flag = "PASS" if ok else "FAIL"
            print(f"  [{flag}] level {s['level']}  n={s['n']:3}  init={s['init_match']}  "
                  f"hashes {s['hash_ok']}/{s['actions_ok']}  "
                  f"completed={s['completed']}  {s['note']}")
    print(f"\n=== seed={a.seed}: {ok_levels}/{tot_levels} levels reproduce on the real game code "
          f"({actions_used} actions)")
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(out, indent=1))
        print(f"written {a.json_out}")
    return 0 if ok_levels else 1


if __name__ == "__main__":
    raise SystemExit(main())
