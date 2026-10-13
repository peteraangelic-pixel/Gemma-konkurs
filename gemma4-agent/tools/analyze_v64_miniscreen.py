#!/usr/bin/env python3
"""Evaluate the V6.4 mini-screen against the pre-registered expectations P1-P5.

Written BEFORE the run finished, so the verdict is mechanical rather than narrated after the fact.

Inputs (both committed by the workflows):
  --result  kaggle_results/v6-4-miniscreen/agent_benchmark_result.json   (per-task patch/resolved)
  --traces  kaggle_results/v6-4-miniscreen/traces/trace-operations.json  (operational tool calls)

P1  >= 4/6 tasks have a REPOSITORY edit (relative target) within call 4   baseline 0/6
P2  <= 1/6 empty trees                                                    baseline 5/6
P3  submit_patch never appears                                            baseline tens of calls
P4  fastapi_15030 does not repeat a run of >= 3 edit calls                baseline 9 in a row
P5  fastapi_14077 stays resolved (regression control)                     baseline PASS
Falsification: P1 <= 2/6 or P2 > 1/6  =>  the prompt rules do not change behaviour (E6).

Read-only: prints a report, writes nothing unless --out is given.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

WRITE_TOOLS = ("edit_file", "write_file", "apply_patch", "create_file", "str_replace")
MINI_TASKS = ("rich_3105", "rich_3043", "fastapi_15030",
              "requests_6757", "fastapi_15745", "fastapi_14077")


def load_traces(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text())
    out: dict[str, dict] = {}
    for task in data.get("tasks", []):
        out[task["task"]] = task
    return out


def first_repo_edit_call(sequence: list[dict]) -> dict | None:
    """First write call whose target is a relative path, i.e. lands inside the repository."""
    for call in sequence:
        if call.get("tool") not in WRITE_TOOLS:
            continue
        target = str(call.get("target") or "")
        if target and not target.startswith("/"):
            return call
    return None


def max_edit_run(sequence: list[dict]) -> int:
    best = run = 0
    for call in sequence:
        run = run + 1 if call.get("tool") in WRITE_TOOLS else 0
        best = max(best, run)
    return best


def absolute_writes(sequence: list[dict]) -> list[str]:
    return sorted({str(c.get("target")) for c in sequence
                   if c.get("tool") in WRITE_TOOLS and str(c.get("target") or "").startswith("/")})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--result", type=Path, required=True)
    ap.add_argument("--traces", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    results = {t["task_id"]: t for t in json.loads(args.result.read_text())["tasks"]}
    traces = load_traces(args.traces)

    rows = []
    for task in MINI_TASKS:
        res = results.get(task, {})
        trace = traces.get(task, {})
        sequence = trace.get("sequence") or []
        repo_call = first_repo_edit_call(sequence)
        submit_calls = [c for c in sequence if c.get("tool") == "submit_patch"]
        rows.append({
            "task": task,
            "patch_chars": res.get("patch_chars"),
            "resolved": res.get("resolved"),
            "repo_edit_call": repo_call.get("i") if repo_call else None,
            "repo_edit_target": repo_call.get("target") if repo_call else None,
            "repo_edit_time": repo_call.get("t") if repo_call else None,
            "max_edit_run": max_edit_run(sequence),
            "submit_calls": len(submit_calls),
            "absolute_writes": absolute_writes(sequence),
            "calls": len(sequence),
        })

    repo_in_deadline = [r for r in rows if r["repo_edit_call"] is not None and r["repo_edit_call"] <= 4]
    repo_any = [r for r in rows if r["repo_edit_call"] is not None]
    empty = [r for r in rows if r["patch_chars"] == 0]
    submits = sum(r["submit_calls"] for r in rows)
    f15030 = next(r for r in rows if r["task"] == "fastapi_15030")
    f14077 = next(r for r in rows if r["task"] == "fastapi_14077")

    checks = [
        ("P1", len(repo_in_deadline) >= 4,
         f"edycja w repo w terminie call 4: {len(repo_in_deadline)}/6 (cel >= 4/6, baseline 0/6)"),
        ("P2", len(empty) <= 1,
         f"puste drzewa: {len(empty)}/6 (cel <= 1/6, baseline 5/6)"),
        ("P3", submits == 0,
         f"wywołania submit_patch: {submits} (cel 0, baseline dziesiątki)"),
        ("P4", f15030["max_edit_run"] < 3,
         f"fastapi_15030 najdłuższa seria edycji: {f15030['max_edit_run']} (cel < 3, baseline 9)"),
        ("P5", bool(f14077["resolved"]),
         f"fastapi_14077 rozwiązany: {f14077['resolved']} (cel PASS, baseline PASS)"),
    ]

    lines = ["# V6.4 mini-screen — wynik wobec pre-rejestracji (P1-P5)", ""]
    lines.append("| zadanie | patch | PASS | 1. edycja w repo | plik | czas | seria edycji | submit | zapisy /tmp |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        lines.append(
            f"| `{r['task']}` | {r['patch_chars']} | {'TAK' if r['resolved'] else 'nie'} | "
            f"{r['repo_edit_call'] if r['repo_edit_call'] is not None else '**brak**'} | "
            f"{r['repo_edit_target'] or '—'} | "
            f"{r['repo_edit_time'] if r['repo_edit_time'] is not None else '—'} | "
            f"{r['max_edit_run']} | {r['submit_calls']} | {', '.join(r['absolute_writes']) or '—'} |")
    lines += ["", "## Werdykt mechaniczny", ""]
    for code, ok, detail in checks:
        lines.append(f"- **{code}**: {'SPEŁNIONE' if ok else 'NARUSZONE'} — {detail}")
    falsified = len(repo_in_deadline) <= 2 or len(empty) > 1
    lines += [
        "",
        ("> **FALSYFIKACJA (E6):** P1 <= 2/6 lub P2 > 1/6 — reguły promptu **nie zmieniają zachowania**; "
         "następne dźwignie (telemetria, parametry, architektura) dostają osobny test, bez dokładania reguł."
         if falsified else
         "> Żadna z dwóch przesłanek falsyfikacji nie zaszła (P1 >= 3/6 i P2 <= 1/6). "
         "E5 obowiązuje: to wciąż nie jest prognoza wyniku — rozstrzyga pełny przebieg."),
        "",
        f"- edycja w repo: pokrycie {len(repo_any)}/6, w terminie call 4: {len(repo_in_deadline)}/6",
        f"- puste drzewa: {len(empty)}/6 = {', '.join(r['task'] for r in empty) or 'brak'}",
        f"- rozwiązane: {sum(1 for r in rows if r['resolved'])}/6",
    ]
    report = "\n".join(lines) + "\n"
    print(report)
    if args.out:
        args.out.write_text(report)
        print(f"zapisano: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
