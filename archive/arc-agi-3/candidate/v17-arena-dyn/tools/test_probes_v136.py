#!/usr/bin/env python3
"""Run the two v13.5 probe cells against stubs — no GPU, no engine, no model.

The probes live in dedicated notebook cells ("v13.6 budget probe" before the
run, "v13.6 roster probe" after it). v13.5 adds per-run `baseline` visibility
and weighted `coverage_pct` (score <= 100 x coverage, rule 30/30). The notebook itself needs the Kaggle
bundle, so this test extracts the cell sources, feeds them the handful of
names they touch (`bm`, `target`, `WORKING_DIR`, `TRUE_SUBMISSION`, `json`,
`re`) and checks they print what they claim. Both cells are wrapped in
try/except; that is exactly why they need a test — a silent `skipped:` line
is invisible in a 9-hour log. Also checks the guarded roster-probe hook
(patch of the v14 audit: an AttributeError there used to kill the notebook
before the run started).

    python3 tools/test_probes.py
"""
from __future__ import annotations

import io
import json
import re
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace as NS

PKG = Path(__file__).resolve().parent.parent


def cells() -> list[str]:
    nb = json.loads((PKG / "arc3-duck-v13.ipynb").read_text())
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


def make_run(gid: str, levels: int, total: int, per_level: list[int], tokens: list[int],
             wall_s: float, score: float, baseline: list[int] | None = None) -> NS:
    hist = [NS(generated_tokens=t) for t in tokens]
    return NS(game_id=gid, history=hist, actions_per_level=per_level,
              levels_completed=levels, number_of_levels=total,
              final_generated_tokens=sum(tokens), final_wallclock_seconds=wall_s,
              final_score=score, state="completed",
              base_actions_per_level=baseline if baseline is not None else list(range(1, total + 1)))


def test_budget_probe_flags_an_over_generous_cap(tmp: Path) -> None:
    src = find("v13.6 budget probe")
    bm = NS(games=[object()] * 110, n_passes=1, solver=NS(concurrency=10,
                                                          max_runtime_s_per_game=532 * 60))
    out = run(src, bm=bm, target=NS(max_runtime_s=32400.0), WORKING_DIR=tmp,
              TRUE_SUBMISSION=True, json=json)
    assert "v13.6 budget:" in out and "UWAGA cap jest" in out, out
    rec = json.loads((tmp / "budget_probe.json").read_text())
    assert rec["games"] == 110 and rec["fair_share_s_per_game"] < 4000, rec
    assert rec["cap_over_fair"] > 8, rec          # 532 min vs ~48 min
    print("budget probe: 110 gier -> uczciwy udzial "
          f"{rec['fair_share_s_per_game'] / 60:.0f} min, cap {rec['cap_over_fair']}x  OK")

    bm2 = NS(games=[object()] * 110, n_passes=1, solver=NS(concurrency=10,
                                                           max_runtime_s_per_game=2900))
    out2 = run(src, bm=bm2, target=NS(max_runtime_s=32400.0), WORKING_DIR=tmp,
               TRUE_SUBMISSION=True, json=json)
    assert "UWAGA" not in out2, out2
    print("budget probe: cap = udzial -> brak ostrzezenia  OK")


def test_roster_probe_detects_duplicates(tmp: Path) -> None:
    src = find("v13.6 roster probe")
    runs = [
        make_run("ls20-9607627b", 3, 6, [20, 30, 40], [3000, 4000, 5000], 2880, 25.0),
        make_run("ls20-11112222", 4, 6, [10, 10, 10, 50], [600, 900, 1200, 5000], 2880, 33.0),
        make_run("tn36-ef4dde99", 1, 8, [16], [1200], 2880, 5.0),
        make_run("ar25-00000000", 0, 5, [], [], 2880, 0.0),
    ]
    out = run(src, bm=NS(game_runs=runs), WORKING_DIR=tmp, json=json)
    lines = [json.loads(l) for l in (tmp / "roster_probe_runs.jsonl").read_text().splitlines()]
    assert len(lines) == 4, lines
    assert lines[0]["base"] == "ls20" and lines[0]["tok_per_action"] > 0
    assert "POWTARZA SIE 1 bazowych gier (do 2x)" in out, out
    # v13.5: baseline widocznosc + pokrycie wazone
    assert lines[0]["baseline"] == 6, lines[0]          # stub ma baseline [..6 poz.]
    assert lines[0]["coverage_pct"] > 0, lines[0]
    assert "sufit wyniku" in out and "score <= 100 x pokrycie" in out, out
    assert "baseline widoczny w 4 runach" in out, out

    # wszystko ukryte (tryb submisji) -> werdykt "nieaktywny"
    hidden = [NS(game_id="aa11-1", history=[], actions_per_level=[], levels_completed=0,
                 number_of_levels=6, final_generated_tokens=0, final_wallclock_seconds=60.0,
                 final_score=0.0, state="completed", base_actions_per_level=None),
              NS(game_id="bb22-2", history=[], actions_per_level=[], levels_completed=0,
                 number_of_levels=6, final_generated_tokens=0, final_wallclock_seconds=60.0,
                 final_score=0.0, state="completed", base_actions_per_level=None)]
    out3 = run(src, bm=NS(game_runs=hidden), WORKING_DIR=tmp, json=json)
    assert "baseline UKRYTY w submisji -> prog wzgledny nieaktywny" in out3, out3
    assert "pamiec miedzy wpisami PLACI" in out, out

    one_action_per_call = make_run("ls20-1111", 1, 3, [3], [900, 900, 900], 600, 5.0)
    out2 = run(src, bm=NS(game_runs=[one_action_per_call]), WORKING_DIR=tmp, json=json)
    assert "ZADNY bazowy kod sie nie powtarza" in out2, out2
    assert "v13.6 batch: a/call = 1.0" in out2 and "baza r019 = 4.357" in out2, out2
    print("roster probe: duplikaty wykryte; brak duplikatow -> werdykt 0 pkt; "
          "a/call podnosi alarm  OK")


def test_roster_probe_survives_a_broken_run(tmp: Path) -> None:
    src = find("v13.6 roster probe")

    class Boom:
        @property
        def game_id(self):
            raise RuntimeError("no game_id")

    out = run(src, bm=NS(game_runs=[Boom()]), WORKING_DIR=tmp, json=json)
    assert "skipped" in out, out          # swallowed, never raises
    print("roster probe: wyjatek w danych -> 'skipped', komorka nie umiera  OK")


def test_roster_hook_is_guarded() -> None:
    hook = find("_install_roster_probe")
    assert "except AttributeError as exc" in hook, "brak guardu na _orig_play"
    assert "except Exception as _probe_exc" in hook, "brak guardu na print(_install_...)"
    print("roster hook: AttributeError-proof (fix z audytu v14)  OK")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_budget_probe_flags_an_over_generous_cap(tmp)
        test_roster_probe_detects_duplicates(tmp)
        test_roster_probe_survives_a_broken_run(tmp)
    test_roster_hook_is_guarded()
    print("\nwszystkie testy sond przeszly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
