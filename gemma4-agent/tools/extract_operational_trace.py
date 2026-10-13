#!/usr/bin/env python3
"""Extract operational traces from read-only Kaggle kernel logs and output listings.

Purpose (from the 2026-10-13 review): find out why the agent ends sessions without writing any
edit. We look for OPERATIONAL traces only - timing, tool names, the moment of the first edit and
any submit_patch call - not at the model's reasoning. The kernel log is the only surviving record,
and the runner prints one line per task, so the extractor is deliberately honest about what it did
not find.

Inputs are produced without GPU by 'kaggle kernels logs' and 'kaggle kernels output'; this script
never runs a kernel.

    python3 gemma4-agent/tools/extract_operational_trace.py \
        --logs-dir <dir with *.log> --outputs-dir <dir with one subdir per kernel> --out <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

# Words that mark an OPERATIONAL line we care about. Chosen from the tools the agent can call and
# from the runner's own prints; deliberately no reasoning-related words.
MARKERS = (
    "benchmark task", "submit_patch", "edit_file", "write_file", "read_file", "run_command",
    "get_status", "tool call", "tool_call", "tool_use", "function_call", "function call",
    "turn ", "session", "tool calls", "patch_chars", "resolved", "localiz", "empty patch",
    "budget_warning", "traceback", "error:", "exception", "warning",
)
HEAD_LINES = 40
TAIL_LINES = 40
MAX_MATCHES = 1500
LINE_CAP = 400
HASH_LIMIT_BYTES = 20 * 1024 * 1024  # do not hash giant binaries, just record their size


def sha256(path: Path, limit: int = HASH_LIMIT_BYTES) -> str:
    digest = hashlib.sha256()
    if path.stat().st_size > limit:
        with path.open("rb") as handle:
            digest.update(handle.read(limit))
        return digest.hexdigest() + f" (first {limit} bytes)"
    digest.update(path.read_bytes())
    return digest.hexdigest()


def excerpt(path: Path, out_path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    matches: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        cleaned = " ".join(line.split())[:LINE_CAP]
        if not cleaned:
            continue
        lowered = cleaned.casefold()
        if any(marker in lowered for marker in MARKERS):
            matches.append((number, cleaned))

    kept = matches[:MAX_MATCHES]
    body: list[str] = [
        f"# {path.name}",
        f"- total lines: {len(lines)} | operational matches: {len(matches)}"
        + (f" (showing first {MAX_MATCHES})" if len(matches) > MAX_MATCHES else ""),
        "",
        f"## first {min(HEAD_LINES, len(lines))} lines",
        *(f"    {line[:LINE_CAP]}" for line in lines[:HEAD_LINES]),
        "",
        "## operational matches",
        *(f"  {number}: {line}" for number, line in kept),
        "",
        f"## last {min(TAIL_LINES, len(lines))} lines",
        *(f"    {line[:LINE_CAP]}" for line in lines[-TAIL_LINES:]),
        "",
    ]
    out_path.write_text("\n".join(body), encoding="utf-8")
    return {"log": path.name, "lines": len(lines), "matches": len(matches),
            "excerpt_bytes": out_path.stat().st_size}


def listing(outputs_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(outputs_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(outputs_dir).as_posix()
        rows.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256(path)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--outputs-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"logs": [], "outputs": [], "outputs_row_count": 0}

    for log_path in sorted(args.logs_dir.glob("*.log")):
        summary["logs"].append(excerpt(log_path, args.out / f"{log_path.stem}-excerpt.txt"))

    if args.outputs_dir.is_dir():
        rows = listing(args.outputs_dir)
        summary["outputs"] = rows
        summary["outputs_row_count"] = len(rows)
        table = ["# Output files downloaded read-only from the Kaggle kernels", ""]
        if rows:
            table += ["| bytes | sha256 | path |", "| --- | --- | --- |"]
            table += [f"| {r['bytes']} | {r['sha256'][:16]} | `{r['path']}` |" for r in rows]
        else:
            table.append("_no output files were downloaded_")
        (args.out / "outputs-listing.md").write_text("\n".join(table) + "\n", encoding="utf-8")

    (args.out / "trace-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"logs analysed: {len(summary['logs'])}")
    for row in summary["logs"]:
        print(f"  {row['log']}: {row['lines']} lines, {row['matches']} operational matches, "
              f"excerpt {row['excerpt_bytes']} B")
    print(f"output files listed: {summary['outputs_row_count']}")
    for row in summary["outputs"][:40]:
        print(f"  {row['bytes']:>10} B  {row['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
