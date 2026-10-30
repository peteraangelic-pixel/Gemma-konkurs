"""v15 invariants: nothing that v13.3 certified may drift.

The risk of this build is not that the four edits are wrong (they are env-only or read-only),
it is that a build step quietly touched the patch chain, the standalone module or the
playbook. These hashes are the v13.3-arena ones.
"""
import hashlib
import json
import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def test_patch_chain_unchanged():
    assert md5(PKG / "patches" / "0006-winpath-replay.patch") == \
        "04a91380f253877f14fb19e7ea30892c"
    assert len(list((PKG / "patches").glob("*.patch"))) == 2, "v13.3 chain is 0006 + 0007"
    # 0007 must stay the log-only patch (42 insertions, no behaviour change)
    txt = (PKG / "patches" / "0007-arena-replay-log.patch").read_text()
    assert txt.count("\n+def _log(") == 1
    assert "-    return (int(data.get(\"best_levels\", 0)) <= 0" in txt


def test_standalone_module_and_playbook_unchanged():
    # the module the 11 winpath tests and the engine run against
    assert md5(PKG / "src" / "arc3_winpath.py") == "b8ffedaa4fdede79500d15830e9bf762"
    assert hashlib.md5((PKG / "playbook.json").read_bytes()).hexdigest() == \
        "e2d86b1e07fe35d2412065268d142175"
    pb = json.loads((PKG / "playbook.json").read_text())
    assert sum(len(g["levels"]) for g in pb["games"].values()) == 14


def test_notebook_keeps_v133_mechanisms_and_adds_the_measured_threshold():
    nb = json.loads((PKG / "arc3-duck-v15.ipynb").read_text())
    cells = ["".join(c.get("source", [])) for c in nb["cells"]]
    assert len(cells) == 37
    variant = cells[1]
    assert '"ARC3_OPENER_COMMIT_HINT": "1"' in variant          # the v13.3 mechanism
    assert "duck-extra-05.patch" in variant                     # the log patch is registered
    switch = cells[2]
    assert "ESCALATE_ACTIONS = 20" in switch
    assert "ESCALATE_ACTIONS = 10" not in switch
    assert any("v15 budget probe" in c for c in cells)
    assert any("v15 roster probe" in c for c in cells)
    cfg = next(c for c in cells if "_install_roster_probe" in c and "bm.solver" in c)
    i = cfg.index("_orig_play = _S._HarnessGameSession.play")
    assert "try:" in cfg[max(0, i - 200):i], "probe attribute lookup must be guarded"
