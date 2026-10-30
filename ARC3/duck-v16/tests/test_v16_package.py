"""v16 invariants: what v13.4 certified must not drift, and the fixtures must be honest."""
import hashlib
import json
import subprocess
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
FIX = PKG / "tests" / "fixtures"


def test_patch_chain_unchanged():
    names = sorted(p.name for p in (PKG / "patches").glob("*.patch"))
    assert names == ["0006-winpath-replay.patch", "0007-arena-replay-log.patch",
                     "0008-arena-escalate-relative.patch", "0009-arena-self-pace.patch"], names
    assert hashlib.md5((PKG / "src" / "arc3_winpath.py").read_bytes()).hexdigest() == \
        "b8ffedaa4fdede79500d15830e9bf762"
    assert hashlib.md5((PKG / "playbook.json").read_bytes()).hexdigest() == \
        "e2d86b1e07fe35d2412065268d142175"


def test_fixtures_reproduce_the_patch():
    """diff(pre, post) must be exactly the 0009 patch body."""
    pre = (FIX / "tool_agent_0009_pre.py").read_text().splitlines()
    post = (FIX / "tool_agent_0009_post.py").read_text().splitlines()
    diff = subprocess.run(["diff", "-u", str(FIX / "tool_agent_0009_pre.py"),
                           str(FIX / "tool_agent_0009_post.py")],
                          capture_output=True, text=True).stdout
    added = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))
    patch = (PKG / "patches" / "0009-arena-self-pace.patch").read_text()
    p_added = sum(1 for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++"))
    p_removed = sum(1 for l in patch.splitlines() if l.startswith("-") and not l.startswith("---"))
    assert (added, removed) == (p_added, p_removed), (added, removed, p_added, p_removed)
    # and every added line of the patch appears in the post fixture
    post_text = "\n".join(post)
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            assert line[1:] in post_text, line[:80]


def test_notebook_carries_everything():
    nb = json.loads((PKG / "arc3-duck-v16.ipynb").read_text())
    cells = ["".join(c.get("source", [])) for c in nb["cells"]]
    assert len(cells) == 41, len(cells)
    variant = cells[1]
    for needle in ('"ARC3_OPENER_COMMIT_HINT": "1"', '"ARC3_ESCALATE_RELATIVE": "1"',
                   '"ARC3_ESCALATE_SELF_PACE": "1"', '"ARC3_ESCALATE_MAX_PER_LEVEL": "2"',
                   "duck-extra-07.patch", "0009-arena-self-pace.patch"):
        assert needle in variant, needle
    switch = cells[2]
    assert "ESCALATE_ACTIONS = 20" in switch and "ESCALATE_ACTIONS = 10" not in switch
    assert any("v16 coverage probe" in c for c in cells)
    assert any("v13.4 budget probe" in c for c in cells)
    assert any("v13.4 roster probe" in c for c in cells)
    cfg = next(c for c in cells if "_install_roster_probe" in c and "bm.solver" in c)
    i = cfg.index("_orig_play = _S._HarnessGameSession.play")
    assert "try:" in cfg[max(0, i - 200):i]
