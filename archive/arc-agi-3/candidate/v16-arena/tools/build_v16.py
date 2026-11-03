#!/usr/bin/env python3
"""Build `arc3-duck-v16.ipynb` (v16-arena) from the v13.4-unified notebook.

v16-arena = v13.4-unified + exactly one new experimental variable (D' slot
priority), everything else untouched byte-for-byte:

  base  v13.4-unified (39 cells): v13.2 mechanics + opener hint + patch 0007
        (win-path log) + ESCALATE_ACTIONS=20 + patch 0008 (relative trigger,
        cap 2/level) + guarded roster hook + budget/roster probes
  new   patch 0009 `ARC3_PRIORITY_DPRIME=1`: D' slot priority on the shared
        priority gate and on the fallback path. The shipped `priority_value`
        stays in the file and is what runs when the switch is `"0"`, so the
        variable is one env line.

Everything else (model, serving, playbook, win-path, plan-commit, escalation)
is inherited unchanged; with `ARC3_PRIORITY_DPRIME="0"` the notebook is
v13.4-unified again. Two cells are added purely for observability: a pre-run
D' probe (does the switch actually reach the scheduler? are both paths sane?)
and a post-run D' meter (what the measured token pace per cleared level was).

Usage:
  python3 tools/build_v16.py \
      [--prev ../v16-arena/src/arc3-duck-v13-4-unified.ipynb] \
      [--patch patches/0009-priority-dprime.patch] [--out arc3-duck-v16.ipynb]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
MARK_V134_CELLS = 39  # v13.4-unified has exactly 39 cells


def cell_source(cell: dict) -> str:
    return "".join(cell.get("source", []))


def set_source(cell: dict, text: str) -> None:
    cell["source"] = text.splitlines(keepends=True)


DPRIME_PROBE_CELL = r'''# === v16 D' priority probe: czy przelacznik naprawde trafia do schedulera? ===
# Patch 0009 dodaje ARC3_PRIORITY_DPRIME. Ten blok (0 kosztu GPU, przed
# bm.run) sprawdza trzy rzeczy, ktorych nie widac w logu po fakcie:
#   1. czy flaga jest w env i czy patch sie zaladowal (dprime_enabled),
#   2. czy przy WYLACZONYM przelaczniku select_priority zwraca dokladnie to
#      samo co fabryczne priority_value (jednozmiennosciowy eksperyment),
#   3. czy przy WLACZONYM przelaczniku D' rozroznia gry (glebsza > plytsza,
#      tanszy zmierzony pace > drozszy).
# NICZEGO nie zmienia. Awaria -> "skipped", notebook leci dalej.
try:
    from inference.agent import priority_scheduler as _dprime_ps

    _dprime_on = bool(_dprime_ps.dprime_enabled())
    _snap = _dprime_ps.PrioritySnapshot
    _early = _snap(level=1, actions=0, tokens=0.0, total_levels=8)
    _mid = _snap(level=3, actions=40, tokens=90000.0, total_levels=7,
                 mean_tokens_per_cleared_level=31000.0)
    _deep = _snap(level=5, actions=40, tokens=90000.0, total_levels=7,
                  mean_tokens_per_cleared_level=31000.0)
    _legacy = _dprime_ps.priority_value(_mid, tail_fraction=0.2)
    print(f"v16 dprime: switch={'ON' if _dprime_on else 'OFF'} "
          f"env={os.environ.get('ARC3_PRIORITY_DPRIME')!r} "
          f"legacy(mid)={_legacy} dprime(mid)={_dprime_ps.dprime_priority(_mid, tail_fraction=0.2)}",
          flush=True)
    print(f"v16 dprime: depth order deep>mid={_dprime_ps.dprime_priority(_deep) > _dprime_ps.dprime_priority(_mid)} "
          f"fresh={_dprime_ps.dprime_priority(_early)}", flush=True)
    _cheap = _snap(level=3, actions=40, tokens=90000.0, total_levels=7,
                   mean_tokens_per_cleared_level=8000.0)
    print(f"v16 dprime: cheap>pricey={_dprime_ps.dprime_priority(_cheap) > _dprime_ps.dprime_priority(_mid)}",
          flush=True)
    _mode_kwargs = dict(normalize_score=True, tail_lookup="remaining", tail_fraction=0.2)
    os.environ["ARC3_PRIORITY_DPRIME"] = "0"
    _off = _dprime_ps.select_priority(_mid, **_mode_kwargs)
    os.environ["ARC3_PRIORITY_DPRIME"] = "1" if _dprime_on else "0"
    print(f"v16 dprime: switch-off == priority_value: {_off == _legacy}", flush=True)
    if _off != _legacy:
        print("v16 dprime: UWAGA przelacznik zmienia wynik takze przy OFF - "
              "eksperyment nie jest jednozmiennosciowy", flush=True)
    if not _dprime_on:
        print("v16 dprime: UWAGA ARC3_PRIORITY_DPRIME nieaktywny - ten bieg jest "
              "v13.4-unified, nie v16", flush=True)
except Exception as _dprime_exc:
    print(f"v16 dprime probe skipped: {_dprime_exc!r}", flush=True)
'''

DPRIME_METER_CELL = r'''# === v16 D' metering: jaki byl zmierzony pace i czy D' mial co sortowac? ===
# Post-run, 0 kosztu GPU. Liczy z bm.game_runs to, czego D' uzywa jako wejscia:
# tokeny-na-ukonczony-poziom (mean_tokens_per_cleared_level) i akcje na call.
# Jesli pace jest ~0 (malo ukonczonych poziomow), D' pracuje na referencji 30k
# i jego wklad w sortowanie jest maly - to widac wlasnie tutaj.
import json as _v16_json

_v16_out = WORKING_DIR / "dprime_metering.jsonl"
try:
    _v16_rows = []
    for _i, _r in enumerate(list(getattr(bm, "game_runs", None) or [])):
        _hist = list(getattr(_r, "history", []) or [])
        _tokens = sum(int(getattr(_h, "generated_tokens", 0) or 0) for _h in _hist)
        _calls = sum(1 for _h in _hist if int(getattr(_h, "generated_tokens", 0) or 0) > 0)
        _levels = int(getattr(_r, "levels_completed", 0) or 0)
        _actions = sum(int(_x or 0) for _x in (getattr(_r, "actions_per_level", []) or []))
        _v16_rows.append({
            "index": _i,
            "game_id": str(getattr(_r, "game_id", "?") or "?"),
            "levels": _levels,
            "actions": _actions,
            "tokens": _tokens,
            "calls": _calls,
            "actions_per_call": round(_actions / _calls, 2) if _calls else 0.0,
            "tokens_per_action": round(_tokens / _actions, 1) if _actions else 0.0,
            "tokens_per_cleared_level": round(_tokens / _levels, 1) if _levels else 0.0,
            "score": round(float(getattr(_r, "final_score", 0.0) or 0.0), 2),
        })
    with _v16_out.open("w", encoding="utf-8") as _fh:
        for _row in _v16_rows:
            _fh.write(_v16_json.dumps(_row, sort_keys=True) + "\n")
    _paces = [r["tokens_per_cleared_level"] for r in _v16_rows if r["levels"]]
    _acpc = [r["actions_per_call"] for r in _v16_rows if r["calls"]]
    _summary = {
        "runs": len(_v16_rows),
        "runs_with_a_cleared_level": len(_paces),
        "mean_tokens_per_cleared_level": round(sum(_paces) / len(_paces), 1) if _paces else 0.0,
        "min_tokens_per_cleared_level": round(min(_paces), 1) if _paces else 0.0,
        "max_tokens_per_cleared_level": round(max(_paces), 1) if _paces else 0.0,
        "mean_actions_per_call": round(sum(_acpc) / len(_acpc), 2) if _acpc else 0.0,
        "switch": os.environ.get("ARC3_PRIORITY_DPRIME"),
    }
    print("v16 dprime metering: " + _v16_json.dumps(_summary, sort_keys=True), flush=True)
    print(f"v16 dprime metering: zapisane do {_v16_out}", flush=True)
    if not _paces:
        print("v16 dprime metering: ZADEN run nie ukonczyl poziomu -> D' dzialal "
              "na referencji 30k (sortowanie = efekt uboczny, nie pomiar)", flush=True)
except Exception as _v16_exc:
    print(f"v16 dprime metering skipped: {_v16_exc!r}", flush=True)
'''

V16_COMMENT = '''# v16-arena (Arena, 30.10): JEDNA zmienna wobec v13.4-unified — patch 0009
# ARC3_PRIORITY_DPRIME=1: priorytet slotu D' (formula opublikowana, skala 1000)
# zamiast fabrycznego priority_value, na bramce priorytetu i na sciezce
# fallback. D' potrzebuje zmierzonego pace'a tokenow na ukonczony poziom
# (ProgressPace.total_tokens), ktorego stary koszt-mnoznik nie dostarczal.
# Pomiar na porownywalnej linii: 4 drawy D' 31.54/30.74/29.05/24.77 (sr. ~29.0)
# vs baseline ~25.77 (SD ~3.93) — maly, zaszumiony sygnal, nie dowod na 50+.
# Kill-switch: "ARC3_PRIORITY_DPRIME": "0" = dokladnie v13.4-unified.
'''

WRITER_0009 = '''# ARC3 Duck v16-arena: patch 0009-priority-dprime — D' slot priority.
# Jedna zmienna eksperymentalna wobec v13.4-unified. Env-gated: przy
# ARC3_PRIORITY_DPRIME=0 select_priority() wywoluje fabryczne priority_value()
# z tymi samymi argumentami, wiec zachowanie jest identyczne.
from pathlib import Path as _P
'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev", default=str(PKG / "src" / "arc3-duck-v13-4-unified.ipynb"))
    ap.add_argument("--patch", default=str(PKG / "patches" / "0009-priority-dprime.patch"))
    ap.add_argument("--out", default=str(PKG / "arc3-duck-v16.ipynb"))
    args = ap.parse_args()

    nb = json.loads(Path(args.prev).read_text())
    cells = nb["cells"]
    assert len(cells) == MARK_V134_CELLS, f"prev has {len(cells)} cells, expected {MARK_V134_CELLS}"

    patch_text = Path(args.patch).read_text()
    if not patch_text.endswith("\n"):
        patch_text += "\n"

    # 1. ARC3_VARIANT cell: register patch 0009 and its switch.
    variant_idx = next(i for i, c in enumerate(cells) if "ARC3_VARIANT = " in cell_source(c))
    src = cell_source(cells[variant_idx])
    m = re.search(r"ARC3_VARIANT = (\{.*\})$", src, flags=re.M)
    assert m, "ARC3_VARIANT literal not found"
    variant = json.loads(m.group(1))
    env = variant["env"]
    assert env.get("ARC3_ESCALATE_RELATIVE") == "1" and env.get("ARC3_OPENER_COMMIT_HINT") == "1"
    assert "/kaggle/duck-extra-06.patch" in variant["patch_files"]
    assert "0008-arena-escalate-relative.patch" in variant["patches"]
    env["ARC3_PRIORITY_DPRIME"] = "1"
    env["ARC3_PRIORITY_PACE"] = "0"  # D' reads raw tokens; the factor stays off
    variant["patch_files"].append("/kaggle/duck-extra-07.patch")
    variant["patches"].append("0009-priority-dprime.patch")
    variant["name"] = "v16-arena"
    src = src[:m.start(1)] + json.dumps(variant) + src[m.end(1):]
    set_source(cells[variant_idx], src)

    # 2. Switch cell: version print + comment block.
    switch_idx = next(i for i, c in enumerate(cells) if "v13 switch" in cell_source(c))
    src = cell_source(cells[switch_idx])
    anchor = ('# (AttributeError-proof) + budget/roster probes from v14 (observability only).\n')
    assert src.count(anchor) == 1, "v13.4 comment anchor"
    src = src.replace(anchor, anchor + V16_COMMENT, 1)
    src, n = re.subn(r'v13\.4-unified profile', "v16-arena profile", src, count=1)
    assert n == 1, "switch print anchor"
    set_source(cells[switch_idx], src)

    # 3. extra-07 writer cell right after the extra-06 writer cell.
    w6_idx = next(i for i, c in enumerate(cells)
                  if "duck-extra-06.patch" in cell_source(c) and "write_text" in cell_source(c))
    writer = WRITER_0009 + f'_P("/kaggle/duck-extra-07.patch").write_text({patch_text!r})\n'
    cells.insert(w6_idx + 1, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": writer.splitlines(keepends=True),
    })

    # 4. D' probe immediately before the budget probe (both pre-run).
    budget_idx = next(i for i, c in enumerate(cells) if "v13.4 budget probe" in cell_source(c))
    cells.insert(budget_idx, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": DPRIME_PROBE_CELL.splitlines(keepends=True),
    })

    # 5. D' metering at the very end (after the roster probe).
    cells.append({
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": DPRIME_METER_CELL.splitlines(keepends=True),
    })

    out = Path(args.out)
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"built {out} ({len(cells)} cells, {out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
