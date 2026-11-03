#!/usr/bin/env python3
"""Buduje drzewo v18-arena: kontroler szablonowy + trzy zabezpieczenia, jako JEDEN zestaw.

Wejscie: katalog `analysis/` z galezi Smaka (read-only, nie kopiujemy go do repo).
Wyjscie: katalog build/ z podmienionymi plikami + wygenerowanym diffem do przegladu.

Trzy zmiany, kazda niezalezna i kazda za przelacznikiem srodowiskowym:

  0012 single-mismatch  ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH=1
       niezgodna komorka musi byc dokladnie jedna, inaczej abstynencja
  0013 action-guard     ARC3_TEMPLATE_ACTION_GUARD=32
       twardy limit akcji kontrolera na poziom, przezbrajany przy zmianie poziomu
  0014 hook-safe        (zawsze)
       idempotentny install, zachowanie oryginalnej semantyki should_stop,
       kill-switch ARC3_TEMPLATE_ENABLED=0

Czwarta propozycja (detektor zmiany mechaniki) NIE jest tu nalozona - pomiar w
verify_v18.py pokazuje, ze wyzerowalaby learned na poziomach 2-3 ft09, czyli
zabrala 2 z 3 ukonczonych poziomow. Patrz reports/verify-summary.txt.

Kazde podstawienie tekstowe musi trafic dokladnie raz, inaczej build konczy sie
bledem - to nie jest "apply patch z nadzieja, ze sie przyjmie".

Uzycie:
  python3 tools/build_v18.py --analysis /sciezka/arc-agi-3/analysis [--out build]
"""
from __future__ import annotations

import argparse
import difflib
import pathlib
import sys

# --- 0012: bramka "dokladnie jedna niezgodna komorka" -------------------------
GATE_OLD = """        for i,j in target['coords']:
            expected=cells[(ref['y']+i*pitch,ref['x']+j*pitch)]
            actual=cells[(target['y']+i*pitch,target['x']+j*pitch)]
            if actual!=expected:
                choices.append((target['border']-ref['border'],target['y']+i*pitch+size//2,
                                target['x']+j*pitch+size//2,expected,None))
                break
"""
GATE_NEW = """        # ARM: bramka single-mismatch (ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH=1).
        # Wymagaj DOKLADNIE jednej niezgodnej komorki - inaczej abstynencja.
        # Bez przelacznika zachowanie jest bajt w bajt jak w oryginale.
        if _single_mismatch():
            wrong=[(i,j) for i,j in target['coords']
                   if cells[(target['y']+i*pitch,target['x']+j*pitch)]
                   !=cells[(ref['y']+i*pitch,ref['x']+j*pitch)]]
            if len(wrong)!=1:continue
            i,j=wrong[0]
            expected=cells[(ref['y']+i*pitch,ref['x']+j*pitch)]
            choices.append((target['border']-ref['border'],target['y']+i*pitch+size//2,
                            target['x']+j*pitch+size//2,expected,None))
            continue
        for i,j in target['coords']:
            expected=cells[(ref['y']+i*pitch,ref['x']+j*pitch)]
            actual=cells[(target['y']+i*pitch,target['x']+j*pitch)]
            if actual!=expected:
                choices.append((target['border']-ref['border'],target['y']+i*pitch+size//2,
                                target['x']+j*pitch+size//2,expected,None))
                break
"""

SWITCH_OLD = """import numpy as np
"""
SWITCH_NEW = """import os
import numpy as np


def _single_mismatch():
    \"\"\"Przelacznik bramki single-mismatch (domyslnie wylaczona).\"\"\"
    return os.environ.get('ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH')=='1'
"""

# --- 0013: straznik akcji na poziom ------------------------------------------
GUARD_INIT_OLD = """        self.hits=0
        self.mismatches=0
        self.learned=None
"""
GUARD_INIT_NEW = """        self.hits=0
        self.mismatches=0
        self.learned=None
        # ARM: straznik akcji na poziom (ARC3_TEMPLATE_ACTION_GUARD=K, 0 = wylaczony).
        # Bez niego kontroler przy przejsciowym efekcie klikniecia (komorka wraca)
        # klika bez konca: rejected nigdy nie nastepuje, bo predykcja sie zgadza
        # co klatke. Zmierzone: 120 akcji w 240 klatkach.
        # Nazwy prywatne (_arm_*), zeby nie kolidowac z licznikami podklasy
        # template_guarded.GuardedTemplateTransfer. Kolizja = podwojne liczenie
        # i cap 32 zjezdzajacy do 16 (zmierzone).
        self._arm_guard=int(os.environ.get('ARC3_TEMPLATE_ACTION_GUARD','0') or 0)
        self._arm_level_actions=0
        self._arm_cap_hits=0
"""

