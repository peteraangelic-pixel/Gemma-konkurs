#!/usr/bin/env python3
"""Sonda falszywego rozpoznania kontrolera szablonowego (template_transfer.py).

Buduje syntetyczne plansze w geometrii ft09 (dwa panele 3x3 kafelkow, kafelek
mniejszy od skoku, pieczec w srodku, panel zadania z obwodka) i sprawdza, jak
czesto polityka PROponuje klikniecie oraz czy przewidziany kolor jest zgodny
z prawda. Rodziny roznia sie REGULA:

  copy     regula = kopiuj z panelu referencyjnego (kontrola pozytywna)
  rotate   regula = obrot 90 stopni
  invert   regula = zamiana dwoch kolorow
  random   brak reguly (szum o tym samym ukladzie)

Wynik dla wersji z 31.10.2026 (300 prob na rodzine):
  rodzina  oryginal                 bramka "dokladnie jedna niezgodna komorka"
  copy     149 rozpoznan / 100%     149 / 100%
  rotate   299 / 6%                  17 / 18%
  invert   300 / 0%                   0 /  -
  random   297 / 8%                   8 / 12%

Użycie:
  python3 tools/template_false_positive_probe.py --policy /sciezka/template_transfer.py
  python3 tools/template_false_positive_probe.py --policy … --gate   # z wariantem bramki

Uwaga metodologiczna: to NIE sa prawdziwe gry. Plansze sa syntetyczne, wiec liczby
mowia o zachowaniu na "planszach wygladajacych jak szablon", a nie o rozkladzie
w publicznym rosterze. Do prawdziwych gier potrzebny jest arcengine (patrz raport).
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from collections import Counter

import numpy as np

SIZE = 18      # panel 3x3 kafelkow
PITCH = 6      # skok miedzy kafelkami
TILE = 4       # rozmiar kafelka (< skok, jak 6 < 8 w ft09)
GAP = 6 * PITCH
COLORS = list(range(1, 13))


def make_board(rng, rule):
    panel = rng.integers(0, 3, size=(4, 4))
    panel = np.where(panel == 2, rng.integers(0, 2), panel)
    if rule == "copy":
        truth = panel.copy()
    elif rule == "rotate":
        truth = np.rot90(panel, 1).copy()
    elif rule == "invert":
        truth = np.where(panel == 0, 1, 0)
    else:
        truth = rng.integers(0, 2, size=(4, 4))
    target = truth.copy()
    missing = (int(rng.integers(0, 4)), int(rng.integers(0, 4)))
    target[missing] = 1 - truth[missing]

    h = w = SIZE + GAP + SIZE + 8
    grid = np.zeros((h, w), dtype=np.uint8)
    pal = rng.choice(COLORS, size=4, replace=False)
    grid[:] = int(pal[0])

    def paint(oy, ox, cells, outline=False):
        for i in range(4):
            for j in range(4):
                if (i, j) == (1, 1):
                    continue
                y0, x0 = oy + i * PITCH, ox + j * PITCH
                grid[y0:y0 + TILE, x0:x0 + TILE] = int(pal[1 + int(cells[i, j])])
        grid[oy + PITCH:oy + PITCH + TILE, ox + PITCH:ox + PITCH + TILE] = int(pal[0])
        if outline:
            c = int(pal[3])
            grid[oy - 1:oy + SIZE + 1, ox - 1] = c
            grid[oy - 1:oy + SIZE + 1, ox + SIZE] = c
            grid[oy - 1, ox - 1:ox + SIZE + 1] = c
            grid[oy + SIZE, ox - 1:ox + SIZE + 1] = c

    paint(4, 4, panel)
    paint(4, 4 + SIZE + GAP, target, outline=True)
    return grid, truth, (4 + SIZE + GAP, 4), pal


def load_policy(path):
    spec = importlib.util.spec_from_file_location("policy_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["policy_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def measure(policy, rule, trials, seed=11):
    rng = np.random.default_rng(seed)
    fired = correct = 0
    for _ in range(trials):
        grid, truth, (ox, oy), pal = make_board(rng, rule)
        out = policy.infer_copy_action(grid)
        if out is None:
            continue
        fired += 1
        _, x, y = out[0]
        ci, cj = (y - oy) // PITCH, (x - ox) // PITCH
        if 0 <= ci < 4 and 0 <= cj < 4:
            if out[1]["expected_color"] == int(pal[1 + int(truth[ci, cj])]):
                correct += 1
    return fired, correct


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True, help="sciezka do template_transfer.py")
    ap.add_argument("--trials", type=int, default=300)
    ap.add_argument("--families", default="copy,rotate,invert,random")
    args = ap.parse_args(argv)
    policy = load_policy(args.policy)
    print(f"polityka: {args.policy}  (proby na rodzine: {args.trials})")
    print(f"{'rodzina':9s} {'rozpoznane':>11s} {'trafne':>8s} {'precyzja':>9s}")
    for rule in args.families.split(","):
        fired, correct = measure(policy, rule, args.trials)
        prec = "n/a" if not fired else f"{100 * correct / fired:.0f}%"
        print(f"{rule:9s} {fired:11d} {correct:8d} {prec:>9s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
