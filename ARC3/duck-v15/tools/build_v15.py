#!/usr/bin/env python3
"""Build `arc3-duck-v15.ipynb` from the certified v13.3-arena notebook.

v15 = v13.3-arena + four changes, all of them env-only or read-only:

1. ESCALATE_ACTIONS 10 -> 20   (measured on r085's 32 completed levels: 154 vs 60 injections,
                                15.3% vs 6.0% of the game's token pool; at 10 the directive
                                fires on 31/32 levels while the agent is at or better than the
                                human baseline).
2. The c45 roster hook is guarded. It looked up `_HarnessGameSession.play` outside any
   try/except inside the cell that also sets `bm.solver.*` - a missing attribute kills the
   notebook before the run starts.
3. New pre-run budget probe: fair share vs the configured per-game cap (all three saved runs
   end at exactly max == min == cap, so the cap is the action allotment).
4. New post-run roster probe reading `bm.game_runs`: whether base game codes repeat (the 0 vs
   +5..15 question for patch 0006) and `actions_per_call` (is the batch pressure working).

Untouched, deliberately: the 7-patch chain (v13.3 certified 7/7 on clean r033),
`src/` (standalone == patched, byte for byte), `playbook.json` (14/14 on the real engine),
`ARC3_OPENER_COMMIT_HINT=1` and `ARC3_WINPATH_LOG=1` (the two mechanisms v13.3 exists for).

Usage:
  python3 tools/build_v15.py --src <duck-v13-3-arena dir> --out arc3-duck-v15.ipynb
"""
from __future__ import annotations

import argparse
import json
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


