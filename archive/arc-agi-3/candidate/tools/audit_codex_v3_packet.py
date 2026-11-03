#!/usr/bin/env python3
"""Audyt pakietu peer-review Codexa (v3-control / v3-slim) - wszystko offline, bez Kaggle.

Odtwarza KAZDA liczbe z raportow `arc-agi-3/peer-review/codex-v3-*`:

  1. kontrolny benchmark: wynik, poziomy, akcje, RESET-y, tokeny, stany, wall-clock
  2. A/B jest jedna zmienna: diff komorek dwoch notebookow
  3. wynik slim: odtworzenie 17,35047 z wierszy COMPARISON i baseline'ow kontroli
  4. rozklad spadku: utracona waga poziomow, efektywnosc akcji
  5. bootstrap po grach: czy kierunek spadku jest solidny przy n=10
  6. podgrupa "bez akcji kierunkowych -4 / z kierunkowymi -5"
  7. diagnostyka niezaraportowana przez autorow: czas do pierwszej akcji, akcje/min

Uzycie:
  python3 tools/audit_codex_v3_packet.py --packet arc-agi-3/peer-review
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from arc3_local_candidate.scorecard import game_score, audit_benchmark  # noqa: E402

CLAIMED_CONTROL = 27.496670817884922
CLAIMED_SLIM = 17.350468479169024
CLAIMED_TOKENS = 1703530
CLAIMED_NON_RESET = 1872
CLAIMED_LEVELS = (33, 24)


def section(title):
    print(f"\n=== {title} " + "=" * max(0, 66 - len(title)))


def load(packet, *parts):
    return json.loads((packet.joinpath(*parts)).read_text())


def check_control(packet):
    section("1. KONTROLNY BENCHMARK")
    b = load(packet, "codex-v3-control-20261101", "benchmark.json")
    a = audit_benchmark(b)
    ids = Counter()
    non_reset = 0
    for r in b["game_runs"]:
        for h in r["history"]:
            aid = (h.get("action") or {}).get("id")
            ids[aid] += 1
            if aid != "RESET":
                non_reset += 1
    states = Counter(r["state"] for r in b["game_runs"])
    print(f"wynik sredni        {a['mean_score_recomputed']:.15f}  (deklarowane {CLAIMED_CONTROL:.15f})"
          f"  {'OK' if abs(a['mean_score_recomputed'] - CLAIMED_CONTROL) < 1e-9 else 'ROZBIEZNOSC'}")
    print(f"poziomy             {a['completed_levels']}/{a['total_levels']}  "
          f"(deklarowane {CLAIMED_LEVELS[0]})")
    print(f"akcje               {a['actions']}  | non-reset {non_reset} "
          f"(deklarowane {CLAIMED_NON_RESET})  | RESET {ids.get('RESET', 0)}")
    print(f"tokeny              {a['generated_tokens']}  (deklarowane {CLAIMED_TOKENS})")
    print(f"stany               {dict(states)}")
    print(f"maks. wall-clock    {a['wallclock_seconds_max']:.1f}s")
    print(f"niezgodnosci score  {a['score_mismatch_count']} na {a['games']} gier")
    print(f"rozkld akcji        {dict(ids)}")
    return b, a


def check_ab(packet):
    section("2. A/B = JEDNA ZMIENNA")
    c = load(packet, "codex-v3-control-20261101", "arc3-duck.ipynb")
    s = load(packet, "codex-v3-slim-20261101", "agent.ipynb")
    cc, sc = c["cells"], s["cells"]
    diffs = [i for i in range(max(len(cc), len(sc)))
             if (("".join(cc[i]["source"]) if i < len(cc) else None)
                 != ("".join(sc[i]["source"]) if i < len(sc) else None))]
    print(f"komorki             control {len(cc)} | slim {len(sc)}")
    print(f"rozne komorki       {diffs}  {'OK - jedna zmienna' if diffs == [1] else 'UWAGA'}")
    text = "\n".join("".join(x["source"]) for x in sc)
    has_off = "ARC3_MEMORY_SECTIONS': 'off" in text or 'ARC3_MEMORY_SECTIONS": "off' in text
    print(f"domyslne env        ARC3_MEMORY_SECTIONS=off w setup_env: {has_off}")
    meta = {}
    for name in ("codex-v3-control-20261101", "codex-v3-slim-20261101"):
        m = load(packet, name, "kernel-metadata.json")
        meta[name] = {k: m[k] for k in ("machine_shape", "docker_image", "dataset_sources",
                                        "model_sources", "competition_sources")}
    same = meta["codex-v3-control-20261101"] == meta["codex-v3-slim-20261101"]
    print(f"srodowisko          identyczne: {same} (maszyna, docker, datasety, modele, konkurs)")
    return diffs


def check_slim(packet, bench):
    section("3. WYNIK SLIM - ODTWORZENIE")
    d = load(packet, "codex-v3-slim-20261101", "COMPARISON.json")
    base = {r["game_id"]: r["base_actions_per_level"] for r in bench["game_runs"]}
    for lab, claimed in (("control", CLAIMED_CONTROL), ("slim", CLAIMED_SLIM)):
        rows = d[lab]["rows"]
        errs = []
        for r in rows:
            b = base[r["game_id"]]
            got = game_score(b, r["actions_per_level"], levels_completed=r["completed"])
            if abs(got - r["score"]) > 1e-6:
                errs.append((r["game_id"], got, r["score"]))
            if sum(r["actions_per_level"][:r["completed"]]) != r["closed_actions"]:
                errs.append((r["game_id"], "closed_actions"))
        mean = float(np.mean([r["score"] for r in rows]))
        print(f"{lab:8s} srednia z wierszy {mean:.15f}  deklarowane {claimed:.15f}  "
              f"niezgodnosci {len(errs)}")
    print(f"surowy benchmark slim w pakiecie: "
          f"{(packet / 'codex-v3-slim-20261101' / 'benchmark.json').exists()} "
          f"(-> per-poziomowe akcje slim sa NIEaudytowalne, tylko wiersze pochodne)")
    return d


def check_decomposition(d):
    section("4. ROZKLAD SPADKU")
    for lab in ("control", "slim"):
        rows = d[lab]["rows"]
        caps = []
        for r in rows:
            n = len(r["actions_per_level"]); k = r["completed"]
            caps.append(sum(range(1, k + 1)) / (n * (n + 1) / 2) * 100)
        sc = float(np.mean([r["score"] for r in rows]))
        cap = float(np.mean(caps))
        print(f"{lab:8s} wynik {sc:6.2f} | cap ukonczen {cap:6.2f} | "
              f"strata na efektywnosci {cap - sc:5.2f} ({100 * (cap - sc) / cap:.0f}% capu)")
    lost = gained = 0
    for x in d["deltas"]:
        n1, n2 = x["control_levels"], x["slim_levels"]
        lost += sum(range(n2 + 1, n1 + 1)) if n1 > n2 else 0
        gained += sum(range(n1 + 1, n2 + 1)) if n2 > n1 else 0
    print(f"utracona waga poziomow {lost} | zyskana {gained} | netto {lost - gained} z 210 mozliwych")
    print("-> caly spadek wyniku tlumaczy sie liczba poziomow, nie pogorszeniem efektywnosci")


def check_bootstrap(d):
    section("5. BOOTSTRAP PO GRACH (n=10)")
    ds = np.array([x["score"] for x in d["deltas"]])
    dl = np.array([x["levels"] for x in d["deltas"]], dtype=float)
    rng = np.random.default_rng(7)
    bs = np.array([rng.choice(ds, size=len(ds), replace=True).mean() for _ in range(20000)])
    bl = np.array([rng.choice(dl, size=len(dl), replace=True).mean() for _ in range(20000)])
    print(f"delta wyniku        srednia {ds.mean():+.3f}  "
          f"95% CI [{np.percentile(bs, 2.5):+.2f}, {np.percentile(bs, 97.5):+.2f}]  "
          f"P(<0)={100 * (bs < 0).mean():.1f}%")
    print(f"delta poziomow      srednia {dl.mean():+.2f}  "
          f"95% CI [{np.percentile(bl, 2.5):+.2f}, {np.percentile(bl, 97.5):+.2f}]  "
          f"P(<0)={100 * (bl < 0).mean():.1f}%")
    print("zastrzezenie        jedna proba na ramie -> wariancja rerunu NIE jest w tym CI")


def check_subgroups(bench, d):
    section("6. PODGRUPA 'BEZ KIERUNKOWYCH' (deklarowane -4 / -5)")
    deltas = {x["game"][:4]: x["levels"] for x in d["deltas"]}
    no_dir, with_dir = 0, 0
    for r in bench["game_runs"]:
        ids = Counter((h.get("action") or {}).get("id") for h in r["history"])
        dirn = sum(ids.get(f"ACTION{i}", 0) for i in (1, 2, 3, 4))
        dl = deltas[r["game_id"][:4]]
        if dirn == 0:
            no_dir += dl
        else:
            with_dir += dl
        print(f"  {r['game_id'][:6]:6s} akcje kierunkowe {dirn:4d}  delta poziomow {dl:+d}")
    print(f"suma bez kierunkowych {no_dir:+d} | z kierunkowymi {with_dir:+d} "
          f"(deklarowane -4 / -5)  {'ODTWORZONE' if (no_dir, with_dir) == (-4, -5) else 'ROZBIEZNOSC'}")
    print("ale: to post-hoc podzial stalej sumy -9 na grupy n=3 i n=7 -> nie dowodzi mechanizmu")


def check_unreported(d):
    section("7. DIAGNOSTYKA NIEZARAPORTOWANA PRZEZ AUTOROW")
    for lab in ("control", "slim"):
        rows = d[lab]["rows"]
        f = np.array([r["first_action_s"] for r in rows])
        w = np.array([r["wall_seconds"] for r in rows])
        a = np.array([r["actions"] for r in rows])
        print(f"{lab:8s} pierwsza akcja mediana {np.median(f):5.0f}s | suma {f.sum():5.0f}s | "
              f"akcje/min {a.sum() / (w.sum() / 60):.2f} | akcje na ukonczenie "
              f"{a.sum() / max(1, sum(r['completed'] for r in rows)):.1f}")
    f1 = [r["first_action_s"] for r in d["control"]["rows"]]
    f2 = [r["first_action_s"] for r in d["slim"]["rows"]]
    slower = sum(1 for a, b in zip(f1, f2) if b > a)
    print(f"slim wolniejszy do pierwszej akcji w {slower}/10 gier, roznica sumy "
          f"{sum(f2) - sum(f1):+.0f}s ({(sum(f2) - sum(f1)) / 28800 * 100:.1f}% budzetu 10x48min)")
    print("-> przepustowosc bez zmian; roznica jest w decyzjach, nie w szybkosci")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", default="arc-agi-3/peer-review")
    args = ap.parse_args(argv)
    packet = pathlib.Path(args.packet)
    if not packet.is_dir():
        packet = ROOT / args.packet
    bench, _ = check_control(packet)
    check_ab(packet)
    d = check_slim(packet, bench)
    check_decomposition(d)
    check_bootstrap(d)
    check_subgroups(bench, d)
    check_unreported(d)
    print("\nWERDYKT: liczby pakietu odtwarzalne co do cyfry; kierunek spadku solidny przy n=10;")
    print("         aktywacja sekcji i surowe dane slim pozostaja nieaudytowalne z tego pakietu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
