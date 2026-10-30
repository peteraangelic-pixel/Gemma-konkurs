#!/usr/bin/env python3
"""End-to-end test of v13.1's cross-entry replay, using the package's OWN module.

The claim under test (duck-v13-1 README, "magazyn kluczowany bazowym kodem gry"):
a level solved in one benchmark entry is replayed at zero model tokens in the next
entry of the same game, because the store is keyed by the base game code and roster
entries are clones of the same game.

Why simulate instead of trusting the unit tests: their `test_winpath.py` uses a fake
solver contract, so it proves the plumbing but not that a *real* game reaches
`levels_completed` from a replayed chain. Here the engine is the real one, the module is
theirs (imported unmodified from the checked-out branch), and the only thing faked is the
LLM: entry 1 "solves" a level by executing the playbook's actions through
`_execute_action`, exactly as the agent would.

    python3 winpath_sim.py /tmp/pk-a450/arc-agi-3/duck-v13-1/src/arc3_winpath.py \
        /tmp/pk-a450/arc-agi-3/duck-v13-1/playbook.json --game tu93
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))


def load_winpath(path: str):
    spec = importlib.util.spec_from_file_location("arc3_winpath_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _last_frame_2d(frame_sequence):
    """taaf.GameState.frame is `Frame(data=<2D int8 last frame>)`; peek through animations."""
    a = np.asarray(frame_sequence, dtype=np.int8)
    while a.ndim > 2:
        a = a[-1]
    return a


class FakeState:
    """The slice of `taaf.GameState` that arc3_winpath touches.

    v13.2 added a guard that reads `game_state.raw.state`, so `raw` has to be modelled too -
    otherwise the guard silently never fires and the test would certify a path it never took.
    """

    def __init__(self, frame, levels_completed, available, state=None):
        self.frame = type("Frame", (), {"data": _last_frame_2d(frame)})()
        self.levels_completed = levels_completed
        self.available_actions = available
        self.raw = type("Raw", (), {"state": state})()


class FakeGame:
    def __init__(self, web, game_id):
        self.web = web
        self.game_run = type("GR", (), {"game_id": game_id})()
        self.current_state = FakeState(web.last.frame, web.levels_completed, web.available,
                                       getattr(web.last, "state", None))


class FakeSession:
    """One benchmark entry: the replay hook's view of a harness game session."""

    def __init__(self, web, wp, game_id, pass_index=0):
        self.web = web
        self.wp = wp
        self.game = FakeGame(web, game_id)
        self.pass_index = pass_index
        self.tokens_llm = 0
        self.actions_llm = 0
        self.actions_replay = 0

    # --- harness contract ------------------------------------------------
    def should_stop(self):
        return False

    def _execute_action(self, action_input, batch_index=0, batch_size=1, generated_tokens=0):
        from arcengine import GameAction  # noqa: PLC0415

        prev_level = self.web.levels_completed
        prev_grid = self.wp._grid_of(self.game.current_state)
        fd = self.web.step(int(action_input.id.value), dict(action_input.data or {}))
        if generated_tokens:
            self.tokens_llm += generated_tokens
            self.actions_llm += 1
        else:
            self.actions_replay += 1
        self.game.current_state = FakeState(fd.frame, self.web.levels_completed,
                                           self.web.available, fd.state)
        payload = {"game_over": self.web.is_over}
        self.wp.record_action(
            self,
            action_name=action_input.id.name,
            action_data=dict(action_input.data or {}),
            previous_completed=prev_level,
            previous_grid=prev_grid,
            new_state=self.game.current_state,
            payload=payload,
        )
        return payload

    def run_turn_with_replay(self):
        """What the patched solver loop does before asking the model."""
        return self.wp.maybe_replay(self)


def entry(web_factory, wp, game_id, plan, tokens_per_action=600, pass_index=0):
    """Play one benchmark entry: replay first, then 'LLM' (planned actions), then replay."""
    web = web_factory()
    sess = FakeSession(web, wp, game_id, pass_index)
    wp.begin_session(sess)
    from arcengine import ActionInput, GameAction  # noqa: PLC0415

    log = []
    for _ in range(50):  # bounded loop, mirrors `while not should_stop()`
        if sess.run_turn_with_replay():
            log.append("replay-turn")
            if web.is_won:
                break
            continue
        if not plan:
            break
        action, data = plan.pop(0)
        sess._execute_action(
            ActionInput(id=GameAction[action], data=dict(data or {})),
            batch_index=0, batch_size=1, generated_tokens=tokens_per_action,
        )
        log.append(f"llm:{action}")
    wp.end_session(sess)
    return {
        "game_id": game_id, "levels": web.levels_completed,
        "actions_llm": sess.actions_llm, "actions_replay": sess.actions_replay,
        "tokens_llm": sess.tokens_llm, "score": round(web.score(), 2),
        "log": log,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("winpath_py")
    ap.add_argument("playbook")
    ap.add_argument("--game", default="tu93")
    ap.add_argument("--games-dir", default=None)
    ap.add_argument("--fresh-store", action="store_true", default=True)
    a = ap.parse_args(argv)

    store = Path(tempfile.mkdtemp(prefix="wp_store_"))
    os.environ["ARC3_WINPATH"] = "1"
    os.environ["ARC3_WINPATH_DIR"] = str(store)
    os.environ["ARC3_WINPATH_REPLAY"] = "1"
    os.environ["ARC3_DEAD_SKIP"] = "0"

    wp = load_winpath(a.winpath_py)
    from lab.engine import Lab  # noqa: PLC0415

    lab = Lab(games_dir=a.games_dir)
    book = json.loads(Path(a.playbook).read_text())
    levels = book["games"][a.game]["levels"]
    plan = [(x["name"], x.get("data")) for x in levels["0"]["actions"]]
    want = len(levels)

    print(f"store: {store} (no playbook.json here, so entry 1 starts empty)")
    print(f"game {a.game}: plan = level-1 actions for entry 1, "
          f"{want} level(s) stored in the playbook\n")

    made = []

    def factory():
        s = lab.session(a.game)
        made.append(s)
        return s

    r1 = entry(factory, wp, f"{a.game}-entry1", list(plan))
    print(f"entry 1 ({r1['game_id']}): levels={r1['levels']} "
          f"llm_actions={r1['actions_llm']} replay_actions={r1['actions_replay']} "
          f"tokens={r1['tokens_llm']}")
    print(f"  store file: {(store / (a.game + '.json')).exists()}")
    stored = json.loads((store / (a.game + ".json")).read_text())
    print(f"  recorded levels in store: {sorted(stored['levels'])}  "
          f"passes_completed={stored['passes_completed']}")

    # entry 2: a fresh game, same base code (a roster clone), NO llm plan at all
    r2 = entry(factory, wp, f"{a.game}-clone-2", [])
    print(f"\nentry 2 ({r2['game_id']}): levels={r2['levels']} "
          f"llm_actions={r2['actions_llm']} replay_actions={r2['actions_replay']} "
          f"tokens={r2['tokens_llm']}")
    print(f"  log: {r2['log']}")
    print(f"\nVERDICT: cross-entry replay {'WORKS' if r2['levels'] > 0 and r2['tokens_llm'] == 0 else 'DID NOT FIRE'}"
          f"  (entry1 {r1['levels']} -> entry2 {r2['levels']} levels, "
          f"{r2['tokens_llm']} tokens)")
    return 0 if r2["levels"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
