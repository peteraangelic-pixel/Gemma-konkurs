#!/usr/bin/env python3
"""Compare screening results across candidates and rewrite kaggle_results/screening_history.md.

Usage:
    python3 gemma4-agent/tools/compare_screenings.py            # writes the markdown report
    python3 gemma4-agent/tools/compare_screenings.py --json     # machine-readable summary too
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "gemma4-agent" / "kaggle_results"
SCRATCH = ("issue.txt", "locate.py", "repro.py", "notes.txt")
CLOCK_CAP = 315.0

CANDIDATES = [
    ("V3", "v3-benchmark"),
    ("V4", "v4-benchmark"),
    ("V5", "v5-benchmark"),
    ("V6.1", "v6-1-benchmark"),
    ("V6.2", "v6-benchmark"),
]


def stats(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = data.get("tasks") or []
    total = len(tasks) or 1
    scratch_tasks = [r.get("task_id") for r in tasks
                     if any(f in SCRATCH for f in (r.get("touched_files") or []))]
    scratch_only = [r.get("task_id") for r in tasks
                    if any(f in SCRATCH for f in (r.get("touched_files") or []))
                    and not any(f.endswith((".py", ".pyi")) and f.split("/")[-1] not in SCRATCH
                                for f in (r.get("touched_files") or []))]
    empty = [r.get("task_id") for r in tasks if (r.get("patch_chars") or 0) == 0]
    clock = [r.get("task_id") for r in tasks if (r.get("duration_seconds") or 0) >= CLOCK_CAP]
    resolved = [r.get("task_id") for r in tasks if r.get("resolved")]
    return {
        "total": len(tasks),
        "resolved": len(resolved),
        "resolved_ids": resolved,
        "empty": len(empty),
        "empty_ids": empty,
        "clock_deaths": len(clock),
        "scratch": len(scratch_tasks),
        "scratch_ids": scratch_tasks,
        "scratch_only": len(scratch_only),
        "scratch_only_ids": scratch_only,
        "localization_hits": data.get("localization_hits"),
        "touching_tests": data.get("tasks_touching_tests"),
        "mean_seconds": round(data.get("mean_task_duration_seconds") or 0, 1),
        "sha": data.get("submission_sha256"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=RESULTS / "screening_history.md")
    args = parser.parse_args()

    rows = [(tag, stats(RESULTS / folder / "agent_benchmark_result.json")) for tag, folder in CANDIDATES]
    present = [(tag, s) for tag, s in rows if s]

    lines = [
        "# Historia screeningów: co każdy wynik zmienił",
        "",
        "Te same 30 zadań i seed 20261009 w każdym przebiegu. Kolumny diagnostyczne istnieją tylko",
        "dla przebiegów po dodaniu diagnostyki per zadanie (V6.1, V6.2).",
        "",
        "| kandydat | rozwiązane | puste drzewa (zero edycji) | śmierci na zegarze | zadania z plikami-śmieciami | w tym TYLKO śmieci | trafienia lokalizatora | średni czas |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for tag, s in present:
        loc = "—" if s["localization_hits"] is None else f"{s['localization_hits']}/{s['total']}"
        lines.append(
            f"| {tag} | **{s['resolved']}/{s['total']}** | {s['empty']} | {s['clock_deaths']} "
            f"| {s['scratch']} | {s['scratch_only']} | {loc} | {s['mean_seconds']} s |")

    lines += ["", "## Zmiany statusu między kolejnymi kandydatami", ""]
    for (tag_a, a), (tag_b, b) in zip(present, present[1:]):
        gained = sorted(set(b["resolved_ids"]) - set(a["resolved_ids"]))
        lost = sorted(set(a["resolved_ids"]) - set(b["resolved_ids"]))
        lines.append(f"- {tag_a} → {tag_b}: +{len(gained)} ({', '.join(gained) or '—'}), "
                     f"-{len(lost)} ({', '.join(lost) or '—'})")

    for tag, s in present:
        if s["scratch"]:
            lines += ["", f"### {tag}: zadania z plikami-śmieciami w diffie", "",
                      f"- wszystkie: {', '.join(s['scratch_ids'])}",
                      f"- **bez żadnej edycji kodu: {', '.join(s['scratch_only_ids'])}**"]
    for tag, s in present:
        if s["empty"]:
            lines += ["", f"### {tag}: puste drzewa ({s['empty']})", "",
                      f"- {', '.join(s['empty_ids'])}"]

    lines += [
        "",
        "## Reguły interpretacji (wyuczone na tych przebiegach)",
        "",
        "1. **Śmierć na zegarze nie przekreśla zadania** — oceniany jest diff drzewa roboczego, także gdy",
        "   sesja padnie przed `submit_patch()` (dowód: V3 miał 16/30 takich sesji i 11/30 rozwiązanych).",
        "2. **Przekreśla ją brak użytecznej edycji** — V5 (6 pustych drzew) i V6.1 (7 drzew bez edycji kodu,",
        "   bo diff wypełniły pliki robocze) to dwa różne objawy tej samej przyczyny.",
        "3. **Publiczny screening 30 zadań nie przewiduje ukrytego wyniku** (V3/V4/V5: 10–11/30 przy",
        "   oficjalnym 0.03), ale z diagnostyką per zadanie niezawodnie wskazuje mechanizmy porażek.",
        "",
    ]

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:14]))
    if args.json:
        print(json.dumps({tag: s for tag, s in present}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
