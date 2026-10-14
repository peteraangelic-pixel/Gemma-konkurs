#!/usr/bin/env python3
"""Failure taxonomy audit: where do the lost tasks actually go?

The ARC-AGI-3 sibling session's "stuck audit" inspired this: before choosing the next lever,
classify every failed task by mechanism, using data we already have. The benchmark result JSON
records, per task, `resolved`, `patch_chars`, `touched_files`, `gold_fixable_files` and
`localized`, so each failure can be put into exactly one bucket:

  N  no edit at all            (patch_chars == 0 and no repository file touched)
  W  edited, but no gold file  (a real edit, none of the gold fixable files touched)
  R  edited a gold file, still failed
  P  resolved

For every bucket crossing `localized` (the locator's candidate list contained a gold fixable
file) the audit prints counts, so we can see how much of the loss is "the tool pointed at the
wrong file", how much is "the session never edited", and how much is "right file, wrong fix".

Read-only; no network, no GPU.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BUCKETS = ("P resolved", "N no edit at all", "W edited, no gold file", "R edited gold file, failed")


def norm(path: str) -> str:
    return path.strip().lstrip("./")


def classify(task: dict) -> tuple[str, str]:
    """Return (bucket, detail) for one per-task record."""
    resolved = bool(task.get("resolved"))
    patch_chars = int(task.get("patch_chars") or 0)
    touched = [norm(p) for p in (task.get("touched_files") or [])]
    gold = [norm(p) for p in (task.get("gold_fixable_files") or [])]
    repo_touched = [p for p in touched if not p.startswith("/")]
    if resolved:
        return BUCKETS[0], ""
    if patch_chars == 0 and not repo_touched:
        scratch = ", ".join(sorted({p for p in touched if p.startswith("/")})) or "nothing"
        return BUCKETS[1], f"scratch writes: {scratch}"
    hit = sorted(set(repo_touched) & set(gold))
    if hit:
        return BUCKETS[3], "touched " + ", ".join(hit[:3])
    return BUCKETS[2], "touched " + (", ".join(repo_touched[:3]) or f"(patch {patch_chars} chars, no file list)")


def audit(path: Path, tag: str, verbose: bool) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = data.get("tasks") or []
    if not tasks:
        return {"tag": tag, "path": str(path), "tasks": 0, "error": "no per-task records"}
    table: dict[str, dict[str, int]] = {b: {"localized": 0, "not_localized": 0} for b in BUCKETS}
    rows: list[str] = []
    for task in tasks:
        bucket, detail = classify(task)
        loc = "localized" if task.get("localized") else "not_localized"
        table[bucket][loc] += 1
        rows.append(f"| {task.get('task_id')} | {task.get('repo')} | {bucket} | {loc.replace('_', ' ')} "
                    f"| {int(task.get('patch_chars') or 0)} | {task.get('tool_calls')} "
                    f"| {task.get('duration_seconds', 0):.0f} | {detail} |")
    total = {b: table[b]["localized"] + table[b]["not_localized"] for b in BUCKETS}
    n = len(tasks)
    resolved = total[BUCKETS[0]]
    print(f"=== {tag} ({path}) ===")
    print(f"tasks: {n} | resolved: {resolved} ({resolved / n:.1%})")
    print()
    print(f"{'bucket':28} {'localized':>10} {'not loc.':>9} {'total':>6} {'share':>7}")
    print("-" * 64)
    for bucket in BUCKETS:
        loc, nloc = table[bucket]["localized"], table[bucket]["not_localized"]
        print(f"{bucket:28} {loc:>10} {nloc:>9} {total[bucket]:>6} {total[bucket] / n:>6.1%}")
    print()
    fails = n - resolved
    if fails:
        print("failure mix: " + " · ".join(
            f"{b.split()[0]} {total[b]}/{fails} ({total[b] / fails:.0%})" for b in BUCKETS[1:]))
        loc_fail = sum(table[b]["localized"] for b in BUCKETS[1:])
        print(f"failures whose task was localized: {loc_fail}/{fails} ({loc_fail / fails:.0%})")
    if verbose:
        print()
        print("| task | repo | bucket | localized | patch_chars | calls | s | detail |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- |")
        print("\n".join(rows))
    print()
    return {"tag": tag, "path": str(path), "tasks": n, "resolved": resolved,
            "buckets": {b: table[b] for b in BUCKETS}, "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--result", action="append", required=True,
                    help="path=tag, e.g. gemma4-agent/kaggle_results/v6-4-benchmark/agent_benchmark_result.json=V6.4")
    ap.add_argument("--out", type=Path, default=None, help="write a markdown report here")
    args = ap.parse_args()
    reports = []
    for spec in args.result:
        if "=" in spec:
            path_s, tag = spec.rsplit("=", 1)
        else:
            path_s, tag = spec, Path(spec).parent.name
        reports.append(audit(Path(path_s), tag, verbose=True))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Failure taxonomy audit (per-task buckets from recorded benchmark results)", "",
                 "Buckets: **N** no edit at all · **W** edited but no gold file · **R** edited a gold "
                 "fixable file and still failed · **P** resolved. Generated by "
                 "`tools/audit_failure_taxonomy.py`; read-only, no GPU.", ""]
        for rep in reports:
            if rep.get("error"):
                lines += [f"## {rep['tag']}", "", f"Skipped: {rep['error']}", ""]
                continue
            lines += [f"## {rep['tag']} — resolved {rep['resolved']}/{rep['tasks']}", "",
                      "| bucket | localized | not localized | total |", "| --- | --- | --- | --- |"]
            for bucket in BUCKETS:
                cell = rep["buckets"][bucket]
                lines.append(f"| {bucket} | {cell['localized']} | {cell['not_localized']} | "
                             f"{cell['localized'] + cell['not_localized']} |")
            lines += ["", "| task | repo | bucket | localized | patch_chars | calls | s | detail |",
                      "| --- | --- | --- | --- | --- | --- | --- | --- |", *rep["rows"], ""]
        args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
