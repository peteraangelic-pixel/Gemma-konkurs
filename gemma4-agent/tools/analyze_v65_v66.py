#!/usr/bin/env python3
"""Evaluate a full 30-task run against its pre-registered expectations (V6.5 / V6.6).

Written the night before the runs finished, so the verdict is computed from the committed artefacts
instead of being narrated afterwards.

Usage:
  python3 gemma4-agent/tools/analyze_v65_v66.py --folder v6-5-benchmark --tag V6.5 \
      --reference v6-4-benchmark --expect-first-edit-call-4 12 --expect-solved 9
  python3 gemma4-agent/tools/analyze_v65_v66.py --folder v6-6-benchmark --tag V6.6 \
      --reference v6-4-benchmark --expect-solved 11 --expect-only-outside-writes 0

Result-level metrics need only agent_benchmark_result.json; trace-level metrics (R1, R3) need
traces/trace-operations.json and are reported as "traces missing" until the read-only trace
workflow has run.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "gemma4-agent" / "kaggle_results"
WRITE_TOOLS = ("edit_file", "write_file", "apply_patch", "create_file", "str_replace")
CLOCK_CAP = 315.0
EARLY_END = 280.0
DOCS_RE = re.compile(r"(^|/)(docs|doc)(/|$)|\.md$|\.rst$")


def load_result(folder: str) -> dict:
    path = RESULTS / folder / "agent_benchmark_result.json"
    if not path.is_file():
        raise SystemExit(f"no result JSON at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_traces(folder: str) -> dict[str, dict] | None:
    path = RESULTS / folder / "traces" / "trace-operations.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {t["task"]: t for t in data.get("tasks", [])}


def repo_edits_in_call_4(trace: dict) -> bool:
    for call in trace.get("sequence") or []:
        if call.get("tool") in WRITE_TOOLS:
            target = str(call.get("target") or "")
            if target and not target.startswith("/") and int(call.get("i") or 0) <= 4:
                return True
    return False


def only_outside_writes(trace: dict) -> bool:
    """True when the session wrote something, but never inside the repository tree."""
    writes = [c for c in (trace.get("sequence") or []) if c.get("tool") in WRITE_TOOLS]
    if not writes:
        return False
    return all(str(c.get("target") or "").startswith("/") for c in writes)


def gates(result: dict) -> dict:
    scratch = premature = docs_only = empty = 0
    for task in result["tasks"]:
        files = task.get("touched_files") or []
        patch = task["patch_chars"]
        dur = task["duration_seconds"]
        # scratch = a tracked file that is not a source/test/config path we recognise
        junk = [f for f in files
                if not re.match(r"^(fastapi|rich|requests|httpx|src|tests|docs_src|pydantic)/", str(f))
                and Path(str(f)).name not in ("tox.ini", "setup.py", "pyproject.toml", "setup.cfg")]
        if junk and patch > 0:
            scratch += 1
        if patch == 0 and dur < EARLY_END:
            premature += 1
        if files and all(DOCS_RE.search(str(f)) for f in files):
            docs_only += 1
        if patch == 0:
            empty += 1
    return {"scratch": scratch, "premature": premature, "docs_only": docs_only, "empty": empty}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--folder", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--reference", default="v6-4-benchmark")
    ap.add_argument("--expect-solved", type=int, default=None)
    ap.add_argument("--expect-first-edit-call-4", type=int, default=None)
    ap.add_argument("--expect-only-outside-writes", type=int, default=None)
    ap.add_argument("--reference-only-outside-writes", type=int, default=4,
                    help="baseline count of 'only writes outside the repo' tasks (V6.4: 4)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    result = load_result(args.folder)
    traces = load_traces(args.folder)
    ref = load_result(args.reference)
    ref_traces = load_traces(args.reference)

    resolved = result["resolved_count"]
    total = result["task_count_selected"]
    ci = [round(x * 100, 1) for x in result["score_ci95_wilson"]]
    g = gates(result)

    ref_tasks = {t["task_id"]: t for t in ref["tasks"]}
    cur_tasks = {t["task_id"]: t for t in result["tasks"]}
    common = sorted(set(ref_tasks) & set(cur_tasks))
    gained = [t for t in common if cur_tasks[t]["resolved"] and not ref_tasks[t]["resolved"]]
    lost = [t for t in common if ref_tasks[t]["resolved"] and not cur_tasks[t]["resolved"]]

    lines = [f"# {args.tag} — pełny przebieg 30 zadań, werdykt mechaniczny", ""]
    lines.append(f"- rozwiązane: **{resolved}/{total}** = {round(100*resolved/total,1)} %, CI95 {ci}")
    lines.append(f"- średni czas zadania: {round(result['mean_task_duration_seconds'],1)} s")
    lines.append(f"- bramki: G1 pliki-śmieci = **{g['scratch']}**, G2 przedwczesne puste = **{g['premature']}**, "
                 f"G3 tylko dokumentacja = **{g['docs_only']}**, G4 puste drzewa = **{g['empty']}**")
    lines.append(f"- porównanie parami z `{args.reference}` (V6.4 = 10/30) na {len(common)} wspólnych zadaniach: "
                 f"**+{len(gained)} / −{len(lost)}**")
    if gained:
        lines.append(f"  - zyskane: {', '.join(gained)}")
    if lost:
        lines.append(f"  - utracone: {', '.join(lost)}")

    checks: list[tuple[str, bool, str]] = []
    if args.expect_solved is not None:
        checks.append(("R2 (wynik)", resolved >= args.expect_solved,
                       f"rozwiązane {resolved}/30 vs próg ≥ {args.expect_solved}"))
    if args.expect_first_edit_call_4 is not None:
        if traces is None:
            checks.append(("R3 (termin edycji)", None, "brak śladów — uruchom workflow śladów"))
        else:
            n = sum(1 for t in traces.values() if repo_edits_in_call_4(t))
            checks.append(("R3 (termin edycji)", n >= args.expect_first_edit_call_4,
                           f"edycja w repo w call 4: {n}/30 vs próg ≥ {args.expect_first_edit_call_4} "
                           f"(baseline V6.4: 1/30)"))
    if args.expect_only_outside_writes is not None:
        if traces is None:
            checks.append(("R1 (pułapka pliku)", None, "brak śladów — uruchom workflow śladów"))
        else:
            n = sum(1 for t in traces.values() if only_outside_writes(t))
            checks.append(("R1 (pułapka pliku)", n <= args.expect_only_outside_writes,
                           f"zadania, których jedynym zapisem jest plik poza repo: {n}/30 vs cel "
                           f"≤ {args.expect_only_outside_writes} (baseline V6.4: {args.reference_only_outside_writes})"))
    # gates are always reported as a check, never as a threshold moved after the fact
    checks.append(("R4 (bramki)", g["scratch"] == 0 and g["docs_only"] == 0,
                   f"G1 = {g['scratch']} i G3 = {g['docs_only']} (twarde); G2 = {g['premature']}, "
                   f"G4 = {g['empty']} (raportowane)"))

    lines += ["", "## Werdykt", ""]
    for name, ok, detail in checks:
        verdict = "SPEŁNIONE" if ok else ("BRAK DANYCH" if ok is None else "NARUSZONE")
        lines.append(f"- **{name}**: {verdict} — {detail}")

    if traces is not None and ref_traces is not None:
        def coverage(tr: dict, ref_tr: dict) -> tuple[int, int]:
            cur = sum(1 for t in tr.values()
                      if any(c.get("tool") in WRITE_TOOLS and not str(c.get("target") or "").startswith("/")
                             for c in (t.get("sequence") or [])))
            old = sum(1 for t in ref_tr.values()
                      if any(c.get("tool") in WRITE_TOOLS and not str(c.get("target") or "").startswith("/")
                             for c in (t.get("sequence") or [])))
            return cur, old
        cur_cov, ref_cov = coverage(traces, ref_traces)
        lines += ["", f"- pokrycie edycji w repo: **{cur_cov}/30** (V6.4: {ref_cov}/30)"]

    report = "\n".join(lines) + "\n"
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"zapisano: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
