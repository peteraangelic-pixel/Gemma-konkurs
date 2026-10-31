"""Testy paczki duck-v17: champion v3 + kontroler template + guard + kill-switch.

Każdy test sprawdza EFEKT (bajty, które lecą na Kaggle / zachowanie kontrolera),
nie samo wywołanie funkcji budującej.
"""
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

PKG = pathlib.Path(__file__).resolve().parents[1]
NB = PKG / "arc3-duck-v17.ipynb"
SRC = PKG / "src/base-v3-template.ipynb"
GUARD = PKG / "src/vendor/codex_template_guarded.py"
AUDIT = PKG.parent / "local-lab/template-audit"

sys.path.insert(0, str(PKG / "tools"))
from extract_module import files, patch_text  # noqa: E402

BASE_SHA256 = "550eb185aa12efe9450e011c794ff12625adc18db287cf9f8248fa716208d5fa"
SHIPPED = {
    "ARC3-Inference/inference/utils/codex_template_transfer.py",
    "ARC3-Inference/inference/utils/codex_template_hook.py",
    "ARC3-Inference/inference/utils/codex_template_guarded.py",
    "ARC3-Inference/inference/agent/tool_agent.py",
}


def cell_sources(path):
    return ["".join(c.get("source", [])) for c in json.loads(path.read_text())["cells"]]


# ---------------------------------------------------------------- baza i build
def test_base_is_the_measured_champion_v3():
    raw = SRC.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == BASE_SHA256, "baza to nie zweryfikowany notebook autora"
    src = "\n".join(cell_sources(SRC))
    assert '"name": "v3-world-model"' in src
    variant = src[src.index("ARC3_VARIANT = {"):]
    variant = variant[:variant.index("ARC3_VARIANT = {") + 900]
    assert "0001-level-notes-audit-experiment-hint.patch" in variant
    assert "0002-executable-world-model.patch" in variant
    assert '"ARC3_WORLD_MODEL": "1"' in variant, "champion v3 ma world model ON"


def test_build_is_deterministic(tmp_path):
    out = tmp_path / "rebuild.ipynb"
    subprocess.run([sys.executable, str(PKG / "tools/build_v17.py"), "--out", str(out)],
                   check=True, capture_output=True)
    assert out.read_bytes() == NB.read_bytes(), "build nie jest powtarzalny"


def test_shipped_module_equals_the_audited_one():
    mod = files(patch_text(NB))
    assert set(mod) == SHIPPED
    for shipped, audited in (
        ("ARC3-Inference/inference/utils/codex_template_transfer.py", "template_transfer.py"),
        ("ARC3-Inference/inference/utils/codex_template_hook.py", "template_hook.py"),
    ):
        assert mod[shipped].rstrip("\n") == (AUDIT / audited).read_text().rstrip("\n"), \
            f"{audited}: wysyłane bajty różnią się od przetestowanych"
    # extractor składa plik z linii patcha, więc gubi końcowy newline — porównujemy resztę
    assert mod["ARC3-Inference/inference/utils/codex_template_guarded.py"].rstrip("\n") \
        == GUARD.read_text().rstrip("\n"), "warstwa guard w notebooku różni się od src/vendor"


def test_only_cell_8_changed_against_the_author_notebook():
    before, after = cell_sources(SRC), cell_sources(NB)
    assert len(before) == len(after) == 30
    assert [i for i, (a, b) in enumerate(zip(before, after)) if a != b] == [8], \
        "zmieniona komórka inna niż patch template"


# ------------------------------------------------------------------- patch
def test_every_hunk_counter_matches_its_body():
    """Stary błąd: licznik hunka +8 przy 7 nowych liniach. Sprawdzamy ARYTMETYKĘ, nie string."""
    lines = patch_text(NB).splitlines()
    seen = 0
    for i, line in enumerate(lines):
        if not line.startswith("@@"):
            continue
        seen += 1
        head = line.split("@@")[1].split()
        old_n, new_n = int(head[0].split(",")[1]), int(head[1].split(",")[1])
        old = new = 0
        for body in lines[i + 1:]:
            if body.startswith(("@@", "diff --git", "--- ", "+++ ", "new file mode", "index ")):
                break
            s = body[:1]
            if s == " " or body == "":
                old += 1
                new += 1
            elif s == "-":
                old += 1
            elif s == "+":
                new += 1
        assert (old, new) == (old_n, new_n), f"{line!r}: ciało ma ({old},{new})"
    assert seen == 4, f"oczekiwano 4 hunków (3 pliki + tool_agent), jest {seen}"


