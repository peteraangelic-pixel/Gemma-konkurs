#!/usr/bin/env python3
"""Build `arc3-duck-v13.ipynb` (v13.3-arena) from the certified v13.2 notebook.

Lineage: base-v11 -> v13 -> v13.1 -> v13.2 (Pokemon 6b10853, certified by
Arena: 6/6+12/12+8/8, playbook 14/14 on-engine) -> v13.3-arena changes
exactly three things:

1. Variant env gains `ARC3_OPENER_COMMIT_HINT: "1"` - the harness-shipped,
   env-gated batching pressure on every fresh opener. Upstream measurement
   (tool_agent.py docstring): sequences following a resumption batch 6.73 /
   6.91 actions; fresh openers 5.43 / 3.91. This is the "force batching on
   the first turn" lever from the c87 audit, WITHOUT a new prompt patch.
   Kill-switch: set "0" in the variant cell.
2. Patch 0007 (duck-extra-05): stdout event log for win-path replay and
   dead-skip (`[arc3-winpath] ...` lines: session begin/end, playbook match,
   replay start/ok/abort+reason, record, dead-skip). Answers the 7911f950 +
   c87 audit finding that a silent replay failure is a diagnosis risk.
   Kill-switch: `ARC3_WINPATH_LOG: "0"` (log only; logic untouched).
3. Version prints/metadata: v13.3-arena / arc3-duck-v13-3-arena.

Playbook, serving cell, ESCALATE_ACTIONS=10, PLAN_COMMIT=1, CAP=0,
WINPATH=1, DEAD_SKIP=1, conc=10: byte-identical to v13.2.

Usage:
  python3 tools/build_v133_arena.py \
      [--prev ../duck-v13-2/arc3-duck-v13.ipynb] \
      [--patch patches/0007-arena-replay-log.patch] [--out arc3-duck-v13.ipynb]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
MARK_V132_CELLS = 35  # v13.2 has exactly 35 cells


def cell_source(cell: dict) -> str:
    return "".join(cell.get("source", []))


def set_source(cell: dict, text: str) -> None:
    cell["source"] = text.splitlines(keepends=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev", default=str(PKG.parent / "duck-v13-2" / "arc3-duck-v13.ipynb"))
    ap.add_argument("--patch", default=str(PKG / "patches" / "0007-arena-replay-log.patch"))
    ap.add_argument("--out", default=str(PKG / "arc3-duck-v13.ipynb"))
    args = ap.parse_args()

    nb = json.loads(Path(args.prev).read_text())
    cells = nb["cells"]
    assert len(cells) == MARK_V132_CELLS, f"prev has {len(cells)} cells, expected {MARK_V132_CELLS}"

    patch_text = Path(args.patch).read_text()
    if not patch_text.endswith("\n"):
        patch_text += "\n"

    # 1. ARC3_VARIANT cell: env + patch registration + name.
    variant_idx = next(i for i, c in enumerate(cells) if "ARC3_VARIANT" in cell_source(c))
    src = cell_source(cells[variant_idx])
    m = re.search(r"ARC3_VARIANT = (\{.*\})$", src, flags=re.M)
    assert m, "ARC3_VARIANT literal not found"
    variant = json.loads(m.group(1))
    env = variant["env"]
    assert env.get("ARC3_WINPATH") == "1" and env.get("ARC3_DEAD_SKIP") == "1"
    env["ARC3_OPENER_COMMIT_HINT"] = "1"
    assert "/kaggle/duck-extra-04.patch" in variant["patch_files"]
    variant["patch_files"].append("/kaggle/duck-extra-05.patch")
    assert "0006-winpath-replay.patch" in variant["patches"]
    variant["patches"].append("0007-arena-replay-log.patch")
    variant["name"] = "v13-3-arena"
    src = src[:m.start(1)] + json.dumps(variant) + src[m.end(1):]
    set_source(cells[variant_idx], src)

    # 2. Switch cell: version print + comment about the new switches.
    switch_idx = next(i for i, c in enumerate(cells) if "v13 switch" in cell_source(c))
    src = cell_source(cells[switch_idx])
    src, n = re.subn(r'# exit early\), ARC3_LEVEL_TOKEN_CAP="0" \(measured -0\.4\.\.-2\.2 pts at 45k\)\.',
                     '# exit early), ARC3_LEVEL_TOKEN_CAP="0" (measured -0.4..-2.2 pts at 45k).\n'
                     '# v13.3-arena additions: ARC3_OPENER_COMMIT_HINT=1 (batching pressure on\n'
                     '# every fresh opener; upstream-measured 3.91-5.43 -> 6.73-6.91 actions per\n'
                     '# batch) and patch 0007: win-path event log to stdout (ARC3_WINPATH_LOG=0\n'
                     '# quiets it; hint kill-switch: "ARC3_OPENER_COMMIT_HINT": "0" in variant).',
                     src, count=1)
    assert n == 1, "switch comment anchor not found"
    src, n = re.subn(r'v13\.2 profile', 'v13.3-arena profile', src, count=1)
    assert n == 1, "switch print anchor not found"
    set_source(cells[switch_idx], src)

    # 3. duck-extra-05 writer cell after the extra-04 writer cell.
    write_idx = max(i for i, c in enumerate(cells)
                    if "duck-extra-04.patch" in cell_source(c) and "write_text" in cell_source(c))
    writer = (
        "# ARC3 Duck v13.3-arena: patch 0007-arena-replay-log — stdout event\n"
        "# log for win-path replay and dead-skip (7911f950/c87 audits: a silent\n"
        "# replay failure is a diagnosis risk). Env-gated: with ARC3_WINPATH\n"
        "# unset the patched code is inert; ARC3_WINPATH_LOG=0 quiets the log.\n"
        "from pathlib import Path as _P\n"
        f'_P("/kaggle/duck-extra-05.patch").write_text({patch_text!r})\n'
    )
    cells.insert(write_idx + 1, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": writer.splitlines(keepends=True),
    })

    out = Path(args.out)
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"built {out} ({len(cells)} cells, {out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
