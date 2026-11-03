#!/usr/bin/env python3
"""Sonda petli oscylacji kontrolera szablonowego (template_transfer.TemplateTransfer).

Powod: zarzut z audytu galezi Pokemon (9d528ac4) - komorka, ktora po kliknieciu
przyjmuje oczekiwany kolor na jedna klatke, a potem wraca, NIE uniewaznia
predykcji (`rejected` nigdy nie nastepuje), wiec kontroler klika dalej bez konca.
Weryfikujemy to na prawdziwym module Smaka (nie na opisie) i mierzymy, ile
akcji zjada dobudowany straznik (limit akcji na poziom + przezbrojenie po
zmianie poziomu).

Model zamkniety:
  klatka parzysta  -> klikniety piksel ma kolor oczekiwany (predykcja sie zgadza)
  klatka nieparzysta -> piksel wraca do zlej wartosci (znow niezgodnosc)
Liczymy, ile razy `act` zwrocil akcje w ciagu FRAMES klatek.

Użycie:
  python3 tools/template_oscillation_probe.py --policy /sciezka/template_transfer.py
  python3 tools/template_oscillation_probe.py --policy … --budget 32 --frames 120
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"BLAD: nie da sie zaladowac {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def guarded_class(base, budget):
    """TemplateTransfer + twardy limit akcji na poziom, przezbrajany przy zmianie poziomu."""

    class Guarded(base):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.budget = budget
            self.used = 0

        def act(self, grid, available, level):
            if level != getattr(self, "_budget_level", None):
                self.used = 0
                self._budget_level = level
            if self.used >= self.budget:
                return None
            out = super().act(grid, available, level)
            if out is not None:
                self.used += 1
            return out

    return Guarded


def make_oscillating_board(rng, rule="copy"):
    """Plansza z jednego z zadan sondy falszywych rozpoznan (ta sama geometria)."""
    probe = _load(HERE / "template_false_positive_probe.py", "fp_probe")
    return probe.make_board(rng, rule)


def run(policy_mod, frames, budget=None, rule="copy", seed=5, mode="alternate"):
    rng = np.random.default_rng(seed)
    grid, truth, (ox, oy), pal = make_oscillating_board(rng, rule)
    pitch = _load(HERE / "template_false_positive_probe.py", "fp_probe2").PITCH

    cls = policy_mod.TemplateTransfer
    tr = cls() if budget is None else guarded_class(cls, budget)()

    first = tr.act(grid, [6], 0)
    if first is None:
        raise SystemExit("BLAD: polityka nie zaproponowala zadnej akcji na planszy startowej "
                         "- sonda nie ma czego oscylowac")
    pred = tr.prediction
    row, col = pred["row"], pred["col"]
    expected = int(pred["expected_color"])
    wrong = int(grid[row, col])
    if expected == wrong:
        raise SystemExit("BLAD: kolor oczekiwany rowny obecnemu - brak niezgodnosci")

    actions = 1
    for step in range(frames - 1):
        if mode == "instant":
            grid[row, col] = wrong             # walidacja tylko w obrebie klatki
        elif step % 2 == 0:
            grid[row, col] = expected          # predykcja sie potwierdza
        else:
            grid[row, col] = wrong             # i komorka wraca
        if tr.act(grid, [6], 0) is not None:
            actions += 1

    # przezbrojenie: nowy poziom musi wyzerowac licznik
    rearmed = None
    if budget is not None:
        for _ in range(budget):
            tr.act(grid, [6], 0)
        used_before = tr.used
        tr.act(grid, [6], 1)                   # poziom 2 - licznik od zera
        rearmed = (used_before, tr.used, budget)
    return actions, frames, rearmed


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True, help="sciezka do template_transfer.py")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--budget", type=int, default=32)
    ap.add_argument("--family", default="copy")
    ap.add_argument("--mode", default="alternate", choices=["alternate", "instant"],
                    help="alternate = klikniety piksel trzyma kolor jedna klatke; "
                         "instant = walidacja tylko w obrebie klatki (warjant z audytu Pokemon)")
    args = ap.parse_args(argv)

    mod = _load(args.policy, "policy_osc")
    free, frames, _ = run(mod, args.frames, None, args.family, mode=args.mode)
    held, _, rearm = run(mod, args.frames, args.budget, args.family, mode=args.mode)

    print(f"polityka: {args.policy}   rodzina: {args.family}   tryb: {args.mode}   klatek: {frames}")
    print(f"bez straznika : {free:3d} akcji  ({100 * free / frames:.0f}% klatek z akcja)")
    print(f"straznik {args.budget:3d}   : {held:3d} akcji  (limit trzyma: {held <= args.budget})")
    if rearm:
        before, after, cap = rearm
        ok = after < cap and after <= 1
        print(f"przezbrojenie : po {before} uzytych i zmianie poziomu licznik = {after} "
              f"(limit {cap}; {'OK - moze znow dzialac' if ok else 'BLAD - licznik nie wyzerowany'})")
    print()
    print("Wniosek: predykcja walidujaca sie co klatke NIE uniewaznia kontrolera, wiec bez")
    print("limitu akcji na poziom petla jest nieograniczona. To pokazuje, ze zdanie")
    print('"falszywe rozpoznanie kosztuje najwyzej 1 akcje" obowiazuje tylko dla')
    print("niezgodnosci TRWALEJ (normalny przypadek), nie dla oscylacji.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
