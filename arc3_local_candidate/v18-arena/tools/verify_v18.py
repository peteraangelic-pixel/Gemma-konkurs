#!/usr/bin/env python3
"""Zestaw akceptacyjny v18-arena - wszystko offline, na prawdziwym module i prawdziwych klatkach.

Sprawdza szesc rzeczy i zadna nie jest "test jednostkowy dla testu":

  1. NEUTRALNOSC DOMYSLNA   - bez zmiennych srodowiskowych v18 podejmuje te same decyzje
                              co oryginal na 3 klatkach ft09 i 400 planszach syntetycznych.
  2. BRAMKA                 - tabela falszywych rozpoznan (copy/rotate/invert/random).
  3. STRAZNIK               - oscylacja: bez limitu nieograniczona, z limitem 32 - 32 akcje,
                              przezbrojenie przy zmianie poziomu.
  4. HOOK                   - idempotentny install, should_stop oddany oryginalowi,
                              kill-switch.
  5. DETEKTOR (kontrfaktycznie) - czy proponowany "detektor zmiany mechaniki" z mojego
                              raportu zniszczylby wynik ft09. Odpowiedz: tak.
  6. KOSZT NA FT09          - akcje startowe trzech poziomow pod kazda kombinacja przelacznikow.

Uzycie:
  python3 tools/verify_v18.py --analysis /sciezka/analysis --build /sciezka/build
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import sys
from types import SimpleNamespace

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
TOOLS = HERE.parents[1] / "tools"
FIGHT_GPUS = None  # placeholder, nieuzywane


def load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise SystemExit(f"BLAD: nie da sie zaladowac {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def probe_module():
    return load(TOOLS / "template_false_positive_probe.py", "fp_probe_v18")


def grids(analysis: pathlib.Path):
    out = {}
    for name, key in [("ft09-initial-grid.json", "L1"),
                      ("ft09-level2-grid.json", "L2"),
                      ("ft09-level3-grid.json", "L3")]:
        p = analysis / "causal-agent-20261031" / name
        if not p.exists():
            raise SystemExit(f"BLAD: brak {p} - potrzebne prawdziwe klatki ft09")
        out[key] = np.array(json.loads(p.read_text()), dtype=np.uint8)
    return out


def ft09_actions(mod, frames, learned_by_level=True):
    """Symuluje trzy wejscia w poziom z modelem przenoszonym miedzy poziomami."""
    tr = mod.TemplateTransfer()
    learned = None
    res = {}
    for lvl, key in [(0, "L1"), (1, "L2"), (2, "L3")]:
        out = tr.act(frames[key], [6], lvl)
        res[key] = None if out is None else tuple(out)
        learned = tr.learned
        if learned is None and not learned_by_level:
            break
    return res, learned


def check_neutral(orig, new, frames):
    """1. Bez env v18 == oryginal: na ft09 i na planszach syntetycznych."""
    a_orig, _ = ft09_actions(orig, frames)
    a_new, _ = ft09_actions(new, frames)
    diff_ft09 = {k: (a_orig[k], a_new[k]) for k in a_orig if a_orig[k] != a_new[k]}

    fp = probe_module()
    rng = np.random.default_rng(4242)
    mismatch = 0
    for family in ("copy", "rotate", "invert", "random"):
        for _ in range(100):
            grid, _truth, _o, _p = fp.make_board(rng, family)
            o = orig.infer_copy_action(grid)
            n = new.infer_copy_action(grid)
            if (o is None) != (n is None):
                mismatch += 1
            elif o is not None and (tuple(o[0]) != tuple(n[0])
                                    or o[1]["expected_color"] != n[1]["expected_color"]):
                mismatch += 1
    return diff_ft09, mismatch


def check_gate(orig, new, trials):
    """2. Tabela bramki (env single-mismatch)."""
    fp = probe_module()
    os.environ.pop("ARC3_TEMPLATE_ACTION_GUARD", None)
    rows = []
    for family in ("copy", "rotate", "invert", "random"):
        os.environ.pop("ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH", None)
        base = fp.measure(orig, family, trials)
        os.environ["ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH"] = "1"
        gated = fp.measure(new, family, trials)
        os.environ.pop("ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH", None)
        rows.append((family, base, gated))
    return rows


def check_guard(orig, new, frames, cap=32, steps=240):
    """3. Straznik: oscylacja bez limitu i z limitem + przezbrojenie."""
    a = frames["L1"].copy()
    os.environ.pop("ARC3_TEMPLATE_ACTION_GUARD", None)
    free = new.TemplateTransfer()
    first = free.act(a, [6], 0)
    if first is None:
        raise SystemExit("BLAD: brak akcji startowej na ft09 - sonda straznika nie ma czego pętlić")
    pred = free.prediction
    row, col, exp = pred["row"], pred["col"], int(pred["expected_color"])
    wrong = int(a[row, col])
    count_free = 1
    for step in range(steps - 1):
        a[row, col] = exp if step % 2 == 0 else wrong
        if free.act(a, [6], 0) is not None:
            count_free += 1

    os.environ["ARC3_TEMPLATE_ACTION_GUARD"] = str(cap)
    b = frames["L1"].copy()
    held = new.TemplateTransfer()
    h = held.act(b, [6], 0)
    if h is None:
        raise SystemExit("BLAD: straznik zablokowal pierwsza akcje")
    pred = held.prediction
    row2, col2, exp2 = pred["row"], pred["col"], int(pred["expected_color"])
    wrong2 = int(b[row2, col2])
    count_held = 1
    for step in range(steps - 1):
        b[row2, col2] = exp2 if step % 2 == 0 else wrong2
        if held.act(b, [6], 0) is not None:
            count_held += 1
    after_cap = held.act(b, [6], 0)
    rearmed = held.act(frames["L2"], [6], 1)
    level_actions_after = held._arm_level_actions
    os.environ.pop("ARC3_TEMPLATE_ACTION_GUARD", None)
    return dict(free=count_free, held=count_held, cap=cap,
                blocked_at_cap=after_cap is None, cap_hits=held._arm_cap_hits,
                rearmed=rearmed is not None, level_actions_after_rearm=level_actions_after)


class FakeTA:
    """Minimalny stub tool-agenta: tyle, ile hook naprawde dotyka.

    Metody pomocnicze musza byc na instancji ToolAgent, bo hook wola je przez
    `self` wewnatrz podmienionego `analyze`.
    """

    def __init__(self, grid):
        self.calls = SimpleNamespace(original=0, tool=0)
        self._grid = grid
        self.AnalyzerTurnResult = _Result
        owner = self

        class Agent(_Agent):
            def __init__(self):
                super().__init__(owner)

        self.ToolAgent = Agent

    # --- funkcje modulu, ktore hook wola jako ta.<nazwa> ---
    def load_runtime_state(self, state_path):
        return SimpleNamespace(grid=self._grid, level=0), None

    def _normalize_valid_actions(self, valid):
        return list(valid or ["MOUSE"])


class _Result:
    def __init__(self, step_executed=False, reasoning=""):
        self.step_executed = step_executed
        self.reasoning = reasoning


class _Agent:
    def __init__(self, ta):
        self._ta = ta

    # --- oryginalny analyze: sygnatura musi pasowac do inspect.signature ---
    def analyze(self, state_path, should_stop=None, valid_actions=None, step_env=None):
        self._ta.calls.original += 1
        return _Result(step_executed=False, reasoning="original")

    # --- to, co wola hook ---
    def _ensure_session(self, state_path):
        return None

    def load_runtime_state(self, state_path):
        return SimpleNamespace(grid=self._ta._grid, level=0), None

    def _normalize_valid_actions(self, valid):
        return list(valid or ["MOUSE"])

    def _run_python_tool(self, state_path, payload):
        self._ta.calls.tool += 1
        return SimpleNamespace(step_executed=True)


def check_hook(new, frames):
    """4. Hook: idempotencja, powinność oddania should_stop oryginalowi, kill-switch."""
    ta = FakeTA(frames["L1"])
    state = SimpleNamespace(resolve=lambda: "/tmp/fake-state.json")
    env_backup = dict(os.environ)
    os.environ.pop("ARC3_TEMPLATE_ENABLED", None)
    os.environ.pop("ARC3_TEMPLATE_ONLY", None)

    agent = ta.ToolAgent()
    first = new.template_hook.install(ta, new.TemplateTransfer)
    second = new.template_hook.install(ta, new.TemplateTransfer)
    # analyze jest metoda klasy, wiec dostep przez instancje daje nowy bound method
    # przy kazdym wywolaniu - porownujemy funkcje, nie obiekt bound.
    idempotent = (first is second
                  and getattr(agent.analyze, "__func__", agent.analyze) is first)

    # 1) normalne wejscie: kontroler dziala (ft09 start -> akcja)
    res = agent.analyze(state_path=state, should_stop=None,
                        valid_actions=["MOUSE"], step_env=None)
    fired = bool(getattr(res, "step_executed", False)) and ta.calls.tool == 1

    # 2) should_stop=True -> oryginal, nie nasz wlasny wynik
    before = (ta.calls.original, ta.calls.tool)
    res_stop = agent.analyze(state_path=state, should_stop=lambda: True,
                             valid_actions=["MOUSE"], step_env=None)
    delegated = (ta.calls.original == before[0] + 1 and ta.calls.tool == before[1]
                 and getattr(res_stop, "reasoning", "") == "original")

    # 3) kill switch -> oryginal
    os.environ["ARC3_TEMPLATE_ENABLED"] = "0"
    before = (ta.calls.original, ta.calls.tool)
    agent.analyze(state_path=state, should_stop=None,
                  valid_actions=["MOUSE"], step_env=None)
    killed = ta.calls.original == before[0] + 1 and ta.calls.tool == before[1]

    os.environ.clear()
    os.environ.update(env_backup)
    return dict(idempotent=idempotent, fired_on_ft09=fired,
                stop_delegates_to_original=delegated, kill_switch=killed)


def check_detector(orig, frames):
    """5. Kontrfaktycznie: czy 'detektor zmiany mechaniki' zabilby ft09?

    Wariant: przed uzyciem learned odtworz mapowanie symbol->wartosc z paneli
    BIEZACEGO poziomu (bez obrysowanego) i odrzuc learned, jesli sie nie zgadza.
    """
    tr = orig.TemplateTransfer()
    tr.act(frames["L1"], [6], 0)
    learned = tr.learned
    out = {"learned_from_L1": learned, "levels": {}}
    for key in ("L2", "L3"):
        a = frames[key]
        fresh = derive_mapping(a, orig)
        same = fresh == (learned or {}).get("colors")
        out["levels"][key] = {"fresh_mapping": fresh,
                              "learned_mapping": (learned or {}).get("colors"),
                              "agrees": same,
                              "would_abstain": not same}
    return out


def derive_mapping(a, mod):
    """Odtworzenie mapowania symbol->wartosc z samych paneli biezacej klatki."""
    from collections import Counter
    squares = [r for r in mod.rectangles(a)
               if r[1] - r[0] == r[3] - r[2] and r[1] - r[0] >= 3]
    sizes = Counter(r[1] - r[0] for r in squares)
    sizes = [s for s, n in sizes.items() if n >= 8]
    if not sizes:
        return None
    size = max(sizes, key=lambda s: s * s * sum(r[1] - r[0] == s for r in squares))
    cells = {(r[0], r[2]): r[4] for r in squares if r[1] - r[0] == size}
    gaps = Counter()
    for y, x in cells:
        for yy, xx in cells:
            if y == yy and size < xx - x <= 3 * size:
                gaps[xx - x] += 1
    if not gaps:
        return None
    pitch = max(gaps, key=gaps.get)
    origins = {(y - i * pitch, x - j * pitch) for y, x in cells
               for i in range(3) for j in range(3)}
    bg = int(np.bincount(a.ravel(), minlength=256).argmax())
    span = 2 * pitch + size
    panels = []
    for y, x in sorted(origins):
        if y < 0 or x < 0 or y + span > len(a) or x + span > a.shape[1]:
            continue
        coords = [(i, j) for i in range(3) for j in range(3) if (i, j) != (1, 1)]
        if not all((y + i * pitch, x + j * pitch) in cells for i, j in coords):
            continue
        if (y + pitch, x + pitch) in cells:
            continue
        margin = max(1, pitch - size) * 2
        ring = a[max(0, y - margin):min(len(a), y + span + margin),
                 max(0, x - margin):min(a.shape[1], x + span + margin)].copy()
        border = int(np.count_nonzero(ring != bg))
        panels.append({"y": y, "x": x, "border": border, "coords": coords})
    if len(panels) < 2:
        return None
    sub = size // 3
    target = max(panels, key=lambda p: p["border"])
    mapping = {}
    for p in panels:
        if p is target:
            continue
        for i, j in p["coords"]:
            patch = a[p["y"] + pitch + i * sub:p["y"] + pitch + (i + 1) * sub,
                      p["x"] + pitch + j * sub:p["x"] + pitch + (j + 1) * sub]
            if patch.size == 0:
                continue
            sym = int(patch[0, 0])
            val = cells[(p["y"] + i * pitch, p["x"] + j * pitch)]
            if not np.all(patch == sym):
                continue
            if sym in mapping and mapping[sym] != val:
                return None
            mapping.setdefault(sym, val)
    return mapping or None


def check_ft09_matrix(build, frames):
    """6. Akcje startowe trzech poziomow pod kazda kombinacja przelacznikow."""
    combos = [
        ("domyslnie", {}),
        ("bramka", {"ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH": "1"}),
        ("straznik=32", {"ARC3_TEMPLATE_ACTION_GUARD": "32"}),
        ("oba", {"ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH": "1",
                 "ARC3_TEMPLATE_ACTION_GUARD": "32"}),
    ]
    rows = []
    for label, env in combos:
        for k, v in env.items():
            os.environ[k] = v
        mod = load(pathlib.Path(build) / "template_transfer.py", f"v18_mod_{label}")
        acts, learned = ft09_actions(mod, frames)
        rows.append((label, acts, learned))
        for k in env:
            os.environ.pop(k, None)
    return rows


def check_compat(analysis, build, frames, cap=32, steps=240):
    """7. Kompatybilnosc z ich podklasa GuardedTemplateTransfer (podwojne liczenie).

    Jesli moj straznik w klasie bazowej uzywalby tych samych nazw pol co ich
    podklasa, kazda akcja liczylaby sie dwa razy i cap 32 zjezdzalby do 16.
    """
    import shutil
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="v18compat-"))
    src = analysis / "template_guarded.py"
    if not src.exists():
        return {"skipped": "brak template_guarded.py w zrodle"}
    (tmp / "template_guarded.py").write_text(src.read_text())
    (tmp / "template_transfer.py").write_text(
        (build / "template_transfer.py").read_text())
    (tmp / "template_hook.py").write_text((build / "template_hook.py").read_text())
    try:
        sys.path.insert(0, str(tmp))
        tg = load(tmp / "template_guarded.py", "tg_compat")
        a = frames["L1"].copy()
        agent = tg.GuardedTemplateTransfer()
        first = agent.act(a, [6], 0)
        if first is None:
            return {"error": "brak akcji startowej"}
        # ta sama symulacja co w ich tescie: 6x6 blok z oczekiwanym kolorem,
        # poprzedni blok wraca do 9 (oscylacja)
        count, previous = 1, None
        _, x, y = first
        a[y - 3:y + 3, x - 3:x + 3] = agent.prediction["expected_color"]
        previous = (x, y)
        for _ in range(steps - 1):
            out = agent.act(a, [6], 0)
            if out is None:
                break
            _, x, y = out
            a[y - 3:y + 3, x - 3:x + 3] = agent.prediction["expected_color"]
            if previous is not None:
                xx, yy = previous
                a[yy - 3:yy + 3, xx - 3:xx + 3] = 9
            previous = (x, y)
            count += 1
        return {"stacked_cap_actions": count, "cap": cap,
                "no_double_count": count >= cap}
    finally:
        sys.path.remove(str(tmp))
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--build", required=True)
    ap.add_argument("--trials", type=int, default=300)
    args = ap.parse_args(argv)

    analysis = pathlib.Path(args.analysis)
    build = pathlib.Path(args.build)
    frames = grids(analysis)
    orig = load(analysis / "template_transfer.py", "v18_orig")

    sys.modules["template_transfer"] = load(build / "template_transfer.py", "template_transfer")
    sys.modules["template_hook"] = load(build / "template_hook.py", "template_hook")
    new = SimpleNamespace(TemplateTransfer=sys.modules["template_transfer"].TemplateTransfer,
                          template_hook=sys.modules["template_hook"],
                          infer_copy_action=sys.modules["template_transfer"].infer_copy_action)

    print("v18-arena: zestaw akceptacyjny")
    print(f"  zrodlo: {analysis}")
    print(f"  build : {build}")

    print("\n[1] NEUTRALNOSC DOMYSLNA (bez env)")
    diff_ft09, sm = check_neutral(orig, new, frames)
    print(f"    ft09 rozbieznosci: {len(diff_ft09)} {diff_ft09 if diff_ft09 else ''}")
    print(f"    plansze syntetyczne (400): rozbieznosci = {sm}")

    print("\n[2] BRAMKA (env ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH=1)")
    print(f"    {'rodzina':9s} {'oryginal':>18s} {'bramka':>18s}")
    for family, base, gated in check_gate(orig, new, args.trials):
        print(f"    {family:9s} {base[0]:6d}/{base[1]:<4d}      {gated[0]:6d}/{gated[1]:<4d}")

    print("\n[3] STRAZNIK (oscylacja, 240 klatek)")
    g = check_guard(orig, new, frames)
    print(f"    bez limitu: {g['free']:3d} akcji | limit {g['cap']}: {g['held']:3d} akcji")
    print(f"    blokada na capie: {g['blocked_at_cap']}  cap_hits={g['cap_hits']}")
    print(f"    przezbrojenie po zmianie poziomu: {g['rearmed']} "
          f"(level_actions={g['level_actions_after_rearm']})")

    print("\n[4] HOOK")
    h = check_hook(new, frames)
    for k, v in h.items():
        print(f"    {k:28s} {v}")

    print("\n[5] DETEKTOR ZMIANY MECHANIKI - kontrfaktycznie")
    d = check_detector(orig, frames)
    print(f"    learned z L1: {d['learned_from_L1']}")
    for key, row in d["levels"].items():
        print(f"    {key}: mapowanie z biezacej klatki = {row['fresh_mapping']} "
              f"vs learned {row['learned_mapping']} -> abstynencja: {row['would_abstain']}")

    print("\n[7] KOMPATYBILNOSC z template_guarded.py (podwojne liczenie)")
    c = check_compat(analysis, build, frames)
    print(f"    {c}")

    print("\n[6] FT09 POD PRZELACZNIKAMI")
    for label, acts, learned in check_ft09_matrix(build, frames):
        print(f"    {label:12s} {acts}")

    ok = (len(diff_ft09) == 0 and sm == 0 and h["idempotent"] and c.get("no_double_count", False)
          and h["fired_on_ft09"] and h["stop_delegates_to_original"] and h["kill_switch"]
          and g["blocked_at_cap"] and g["rearmed"])
    print(f"\nWERDYKT: {'OK - v18 domyslnie neutralna, zabezpieczenia dzialaja' if ok else 'BLAD'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
