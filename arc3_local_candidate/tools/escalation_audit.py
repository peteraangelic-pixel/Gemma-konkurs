#!/usr/bin/env python3
"""Niezależny audyt reguł eskalacji na realnych benchmarkach (bez patcha, bez harnessu).

Ile razy reguła wtrąca się do kontekstu i ile z tych wtrąceń jest PRZEDWCZESNYCH
(czyli próg wypadł poniżej ludzkiego baseline'u dla tego poziomu).

Cztery reguły:
  abs20        próg 20 akcji (to, co realnie leci w submisji z v13.2)
  abs20cap2    j.w. + maks. 2 wtrącenia na poziom (v13.4)
  relative     patch 0008: max(20, 1,2 × baseline), cap 2 — DZIAŁA TYLKO NA REPLAY
               (w submisji `base_actions_per_level = None` w taaf/game.py, więc
               degeneruje się do abs20cap2; kolumna pokazuje jego wartość GÓRNĄ)
  selfpace     patch 0009 (Gemma duck-v16): clamp(1,5 × mediana WŁASNYCH ukończonych
               poziomów, 20, 120), cap 2 — nie potrzebuje ukrytych danych

Użycie:
  python3 escalation_audit.py fixtures/r085.json [r093.json …]

Wynik dla korpusu r085/r093/r110/r118 (30.10.2026):
  r085 (32 poziomy): abs20 67/26 · abs20cap2 42/26 · relative 8/0 · selfpace 22/14
  r093 (27):         72/23     · 39/23       · 10/0       · 22/13
  r110 (4):           8/4      ·  5/4        ·  3/0       ·  5/4
  r118 (2):           3/1      ·  2/1        ·  2/0       ·  2/1
Czyli: względna jest najlepsza tam, gdzie ma dane; self-pace jest lepszy od
absolutnej, ale gorszy od względnej — i to on jedyny działa w biegu, który się liczy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

POLICIES = ("abs20", "abs20cap2", "relative", "selfpace")


def median_int(values: list[int]) -> int:
    v = sorted(x for x in values if x > 0)
    if not v:
        return 0
    mid = len(v) // 2
    return v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) // 2


def clamp(x: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(x)))


def policies(base: list[int], actions: list[int], done: int,
             floor: int = 20, cap: int = 2) -> dict[str, list[tuple[int, int, int, bool]]]:
    """(poziom, liczba wtrąceń, próg, czy przedwczesne) dla każdej reguły."""
    out: dict[str, list[tuple[int, int, int, bool]]] = {k: [] for k in POLICIES}
    for i in range(min(done, len(actions))):
        a = int(actions[i] or 0)
        if a <= 0:
            continue
        b = int(base[i]) if i < len(base) else 0
        n_abs = a // floor
        out["abs20"].append((i + 1, n_abs, floor, bool(n_abs and b and floor < b)))
        n_cap = min(cap, n_abs)
        out["abs20cap2"].append((i + 1, n_cap, floor, bool(n_cap and b and floor < b)))
        thr_rel = max(floor, int(b * 1.2)) if b > 0 else floor
        n_rel = min(cap, a // thr_rel) if a >= thr_rel else 0
        out["relative"].append((i + 1, n_rel, thr_rel, bool(n_rel and b and thr_rel < b)))
        pace = median_int([int(x or 0) for x in actions[:i]])
        thr_self = floor if pace <= 0 else clamp(max(floor, pace * 1.5), 1, 120)
        n_self = min(cap, a // thr_self) if a >= thr_self else 0
        out["selfpace"].append((i + 1, n_self, thr_self, bool(n_self and b and thr_self < b)))
    return out


def audit(path: str) -> dict[str, list[int]]:
    data = json.loads(Path(path).read_text())
    totals = {k: [0, 0, 0] for k in POLICIES}  # wtrącenia, przedwczesne, poziomy
    for run in data.get("game_runs") or []:
        base = run.get("base_actions_per_level") or []
        actions = run.get("actions_per_level") or []
        done = int(run.get("levels_completed") or 0)
        if not base or not done:
            continue
        for name, rows in policies(base, actions, done).items():
            totals[name][0] += sum(r[1] for r in rows)
            totals[name][1] += sum(1 for r in rows if r[3])
            totals[name][2] += len(rows)
    return totals


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    ok = True
    for path in argv[1:]:
        totals = audit(path)
        levels = totals["abs20"][2]
        print(f"{Path(path).name}  ({levels} poziomów, gry z widocznym baseline'em)")
        for name in POLICIES:
            nudges, premature, _ = totals[name]
            print(f"   {name:10s} wtrącenia={nudges:4d}  przedwczesne={premature:2d}/{levels}")
        # reguła względna nie może być gorsza od self-pace tam, gdzie ma dane
        if totals["relative"][1] > totals["selfpace"][1]:
            ok = False
            print("   UWAGA: względna wypadła gorzej niż self-pace — sprawdź dane wejściowe")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
