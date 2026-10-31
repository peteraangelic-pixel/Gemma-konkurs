#!/usr/bin/env python3
"""Niezależne odtworzenie kontrolera `template` na PRAWDZIWYM silniku ARC-AGI-3.

Nie ufa zapisanym JSON-om: bierze `template_transfer.py` z gałęzi autora, lokalny
silnik (arcengine 0.9.3 + arc-agi 0.9.9, pliki gier z repo) i gra od zera — dokładnie
tak, jak robi to notebook: piksele + available_actions + numer poziomu, nic więcej.

    PYTHONPATH=/tmp/ae:/tmp/agx python3 template_replay.py --games ft09 --compare
    PYTHONPATH=/tmp/ae:/tmp/agx python3 template_replay.py --all --cap 256
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "template-audit"))
from template_transfer import TemplateTransfer  # noqa: E402


def _wrapper():
    from arc_agi import LocalEnvironmentWrapper

    return LocalEnvironmentWrapper


def make_arcade(env_dir):
    from arc_agi import Arcade, OperationMode

    return Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(env_dir))


def play(envs, gid, cap=256, seed=731, stop_on_abstain=True, controller_factory=TemplateTransfer):
    from arcengine import GameAction, GameState

    LocalEnvironmentWrapper = _wrapper()
    log = logging.getLogger("audit")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    env = LocalEnvironmentWrapper(environment_info=envs[gid], logger=log,
                                  scorecard_id="audit", seed=seed, include_frame_data=True)
    fd = env.reset()
    ctl = controller_factory()
    trace = []
    per_level = []
    last_level = 0
    level_actions = 0
    t0 = time.time()
    while fd is not None and len(trace) < cap:
        # UWAGA: po level-upie `fd.frame` ma 2 klatki [przejściowa, ustalona].
        # Harness (runtime state) widzi USTALONĄ, więc bierzemy ostatnią. Kto bierze
        # frame[0], dostaje klatkę animacji i kontroler abstynuje — patrz RAPORT.
        grid = np.array(fd.frame[-1], dtype=np.uint8)
        avail = list(fd.available_actions or [])
        controls = [6] if 6 in avail else []
        if fd.levels_completed > last_level:
            per_level.append(level_actions)
            level_actions = 0
            last_level = fd.levels_completed
        act = ctl.act(grid, controls, int(fd.levels_completed) + 1)
        if act is None:
            break
        _, x, y = act
        trace.append((x, y))
        fd = env.step(GameAction.ACTION6, {"x": int(x), "y": int(y)})
        level_actions += 1
        if fd is not None and fd.state in (GameState.WIN, GameState.GAME_OVER):
            break
    if fd is not None and level_actions:
        per_level.append(level_actions)
    return {
        "game": gid,
        "actions": len(trace),
        "levels": int(fd.levels_completed) if fd is not None else 0,
        "per_level": per_level,
        "state": str(fd.state.value) if fd is not None else "?",
        "seconds": round(time.time() - t0, 3),
        "trace": trace[:40],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", nargs="*", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--cap", type=int, default=256)
    ap.add_argument("--env", default="/tmp/v18lab/arc-agi-3/games/environment_files")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    arcade = make_arcade(a.env)
    envs = {e.game_id: e for e in arcade.available_environments}
    ids = sorted(envs) if a.all else [g for g in sorted(envs) if any(s in g for s in a.games or ["ft09"])]
    rows = []
    print(f"{'gra':10}{'akcje':>7}{'poziomy':>9}{'per_level':>18}{'stan':>14}{'s':>7}")
    for gid in ids:
        r = play(envs, gid, cap=a.cap)
        rows.append(r)
        print(f"{gid[:8]:10}{r['actions']:7}{r['levels']:9}{str(r['per_level']):>18}"
              f"{r['state']:>14}{r['seconds']:7.2f}")
    if a.compare:
        gold = json.load(open("/tmp/v18lab/arc-agi-3/analysis/causal-agent-20261031/"
                              "harness-template-repro/game-run.json"))
        mine = rows[0]
        print(f"\nzapisane przez autora: akcje={sum(gold['actions_per_level'])} "
              f"poziomy={gold['levels_completed']} per_level={gold['actions_per_level'][:3]}")
        print(f"moje odtworzenie:      akcje={mine['actions']} poziomy={mine['levels']} "
              f"per_level={mine['per_level']}")
        recorded = [(e["action"]["data"]["x"], e["action"]["data"]["y"]) for e in gold["history"]]
        same = recorded[:len(mine["trace"])] == mine["trace"][:len(recorded)]
        print(f"pierwsze {min(len(recorded), len(mine['trace']))} kliknięć identyczne: {same}")
        if not same:
            for i, (a1, b1) in enumerate(zip(recorded, mine["trace"])):
                if a1 != b1:
                    print(f"  pierwsza różnica na akcji {i + 1}: autor={a1} ja={b1}")
                    break
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1))
        print(f"\nzapisano {a.out}")


if __name__ == "__main__":
    main()
