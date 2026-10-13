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

    (args.out / "trace-operations.json").write_text(
        json.dumps({"tasks": summaries, "failures": failures}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

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
    for row in summaries[:32]:
        first = row["first_write_call"]
        print(f"  {row['kernel']}/{row['task']:18} events={row['events']:>3} dur={row['duration_s']}s "
              f"tools={list(row['tool_counts'])[:4]} first_write={first['tool'] if first else None}"
              f"@{first.get('t') if first else '-'} submits={len(row['submit_patch_calls'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
