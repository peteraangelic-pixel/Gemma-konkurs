#!/usr/bin/env python3
"""What the evolved locator changes on the 30 tasks whose outcomes we already know.

The dev-set fitness (0.6227 vs 0.5875) and the held-out validation (0.5846 vs 0.5558) say the
evolved constants rank files better *on average*. This tool answers the narrower and more useful
question: on the exact 30 tasks the competition screen scored, does the first gold fixable file move
up, and does it move up for the buckets that actually lost tasks - the 11 sessions that never
edited (N), and the 8 that edited a correct file and still failed (R)?

Read-only: it joins the recorded V6.4 result with the cached features and two configurations.

Usage:
    python3 gemma4-agent/tools/screen_locator_impact.py --features /tmp/locator-evolve/dev
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pickle
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
ANALYSIS = ROOT / "gemma4-agent" / "analysis" / "locator-evolve"
RESULT = ROOT / "gemma4-agent" / "kaggle_results" / "v6-4-benchmark" / "agent_benchmark_result.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def rank_of_first_gold(feats: dict, config: dict, evol) -> int | None:
    ranked = evol.score_config(feats, config)
    gold = set(feats["targets"])
    for position, name in enumerate(ranked, start=1):
        if name in gold:
            return position
    return None


def bucket(row: dict) -> str:
    if row["resolved"]:
        return "P"
    if row["patch_chars"] == 0:
        return "N"
    if set(row["touched_files"]) & set(row["gold_fixable_files"]):
        return "R"
    return "W"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", default="/tmp/locator-evolve/dev")
    parser.add_argument("--best", default=str(ANALYSIS / "best_config.json"))
    parser.add_argument("--out", default=str(ANALYSIS / "screen-impact.json"))
    args = parser.parse_args()

    evol = load_module(TOOLS / "evolve_locator.py", "evolve_locator")
    rows = {task["task_id"]: task for task in json.loads(RESULT.read_text())["tasks"]}
    best = json.loads(Path(args.best).read_text())
    baseline = evol.BASELINE

    table = []
    for path in sorted(Path(args.features).glob("*.pkl")):
        feats = pickle.loads(path.read_bytes())
        task_id = feats["task_id"]
        if task_id not in rows:
            continue
        row = rows[task_id]
        before = rank_of_first_gold(feats, baseline, evol)
        after = rank_of_first_gold(feats, best, evol)
        table.append({"task": task_id, "bucket": bucket(row), "resolved": row["resolved"],
                      "gold": row["gold_fixable_files"], "baseline_rank": before,
                      "evolved_rank": after})

    def fmt(value: int | None) -> str:
        return "—" if value is None else str(value)

    print(f"{'task':18}{'koszyk':>7}{'przed':>7}{'po':>6}  zmiana")
    moves = []
    for entry in sorted(table, key=lambda e: (e["bucket"], e["task"])):
        before, after = entry["baseline_rank"], entry["evolved_rank"]
        if before is None and after is None:
            delta = "brak złota w rankingu"
        elif before is None:
            delta = "pojawia się"
        elif after is None:
            delta = "znika"
        elif after < before:
            delta = f"↑ o {before - after}"
        elif after > before:
            delta = f"↓ o {after - before}"
        else:
            delta = "bez zmian"
        print(f"{entry['task']:18}{entry['bucket']:>7}{fmt(before):>7}{fmt(after):>6}  {delta}")
        moves.append({**entry, "delta": delta})

    summary: dict[str, dict] = {}
    for name in ("P", "N", "R", "W"):
        subset = [m for m in moves if m["bucket"] == name]
        if not subset:
            continue
        better = sum(1 for m in subset if m["baseline_rank"] and m["evolved_rank"]
                     and m["evolved_rank"] < m["baseline_rank"])
        worse = sum(1 for m in subset if m["baseline_rank"] and m["evolved_rank"]
                    and m["evolved_rank"] > m["baseline_rank"])
        top3_before = sum(1 for m in subset if m["baseline_rank"] and m["baseline_rank"] <= 3)
        top3_after = sum(1 for m in subset if m["evolved_rank"] and m["evolved_rank"] <= 3)
        summary[name] = {"tasks": len(subset), "improved": better, "worsened": worse,
                         "top3_before": top3_before, "top3_after": top3_after}
        print(f"\n{name}: {len(subset)} zadań, poprawa {better}, pogorszenie {worse}, "
              f"gold w top-3 {top3_before} → {top3_after}")

    payload = {"baseline": baseline, "evolved": best, "summary": summary, "tasks": moves}
    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
