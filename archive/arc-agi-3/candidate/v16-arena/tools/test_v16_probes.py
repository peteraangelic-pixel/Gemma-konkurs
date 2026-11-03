#!/usr/bin/env python3
"""Run the two v16 cells (D' probe, D' metering) against stubs.

Neither cell may change the run and neither may raise: the probe sits before
`bm.run`, so an exception there would kill a 9-hour notebook before it starts,
and the metering sits after it, where a raise would hide the results. Both are
wrapped in try/except in the notebook, which is exactly why they need a test:
a silent `skipped:` line is invisible in a real log.

    python3 tools/test_v16_probes.py
"""
from __future__ import annotations

import io
import json
import os as _real_os
import sys
import tempfile
import types
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace as NS

PKG = Path(__file__).resolve().parent.parent


def cells() -> list[str]:
    nb = json.loads((PKG / "arc3-duck-v16.ipynb").read_text())
    return ["".join(c.get("source", [])) for c in nb["cells"] if c["cell_type"] == "code"]


def find(fragment: str) -> str:
    hits = [c for c in cells() if fragment in c]
    assert len(hits) == 1, f"{fragment!r}: {len(hits)} cells"
    return hits[0]


def run(src: str, **env) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        exec(compile(src, "<cell>", "exec"), {"__name__": "__cell__", **env})
    return buf.getvalue()


def fake_scheduler(*, dishonest_off: bool = False) -> types.ModuleType:
    """Minimal stand-in for inference.agent.priority_scheduler.

    It reads the *real* ARC3_PRIORITY_DPRIME, exactly like the patch, so the
    probe's own off-switch check is exercised for real rather than against a
    cached boolean. The cell is executed with the real ``os`` module.
    """
    def enabled() -> bool:
        return _real_os.environ.get("ARC3_PRIORITY_DPRIME") == "1"

    module = types.ModuleType("inference.agent.priority_scheduler")

    class PrioritySnapshot:
        def __init__(self, level, actions, tokens, cost_multiplier=1.0,
                     total_levels=None, mean_tokens_per_cleared_level=0.0):
            self.level = level
            self.actions = actions
            self.tokens = tokens
            self.total_levels = total_levels
            self.mean_tokens_per_cleared_level = mean_tokens_per_cleared_level

    def priority_value(state, **kwargs):
        return 100 + int(state.level)

    def dprime_priority(state, tail_fraction=1.0):
        depth = state.level * 1000
        return depth + (500 if state.mean_tokens_per_cleared_level < 20_000 else 0)

    def select_priority(state, tail_fraction=None, endgame=False, **legacy):
        # Same contract as the patch: the env decides on every call.
        if dishonest_off or enabled():
            return dprime_priority(state)
        return priority_value(state, tail_fraction=tail_fraction, endgame=endgame, **legacy)

    module.PrioritySnapshot = PrioritySnapshot
    module.priority_value = priority_value
    module.dprime_priority = dprime_priority
    module.select_priority = select_priority
    module.dprime_enabled = enabled
    return module


def install(module: types.ModuleType) -> None:
    inference = types.ModuleType("inference")
    agent = types.ModuleType("inference.agent")
    agent.priority_scheduler = module
    inference.agent = agent
    sys.modules["inference"] = inference
    sys.modules["inference.agent"] = agent
    sys.modules["inference.agent.priority_scheduler"] = module


def make_run(gid: str, levels: int, actions: list[int], tokens: list[int],
             score: float) -> NS:
    hist = [NS(generated_tokens=t) for t in tokens]
    return NS(game_id=gid, history=hist, actions_per_level=actions,
              levels_completed=levels, final_score=score)


def with_switch(value: str | None):
    """Set the real switch for the duration of a probe run."""
    class Env:
        def __enter__(self):
            self.old = _real_os.environ.get("ARC3_PRIORITY_DPRIME")
            if value is None:
                _real_os.environ.pop("ARC3_PRIORITY_DPRIME", None)
            else:
                _real_os.environ["ARC3_PRIORITY_DPRIME"] = value
            return self

        def __exit__(self, *exc):
            if self.old is None:
                _real_os.environ.pop("ARC3_PRIORITY_DPRIME", None)
            else:
                _real_os.environ["ARC3_PRIORITY_DPRIME"] = self.old
    return Env()


