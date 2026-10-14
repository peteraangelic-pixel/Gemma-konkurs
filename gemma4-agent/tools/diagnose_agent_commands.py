#!/usr/bin/env python3
"""Diagnose what the agent actually did, from the raw kernel traces.

Why this exists: the committed trace summaries keep tool names and targets only, so the two biggest
failure buckets of the V6.4 full run cannot be explained from them:

  N (11 tasks, no change in the repo) - three of them called `edit_file` and still produced an empty
  diff. Was the call rejected (old_string not found), or was the change reverted later?
  R (8 tasks, gold file edited, tests still failed) - what commands did those sessions run, and in
  what order? Which arguments did the edits carry?

This tool walks the raw `trace_*.json` files downloaded from the kernel output (read-only), extracts
each tool call with its arguments and the observation that followed it, and writes a compact
markdown report: a command-head histogram, a per-task pre-edit call list, and full call-level
evidence for the focus tasks. Model free text is never included - only tool names, argument
summaries (path, lengths, command head) and short observation heads, so the report stays small and
carries no model prose.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

CALL_KEYS = ("function_call", "function_calls", "tool_call", "tool_calls", "tool_use",
             "function_call_part")
NAME_KEYS = ("name", "tool", "tool_name", "function_name", "function")
ARG_KEYS = ("args", "arguments", "input", "parameters", "kwargs")
EDIT_TOOLS = ("edit_file", "write_file", "submit_patch")
ERROR_MARKERS = ("error", "not found", "no match", "failed", "does not", "cannot", "invalid",
                 "could not", "unable")


def iter_events(root: object) -> tuple[list, str]:
    """Find the biggest list of step dicts inside a trace document."""
    if isinstance(root, list):
        return root, "<root list>"
    if isinstance(root, dict):
        best: tuple[list, str] = ([], "<none>")
        for key, value in root.items():
            if isinstance(value, list) and value and isinstance(value[0], (dict, list)):
                if len(value) > len(best[0]):
                    best = (value, key)
        return best
    return [], "<none>"


def extract_calls(node: object, out: list[dict], depth: int = 0) -> None:
    if depth > 6:
        return
    if isinstance(node, list):
        for item in node:
            extract_calls(item, out, depth + 1)
        return
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        if key in CALL_KEYS and value is not None:
            for call in (value if isinstance(value, list) else [value]):
                if not isinstance(call, dict):
                    continue
                name = next((call[c] for c in NAME_KEYS if isinstance(call.get(c), str)), None)
                args = next((call[c] for c in ARG_KEYS if isinstance(call.get(c), dict)), None)
                if args is None:
                    # Some writers store the arguments JSON-encoded as a string.
                    for candidate in ARG_KEYS:
                        raw = call.get(candidate)
                        if isinstance(raw, str) and raw.strip().startswith("{"):
                            try:
                                parsed = json.loads(raw)
                            except json.JSONDecodeError:
                                continue
                            if isinstance(parsed, dict):
                                args = parsed
                                break
                if name or args:
                    out.append({"tool": name or "<unnamed>", "args": args or {}})
                else:
                    # Shape like {"function_call": {"name": ..., "args": {...}}}: descend into it
                    # instead of dropping the call (the first version of this tool dropped all of
                    # them, which a synthetic trace caught before it reached the runner).
                    extract_calls(call, out, depth + 1)
            continue
        if isinstance(value, (dict, list)):
            extract_calls(value, out, depth + 1)


def extract_observation(node: object, depth: int = 0) -> str:
    """Return the text of the tool result attached to a step, if any."""
    if depth > 6:
        return ""
    if isinstance(node, dict):
        obs = node.get("observation")
        if isinstance(obs, dict):
            for key in ("content", "text", "result", "output"):
                if isinstance(obs.get(key), str):
                    return obs[key]
            extra = obs.get("extra")
            if isinstance(extra, dict) and isinstance(extra.get("content"), str):
                return extra["content"]
        if isinstance(obs, str):
            return obs
        for value in node.values():
            if isinstance(value, (dict, list)):
                text = extract_observation(value, depth + 1)
                if text:
                    return text
    if isinstance(node, list):
        for item in node:
            text = extract_observation(item, depth + 1)
            if text:
                return text
    return ""


BORING_HEADS = {"cd", "echo", "export", "true", "set", "if", "for", "fi", "then", "python", "python3"}


def leader(command: str) -> str:
    """The first informative command in a shell line - what the session was actually doing.

    A chain like `cd /workspace && python3 -c ... | head` would otherwise be counted as `cd`, which
    says nothing about the behaviour under diagnosis.
    """
    for part in re.split(r"&&|\|\||;|\|", command or ""):
        tokens = [tok for tok in re.split(r"\s+", part.strip()) if tok and not tok.startswith("-")]
        if not tokens:
            continue
        head = tokens[0].split("/")[-1]
        if head in BORING_HEADS and len(tokens) > 1 and head.startswith("python"):
            return "python3 -c" if tokens[1] == "-c" else "python3"
        if head not in BORING_HEADS:
            return head
    tokens = [tok for tok in re.split(r"\s+", (command or "").strip()) if tok]
    return tokens[0].split("/")[-1] if tokens else "(empty)"


def command_head(command: str) -> str:
    tokens = [t for t in re.split(r"\s+", command.strip()) if t and not t.startswith("-")]
    return " ".join(tokens[:2])[:60] or "(empty)"


def summarise_call(call: dict) -> tuple[str, str, str]:
    """Return (tool, argument summary, command text) for one call."""
    tool = str(call["tool"])
    args = call["args"] or {}
    command = ""
    parts: list[str] = []
    for key in ("command", "cmd", "code"):
        if isinstance(args.get(key), str):
            command = args[key]
            parts.append(f"{key}={command_head(command)}")
    for key in ("filepath", "path", "file", "target", "filename"):
        if isinstance(args.get(key), str):
            parts.append(f"{key}={args[key][:80]}")
    for key in ("old_string", "new_string", "content"):
        if isinstance(args.get(key), str):
            parts.append(f"{key}_len={len(args[key])}")
    for key in ("start_line", "end_line", "allow_multiple", "k"):
        if key in args:
            parts.append(f"{key}={args[key]}")
    return tool, ", ".join(parts) or "(no recognised args)", command


def load_trace(path: Path) -> tuple[str, list[dict], str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    task = path.stem[6:] if path.stem.startswith("trace_") else path.stem
    for key in ("task", "task_id", "instance_id"):
        value = data.get(key) if isinstance(data, dict) else None
        if isinstance(value, str) and value:
            task = value
            break
    events, container = iter_events(data)
    return task, events, container


def analyse(traces_dir: Path, focus: list[str], out: Path | None, max_obs: int = 220) -> int:
    files = sorted(traces_dir.rglob("trace_*.json"))
    if not files:
        print(f"no trace_*.json under {traces_dir}")
        return 1
    command_heads: Counter = Counter()
    lines: list[str] = ["# What the agent actually ran (raw V6.4 kernel traces)", "",
                        f"Traces read: {len(files)}. Tool arguments and short observation heads only; "
                        "no model prose.", ""]
    per_task: dict[str, list[str]] = {}
    task_index: dict[str, str] = {}
    for path in files:
        task, events, container = load_trace(path)
        calls: list[dict] = []
        observations: list[str] = []
        for event in events:
            found: list[dict] = []
            extract_calls(event, found)
            calls.extend(found or [])
            observations.append(extract_observation(event))
        if not calls:
            lines.append(f"- `{task}`: no tool calls parsed (container `{container}`, {len(events)} events)")
            continue
        rows: list[str] = []
        first_edit_index = None
        for index, call in enumerate(calls):
            tool, summary, command = summarise_call(call)
            if command:
                command_heads[leader(command)] += 1
            if first_edit_index is None and tool in EDIT_TOOLS:
                first_edit_index = index
            rows.append(f"  {index + 1:2}. {tool}: {summary}")
            if task in focus and tool in EDIT_TOOLS:
                observation = observations[index] if index < len(observations) else ""
                head = " ".join(observation.split())[:max_obs]
                flagged = any(marker in observation.lower() for marker in ERROR_MARKERS)
                rows.append(f"      -> obs[{'ERROR-LIKE' if flagged else 'ok-ish'}]: {head or '(empty)'}")
        pre_edit = f" | pre-edit calls: {first_edit_index}" if first_edit_index is not None else " | NO EDIT"
        per_task[task] = rows
        task_index[task] = pre_edit
    lines += ["", "## Command-head histogram (first token of every `run_command`)", ""]
    for head, count in command_heads.most_common(30):
        lines.append(f"- `{head}`: {count}")
    lines += ["", "## Per-task call lists", ""]
    for task in sorted(per_task):
        lines += [f"### {task}{task_index.get(task, '')}", "", "```", *per_task[task], "```", ""]
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"report: {out} ({len(lines)} lines)")
    else:
        print("\n".join(lines))
    print(f"traces parsed: {len(per_task)}/{len(files)}; command heads: {sum(command_heads.values())}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--traces-dir", type=Path, required=True)
    ap.add_argument("--focus", default="", help="comma-separated task ids for call-level evidence")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    focus = [t.strip() for t in args.focus.split(",") if t.strip()]
    return analyse(args.traces_dir, focus, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
