#!/usr/bin/env python3
"""Build `arc3-duck-v17.ipynb` (v17-arena-dyn) from the certified v13.7-final.

v17-arena-dyn = v13.7-final + exactly one LIVE new variable (D' slot priority):

  base  v13.7-final (41 cells): v13.6 (self-pace 0009 + live a/call instrument
        + coverage/baseline probes) + patch 0010 dyn-level-budget, DORMANT
        (`ARC3_LEVEL_TOKEN_CAP="0"` => module inert on the submission)
  new   patch 0011 `ARC3_PRIORITY_DPRIME=1`: D' slot priority on the shared
        priority gate and on the fallback path. The shipped `priority_value`
        stays in the file and is what runs when the switch is `"0"`.

Both levers are packaged and independent: D' is ON (it is the one thing this
build measures), the level budget is inherited armed-off and is armed by ONE
value. If it is ever armed, arm it LOW (~20000), not at 60000: the rule is
`cap = clamp(max(static_cap, median*4), cap_min, cap_max)`, so the arming value
is also the FLOOR - at 60000 it can only ever loosen, never cut the games that
burn everything on a level they never clear (measured: it engages in 16/40
games and tightens in 0/16).

Why this pairing and not v16-arena: v13.4's relative escalation (patch 0008)
is DEAD in the rerun that counts — `taaf/game.py` documents
`base_actions_per_level is None` in submission mode, so 0008 degrades to the
absolute 20 + cap 2 (measured: 42 nudges / 26 premature on r085). Self-pace
needs no hidden data, so it is the highest-value base available today. D' is
orthogonal to it: different file (priority_scheduler.py), different question
(which game gets the next slot, not when to nudge).

Everything else (model, serving, playbook, win-path, plan-commit) is inherited
unchanged; with `ARC3_PRIORITY_DPRIME="0"` the notebook is v13.6-final again.
Two cells are added purely for observability: a pre-run D' probe (is the switch
live? is the OFF path byte-identical?) and a post-run D' meter.

Usage:
  python3 tools/build_v17.py [--prev src/base-v13-7-final.ipynb] \
      [--patch patches/0010-priority-dprime.patch] [--out arc3-duck-v17.ipynb]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
MARK_V137_CELLS = 41  # v13.7-final has exactly 41 cells

DPRIME_PROBE_CELL = r'''# === v17 D' priority probe: czy przelacznik naprawde trafia do schedulera? ===
# Patch 0010 dodaje ARC3_PRIORITY_DPRIME. Ten blok (0 kosztu GPU, przed bm.run)
# sprawdza trzy rzeczy, ktorych nie widac w logu po fakcie:
#   1. czy flaga jest w env i czy patch sie zaladowal (dprime_enabled),
#   2. czy przy WYLACZONYM przelaczniku select_priority zwraca dokladnie to
#      samo co fabryczne priority_value (jednozmiennosciowy eksperyment),
#   3. czy przy WLACZONYM przelaczniku D' rozroznia gry.
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
    _mode_kwargs = dict(normalize_score=True, tail_lookup="remaining", tail_fraction=0.2)
    _legacy = _dprime_ps.priority_value(_mid, **_mode_kwargs)
    print(f"v17 dprime: switch={'ON' if _dprime_on else 'OFF'} "
          f"env={os.environ.get('ARC3_PRIORITY_DPRIME')!r} "
          f"legacy(mid)={_legacy} dprime(mid)={_dprime_ps.dprime_priority(_mid, tail_fraction=0.2)}",
          flush=True)
    print(f"v17 dprime: depth order deep>mid={_dprime_ps.dprime_priority(_deep) > _dprime_ps.dprime_priority(_mid)} "
          f"fresh={_dprime_ps.dprime_priority(_early)}", flush=True)
    _cheap = _snap(level=3, actions=40, tokens=90000.0, total_levels=7,
                   mean_tokens_per_cleared_level=8000.0)
    print(f"v17 dprime: cheap>pricey={_dprime_ps.dprime_priority(_cheap) > _dprime_ps.dprime_priority(_mid)}",
          flush=True)
    os.environ["ARC3_PRIORITY_DPRIME"] = "0"
    _off = _dprime_ps.select_priority(_mid, **_mode_kwargs)
    os.environ["ARC3_PRIORITY_DPRIME"] = "1" if _dprime_on else "0"
    print(f"v17 dprime: switch-off == priority_value: {_off == _legacy}", flush=True)
    if _off != _legacy:
        print("v17 dprime: UWAGA przelacznik zmienia wynik takze przy OFF - "
              "eksperyment nie jest jednozmiennosciowy", flush=True)
    if not _dprime_on:
        print("v17 dprime: UWAGA ARC3_PRIORITY_DPRIME nieaktywny - ten bieg jest "
              "v13.6-final, nie v17", flush=True)
except Exception as _dprime_exc:
    print(f"v17 dprime probe skipped: {_dprime_exc!r}", flush=True)
'''

DPRIME_METER_CELL = r'''# === v17 D' metering: jaki byl zmierzony pace i czy D' mial co sortowac? ===
# Post-run, 0 kosztu GPU. Liczy z bm.game_runs to, czego D' uzywa jako wejscia:
# tokeny na ukonczony poziom (mean_tokens_per_cleared_level) i akcje na call.
# Jesli pace jest ~0 (malo ukonczonych poziomow), D' pracuje na referencji 30k
# i jego wklad w sortowanie jest maly - to widac wlasnie tutaj.
import json as _v17_json

_v17_out = WORKING_DIR / "dprime_metering.jsonl"
try:
    _v17_rows = []
    for _i, _r in enumerate(list(getattr(bm, "game_runs", None) or [])):
        _hist = list(getattr(_r, "history", []) or [])
        _tokens = sum(int(getattr(_h, "generated_tokens", 0) or 0) for _h in _hist)
        _calls = sum(1 for _h in _hist if int(getattr(_h, "generated_tokens", 0) or 0) > 0)
        _levels = int(getattr(_r, "levels_completed", 0) or 0)
        _actions = sum(int(_x or 0) for _x in (getattr(_r, "actions_per_level", []) or []))
        _v17_rows.append({
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
    with _v17_out.open("w", encoding="utf-8") as _fh:
        for _row in _v17_rows:
            _fh.write(_v17_json.dumps(_row, sort_keys=True) + "\n")
    _paces = [r["tokens_per_cleared_level"] for r in _v17_rows if r["levels"]]
    _acpc = [r["actions_per_call"] for r in _v17_rows if r["calls"]]
    _summary = {
        "runs": len(_v17_rows),
        "runs_with_a_cleared_level": len(_paces),
        "mean_tokens_per_cleared_level": round(sum(_paces) / len(_paces), 1) if _paces else 0.0,
        "min_tokens_per_cleared_level": round(min(_paces), 1) if _paces else 0.0,
        "max_tokens_per_cleared_level": round(max(_paces), 1) if _paces else 0.0,
        "mean_actions_per_call": round(sum(_acpc) / len(_acpc), 2) if _acpc else 0.0,
        "switch": os.environ.get("ARC3_PRIORITY_DPRIME"),
    }
    print("v17 dprime metering: " + _v17_json.dumps(_summary, sort_keys=True), flush=True)
    print(f"v17 dprime metering: zapisane do {_v17_out}", flush=True)
    if not _paces:
        print("v17 dprime metering: ZADEN run nie ukonczyl poziomu -> D' dzialal "
              "na referencji 30k (sortowanie = efekt uboczny, nie pomiar)", flush=True)
except Exception as _v17_exc:
    print(f"v17 dprime metering skipped: {_v17_exc!r}", flush=True)
'''

V17_COMMENT = '''# v17-arena-dyn (Arena, 30.10): JEDNA ZYWA zmienna wobec v13.7-final — patch 0011
# ARC3_PRIORITY_DPRIME=1: priorytet slotu D' (formula opublikowana, skala 1000)
# zamiast fabrycznego priority_value, na bramce priorytetu i na sciezce fallback.
# D' potrzebuje zmierzonego pace'a tokenow na ukonczony poziom, ktorego stary
# koszt-mnoznik nie dostarczal. Pomiar na porownywalnej linii: 4 drawy D'
# 31.54/30.74/29.05/24.77 (sr. ~29.0) vs baseline ~25.77 (SD ~3.93) — maly,
# zaszumiony sygnal, nie dowod na 50+. D' jest ortogonalny wobec self-pace
# 0009: inny plik (priority_scheduler.py) i inne pytanie (ktora gra dostaje
# slot, nie kiedy nudge).
# ARMING NOTE (0010 dyn-level-budget, odziedziczony z v13.7): zostaje dormant,
# ARC3_LEVEL_TOKEN_CAP="0". Jesli
# kiedys uzbrajamy, to NISKO (~20000), nie 60000: cap = max(static, mediana*4),
# wiec wartosc uzbrojenia jest jednoczesnie PODLOGA — przy 60000 regula tylko
# poluzowuje (16/40 gier, 0/16 ciaśniej) i nie tnie gier, ktore pala wszystko na
# poziomie, ktorego nie koncza.
# Kill-switch: "ARC3_PRIORITY_DPRIME": "0" = dokladnie v13.7-final.
'''

LEVERS_CELL = r'''# === v17 levers: co DALBY patch 0010, gdyby go uzbroic? (0 kosztu GPU) ===
# Post-run. Liczy z historii kazdej gry koszt tokenow na UKONCZONY poziom i pokazuje,
# jaki cap dostalaby gra przy uzbrojeniu 20000 vs 60000. Regula 0010 to
#   cap = clamp(max(static_cap, mediana(koszty ukonczonych) * 4), cap_min, 150k)
# wiec wartosc uzbrojenia jest jednoczesnie PODLOGA: przy 60000 regula tylko poluzowuje.
# Ten blok jest po to, zeby decyzja o uzbrojeniu byla pomiarem z TEGO biegu, nie z cudzego.
import json as _lv_json
import statistics as _lv_stats

try:
    _lv_rows = []
    for _r in list(getattr(bm, "game_runs", None) or []):
        _hist = list(getattr(_r, "history", []) or [])
        _apl = [int(_x or 0) for _x in (getattr(_r, "actions_per_level", []) or [])]
        _tok = [int(getattr(_h, "generated_tokens", 0) or 0) for _h in _hist]
        _costs, _i = [], 0
        for _n in _apl:
            _costs.append(sum(_tok[_i:_i + _n]))
            _i += _n
        _done = int(getattr(_r, "levels_completed", 0) or 0)
        _comp = _costs[:_done]
        _total = sum(_costs) or 0
        _med = _lv_stats.median(_comp) if len(_comp) >= 2 else None
        _caps = {}
        for _arm in (20000, 60000):
            _caps[_arm] = (int(min(max(_arm, _med * 4.0), 150000)) if _med else _arm)
        _lv_rows.append({
            "game_id": str(getattr(_r, "game_id", "?") or "?")[:4],
            "cleared": _done,
            "levels": len(_costs),
            "median_done": int(_med) if _med else 0,
            "cap_if_armed_20k": _caps[20000],
            "cap_if_armed_60k": _caps[60000],
            "pct_tokens_on_uncleared": round(100.0 * sum(_costs[_done:]) / _total, 1) if _total else 0.0,
        })
    _lv_out = WORKING_DIR / "levers.jsonl"
    with _lv_out.open("w", encoding="utf-8") as _fh:
        for _row in _lv_rows:
            _fh.write(_lv_json.dumps(_row, sort_keys=True) + "\n")
    _engaged = [r for r in _lv_rows if r["median_done"]]
    _tighter60 = sum(1 for r in _engaged if r["cap_if_armed_60k"] < 60000)
    _tighter20 = sum(1 for r in _engaged if r["cap_if_armed_20k"] < 20000)
    _med_unc = _lv_stats.median([r["pct_tokens_on_uncleared"] for r in _lv_rows]) if _lv_rows else 0.0
    print(f"v17 levers: {len(_lv_rows)} gier, regula dyn wlacza sie w {len(_engaged)} "
          f"(reszta: cap = statyczny); mediana tokenow na nieukonczone {_med_unc:.1f}%", flush=True)
    print(f"v17 levers: przy uzbrojeniu 60000 ciaśniej w {_tighter60} grach, "
          f"przy 20000 ciaśniej w {_tighter20} grach -> "
          f"{'uzbrajac NISKO (20000)' if _tighter60 == 0 else 'sprawdzic rozklad'} "
          f"jesli celem jest ciecie marnotrawstwa", flush=True)
    for _r in _lv_rows[:10]:
        print("v17 levers: " + _lv_json.dumps(_r, sort_keys=True), flush=True)
except Exception as _lv_exc:
    print(f"v17 levers skipped: {_lv_exc!r}", flush=True)
'''
WRITER_0011 = '''# ARC3 Duck v17-arena-dyn: patch 0011-priority-dprime — D' slot priority.
# Jedna zmienna eksperymentalna wobec v13.6-final. Env-gated: przy
# ARC3_PRIORITY_DPRIME=0 select_priority() wywoluje fabryczne priority_value()
# z tymi samymi argumentami, wiec zachowanie jest identyczne.
from pathlib import Path as _P
'''


def cell_source(cell: dict) -> str:
    return "".join(cell.get("source", []))


def set_source(cell: dict, text: str) -> None:
    cell["source"] = text.splitlines(keepends=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev", default=str(PKG / "src" / "base-v13-6-final.ipynb"))
    ap.add_argument("--patch", default=str(PKG / "patches" / "0011-priority-dprime.patch"))
    ap.add_argument("--out", default=str(PKG / "arc3-duck-v17.ipynb"))
    args = ap.parse_args()

    nb = json.loads(Path(args.prev).read_text())
    cells = nb["cells"]
    assert len(cells) == MARK_V137_CELLS, f"prev has {len(cells)} cells, expected {MARK_V137_CELLS}"

    patch_text = Path(args.patch).read_text()
    if not patch_text.endswith("\n"):
        patch_text += "\n"

    # 1. ARC3_VARIANT cell: register patch 0010 and its switch.
    variant_idx = next(i for i, c in enumerate(cells) if "ARC3_VARIANT = " in cell_source(c))
    src = cell_source(cells[variant_idx])
    m = re.search(r"ARC3_VARIANT = (\{.*\})$", src, flags=re.M)
    assert m, "ARC3_VARIANT literal not found"
    variant = json.loads(m.group(1))
    env = variant["env"]
    assert env.get("ARC3_ESCALATE_RELATIVE") == "1" and env.get("ARC3_OPENER_COMMIT_HINT") == "1"
    assert env.get("ARC3_ESCALATE_SELF_PACE") == "1", "self-pace must stay armed"
    assert env.get("ARC3_LEVEL_TOKEN_CAP") == "0", "dyn-level-budget must stay dormant"
    assert "/kaggle/duck-extra-08.patch" in variant["patch_files"]
    assert "0010-dyn-level-budget.patch" in variant["patches"], "v13.7 base expected"
    env["ARC3_PRIORITY_DPRIME"] = "1"
    env["ARC3_PRIORITY_PACE"] = "0"  # D' reads raw tokens; the legacy factor stays off
    variant["patch_files"].append("/kaggle/duck-extra-09.patch")
    variant["patches"].append("0011-priority-dprime.patch")
    variant["name"] = "v17-arena-dyn"
    src = src[:m.start(1)] + json.dumps(variant) + src[m.end(1):]
    set_source(cells[variant_idx], src)

    # 2. Switch cell: version print + comment block.
    switch_idx = next(i for i, c in enumerate(cells) if "v13 switch" in cell_source(c))
    src = cell_source(cells[switch_idx])
    anchor = "# (AttributeError-proof) + budget/roster probes from v14 (observability only).\n"
    assert src.count(anchor) == 1, "v13.6 comment anchor"
    src = src.replace(anchor, anchor + V17_COMMENT, 1)
    src, n = re.subn(r"v13\.7-final profile", "v17-arena-dyn profile", src, count=1)
    assert n == 1, "switch print anchor"
    set_source(cells[switch_idx], src)

    # 3. extra-09 writer cell right after the extra-08 writer cell.
    w8_idx = next(i for i, c in enumerate(cells)
                  if "duck-extra-08.patch" in cell_source(c) and "write_text" in cell_source(c))
    writer = WRITER_0011 + f'_P("/kaggle/duck-extra-09.patch").write_text({patch_text!r})\n'
    cells.insert(w8_idx + 1, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": writer.splitlines(keepends=True),
    })

    # 4. D' probe immediately before the budget probe (both pre-run).
    budget_idx = next(i for i, c in enumerate(cells) if "budget probe" in cell_source(c))
    cells.insert(budget_idx, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": DPRIME_PROBE_CELL.splitlines(keepends=True),
    })

    # 5. D' metering, then the lever report (both post-run, 0 GPU).
    for _src in (DPRIME_METER_CELL, LEVERS_CELL):
        cells.append({
            "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": _src.splitlines(keepends=True),
        })

    out = Path(args.out)
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"built {out} ({len(cells)} cells, {out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
