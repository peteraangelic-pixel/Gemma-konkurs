#!/usr/bin/env python3
"""Niezależny audyt patcha 0010 (dyn-level-budget z v13-7-final) — twierdzenia vs arytmetyka.

Dwie części, obie bez GPU i bez ich kodu testowego:

  korpus   ile poziomów UKOŃCZONYCH kosztowało więcej niż statyczny cap (45k/60k/90k),
           jaka część tokenów gry idzie na poziomy, których nigdy nie ukończyła, i jaki
           cap dostałaby każda gra z reguły clamp(max(static, mediana×4), cap_min, 150k);
  logika   ścieżka uśpiona (CAP=0) i ścieżka kontrolna (ARC3_DYN_CAP=0) w kontrze do
           modułu statycznego z patcha 0004 — 8000 decyzji na przypadek, chodzenie losowe.

Użycie:
  python3 audit_dyn_budget.py benchmarks r085.json r093.json r110.json r118.json
  python3 audit_dyn_budget.py logic <moduł_pre_0010.py> <moduł_post_0010.py>

`moduł_pre_0010.py` = `inference/framework/arc3_level_budget.py` z drzewa r033 po
patchach 0001–0009; `moduł_post_0010.py` = ten sam plik po patchu 0010.
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import statistics
import sys
from pathlib import Path

CAPS = (45_000, 60_000, 90_000)
ARMED = 60_000  # proponowana wartość uzbrojenia z README v13-7-final


def level_costs(run: dict) -> list[int]:
    """Tokeny na poziom: historia akcja-po-akcji + actions_per_level jako granice."""
    hist = run.get("history") or []
    apl = [int(x or 0) for x in (run.get("actions_per_level") or [])]
    toks = [int(h.get("generated_tokens", 0) or 0) for h in hist]
    costs, i = [], 0
    for n in apl:
        costs.append(sum(toks[i:i + n]))
        i += n
    if i < len(toks):
        costs.append(sum(toks[i:]))
    return costs


def audit_benchmarks(paths: list[str]) -> int:
    over = {c: [] for c in CAPS}
    rows, shares, dyn_caps, engaged, total = [], [], [], 0, 0
    for path in paths:
        data = json.loads(Path(path).read_text())
        for run in data.get("game_runs") or []:
            total += 1
            gid = str(run.get("game_id", "?"))[:4]
            done = int(run.get("levels_completed") or 0)
            costs = level_costs(run)
            completed = costs[:done]
            tokens = sum(costs)
            share = 100.0 * sum(costs[done:]) / tokens if tokens else 0.0
            shares.append(share)
            for c in completed:
                for cap in CAPS:
                    if c > cap:
                        over[cap].append((gid, c))
            dyn = static_cap = ARMED
            if len(completed) >= 2:
                engaged += 1
                med = statistics.median(completed)
                dyn = int(min(max(static_cap, med * 4.0), 150_000))
                dyn_caps.append((dyn, int(med)))
            rows.append((Path(path).stem, gid, done, len(costs), tokens, share, dyn))

    print("bench  gra  ukonczone/poziomy  tokeny  %tokenow_na_nieukonczone  cap_dyn")
    for r in rows:
        print(f"{r[0]:6s} {r[1]:5s} {r[2]}/{r[3]:<3d} {r[4]:8d} {r[5]:8.1f}% {r[6]:8d}")

    print("\nA. ukończone poziomy droższe niż statyczny cap (dowód, że cap tnie poziomy,")
    print("   które gra inaczej by skończyła):")
    for cap in CAPS:
        hits = over[cap]
        print(f"   cap {cap:6d}: {len(hits):2d} poziom(ów)  {hits[:6]}{' …' if len(hits) > 6 else ''}")

    print("\nB. koncentracja marnotrawstwa (poziomy NIEukończone):")
    vals = [s for s in shares if s is not None]
    if vals:
        print(f"   mediana {statistics.median(vals):.1f}%   maks {max(vals):.1f}%   "
              f"min {min(vals):.1f}%   (n={len(vals)} gier)")
    worst = sorted(range(len(shares)), key=lambda i: -shares[i])[:5]
    for i in worst:
        r = rows[i]
        print(f"   najgorsze: {r[0]}/{r[1]} ukonczone={r[2]}/{r[3]} tokeny={r[4]} "
              f"→ {shares[i]:.1f}% na nieukończone")

    print(f"\nC. reguła adaptacyjna przy uzbrojeniu {ARMED}:")
    print(f"   gry z historią ≥2 ukończonych poziomów: {engaged}/{total} "
          f"({100 * engaged / total:.0f}%) — w pozostałych reguła NIE włącza się "
          f"(cap = statyczny)")
    if dyn_caps:
        caps = [c for c, _ in dyn_caps]
        looser = sum(1 for c in caps if c > ARMED)
        tighter = sum(1 for c in caps if c < ARMED)
        print(f"   cap w tych grach: min {min(caps)}  mediana {statistics.median(caps)}  max {max(caps)}")
        print(f"   luźniej niż statyczny: {looser}/{len(caps)}; ciaśniej: {tighter}/{len(caps)}")
        print("   UWAGA: cap = max(static_cap, mediana×4) jest z konstrukcji NIGDY niższy")
        print("   od wartości uzbrojenia — reguła tylko poluzowuje. Aby ciąć marnotrawstwo,")
        print("   trzeba uzbroić NISKO (np. 20k) i pozwolić medianie×4 podnieść produktywnym.")
    return 0


def _load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _walk(mod, env: dict, steps: int, seed: int = 7) -> list[str]:
    old = {k: os.environ.get(k) for k in env}
    os.environ.update({k: str(v) for k, v in env.items()})
    try:
        lb = mod.LevelBudget.from_env()
        rng = random.Random(seed)
        out, tokens, levels = [], 0, 0
        for _ in range(steps):
            if rng.random() < 0.06:
                levels += 1
            tokens += rng.choice([0, 120, 900, 2500, 6000, 15000, 41000])
            out.append(lb.step(tokens, levels))
            out.append(lb.peek(tokens, levels))
        return out
    finally:
        for k, v in old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def audit_logic(pre_path: str, post_path: str) -> int:
    pre, post = _load(pre_path, "lb_pre"), _load(post_path, "lb_post")
    cases = [
        ({"ARC3_LEVEL_TOKEN_CAP": "0"}, "dormant na submisji: CAP=0"),
        ({"ARC3_LEVEL_TOKEN_CAP": "45000", "ARC3_DYN_CAP": "0"}, "kontrola A/B: cap 45k, DYN_CAP=0"),
        ({"ARC3_LEVEL_TOKEN_CAP": "45000", "ARC3_LEVEL_RESETS_MAX": "0", "ARC3_DYN_CAP": "0"},
         "cap 45k, 0 resetów, DYN_CAP=0"),
        ({"ARC3_LEVEL_TOKEN_CAP": "45000", "ARC3_LEVEL_RESETS_MAX": "3", "ARC3_DYN_CAP": "0"},
         "cap 45k, 3 resety, DYN_CAP=0"),
        ({"ARC3_LEVEL_TOKEN_CAP": "45000", "ARC3_LEVEL_MIN_DONE": "3", "ARC3_DYN_CAP": "0"},
         "cap 45k, min_done 3, DYN_CAP=0"),
    ]
    ok = True
    for env, label in cases:
        a, b = _walk(pre, env, 4000), _walk(post, env, 4000)
        same = a == b
        ok &= same
        first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
        print(f"{'OK  ' if same else 'FAIL'} uśpienie/kontrola: {label} "
              f"({len(a)} decyzji, pierwsza rozbieżność: {first})")

    os.environ["ARC3_LEVEL_TOKEN_CAP"] = str(ARMED)
    os.environ.pop("ARC3_DYN_CAP", None)
    lb = post.LevelBudget.from_env()
    print(f"\nuzbrojenie {ARMED}: dyn_enabled={lb.dyn_enabled} cap_min={lb.cap_min} "
          f"cap_max={lb.cap_max} mult={lb.cap_mult} ladder={lb.ladder}")
    for med in (5_000, 12_000, 15_000, 25_000, 40_000, 80_000):
        probe = post.LevelBudget.from_env()
        probe._level_costs = [med, med]
        cap = probe._current_cap()
        print(f"  mediana {med:6d} → cap {cap:6d}  {'luźniej' if cap > ARMED else 'bez zmian'}")
    print("  drabina RESET mnoży PO clampie, więc cap może przekroczyć cap_max "
          f"(np. {int(150_000 * lb.ladder)} przy jednym resecie)")
    print("\nWERDYKT:", "ZGODNE" if ok else "ROZBIEŻNOŚĆ")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "benchmarks":
        return audit_benchmarks(argv[2:])
    if len(argv) >= 4 and argv[1] == "logic":
        return audit_logic(argv[2], argv[3])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
