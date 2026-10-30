#!/usr/bin/env python3
"""Co daje cięcie akcji, a co dodanie poziomu — na prawdziwym benchmark.json.

Odpowiada na pytanie, które rozstrzyga, czy warto wdrażać "action efficiency":
  * score = sum(level_score_k * k) / sum(k),  level_score = min((human/ai)^2, 1.15)
  * n_k = k+1 -> gra jest ograniczona POKRYCIEM (cap 100*sum(k<=done)/sum(k))
    albo EFEKTYWNOŚCIĄ (raw niżej niż cap).
Dla gier ograniczonych pokryciem cięcie akcji nie zmienia NIC.

    python3 leverage.py <benchmark.json> [benchmark.json ...]
"""
import json
import sys

CAP = 115.0


def parts(g, cut=0.0, extra_levels=0, cost=None):
    """(raw, cap, score) dla jednej gry po cięciu akcji i/lub dodaniu poziomów."""
    done = g["levels_completed"]
    tot = g["number_of_levels"]
    base = g["base_actions_per_level"]
    apl = g["actions_per_level"]
    weight = tot * (tot + 1) / 2
    raw = 0.0
    for k in range(done):
        used = max(1.0, apl[k] * (1.0 - cut))
        raw += min(CAP, (base[k] / used) ** 2 * 100.0) * (k + 1)
    new_done = min(tot, done + extra_levels)
    if cost is None:
        cost = sum(apl[:done]) / done if done else 42.0
    for k in range(done, new_done):
        b = base[k] if k < len(base) else cost
        raw += min(CAP, (b / cost) ** 2 * 100.0) * (k + 1)
    raw /= weight
    cap = 100.0 * (new_done * (new_done + 1) / 2) / weight
    return raw, cap, min(raw, cap)


def table(d, cut=0.0, extra=0):
    rows = []
    for g in d["game_runs"]:
        raw, cap, score = parts(g, cut, extra)
        bound = "pokrycie" if cap < raw else "efektywność"
        rows.append((g["game_id"][:4], g["levels_completed"], g["number_of_levels"],
                     raw, cap, score, bound))
    return rows


def mean_score(d, **kw):
    rows = table(d, **kw)
    return sum(r[5] for r in rows) / len(rows)


def main(paths):
    for path in paths:
        d = json.load(open(path))
        print(f"\n=== {path}")
        print(f"{'gra':6}{'lvl':>6}{'raw':>8}{'cap':>8}{'score':>8}  wiąże")
        for gid, done, tot, raw, cap, score, bound in table(d):
            print(f"{gid:6}{done:3}/{tot:<3}{raw:8.1f}{cap:8.1f}{score:8.1f}  {bound}")
        s0 = mean_score(d)
        print(f"\n{'wariant':38}{'score':>8}{'Δ':>8}")
        print(f"{'dziś':38}{s0:8.2f}{0.0:+8.2f}")
        for cut in (0.10, 0.20, 0.30, 0.50, 0.70):
            s = mean_score(d, cut=cut)
            print(f"{f'cięcie akcji {cut*100:.0f}% (bez nowych poziomów)':38}{s:8.2f}{s-s0:+8.2f}")
        for extra in (1, 2):
            s = mean_score(d, extra=extra)
            print(f"{f'+{extra} poziom na grę':38}{s:8.2f}{s-s0:+8.2f}")
            s = mean_score(d, extra=extra, cut=0.30)
            print(f"{f'+{extra} poziom i cięcie 30%':38}{s:8.2f}{s-s0:+8.2f}")
        cap_bound = sum(1 for r in table(d) if r[6] == "pokrycie")
        print(f"\ngier ograniczonych pokryciem: {cap_bound}/{len(d['game_runs'])}"
              f" -> w nich cięcie akcji daje dokładnie 0")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
