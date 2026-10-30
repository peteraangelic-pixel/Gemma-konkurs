#!/usr/bin/env python3
"""Build `arc3-duck-v13.ipynb` (v13.4-unified) from the certified v13.3-arena.

v13.4-unified = best-of-all-branches under one kill-switch matrix:

  from v13.2 (Pokemon 6b10853, certified)   : PLAN_COMMIT=1, CAP=0, WINPATH=1,
                                              DEAD_SKIP=1, ESCALATE floor, conc=10
  from v13.3-arena (ours, certified)        : ARC3_OPENER_COMMIT_HINT=1,
                                              patch 0007 (win-path event log)
  from v14 (Gemma b38b82e, audited)         : ESCALATE_ACTIONS 10 -> 20 (measured:
                                              @10 = 154 injections / 15.3% pool /
                                              premature on 31/32 levels; @20 = 60/6.0%),
                                              guarded roster-probe hook (AttributeError
                                              could kill the notebook pre-run),
                                              budget probe (pre-run) + roster probe
                                              (post-run, verdict on duplicate bases)
  NEW in v13.4 (needs r033, which Gemma lacked): patch 0008 —
                                              ARC3_ESCALATE_RELATIVE=1 fires the
                                              escalation only above
                                              max(floor, rate * human baseline);
                                              measured: 8 injections, 0 premature.

Everything is env-gated; with every new switch unset the build behaves like
v14, and like v13.2 when additionally the opener hint is off.

Usage:
  python3 tools/build_v134_unified.py \
      [--prev ../duck-v13-3-arena/arc3-duck-v13.ipynb] \
      [--patch patches/0008-arena-escalate-relative.patch] [--out arc3-duck-v13.ipynb]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
MARK_V133_CELLS = 36  # v13.3-arena has exactly 36 cells


def cell_source(cell: dict) -> str:
    return "".join(cell.get("source", []))


def set_source(cell: dict, text: str) -> None:
    cell["source"] = text.splitlines(keepends=True)


BUDGET_CELL = r'''# === v13.4 budget probe (z v14, Gemma b38b82e): co naprawde ogranicza wynik? ===
# Fakty z trzech zapisanych runow (r085, r110, r118): KAZDY run konczy sie
# dokladnie na capie (max(final_wallclock_seconds) == min == 48/48/90 min).
# Gra nie konczy sie wczesniej, wiec cap JEST przydzialem akcji:
#     akcje = cap / (sekundy na akcje),  a sekundy na akcje ~ tokeny na akcje.
# W prawdziwym rerunie cap = 532 min, a uczciwy udzial to
#     (budzet_notebooka - rezerwa) * concurrency / liczba_gier.
# Jesli cap / udzial > 1, ogon rosteru nie zagra wcale i liczy sie jako 0.
# Ten blok NICZEGO nie zmienia - liczy i loguje. Decyzje po pierwszym przebiegu.
try:
    _n_games = len(bm.games)
    _conc = max(1, int(bm.solver.concurrency))
    _total = float(getattr(target, "max_runtime_s", 0.0) or 0.0) or 32400.0
    _reserve = 600.0
    _fair = max(60.0, (_total - _reserve) * _conc / max(1, _n_games))
    _cap = float(getattr(bm.solver, "max_runtime_s_per_game", 0.0) or 0.0)
    _budget = {
        "games": _n_games,
        "passes": getattr(bm, "n_passes", None),
        "concurrency": _conc,
        "notebook_budget_s": _total,
        "fair_share_s_per_game": round(_fair, 1),
        "configured_cap_s": _cap,
        "cap_over_fair": round(_cap / _fair, 2) if _fair else None,
        "true_submission": TRUE_SUBMISSION,
    }
    (WORKING_DIR / "budget_probe.json").write_text(json.dumps(_budget, indent=2))
    print(f"v13.4 budget: {_n_games} gier x {_budget['passes']} pass(es), concurrency {_conc}, "
          f"uczciwy udzial {_fair / 60:.0f} min/gra, cap {_cap / 60:.0f} min "
          f"-> {_budget['cap_over_fair']}x", flush=True)
    if _cap and _fair and _cap / _fair > 1.3:
        print(f"v13.4 budget: UWAGA cap jest {_cap / _fair:.1f}x powyzej udzialu - jesli gra nie konczy "
              f"sie wczesniej, ogon rosteru ({_n_games} gier) nie zagra", flush=True)
except Exception as _budget_exc:
    print(f"v13.4 budget probe skipped: {_budget_exc!r}", flush=True)
'''

ROSTER_CELL = r'''# === v13.4 roster probe (z v14, Gemma b38b82e): czy roster powtarza gry? ====
# Jedyne pytanie, od ktorego zalezy, czy pamiec win-path (patch 0006) jest warta
# 0 czy +5..15 punktow sredniej. Czyta bm.game_runs PO biegu - nie dotyka
# solvera, nie moze wywalic runu. Plik ma inna nazwe niz log hooka c45
# (roster_probe.jsonl), zeby oba zbiory danych przetrwaly.
import json as _v14_json
from collections import Counter as _V14Counter

_v14_out = WORKING_DIR / "roster_probe_runs.jsonl"
try:
    _v14_runs = list(getattr(bm, "game_runs", None) or [])
    _v14_recs = []
    for _i, _r in enumerate(_v14_runs):
        _gid = str(getattr(_r, "game_id", "?") or "?")
        _hist = list(getattr(_r, "history", []) or [])
        _tok = sum(int(getattr(_h, "generated_tokens", 0) or 0) for _h in _hist)
        _calls = sum(1 for _h in _hist if int(getattr(_h, "generated_tokens", 0) or 0) > 0)
        _acts = sum(int(_x or 0) for _x in (getattr(_r, "actions_per_level", []) or []))
        _v14_recs.append({
            "index": _i,
            "game_id": _gid,
            "base": _gid.split("-")[0],
            "levels": int(getattr(_r, "levels_completed", 0) or 0),
            "total_levels": int(getattr(_r, "number_of_levels", 0) or 0),
            "actions": _acts,
            "tokens": _tok,
            "calls": _calls,
            "actions_per_call": round(_acts / _calls, 2) if _calls else 0.0,
            "tok_per_action": round(_tok / _acts, 1) if _acts else 0.0,
            "wall_min": round(float(getattr(_r, "final_wallclock_seconds", 0.0) or 0.0) / 60.0, 1),
            "score": round(float(getattr(_r, "final_score", 0.0) or 0.0), 2),
            "state": str(getattr(_r, "state", "?")),
        })
    with _v14_out.open("w", encoding="utf-8") as _fh:
        for _rec in _v14_recs:
            _fh.write(_v14_json.dumps(_rec, sort_keys=True) + "\n")

    if _v14_recs:
        _bases = _V14Counter(_r["base"] for _r in _v14_recs)
        _dups = {k: v for k, v in _bases.items() if v > 1}
        _zero = [(_r["game_id"], _r["state"]) for _r in _v14_recs if _r["actions"] == 0]
        _acpc = [_r["actions_per_call"] for _r in _v14_recs if _r["calls"]]
        _summary = {
            "runs": len(_v14_recs),
            "unique_bases": len(_bases),
            "duplicate_bases": len(_dups),
            "max_repeats": max(_bases.values()),
            "repeats": dict(sorted(_dups.items(), key=lambda kv: -kv[1])),
            "runs_with_zero_actions": _zero[:20],
            "mean_actions_per_call": round(sum(_acpc) / len(_acpc), 2) if _acpc else 0.0,
            "mean_wall_min": round(sum(_r["wall_min"] for _r in _v14_recs) / len(_v14_recs), 1),
        }
        print("v13.4 roster: " + _v14_json.dumps(_summary, sort_keys=True), flush=True)
        if _dups:
            print(f"v13.4 roster: POWTARZA SIE {len(_dups)} bazowych gier (do {_summary['max_repeats']}x) "
                  f"-> pamiec miedzy wpisami PLACI", flush=True)
        else:
            print("v13.4 roster: ZADNY bazowy kod sie nie powtarza -> pamiec win-path = 0 pkt "
                  "(dokladnie tak, jak twierdzi OCENA-V9 c45)", flush=True)
        print(f"v13.4 roster: zapisane do {_v14_out}", flush=True)
        if _acpc and _summary["mean_actions_per_call"] < 1.5:
            print(f"v13.4 roster: a/call = {_summary['mean_actions_per_call']} < 1.5 -> commit(plan) "
                  f"praktycznie nie odpala; dzwignia 50+ lezy odlogiem", flush=True)
except Exception as _v14_exc:
    print(f"v13.4 roster probe skipped: {_v14_exc!r}", flush=True)
'''

WRITER_0008 = '''# ARC3 Duck v13.4-unified: patch 0008-arena-escalate-relative — próg eskalacji
# względem ludzkiego baseline'u (zmierzone na r085 przez Gemmę b38b82e,
# przeliczone niezależnie przez Arenę: 8 wstrzyknięć / 0 przedwczesnych vs
# 154 / 31-z-32 przy absolutnej 10; absolutna 20 = 60 / 6,0%).
# Env-gated: ARC3_ESCALATE_RELATIVE=0 przywraca dokładne zachowanie v14;
# ARC3_ESCALATE_MAX_PER_LEVEL ogranicza liczbę nudge'ów na poziomie.
from pathlib import Path as _P
'''

GUARDED_ORIG_PLAY = '''    try:
        _orig_play = _S._HarnessGameSession.play
    except AttributeError as exc:  # inny revision bundla -> nie zabijaj notebooka
        return f"probe: POMINIETA (brak _HarnessGameSession.play: {exc!r})"
'''

GUARDED_PRINT = '''try:  # v13.4: ten hook stoi w komorce, ktora ustawia bm.solver.* - nie moze rzucic
    print(_install_roster_probe(), flush=True)
except Exception as _probe_exc:
    print(f"probe: BLAD {_probe_exc!r}", flush=True)
'''

V134_COMMENT = '''# v13.4-unified additions (Gemma b38b82e measured + Arena): ESCALATE_ACTIONS
# 10 -> 20 (@10 on r085: 154 injections = 15.3% of the game's token pool,
# "stop trying" fired before human baseline on 31/32 levels; @20: 60, 6.0%),
# ARC3_ESCALATE_RELATIVE=1 (patch 0008: fire only above max(floor, 1.2 x human
# baseline) -> 8 injections, 0 premature; kill: "0" = exact v14; per-level cap:
# ARC3_ESCALATE_MAX_PER_LEVEL, default 2 in variant), guarded roster-probe hook
# (AttributeError-proof) + budget/roster probes from v14 (observability only).
'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev", default=str(PKG.parent / "duck-v13-3-arena" / "arc3-duck-v13.ipynb"))
    ap.add_argument("--patch", default=str(PKG / "patches" / "0008-arena-escalate-relative.patch"))
    ap.add_argument("--out", default=str(PKG / "arc3-duck-v13.ipynb"))
    args = ap.parse_args()

    nb = json.loads(Path(args.prev).read_text())
    cells = nb["cells"]
    assert len(cells) == MARK_V133_CELLS, f"prev has {len(cells)} cells, expected {MARK_V133_CELLS}"

    patch_text = Path(args.patch).read_text()
    if not patch_text.endswith("\n"):
        patch_text += "\n"

    # 1. ARC3_VARIANT cell.
    variant_idx = next(i for i, c in enumerate(cells) if "ARC3_VARIANT" in cell_source(c))
    src = cell_source(cells[variant_idx])
    m = re.search(r"ARC3_VARIANT = (\{.*\})$", src, flags=re.M)
    assert m, "ARC3_VARIANT literal not found"
    variant = json.loads(m.group(1))
    env = variant["env"]
    assert env.get("ARC3_WINPATH") == "1" and env.get("ARC3_DEAD_SKIP") == "1"
    assert env.get("ARC3_OPENER_COMMIT_HINT") == "1"  # v13.3-arena inheritance
    env["ARC3_ESCALATE_RELATIVE"] = "1"
    env["ARC3_ESCALATE_RATE"] = "1.2"
    env["ARC3_ESCALATE_MAX_PER_LEVEL"] = "2"
    assert "/kaggle/duck-extra-05.patch" in variant["patch_files"]
    variant["patch_files"].append("/kaggle/duck-extra-06.patch")
    assert "0007-arena-replay-log.patch" in variant["patches"]
    variant["patches"].append("0008-arena-escalate-relative.patch")
    variant["name"] = "v13-4-unified"
    src = src[:m.start(1)] + json.dumps(variant) + src[m.end(1):]
    set_source(cells[variant_idx], src)

    # 2. Switch cell: measured threshold + version print.
    switch_idx = next(i for i, c in enumerate(cells) if "v13 switch" in cell_source(c))
    src = cell_source(cells[switch_idx])
    anchor = ('# quiets it; hint kill-switch: "ARC3_OPENER_COMMIT_HINT": "0" in variant).\n')
    assert src.count(anchor) == 1, "v13.3 comment anchor"
    src = src.replace(anchor, anchor + V134_COMMENT, 1)
    old, n = re.subn(r"^ESCALATE_ACTIONS = 10$", "ESCALATE_ACTIONS = 20", src, count=1, flags=re.M)
    assert n == 1, "ESCALATE anchor"
    src = old
    src, n = re.subn(r"v13\.3-arena profile", "v13.4-unified profile", src, count=1)
    assert n == 1, "switch print anchor"
    set_source(cells[switch_idx], src)

    # 3. extra-06 writer cell after the extra-05 writer cell (+ rebrand 0007 comment).
    w5_idx = next(i for i, c in enumerate(cells)
                  if "duck-extra-05.patch" in cell_source(c) and "write_text" in cell_source(c))
    src = cell_source(cells[w5_idx])
    src, n = re.subn(r"ARC3 Duck v13\.3-arena: patch 0007", "ARC3 Duck v13.4-unified: patch 0007",
                     src, count=1)
    assert n == 1, "extra-05 comment rebrand"
    set_source(cells[w5_idx], src)
    writer = WRITER_0008 + f'_P("/kaggle/duck-extra-06.patch").write_text({patch_text!r})\n'
    cells.insert(w5_idx + 1, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": writer.splitlines(keepends=True),
    })

    # 4. Guarded roster-probe hook in the bm.solver cell.
    hook_idx = next(i for i, c in enumerate(cells) if "_install_roster_probe" in cell_source(c))
    src = cell_source(cells[hook_idx])
    old_line = "    _orig_play = _S._HarnessGameSession.play\n"
    assert src.count(old_line) == 1, "orig_play anchor"
    src = src.replace(old_line, GUARDED_ORIG_PLAY, 1)
    old_print = "print(_install_roster_probe(), flush=True)\n"
    assert src.count(old_print) == 1, "probe print anchor"
    src = src.replace(old_print, GUARDED_PRINT, 1)
    set_source(cells[hook_idx], src)

    # 5. Budget probe cell right before the bm.run cell.
    run_idx = next(i for i, c in enumerate(cells) if "await bm.run" in cell_source(c))
    cells.insert(run_idx, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": BUDGET_CELL.splitlines(keepends=True),
    })

    # 6. Post-run roster probe at the very end (after the metering cell).
    cells.append({
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": ROSTER_CELL.splitlines(keepends=True),
    })

    out = Path(args.out)
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"built {out} ({len(cells)} cells, {out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