ESCALATE_NOTE = """# v15 adds (relative to v13.3-arena, all env-only or read-only):
#   ESCALATE_ACTIONS 10 -> 20. Measured on r085's 32 completed levels: @10 fires 154 times
#   (15.3% of the game's token pool in directive text alone) and on 31/32 levels it tells the
#   model to stop probing while it is at or better than the human baseline; @20 fires 60
#   times (6.0%). The directive costs ~146 tokens but each one invites a multi-thousand-token
#   modelling turn, so the count matters more than the text.
#   Kill-switch: set ESCALATE_ACTIONS back to 10 (the v13.3 baseline) in this cell only.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(PKG / "src" / "base-v13-3-arena.ipynb"),
                    help="the certified v13.3-arena notebook (kept under src/ for the record)")
    ap.add_argument("--out", default=str(PKG / "arc3-duck-v15.ipynb"))
    args = ap.parse_args()

    nb = json.loads(Path(args.src).read_text())
    cells = nb["cells"]
    assert len(cells) == 36, f"v13.3 has 36 cells, got {len(cells)}"

    # 1. Switch cell: measured threshold.
    i = next(k for k, c in enumerate(cells) if "v13 switch" in cell_source(c))
    s = cell_source(cells[i])
    s = replace_once(s, "ESCALATE_ACTIONS = 10", "ESCALATE_ACTIONS = 20", "escalate value")
    s = replace_once(s, "import os as _v11_os", ESCALATE_NOTE + "import os as _v11_os", "switch note")
    s = replace_once(s, 'print(f"v13.3-arena profile=', 'print(f"v15 profile=', "profile print")
    set_source(cells[i], s)

    # 2. Guard the c45 roster hook that sits in the config cell.
    i = next(k for k, c in enumerate(cells)
             if "_install_roster_probe" in cell_source(c) and "bm.solver" in cell_source(c))
    s = cell_source(cells[i])
    s = replace_once(
        s,
        "    _orig_play = _S._HarnessGameSession.play\n",
        "    try:\n"
        "        _orig_play = _S._HarnessGameSession.play\n"
        "    except AttributeError as exc:  # inny revision bundla -> nie zabijaj notebooka\n"
        "        return f\"probe: POMINIETA (brak _HarnessGameSession.play: {exc!r})\"\n",
        "probe attribute guard",
    )
    s = replace_once(
        s,
        "print(_install_roster_probe(), flush=True)\n",
        "try:  # v15: ten hook stoi w komorce, ktora ustawia bm.solver.* - nie moze rzucic\n"
        "    print(_install_roster_probe(), flush=True)\n"
        "except Exception as _probe_exc:\n"
        "    print(f\"probe: BLAD {_probe_exc!r}\", flush=True)\n",
        "probe call guard",
    )
    set_source(cells[i], s)

    # 3. Budget probe before the run.
    i = next(k for k, c in enumerate(cells) if "bm.games = _offline_games(" in cell_source(c))
    s = cell_source(cells[i])
    anchor = "# Outside a real submission, stop ~10 min before the wall-clock budget for a graceful exit."
    s = replace_once(s, anchor, BUDGET_PROBE + "\n" + anchor, "budget probe anchor")
    set_source(cells[i], s)

    # 4. Roster probe after the metering cell.
    i = max(k for k, c in enumerate(cells) if "v11 metering" in cell_source(c))
    cells.insert(i + 1, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": ROSTER_PROBE.splitlines(keepends=True),
    })

    # 5. Version strings.
    for c in cells:
        if c["cell_type"] != "code":
            continue
        txt = cell_source(c).replace('"name": "v13-3-arena"', '"name": "v15"')
        if txt != cell_source(c):
            set_source(c, txt)

    out = Path(args.out)
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"built {out} ({len(cells)} cells, {out.stat().st_size} bytes)")


BUDGET_PROBE = r'''# === v15 budget probe: co naprawde ogranicza wynik - cap czy tokeny? ========
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
    print(f"v15 budget: {_n_games} gier x {_budget['passes']} pass(es), concurrency {_conc}, "
          f"uczciwy udzial {_fair / 60:.0f} min/gra, cap {_cap / 60:.0f} min "
          f"-> {_budget['cap_over_fair']}x", flush=True)
    if _cap and _fair and _cap / _fair > 1.3:
        print(f"v15 budget: UWAGA cap jest {_cap / _fair:.1f}x powyzej udzialu - jesli gra nie konczy "
              f"sie wczesniej, ogon rosteru ({_n_games} gier) nie zagra", flush=True)
except Exception as _budget_exc:
    print(f"v15 budget probe skipped: {_budget_exc!r}", flush=True)
'''

ROSTER_PROBE = r'''# === v15 roster probe: czy roster powtarza gry? (0 kosztu GPU) ==============
# Jedyne pytanie, od ktorego zalezy, czy pamiec win-path (patch 0006) jest warta
# 0 czy +5..15 punktow sredniej. v13.x zaklada "tak" i nie mierzy tego wcale.
# Ten blok czyta bm.game_runs PO biegu - nie dotyka solvera, nie moze wywalic runu.
import json as _v14_json
from collections import Counter as _V14Counter

_v14_out = WORKING_DIR / "roster_probe.jsonl"
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
        print("v15 roster: " + _v14_json.dumps(_summary, sort_keys=True), flush=True)
        if _dups:
            print(f"v15 roster: POWTARZA SIE {len(_dups)} bazowych gier (do {_summary['max_repeats']}x) "
                  f"-> pamiec miedzy wpisami PLACI", flush=True)
        else:
            print("v15 roster: ZADNY bazowy kod sie nie powtarza -> pamiec win-path = 0 pkt "
                  "(dokladnie tak, jak twierdzi OCENA-V9 c45)", flush=True)
        print(f"v15 roster: zapisane do {_v14_out}", flush=True)
        if _acpc and _summary["mean_actions_per_call"] < 1.5:
            print(f"v15 roster: a/call = {_summary['mean_actions_per_call']} < 1.5 -> commit(plan) "
                  f"praktycznie nie odpala; dzwignia 50+ lezy odlogiem", flush=True)
except Exception as _v14_exc:
    print(f"v15 roster probe skipped: {_v14_exc!r}", flush=True)
'''


if __name__ == "__main__":
    main()
