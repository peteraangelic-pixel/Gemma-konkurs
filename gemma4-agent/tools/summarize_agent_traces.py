#!/usr/bin/env python3
"""Summarise the harness per-task traces into OPERATIONAL facts only.

The 2026-10-13 review asked for exactly this: timing, tool names, the moment of the first edit and
any submit_patch call - not the model's reasoning. The traces live in
candidate_eval_results/traces/trace_<task>.json inside the Kaggle kernel output and are 50-177 KB
each; they are NOT committed. This script writes two small artifacts:

  trace-operations.json   per task: event count, ordered tool sequence with relative timestamps,
                          counts per tool, the first write-like call, every submit_patch call
  trace-schema-census.md  key paths, value types, counts and maximum string lengths - enough to
                          verify the parse without copying a single character of model text

Hard rule enforced here: no string longer than MAX_STRING characters is ever written, and keys
whose names look like free text (thought/text/reasoning/message body) are never copied at all.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MAX_STRING = 160
MAX_SEQUENCE = 150  # keep the artifact small; a truncated flag says when it bit
TEXTY_KEYS = re.compile(r"(thought|thinking|reasoning|text|body|content_text|message_text)", re.I)
TOOL_KEYS = ("tool", "tool_name", "name", "function", "function_name", "action")
TIME_KEYS = ("timestamp", "time", "ts", "create_time", "created_at", "start_time", "startTime")
PATH_KEYS = ("path", "file", "file_path", "filepath", "filename", "target", "target_file")
WRITE_TOOLS = ("edit_file", "write_file", "apply_patch", "patch", "create_file", "str_replace")
CONTAINER_KEYS = ("events", "trace", "turns", "messages", "steps", "history", "session", "runs",
                  "items", "records")


def short(value: object) -> object:
    if isinstance(value, str):
        return value if len(value) <= MAX_STRING else value[:MAX_STRING] + f"...[{len(value)} chars]"
    return value


def find_events(root: object) -> tuple[list, str]:
    if isinstance(root, list):
        return root, "<root list>"
    if isinstance(root, dict):
        for key in CONTAINER_KEYS:
            value = root.get(key)
            if isinstance(value, list) and value and isinstance(value[0], (dict, list)):
                return value, key
        best: tuple[list, str] = ([], "<none>")
        for key, value in root.items():
            if isinstance(value, list) and len(value) > len(best[0]):
                if value and isinstance(value[0], (dict, list)):
                    best = (value, key)
        return best
    return [], "<none>"


def collect_tool_calls(event: object, out: list[dict], depth: int = 0) -> None:
    """Walk one event and append every tool/function call found, without touching free text."""
    if depth > 6:
        return
    if isinstance(event, list):
        for item in event:
            collect_tool_calls(item, out, depth + 1)
        return
    if not isinstance(event, dict):
        return

    for key, value in event.items():
        if TEXTY_KEYS.search(key):
            if isinstance(value, str):
                out.append({"kind": "text_part", "chars": len(value)})
            continue
        if key in ("function_call", "function_calls", "tool_call", "tool_calls", "tool_use",
                   "function_call_part") and value is not None:
            for call in (value if isinstance(value, list) else [value]):
                if isinstance(call, dict):
                    name = None
                    args = None
                    for candidate in TOOL_KEYS:
                        if isinstance(call.get(candidate), str):
                            name = call[candidate]
                            break
                    for candidate in ("args", "arguments", "input", "parameters", "kwargs"):
                        if isinstance(call.get(candidate), dict):
                            args = call[candidate]
                            break
                    entry: dict = {"kind": "call", "tool": short(name) if name else "<unnamed>"}
                    if args:
                        entry["arg_keys"] = sorted(args)[:12]
                        for candidate in PATH_KEYS:
                            if isinstance(args.get(candidate), str):
                                entry["target"] = short(args[candidate])
                                break
                    out.append(entry)
            continue
        if isinstance(value, (dict, list)):
            collect_tool_calls(value, out, depth + 1)


def event_info(event: object) -> dict:
    calls: list[dict] = []
    collect_tool_calls(event, calls)
    time_value = None
    if isinstance(event, dict):
        for key in TIME_KEYS:
            value = event.get(key)
            if isinstance(value, (int, float, str)):
                time_value = value
                break
        if time_value is None:
            for value in event.values():
                if isinstance(value, dict):
                    for key in TIME_KEYS:
                        if isinstance(value.get(key), (int, float, str)):
                            time_value = value[key]
                            break
    return {"time": time_value, "calls": calls}


def as_seconds(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def kernel_name(trace_path: Path, root: Path) -> str:
    """Name the kernel a trace came from; four tasks ran in BOTH matrices and their behaviours
    differ wildly (rich_3105: 22 calls/315 s in the mini-screen vs 7 calls/43 s in the full run),
    so a summary without the origin is ambiguous - caught on 2026-10-13 after the first run."""
    rel = trace_path.relative_to(root)
    return rel.parts[0] if len(rel.parts) > 1 else "<unknown>"


def summarise(trace_path: Path, root: Path) -> dict:
    data = json.loads(trace_path.read_text(encoding="utf-8", errors="replace"))
    events, container = find_events(data)
    infos = [event_info(event) for event in events]

    times = [as_seconds(info["time"]) for info in infos]
    times = [t for t in times if t is not None]
    base = min(times) if times else None

    sequence: list[dict] = []
    tool_sequence_full: list[str] = []
    truncated = False
    counts: dict[str, int] = {}
    first_write: dict | None = None
    submits: list[dict] = []
    text_parts = 0

    for index, info in enumerate(infos):
        rel = None
        absolute = as_seconds(info["time"])
        if absolute is not None and base is not None:
            rel = round(absolute - base, 1)
        for call in info["calls"]:
            if call.get("kind") != "call":
                text_parts += 1
                continue
            tool = str(call.get("tool", "<unnamed>"))
            counts[tool] = counts.get(tool, 0) + 1
            tool_sequence_full.append(tool)
            entry = {"i": index, "tool": tool}
            if rel is not None:
                entry["t"] = rel
            if call.get("target"):
                entry["target"] = call["target"]
            if len(sequence) < MAX_SEQUENCE:
                sequence.append(entry)
            else:
                truncated = True
            if first_write is None and any(w in tool for w in WRITE_TOOLS):
                first_write = dict(entry)
            if "submit" in tool:
                submits.append(dict(entry))

    return {
        "kernel": kernel_name(trace_path, root),
        "task": trace_path.stem.replace("trace_", ""),
        "events": len(events),
        "container_key": container,
        "duration_s": round(max(times) - base, 1) if len(times) > 1 and base is not None else None,
        "tool_counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "first_write_call": first_write,
        "submit_patch_calls": submits,
        "text_parts_seen": text_parts,
        "sequence": sequence,
        "tool_sequence_full": tool_sequence_full,
        "sequence_truncated": truncated,
    }


def census(root: object, path: str, acc: dict, depth: int = 0) -> None:
    if depth > 8:
        return
    if isinstance(root, dict):
        for key, value in root.items():
            child = f"{path}.{key}" if path else key
            acc.setdefault(child, {"count": 0, "types": set(), "max_len": 0})
            acc[child]["count"] += 1
            acc[child]["types"].add(type(value).__name__)
            if isinstance(value, str):
                acc[child]["max_len"] = max(acc[child]["max_len"], len(value))
            census(value, child, acc, depth + 1)
    elif isinstance(root, list):
        for item in root[:50]:
            census(item, f"{path}[]", acc, depth + 1)


WRITE_TOOLS_AGG = ("edit_file", "write_file", "apply_patch", "create_file", "str_replace")


def aggregate(summaries: list[dict]) -> list[dict]:
    """Per-kernel mechanism metrics, designed to be pre-registered (the V6.4 metric M5).

    'tasks with any write attempt' is the only one that answers the question the V6.3 diagnosis
    left open - whether a session ever tried to edit at all - and it is reported next to, never
    instead of, the resolved count.
    """
    by_kernel: dict[str, list[dict]] = {}
    for row in summaries:
        by_kernel.setdefault(row["kernel"], []).append(row)

    out: list[dict] = []
    for kernel in sorted(by_kernel):
        rows = by_kernel[kernel]
        write_attempts = [r for r in rows
                          if any(r["tool_counts"].get(tool) for tool in WRITE_TOOLS_AGG)]
        first_times = [r["first_write_call"]["t"] for r in write_attempts
                       if r["first_write_call"] and r["first_write_call"].get("t") is not None]
        first_times.sort()
        median_first = first_times[len(first_times) // 2] if first_times else None
        # Call index of the first write, so the V6.4 call-4 deadline can be checked directly
        # instead of being inferred from wall-clock times.
        first_indices = sorted(r["first_write_call"]["i"] for r in write_attempts
                               if r["first_write_call"] and r["first_write_call"].get("i") is not None)
        median_index = first_indices[len(first_indices) // 2] if first_indices else None
        within_deadline = sum(1 for i in first_indices if i <= 4)

        def max_run(tool_set: tuple[str, ...]) -> int:
            """Longest run of consecutive calls from that set, counted over the FULL call list.

            Uses tool_sequence_full, not the truncated display sequence: on the first version the
            sequence cap of 150 events silently reported 43 consecutive submit_patch calls where
            requests_6757 actually made 48.
            """
            best = run = 0
            for row in rows:
                run = 0
                for tool in row.get("tool_sequence_full") or [e["tool"] for e in row["sequence"]]:
                    run = run + 1 if tool in tool_set else 0
                    best = max(best, run)
            return best

        # Repository edit = a write call whose target is a relative path, i.e. it lands inside the
        # repository tree. Added BEFORE the V6.4 mini-screen ran, because the V6.3 evidence showed
        # that counting every write as an "edit" is wrong: fastapi_15745's only write was
        # /tmp/locate.py (absolute, outside the tree) and its diff stayed empty, while rich_3006
        # wrote /tmp/repro.py and then made a real repository edit. Absolute writes are reported
        # separately, never folded into the edit coverage.
        def first_repo_write(row: dict) -> dict | None:
            for call in row["sequence"]:
                if call.get("tool") not in WRITE_TOOLS_AGG:
                    continue
                target = str(call.get("target") or "")
                if target and not target.startswith("/"):
                    return call
            return None

        repo_writes = {r["task"]: first_repo_write(r) for r in rows}
        repo_rows = [r for r in rows if repo_writes[r["task"]]]
        repo_indices = sorted(c["i"] for c in repo_writes.values() if c and c.get("i") is not None)
        repo_within_deadline = sum(1 for i in repo_indices if i <= 4)
        repo_times = sorted(c["t"] for c in repo_writes.values()
                            if c and c.get("t") is not None)
        repo_median_time = repo_times[len(repo_times) // 2] if repo_times else None

        submit_calls = {r["task"]: len(r["submit_patch_calls"]) for r in rows}
        outside = sorted({call.get("target") for r in rows for call in r["sequence"]
                          if call.get("tool") in WRITE_TOOLS_AGG
                          and str(call.get("target", "")).startswith("/")})
        out.append({
            "kernel": kernel,
            "tasks": len(rows),
            "tasks_with_write_attempt": len(write_attempts),
            "write_coverage": f"{len(write_attempts)}/{len(rows)}",
            "tasks_without_write_attempt": sorted(r["task"] for r in rows
                                                  if r not in write_attempts),
            "median_first_write_s": median_first,
            "median_first_write_index": median_index,
            "tasks_first_write_within_call_4": f"{within_deadline}/{len(rows)}",
            "max_consecutive_submit_patch": max_run(("submit_patch",)),
            "max_consecutive_edits": max_run(WRITE_TOOLS_AGG),
            "submit_patch_total": sum(submit_calls.values()),
            "tasks_with_repeated_submit": {t: n for t, n in submit_calls.items() if n >= 2},
            "absolute_write_targets": outside,
            "repo_write_coverage": f"{len(repo_rows)}/{len(rows)}",
            "tasks_without_repo_write": sorted(r["task"] for r in rows
                                               if not repo_writes[r["task"]]),
            "median_first_repo_write_s": repo_median_time,
            "median_first_repo_write_index": (repo_indices[len(repo_indices) // 2]
                                              if repo_indices else None),
            "tasks_repo_write_within_call_4": f"{repo_within_deadline}/{len(rows)}",
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces-dir", type=Path, required=True,
                        help="directory containing trace_*.json (one subdir per kernel is fine)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    trace_files = sorted(args.traces_dir.rglob("trace_*.json"))
    summaries = []
    failures = []
    census_acc: dict = {}
    for path in trace_files:
        try:
            summaries.append(summarise(path, args.traces_dir))
        except Exception as exc:  # noqa: BLE001 - a broken trace must not hide the rest
            failures.append({"trace": path.name, "error": f"{type(exc).__name__}: {exc}"[:200]})
        try:
            census(json.loads(path.read_text(encoding="utf-8", errors="replace")), "", census_acc)
        except Exception:  # noqa: BLE001
            pass

    aggregates = aggregate(summaries)
    (args.out / "trace-operations.json").write_text(
        json.dumps({"tasks": summaries, "failures": failures, "aggregates": aggregates},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    agg_lines = ["# Mechanism metrics per kernel (read-only trace analysis)", "",
                 "Pre-registered as M5 in GATES_V6_4.md; reported next to the resolved count, "
                 "never instead of it.", "",
                 "| kernel | tasks | write coverage | without any write | median first write | "
                 "repo-edit coverage | median first repo edit | "
                 "max consec. submit | max consec. edits | submit calls | repeated submits |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for a in aggregates:
        agg_lines.append(
            f"| `{a['kernel']}` | {a['tasks']} | **{a['write_coverage']}** | "
            f"{len(a['tasks_without_write_attempt'])} | {a['median_first_write_s']} s "
            f"(call {a['median_first_write_index']}, in-deadline {a['tasks_first_write_within_call_4']}) | "
            f"**{a['repo_write_coverage']}** | "
            f"{a['median_first_repo_write_s']} s (call {a['median_first_repo_write_index']}, "
            f"in-deadline {a['tasks_repo_write_within_call_4']}) | "
            f"{a['max_consecutive_submit_patch']} | {a['max_consecutive_edits']} | "
            f"{a['submit_patch_total']} | {a['tasks_with_repeated_submit'] or '—'} |")
    for a in aggregates:
        if a["tasks_without_repo_write"]:
            agg_lines += ["", f"- `{a['kernel']}` tasks with NO repository edit "
                              f"(scratch or nothing at all): "
                              f"{', '.join(a['tasks_without_repo_write'])}"]
        if a["tasks_without_write_attempt"]:
            agg_lines += ["", f"- `{a['kernel']}` tasks without any write attempt: "
                              f"{', '.join(a['tasks_without_write_attempt'])}"]
        if a["absolute_write_targets"]:
            agg_lines += [f"- `{a['kernel']}` write targets outside the relative tree: "
                          f"{', '.join(str(t) for t in a['absolute_write_targets'])}"]
    (args.out / "trace-aggregate.md").write_text("\n".join(agg_lines) + "\n", encoding="utf-8")

    lines = ["# Trace schema census (keys and types only - no model text)", "",
             f"traces read: {len(trace_files)} | parse failures: {len(failures)}", "",
             "| key path | occurrences | types | max string length |", "| --- | --- | --- | --- |"]
    for key in sorted(census_acc):
        row = census_acc[key]
        lines.append(f"| `{key}` | {row['count']} | {', '.join(sorted(row['types']))} "
                     f"| {row['max_len']} |")
    if failures:
        lines += ["", "## Parse failures", ""] + [f"- {f['trace']}: {f['error']}" for f in failures]
    (args.out / "trace-schema-census.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"traces summarised: {len(summaries)} | failures: {len(failures)}")
    for a in aggregates:
        print(f"  [{a['kernel']}] write coverage {a['write_coverage']}, "
              f"median first write {a['median_first_write_s']} s (call index "
              f"{a['median_first_write_index']}, within call 4: {a['tasks_first_write_within_call_4']}), "
              f"max consecutive submit_patch {a['max_consecutive_submit_patch']}, "
              f"absolute write targets {a['absolute_write_targets'] or 'none'}")
    for row in summaries[:32]:
        first = row["first_write_call"]
        print(f"  {row['kernel']}/{row['task']:18} events={row['events']:>3} dur={row['duration_s']}s "
              f"tools={list(row['tool_counts'])[:4]} first_write={first['tool'] if first else None}"
              f"@{first.get('t') if first else '-'} submits={len(row['submit_patch_calls'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
