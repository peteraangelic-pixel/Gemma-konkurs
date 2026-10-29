#!/usr/bin/env python3
"""Reproduce the harness's own `final_score` from saved benchmark.json files.

This is the regression test for `lab.engine.game_score`: parse every benchmark.json the
Smak repo saved under kaggle/ops/results/*/output*/ and check our scorer against the
number the harness printed. Two caps are in play (see game_score docstring), so a case
passes if it matches either - but every case must match one of them, and we report which.

    python3 verify_scoring.py /tmp/smak/arc-agi-3/kaggle/ops/results
"""
import glob
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lab.engine import LEVEL_CAP, game_score  # noqa: E402


def main(root):
    files = sorted(glob.glob(f"{root}/*/output*/benchmark.json"))
    if not files:
        raise SystemExit(f"no benchmark.json under {root}")
    total = ok115 = ok100 = bad = zero = 0
    print(f"{'run':8}{'game':14}{'lvl':>4}{'harness':>9}{'cap1.15':>9}{'cap1.0':>9}  verdict")
    for f in files:
        d = json.load(open(f))
        run = f.split("/")[-3].split("-")[0]
        for g in d["game_runs"]:
            lv = g.get("levels_completed") or 0
            apl = g.get("actions_per_level") or []
            base = g["base_actions_per_level"]
            h = g.get("final_score")
            if lv == 0:
                zero += 1
                if abs(h or 0) > 1e-6:
                    bad += 1
                    print(f"{run:8}{g['game_id']:14}{lv:4}{h!r:>9}  BAD zero-level case")
                continue
            total += 1
            v115 = game_score(apl, base, levels_completed=lv, level_cap=LEVEL_CAP)
            v100 = game_score(apl, base, levels_completed=lv, level_cap=100.0)
            m115, m100 = abs(v115 - h) < 1e-3, abs(v100 - h) < 1e-3
            ok115 += m115
            ok100 += m100
            bad += not (m115 or m100)
            verdict = "ok(115)" if m115 else ("ok(100)" if m100 else "MISMATCH")
            print(f"{run:8}{g['game_id']:14}{lv:4}{h:9.3f}{v115:9.3f}{v100:9.3f}  {verdict}")
    print(f"\n{total} scored cases: taaf formula reproduces {ok115}, "
          f"level_cap=100 variant reproduces {ok100}, neither {bad}; "
          f"{zero} zero-level cases all reported 0.0")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else
                          "/tmp/smak/arc-agi-3/kaggle/ops/results"))
