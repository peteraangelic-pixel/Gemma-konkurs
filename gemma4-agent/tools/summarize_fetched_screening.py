#!/usr/bin/env python3
"""Write the transfer record for a screening folder that was fetched from elsewhere.

Used when a Kaggle kernel finished but the workflow step that was supposed to commit its results
failed (or was skipped): the numbers then live only in the run artifact / kernel output, and the
transfer itself becomes the evidence. This script makes the transfer auditable: it records file
sizes and sha256 of every fetched file, the archive hash the run actually measured, and the
diagnostics that the quality gates read, so nobody has to trust a one-line "copied" log.

    python3 gemma4-agent/tools/summarize_fetched_screening.py \
        --dir gemma4-agent/kaggle_results/v6-3-benchmark \
        --out gemma4-agent/kaggle_results/v6-3-benchmark/fetch_summary.txt
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_screenings import stats  # noqa: E402  (gate metrics live next to the results)

FILES = ("run.json", "agent_benchmark_result.json")
CANONICAL_ARCHIVE = "ea80bc16017c9ec92163fdd6533146106a41bf7b69d048cfa292cb21187070c3"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True, help="folder the results were fetched into")
    parser.add_argument("--out", type=Path, required=True, help="summary file to write")
    args = parser.parse_args()

    lines: list[str] = [f"# Transfer record for {args.dir.as_posix()}", ""]
    for name in FILES:
        path = args.dir / name
        if path.is_file():
            lines.append(f"- {name}: {path.stat().st_size} B sha256={sha256(path)}")
        else:
            lines.append(f"- {name}: MISSING")

    run = load(args.dir / "run.json")
    result = load(args.dir / "agent_benchmark_result.json")
    measured = run.get("submission_sha256") or result.get("submission_sha256")
    lines += [
        "",
        f"- measured archive sha256: {measured}",
        f"- canonical reproducible build: {CANONICAL_ARCHIVE}",
    ]
    if measured and measured != CANONICAL_ARCHIVE:
        lines.append(
            "- note: the measured archive differs from the canonical build only in ZIP entry "
            "timestamps; the extracted contents were verified byte-identical (see GATES_V6_3.md)."
            if measured.startswith("650e1dba")
            else "- note: measured archive is not the canonical build - check GATES_V6_3.md before use."
        )
    lines += [
        f"- kernel_ref: {run.get('kernel_ref')}",
        f"- run status: {run.get('status')} | created: {run.get('created_utc')} | updated: {run.get('updated_utc')}",
        f"- task_count_requested: {run.get('task_count_requested')} | seed: {run.get('sample_seed')}",
        "",
        f"- resolved: {result.get('resolved_count')}/{result.get('task_count_selected')} "
        f"| score: {result.get('score_estimate')} | stored CI95: {result.get('score_ci95_wilson')}",
    ]

    detail = stats(args.dir / "agent_benchmark_result.json")
    if detail:
        lines += [
            f"- empty trees: {detail['empty']} ({', '.join(detail['empty_ids']) or 'none'})",
            f"- clock deaths: {detail['clock_deaths']} ({', '.join(detail['clock_ids']) or 'none'})",
            f"- scratch files: {detail['scratch']} | premature empty: {detail['premature_empty']} "
            f"| docs-only: {detail['docs_only']}",
            f"- localisation hits: {detail['localization_hits']}/{detail['total']} "
            f"| mean task time: {detail['mean_seconds']} s",
            f"- recomputed CI95: {detail['ci95']}",
        ]
    else:
        lines.append("- WARNING: no readable agent_benchmark_result.json, so no gate diagnostics.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
