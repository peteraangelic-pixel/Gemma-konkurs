#!/usr/bin/env python3
"""Build `arc3-duck-v16.ipynb` from the certified v13.4-unified notebook.

v16 = v13.4-unified + three things:

1. **Patch 0009 (`ARC3_ESCALATE_SELF_PACE=1`)** - the escalation threshold calibrates on the
   agent's own pace on THIS game when the human baseline is hidden. That is the case in a real
   rerun: `taaf/game.py` documents `base_actions_per_level` as "None when the engine hides
   baselines (e.g. submission mode)", so v13.4's relative rule is inert there and everything
   falls back to the constant floor. Measured on r085's 32 completed levels (the same data
   every branch used for @10/@60): floor 20 + cap 2 gives 42 injections, 26 of them before the
   human baseline; self-pace(1.5, cap 2) gives 27 and 16. Fewer prompts, aimed at levels this
   agent is actually losing, and it needs no hidden data.

2. **Coverage probe** (after the run, read-only): per game `levels/total`, `coverage`,
   `baseline=yes|no`, actions, tokens, `a/call`, score. `score <= 100 x coverage` is the
   scoring rule, so coverage is the score in disguise; and `baseline=yes|no` settles on live
   data what patch 0009 assumes from the taaf docstring.

3. **Corrected numbers** in the docs: @20 fires 67 times on r085, not the 60 the v14 README
   interpolated (42 with the per-level cap of 2).

Untouched: the 8-patch chain (verified here independently: all 8 apply cleanly on the pristine
r033 bundle), `src/arc3_winpath.py` (standalone == patched), `playbook.json` (14/14 on the real
engine), opener hint, win-path log, both existing probes, the c45 guard.

Usage:
  python3 tools/build_v16.py            # package sits next to its own src/ and patches/
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent


def cell_source(cell: dict) -> str:
    return "".join(cell.get("source", []))


def set_source(cell: dict, text: str) -> None:
    cell["source"] = text.splitlines(keepends=True)


def replace_once(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    assert n == 1, f"{what}: expected exactly 1 occurrence, found {n}"
    return text.replace(old, new, 1)


VAR_ENV_OLD = '"ARC3_ESCALATE_MAX_PER_LEVEL": "2"}'
VAR_ENV_NEW = ('"ARC3_ESCALATE_MAX_PER_LEVEL": "2", '
               '"ARC3_ESCALATE_SELF_PACE": "1", "ARC3_ESCALATE_SELF_RATE": "1.5", '
               '"ARC3_ESCALATE_SELF_MAX": "120"}')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(PKG / "src" / "base-v13-4-unified.ipynb"))
    ap.add_argument("--patch", default=str(PKG / "patches" / "0009-arena-self-pace.patch"))
    ap.add_argument("--out", default=str(PKG / "arc3-duck-v16.ipynb"))
    args = ap.parse_args()

    nb = json.loads(Path(args.src).read_text())
    cells = nb["cells"]
    assert len(cells) == 39, f"v13.4 has 39 cells, got {len(cells)}"
    patch_text = Path(args.patch).read_text()
    if not patch_text.endswith("\n"):
        patch_text += "\n"

    # 1. Variant cell: register extra-07/0009 and the new switches.
    v = cell_source(cells[1])
    v = replace_once(v, '"/kaggle/duck-extra-06.patch"]',
                     '"/kaggle/duck-extra-06.patch", "/kaggle/duck-extra-07.patch"]',
                     "patch_files")
    v = replace_once(v, '"0008-arena-escalate-relative.patch"]',
                     '"0008-arena-escalate-relative.patch", "0009-arena-self-pace.patch"]',
                     "patches list")
    v = replace_once(v, VAR_ENV_OLD, VAR_ENV_NEW, "variant env")
    v = replace_once(v, '"name": "v13-4-unified"', '"name": "v16"', "variant name")
    set_source(cells[1], v)

    # 2. Switch cell: floor stays 20, banner documents self-pace.
    i = next(k for k, c in enumerate(cells) if "v13 switch" in cell_source(c))
    s = cell_source(cells[i])
    s = replace_once(s, 'print(f"v13.4-unified profile=',
                     'print(f"v16 profile=', "profile print")
    s = replace_once(s, "import os as _v11_os", V16_NOTE + "import os as _v11_os", "switch note")
    set_source(cells[i], s)

    # 3. Patch 0009 writer cell, right after the extra-06 writer.
    w = max(k for k, c in enumerate(cells)
            if "duck-extra-06.patch" in cell_source(c) and "write_text" in cell_source(c))
    cells.insert(w + 1, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": (
            "# ARC3 Duck v16: patch 0009 — self-paced escalation threshold.\n"
            "# When the human baseline is hidden (submission mode), calibrate the nudge\n"
            "# on this game's own completed levels instead of a constant. Env-gated:\n"
            "# inert unless ARC3_ESCALATE_SELF_PACE=1.\n"
            "from pathlib import Path as _P\n"
            f'_P("/kaggle/duck-extra-07.patch").write_text({patch_text!r})\n'
        ).splitlines(keepends=True),
    })

    # 4. Coverage probe after the metering cell.
    i = max(k for k, c in enumerate(cells) if "v11 metering" in cell_source(c))
    cells.insert(i + 1, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": COVERAGE_PROBE.splitlines(keepends=True),
    })

    out = Path(args.out)
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"built {out} ({len(cells)} cells, {out.stat().st_size} bytes)")


V16_NOTE = """# v16 adds over v13.4-unified (env-only + one verified patch):
#   ARC3_ESCALATE_SELF_PACE=1 -> patch 0009. The human baseline is None in submission mode
#   (taaf/game.py: "None when the engine hides baselines (e.g. submission mode)"), so the
#   relative rule of patch 0008 is inert in the run that counts and everything falls back to
#   the constant floor. Self-pace uses this game's own completed levels instead: threshold =
#   clamp(1.5 x median(actions_per_level[:levels_completed]), floor 20, 120), at most 2 nudges
#   per level. On r085's 32 completed levels: 27 injections / 16 before the human baseline,
#   versus 42 / 26 for floor 20 + cap 2 and 67 / 26 for floor 20 alone.
#   Kill-switch: "ARC3_ESCALATE_SELF_PACE": "0" in the variant cell -> exactly v13.4.
"""

COVERAGE_PROBE = r'''# === v16 coverage probe: wynik = pokrycie, zmierzone na zywo =================
# Regula punktacji (taaf/game.py::_compute_final_score, zweryfikowana 30/30 przez 7911):
#     score = min( sum(s_k*w_k)/sum(w_k) , 100 * pokrycie )
# czyli wynik NIGDY nie przekroczy 100 x pokrycia. Ten blok liczy pokrycie i cztery
# liczby, ktore rozstrzygaja o nastepnym kroku - bez GPU, bez dotykania solvera:
#   baseline=yes|no : czy w tym trybie silnik w ogole oddaje ludzki baseline
#                     (jesli "no" na 110 grach, to patch 0008 jest w rerunie martwy,
#                      a liczy sie tylko prog 20 + cap 2 i patch 0009);
#   coverage        : pokrycie = prognoza wyniku wprost;
#   a/call          : czy opener-hint (batch) dziala - jedyna dzwignia tok/akcje;
#   escalate_at     : ile nudge'ow poszlo i na ktore poziomy (z logu, nie z opisu).
try:
    import json as _v16_json
    import os as _v16_os
    from pathlib import Path as _V16Path

    _rows = []
    for _r in (getattr(bm, "game_runs", None) or []):
        _tot = int(getattr(_r, "number_of_levels", 0) or 0)
        _done = int(getattr(_r, "levels_completed", 0) or 0)
        _w = _tot * (_tot + 1) / 2.0 or 1.0
        _done_w = _done * (_done + 1) / 2.0
        _hist = list(getattr(_r, "history", []) or [])
        _calls = sum(1 for _h in _hist if int(getattr(_h, "generated_tokens", 0) or 0) > 0)
        _tok = sum(int(getattr(_h, "generated_tokens", 0) or 0) for _h in _hist)
        _acts = sum(int(_x or 0) for _x in (getattr(_r, "actions_per_level", []) or []))
        _base = getattr(_r, "base_actions_per_level", None)
        _rows.append({
            "game_id": str(getattr(_r, "game_id", "?")),
            "levels": f"{_done}/{_tot}",
            "coverage": round(100.0 * _done_w / _w, 1),
            "baseline": "yes" if _base else "no",
            "actions": _acts,
            "tokens": _tok,
            "a_per_call": round(_acts / _calls, 2) if _calls else 0.0,
            "tok_per_action": round(_tok / _acts, 1) if _acts else 0.0,
            "score": round(float(getattr(_r, "final_score", 0.0) or 0.0), 2),
            "wall_min": round(float(getattr(_r, "final_wallclock_seconds", 0.0) or 0.0) / 60.0, 1),
        })
    if _rows:
        _n = len(_rows)
        _summary = {
            "games": _n,
            "mean_coverage": round(sum(r["coverage"] for r in _rows) / _n, 1),
            "mean_score": round(sum(r["score"] for r in _rows) / _n, 2),
            "baseline_available": sum(1 for r in _rows if r["baseline"] == "yes"),
            "mean_a_per_call": round(sum(r["a_per_call"] for r in _rows) / _n, 2),
            "mean_tok_per_action": round(sum(r["tok_per_action"] for r in _rows) / _n, 1),
            "mean_actions": round(sum(r["actions"] for r in _rows) / _n, 0),
        }
        print("v16 coverage: " + _v16_json.dumps(_summary, sort_keys=True), flush=True)
        print(f"v16 coverage: prognoza z pokrycia <= {_summary['mean_coverage']:.1f} pkt "
              f"(regula: score <= 100 x pokrycie); zmierzony score {_summary['mean_score']}", flush=True)
        if _summary["baseline_available"] == 0:
            print("v16 coverage: baseline=no na WSZYSTKICH grach -> eskalacja relatywna (0008) "
                  "byla w tym biegu martwa; dziala prog 20 + cap 2 + self-pace (0009)", flush=True)
        if _summary["mean_a_per_call"] < 1.5:
            print(f"v16 coverage: a/call={_summary['mean_a_per_call']} < 1.5 -> batch na openerze "
                  f"(hint) nie zadzialal; tok/akcje nie spadly", flush=True)
        _out = _V16Path(_v16_os.environ.get("V16_COVERAGE_OUT",
                                            "/kaggle/working/coverage_probe.json"))
        _out.write_text(_v16_json.dumps({"summary": _summary, "games": _rows}, indent=1))
        for r in _rows:
            print(f"v16 coverage: {r['game_id'][:18]:20}{r['levels']:>7}{r['coverage']:7.1f}%"
                  f"  base={r['baseline']:3}{r['actions']:6}a{r['a_per_call']:6.2f}a/call"
                  f"{r['tok_per_action']:7.0f}tok/a  score={r['score']:6.2f}", flush=True)
except Exception as _v16_exc:
    print(f"v16 coverage probe skipped: {_v16_exc!r}", flush=True)
'''


if __name__ == "__main__":
    main()