GUARD_ACT_OLD = """        if level!=self.level:
            self.prediction=None;self.rejected=False;self.level=level
"""
GUARD_ACT_NEW = """        if level!=self.level:
            self.prediction=None;self.rejected=False;self.level=level
            self._arm_level_actions=0
        if self._arm_guard and self._arm_level_actions>=self._arm_guard:
            self._arm_cap_hits+=1
            return None
"""

GUARD_HIT_OLD = """                action,self.prediction=result;self.hits+=1
                if self.prediction.get('model'):self.learned=self.prediction['model']
                return action
"""
GUARD_HIT_NEW = """                action,self.prediction=result;self.hits+=1
                if self.prediction.get('model'):self.learned=self.prediction['model']
                self._arm_level_actions+=1
                return action
"""

# --- 0014: bezpieczny hook ---------------------------------------------------
HOOK_OLD_HEAD = """def install(ta,controller_class):
    original=ta.ToolAgent.analyze
"""
HOOK_NEW_HEAD = """def install(ta,controller_class):
    # ARM: instalacja idempotentna - drugie wywolanie nie owija analyze drugi raz.
    current=ta.ToolAgent.analyze
    if getattr(current,'_arc3_template_hooked',False):
        return current
    original=current
"""

HOOK_OLD_STOP = """        stop=values.get('should_stop')
        if stop and stop():return ta.AnalyzerTurnResult(step_executed=False)
"""
HOOK_NEW_STOP = """        stop=values.get('should_stop')
        # ARM: przy should_stop oddaj sterowanie ORYGINALOWI, zamiast zwracac wlasny
        # wynik. Hook nie zmienia wiec semantyki zatrzymania - tylko ja poprzedza.
        if stop and stop():return original(self,*args,**kwargs)
"""

HOOK_OLD_TAIL = """        return ta.AnalyzerTurnResult(step_executed=result.step_executed,
                                    reasoning='Observation-derived symbolic template action')
    ta.ToolAgent.analyze=analyze
"""
HOOK_NEW_TAIL = """        return ta.AnalyzerTurnResult(step_executed=result.step_executed,
                                    reasoning='Observation-derived symbolic template action')
    analyze._arc3_template_hooked=True
    ta.ToolAgent.analyze=analyze
    return analyze
"""

EDITS = {
    "template_transfer.py": [
        ("switch", SWITCH_OLD, SWITCH_NEW),
        ("gate", GATE_OLD, GATE_NEW),
        ("guard-init", GUARD_INIT_OLD, GUARD_INIT_NEW),
        ("guard-act", GUARD_ACT_OLD, GUARD_ACT_NEW),
        ("guard-hit", GUARD_HIT_OLD, GUARD_HIT_NEW),
    ],
    "template_hook.py": [
        ("hook-head", HOOK_OLD_HEAD, HOOK_NEW_HEAD),
        ("hook-stop", HOOK_OLD_STOP, HOOK_NEW_STOP),
        ("hook-tail", HOOK_OLD_TAIL, HOOK_NEW_TAIL),
    ],
}


def build(analysis: pathlib.Path, out: pathlib.Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    diffs = []
    for name, edits in EDITS.items():
        src = (analysis / name).read_text()
        text = src
        for label, old, new in edits:
            n = text.count(old)
            if n != 1:
                raise SystemExit(f"BLAD: {name}: wzorzec '{label}' wystepuje {n}x "
                                 f"(wymagane dokladnie 1) - zrodlo sie zmienilo")
            text = text.replace(old, new)
        (out / name).write_text(text)
        diff = difflib.unified_diff(
            src.splitlines(keepends=True), text.splitlines(keepends=True),
            fromfile=f"a/analysis/{name}", tofile=f"b/analysis/{name}")
        diffs.append(("".join(diff)))
    (out / "v18-arena.diff").write_text("".join(diffs))
    return diffs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", required=True, help="katalog analysis/ z galezi Smaka")
    ap.add_argument("--out", default="build")
    args = ap.parse_args(argv)
    diffs = build(pathlib.Path(args.analysis), pathlib.Path(args.out))
    print(f"zbudowano {args.out}/")
    for d in diffs:
        print(f"  {d.count(chr(10)):3d} linii diff  "
              f"{[l for l in d.splitlines() if l.startswith('+++')][0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
