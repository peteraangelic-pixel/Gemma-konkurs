#!/usr/bin/env python3
"""Builder: duck-v13.5-consensus -> duck-v13-6-final.

RULE (learned the hard way on v13.5, 30.10): the builder of a new version edits
ONLY INCREMENTALLY on top of the PREVIOUS BUILT notebook (never re-applies an
older transformation). v13.6 adds exactly:

  1. ARC3_VARIANT: + patch 0009 self-pace (ARC3_ESCALATE_SELF_PACE=1,
     ARC3_ESCALATE_SELF_RATE=1.5), patch_files += /kaggle/duck-extra-07.patch,
     name v13-6-final.  (Patch taken byte-for-byte from Gemma duck-v16 0ef2465,
     which builds on OUR v13.4-unified; verified by a450 52b709e 9/9 and by us:
     tests/test_self_pace.py reproduces 22 nudges / 14 premature on r085.)
  2. Switch cell: v13.6 note (self-pace works in the rerun; 0008-relative is
     inert in submission; unconditional a/call print replaces the dead < 1.5
     alarm, c87 28ed67f "warstwa 8: martwy instrument") + version print rebrand.
  3. Roster probe: dead alarm `a/call < 1.5` replaced by an UNCONDITIONAL print
     with the measured base (r019 = 4.357), targets (5.7 for 300 actions/game,
     7.6 for 400) and the 7911 gate (>= 6.0 at the 253 actions/game = 50 pts
     boundary).
  4. New writer cell duck-extra-07.patch (patch 0009), right after extra-06.
  5. extra-05/06 writer comment rebrands + budget/roster probe label rebrands.
  6. kernel-metadata.json slug -> arc3-duck-v13-6-final (the slug drift Gemma
     duck-v16 left behind is NOT reproduced here: their kernel-metadata still
     said arc3-duck-v13-4-unified).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
MARK_V135_CELLS = 39

V136_NOTE = """# v13.6-final = v13.5-consensus + patch 0009 self-pace (Gemma duck-v16 0ef2465;
# verified: a450 52b709e 9/9 patches + our tests/test_self_pace.py -> 22 nudges /
# 14 premature on r085, 1:1 from the shipped code). 0009 calibrates on
# GameRun.actions_per_level - OUR OWN record, NOT hidden in submission mode - so
# unlike 0008-relative it does NOT degrade to 20+cap2 in the rerun that counts.
# Kill switches: ARC3_ESCALATE_SELF_PACE=0 -> exactly v13.5; on a game with a
# visible baseline the relative branch still wins (test 3).
# Instrument fix (c87 28ed67f, "warstwa 8: martwy instrument"): the roster probe's
# a/call alarm `< 1.5` was dead (measured base r019 = 4.357; a dead lever prints
# neutral, a dead METRIC prints false confidence). Now an unconditional print:
# base 4.357, targets ~5.7 (300 actions/game) / ~7.6 (400), gate 7911 >= 6.0
# (253 actions/game = the 50-point boundary). Batching leverage is 24x the whole
# escalation debate (7911 cad326c): keep escalating at 20, watch the a/call print.
"""


def cell_source(cell: dict) -> str:
    return "".join(cell.get("source", []))


def set_source(cell: dict, text: str) -> None:
    cell["source"] = text.splitlines(keepends=True)


def replace_once(src: str, old: str, new: str, what: str) -> str:
    assert src.count(old) == 1, f"{what}: anchor {src.count(old)}x, expected exactly 1"
    return src.replace(old, new, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev", default=str(PKG.parent / "duck-v13-5-consensus" / "arc3-duck-v13.ipynb"))
    ap.add_argument("--out", default=str(PKG / "arc3-duck-v13.ipynb"))
    args = ap.parse_args()

    nb = json.loads(Path(args.prev).read_text())
    cells = nb["cells"]
    assert len(cells) == MARK_V135_CELLS, f"prev has {len(cells)} cells, expected {MARK_V135_CELLS}"

    # 1. ARC3_VARIANT: register 0009 + self-pace env + name.
    variant_idx = next(i for i, c in enumerate(cells) if "ARC3_VARIANT" in cell_source(c))
    src = cell_source(cells[variant_idx])
    m = re.search(r"ARC3_VARIANT = (\{.*\})$", src, flags=re.M)
    assert m, "ARC3_VARIANT literal not found"
    variant = json.loads(m.group(1))
    assert variant["env"].get("ARC3_ESCALATE_RELATIVE") == "1"
    assert variant["env"].get("ARC3_OPENER_COMMIT_HINT") == "1"
    assert "/kaggle/duck-extra-06.patch" in variant["patch_files"]
    assert variant["name"] == "v13-5-consensus", variant["name"]
    variant["name"] = "v13-6-final"
    variant["env"]["ARC3_ESCALATE_SELF_PACE"] = "1"
    variant["env"]["ARC3_ESCALATE_SELF_RATE"] = "1.5"
    variant["patch_files"] = list(variant["patch_files"]) + ["/kaggle/duck-extra-07.patch"]
    variant["patches"] = list(variant["patches"]) + ["0009-arena-self-pace.patch"]
    src = src[:m.start(1)] + json.dumps(variant) + src[m.end(1):]
    set_source(cells[variant_idx], src)

    # 2. Switch cell: v13.6 note + version print rebrand.
    switch_idx = next(i for i, c in enumerate(cells) if "v13 switch" in cell_source(c))
    src = cell_source(cells[switch_idx])
    assert re.search(r"^ESCALATE_ACTIONS = 20$", src, flags=re.M), "still 20"
    tail_anchor = "the roster probe now logs coverage + the baseline visibility verdict.\n"
    assert src.count(tail_anchor) == 1, "v135 note tail anchor"
    src = src.replace(tail_anchor, tail_anchor + V136_NOTE, 1)
    src = replace_once(src, "v13.5-consensus profile", "v13.6-final profile", "switch print")
    set_source(cells[switch_idx], src)

    # 3. extra-05 writer comment rebrand.
    w5_idx = next(i for i, c in enumerate(cells)
                  if "duck-extra-05.patch" in cell_source(c) and "write_text" in cell_source(c))
    src = cell_source(cells[w5_idx])
    src, n = re.subn(r"ARC3 Duck v13\.5-consensus: patch 0007", "ARC3 Duck v13.6-final: patch 0007",
                     src, count=1)
    assert n == 1, "extra-05 comment rebrand"
    set_source(cells[w5_idx], src)

    # 4. Budget probe cell: labels only.
    b_idx = next(i for i, c in enumerate(cells) if "v13.5 budget probe" in cell_source(c))
    src = cell_source(cells[b_idx])
    src = src.replace("v13.5 budget probe", "v13.6 budget probe")
    src = src.replace("v13.5 budget:", "v13.6 budget:")
    set_source(cells[b_idx], src)

    # 5. Roster probe: THE INSTRUMENT FIX first (dead < 1.5 alarm -> unconditional
    #    print), then label rebrands (order matters: the rebrand would break the anchor).
    r_idx = next(i for i, c in enumerate(cells) if "v13.5 roster probe" in cell_source(c))
    src = cell_source(cells[r_idx])
    dead = ('        if _acpc and _summary["mean_actions_per_call"] < 1.5:\n'
            '            print(f"v13.5 roster: a/call = {_summary[\'mean_actions_per_call\']} < 1.5 -> commit(plan) "\n'
            '                  f"praktycznie nie odpala; dzwignia 50+ lezy odlogiem", flush=True)\n')
    alive = ('        print(f"v13.6 batch: a/call = {_summary[\'mean_actions_per_call\']} "\n'
             '              f"(baza r019 = 4.357; cel ~5.7 dla 300 akcji/ge, ~7.6 dla 400; "\n'
             '              f"bramka 7911: >= 6.0 na granicy 253 akcji/ge = 50 pkt; "\n'
             '              f"stary prog 1.5 byl martwy, c87 warstwa-8)", flush=True)\n')
    assert src.count(dead) == 1, f"dead alarm anchor {src.count(dead)}x"
    src = src.replace(dead, alive, 1)
    src = src.replace("v13.5 roster probe", "v13.6 roster probe")
    src = src.replace("v13.5 roster:", "v13.6-final roster:")
    set_source(cells[r_idx], src)

    # 6. New writer cell for duck-extra-07.patch (patch 0009), right after extra-06.
    w6_idx = next(i for i, c in enumerate(cells)
                  if "duck-extra-06.patch" in cell_source(c) and "write_text" in cell_source(c))
    patch_text = (PKG / "patches" / "0009-arena-self-pace.patch").read_text()
    writer = (
        "# ARC3 Duck v13.6-final: patch 0009-arena-self-pace — próg eskalacji na WŁASNYM tempie\n"
        "# gry (Gemma duck-v16 0ef2465; nadzbiór v13.4/v13.5). threshold =\n"
        "# clamp(1.5 × mediana własnych akcji na ukończonych poziomach TEJ gry, floor 20, 120)\n"
        "# + cap 2/poziom. Działa W RERUNIE (GameRun.actions_per_level nie jest ukrywane),\n"
        "# w odróżnieniu od 0008-relatywnego (baseline = None w submisji). r085: 22 nudge'y\n"
        "# / 14 przedwczesnych vs 42 / 26 dla 20+cap2 (tests/test_self_pace.py, 1:1 z kodu).\n"
        "# Env-gated: ARC3_ESCALATE_SELF_PACE=0 -> dokładnie v13.5; baseline widoczny ->\n"
        "# wygryga gałąź relatywna 0008 (test 3 w test_self_pace.py).\n"
        "from pathlib import Path as _P\n"
        f"_P(\"/kaggle/duck-extra-07.patch\").write_text({patch_text!r})\n"
    )
    cells.insert(w6_idx + 1, {"cell_type": "code", "execution_count": None,
                              "metadata": {}, "outputs": [], "source": writer.splitlines(keepends=True)})

    # 7. kernel-metadata.json: slug (do NOT reproduce Gemma duck-v16's slug drift).
    km_path = PKG / "kernel-metadata.json"
    km = json.loads(km_path.read_text())
    km["id"] = "petersharps/arc3-duck-v13-6-final"
    km["title"] = "arc3-duck-v13-6-final"
    km_path.write_text(json.dumps(km, indent=2, ensure_ascii=False) + "\n")

    out = Path(args.out)
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"built {out} ({len(cells)} cells, {out.stat().st_size} bytes)")
    print(f"kernel-metadata id -> {km['id']}")


if __name__ == "__main__":
    main()