def test_patch_applies_to_a_clean_tree(tmp_path):
    """git apply na atrapie drzewa: dowód, że hunk trafia w kontekst i nic nie pęka."""
    root = tmp_path / "tree"
    (root / "ARC3-Inference/inference/agent").mkdir(parents=True)
    (root / "ARC3-Inference/inference/utils").mkdir(parents=True)
    filler = "\n".join(["# filler"] * 7431) + "\n"
    (root / "ARC3-Inference/inference/agent/tool_agent.py").write_text(
        filler + "            reasoning=captured_reasoning,\n"
                 "            yielded_control=yielded_control_reason is not None,\n        )\n")
    patch = tmp_path / "p.diff"
    patch.write_text(patch_text(NB))
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=root, check=True)
    subprocess.run(["git", "apply", str(patch)], cwd=root, check=True)
    tail = (root / "ARC3-Inference/inference/agent/tool_agent.py").read_text().splitlines()[-3:]
    assert tail[1:] == [
        "from inference.utils.codex_template_guarded import install as _install_guarded_template",
        '_install_guarded_template(__import__(__name__, fromlist=["ToolAgent"]))',
    ]
    for rel in SHIPPED - {"ARC3-Inference/inference/agent/tool_agent.py"}:
        compile((root / rel).read_text(), rel, "exec")


# ------------------------------------------------------- guard + kill-switch
def _load_guard(with_env="1"):
    """Import src/vendor/... z atrapami inference.utils.* — bez arcengine, bez Kaggle."""
    made = {}

    def pkg(name):
        m = type(sys)(name)
        m.__path__ = []
        sys.modules[name] = m
        made[name] = m
        return m

    class FakeTransfer:
        def __init__(self, *a, **kw):
            self.level = None
            self.learned = "nauka"

        def act(self, grid, available, level):
            self.level = level
            return ("A", 7, 7)

    transfer = type(sys)("inference.utils.codex_template_transfer")
    transfer.TemplateTransfer = FakeTransfer
    hook_calls = []
    hook = type(sys)("inference.utils.codex_template_hook")

    def install_base(ta, controller_class):
        hook_calls.append(controller_class)

        def enabled(self, *a, **k):
            return "hook"

        ta.ToolAgent.analyze = enabled

    hook.install = install_base
    for name in ("inference", "inference.utils", "inference.utils.codex_template_transfer",
                 "inference.utils.codex_template_hook"):
        made[name] = sys.modules.get(name)
        pkg(name)
    sys.modules["inference.utils.codex_template_transfer"] = transfer
    sys.modules["inference.utils.codex_template_hook"] = hook

    spec = importlib.util.spec_from_file_location("guard_under_test", GUARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, hook_calls, made, FakeTransfer


def test_guard_caps_proposals_and_resets_on_new_level(monkeypatch):
    monkeypatch.setenv("ARC3_TEMPLATE", "1")
    mod, _, made, _ = _load_guard()
    try:
        ctl = mod.GuardedTemplateTransfer(max_actions_per_level=3)
        assert [ctl.act([[0]], [], 1) is not None for _ in range(5)] == [True, True, True, False, False]
        assert ctl.cap_hits == 2
        assert ctl.act([[0]], [], 1) is None, "limit nie trzyma"
        assert ctl.act([[0]], [], 2) is not None, "nowy poziom nie resetuje limitu"
        assert ctl.level_actions == 1
        with pytest.raises(ValueError):
            mod.GuardedTemplateTransfer(max_actions_per_level=0)
    finally:
        _cleanup(made)


def _cleanup(made):
    for k, v in made.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


@pytest.mark.parametrize("env,expected", [(None, "hook"), ("1", "hook"), ("0", "original")])
def test_kill_switch_decides_whether_the_controller_acts(monkeypatch, env, expected):
    if env is None:
        monkeypatch.delenv("ARC3_TEMPLATE", raising=False)
    else:
        monkeypatch.setenv("ARC3_TEMPLATE", env)
    mod, hook_calls, made, _ = _load_guard()
    try:
        ta = type(sys)("fake_ta")
        ta.ToolAgent = type("ToolAgent", (), {})
        ta.ToolAgent.analyze = lambda self, *a, **k: "original"
        mod.install(ta)
        assert ta.ToolAgent.analyze(None) == expected
        assert len(hook_calls) == 1, "hook bazowy nie został założony"
        mod.install(ta)                              # idempotencja
        assert len(hook_calls) == 1
    finally:
        _cleanup(made)


# ------------------------------------------------------------------ metadane
def test_metadata_has_our_own_slug():
    meta = json.loads((PKG / "kernel-metadata.json").read_text())
    assert meta["id"] == "petersharps/arc3-duck-v17-champion-template"
    assert meta["code_file"] == "arc3-duck-v17.ipynb"
    for foreign in ("arc3-duck-v13-2", "arc3-duck-v13-3-arena", "arc3-duck-v13-4-unified"):
        assert foreign not in meta["id"], "kolizja z cudzym slugiem"