def test_probe_reports_the_switch_state(tmp: Path) -> None:
    src = find("v16 D' priority probe")
    install(fake_scheduler())
    with with_switch("1"):
        out = run(src, os=_real_os)
    assert "v16 dprime: switch=ON" in out, out
    assert "switch-off == priority_value: True" in out, out
    assert "depth order deep>mid=True" in out, out
    assert "cheap>pricey=True" in out, out
    assert "UWAGA" not in out, out
    print("dprime probe: switch ON, OFF==legacy, order checks OK")


def test_probe_shouts_when_the_switch_is_not_live(tmp: Path) -> None:
    src = find("v16 D' priority probe")
    install(fake_scheduler())
    with with_switch("0"):
        out = run(src, os=_real_os)
    assert "switch=OFF" in out, out
    assert "nieaktywny" in out, out  # a silent v13.4 run must not pass as v16
    print("dprime probe: switch OFF -> explicit warning OK")


def test_probe_flags_a_non_single_variable_patch(tmp: Path) -> None:
    src = find("v16 D' priority probe")
    install(fake_scheduler(dishonest_off=True))
    with with_switch("1"):
        out = run(src, os=_real_os)
    assert "switch-off == priority_value: False" in out, out
    assert "jednozmiennosciowy" in out, out
    print("dprime probe: OFF path diverges -> labelled non-single-variable OK")


def test_probe_survives_a_missing_module(tmp: Path) -> None:
    src = find("v16 D' priority probe")
    for name in ("inference.agent.priority_scheduler", "inference.agent", "inference"):
        sys.modules.pop(name, None)
    with with_switch(None):
        out = run(src, os=_real_os)
    assert "skipped" in out, out
    print("dprime probe: missing scheduler -> 'skipped', cell does not die OK")


def test_metering_reports_the_measured_pace(tmp: Path) -> None:
    src = find("v16 dprime metering")
    runs = [
        make_run("ls20-9607627b", 3, [20, 30, 40], [3000, 4000, 5000], 25.0),
        make_run("tn36-ef4dde99", 1, [16], [1200], 5.0),
        make_run("ar25-00000000", 0, [], [], 0.0),
    ]
    out = run(src, bm=NS(game_runs=runs), WORKING_DIR=tmp,
              os=NS(environ={"ARC3_PRIORITY_DPRIME": "1"}))
    rows = [json.loads(line) for line in (tmp / "dprime_metering.jsonl").read_text().splitlines()]
    assert len(rows) == 3, rows
    assert rows[0]["tokens_per_cleared_level"] == round(12000 / 3, 1), rows[0]
    assert rows[2]["tokens_per_cleared_level"] == 0.0, rows[2]
    assert "v16 dprime metering: {" in out, out
    print("dprime metering: pace per cleared level written OK")


def test_metering_says_so_when_nothing_was_cleared(tmp: Path) -> None:
    src = find("v16 dprime metering")
    out = run(src, bm=NS(game_runs=[make_run("ls20-x", 0, [], [], 0.0)]),
              WORKING_DIR=tmp, os=NS(environ={"ARC3_PRIORITY_DPRIME": "1"}))
    assert "ZADEN run nie ukonczyl poziomu" in out, out
    print("dprime metering: no cleared level -> explicit note OK")


def test_metering_survives_a_broken_run(tmp: Path) -> None:
    src = find("v16 dprime metering")

    class Boom:
        @property
        def game_id(self):
            raise RuntimeError("no game_id")

    out = run(src, bm=NS(game_runs=[Boom()]), WORKING_DIR=tmp,
              os=NS(environ={"ARC3_PRIORITY_DPRIME": "1"}))
    assert "skipped" in out, out
    print("dprime metering: broken run -> 'skipped' OK")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_probe_reports_the_switch_state(tmp)
        test_probe_shouts_when_the_switch_is_not_live(tmp)
        test_probe_flags_a_non_single_variable_patch(tmp)
        test_probe_survives_a_missing_module(tmp)
        test_metering_reports_the_measured_pace(tmp)
        test_metering_says_so_when_nothing_was_cleared(tmp)
        test_metering_survives_a_broken_run(tmp)
    print("\nwszystkie testy sond v16 przeszły")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
