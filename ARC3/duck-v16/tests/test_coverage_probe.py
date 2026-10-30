"""The coverage probe and the 41-cell numbering must not lie about a finished run."""
import io
import json
import os
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace as NS

PKG = Path(__file__).resolve().parent.parent


def _cell() -> str:
    nb = json.loads((PKG / "arc3-duck-v16.ipynb").read_text())
    hits = ["".join(c.get("source", [])) for c in nb["cells"]
            if "v16 coverage probe" in "".join(c.get("source", []))]
    assert len(hits) == 1
    return hits[0]


def _run(runs, tmp):
    """Run the cell with the probe's output redirected into tmp (env override)."""
    os.environ["V16_COVERAGE_OUT"] = str(Path(tmp) / "coverage_probe.json")
    buf = io.StringIO()
    with redirect_stdout(buf):
        exec(compile(_cell(), "<coverage>", "exec"),
             {"__name__": "__cell__", "bm": NS(game_runs=runs)})
    return buf.getvalue()


def _run_obj(gid, done, total, per_level, tokens_per_action, base):
    hist = []
    for acts, tok in zip(per_level, tokens_per_action):
        hist.append(NS(generated_tokens=tok))                     # one call per level
        hist.extend(NS(generated_tokens=0) for _ in range(acts - 1))
    return NS(game_id=gid, number_of_levels=total, levels_completed=done,
              actions_per_level=per_level, history=hist,
              base_actions_per_level=base, final_score=25.0,
              final_wallclock_seconds=2880.0)


def test_scores_coverage_and_flags_hidden_baseline():
    runs = [_run_obj("ls20-9607627b", 2, 4, [20, 30], [4000, 6000], None),
            _run_obj("tn36-ef4dde99", 1, 8, [16], [3000], [32, 40])]
    with tempfile.TemporaryDirectory() as d:
        out = _run(runs, d)
        assert "v16 coverage:" in out, out
        assert "baseline=no na WSZYSTKICH grach" not in out      # one game does have it
        rec = json.loads((Path(d) / "coverage_probe.json").read_text())
    s = rec["summary"]
    # weights are w_k = k, so coverage = sum(1..done)/sum(1..total):
    # ls20  2 of 4 -> 3/10  = 30.0% ; tn36  1 of 8 -> 1/36 = 2.8%
    assert rec["games"][0]["coverage"] == 30.0, rec["games"][0]
    assert rec["games"][1]["coverage"] == 2.8, rec["games"][1]
    assert s["baseline_available"] == 1 and s["games"] == 2
    assert abs(s["mean_coverage"] - 16.4) < 0.1, s
    print("coverage probe: pokrycie liczone jak regula (30.0% / 2.8%), baseline=yes/1  OK")


def test_flags_hidden_baseline_everywhere():
    runs = [_run_obj("ls20-1111", 1, 3, [10], [1000], None)]
    with tempfile.TemporaryDirectory() as d:
        out = _run(runs, d)
    assert "baseline=no na WSZYSTKICH grach" in out, out
    assert "eskalacja relatywna (0008) byla w tym biegu martwa" in out, out
    print("coverage probe: brak baseline'u -> werdykt o martwym 0008              OK")


def test_a_call_alarm():
    # cn04: 5 actions, all from ONE model call -> a/call = 5 (batch works)
    # dc22: 3 actions from three calls -> a/call = 1 (batch does not work)
    batched = _run_obj("cn04-2222", 1, 5, [5], [2500], None)
    batched.history = [NS(generated_tokens=2500)] + [NS(generated_tokens=0)] * 4
    single = _run_obj("dc22-3333", 1, 3, [1, 1, 1], [900, 900, 900], None)
    with tempfile.TemporaryDirectory() as d:
        out = _run([batched], d)
        rec = json.loads((Path(d) / "coverage_probe.json").read_text())
    assert rec["games"][0]["a_per_call"] == 5.0, rec["games"][0]
    with tempfile.TemporaryDirectory() as d:
        out2 = _run([single], d)
    assert "a/call=1.0 < 1.5" in out2, out2
    print("coverage probe: a/call=5 bez alarmu, a/call=1.0 z alarmem         OK")


def test_survives_broken_data():
    with tempfile.TemporaryDirectory() as d:
        class Boom:
            @property
            def game_id(self):
                raise RuntimeError("nope")
        out = _run([Boom()], d)
    assert "skipped" in out, out
    print("coverage probe: wyjatek -> 'skipped', komorka nie umiera       OK")


if __name__ == "__main__":
    test_scores_coverage_and_flags_hidden_baseline()
    test_flags_hidden_baseline_everywhere()
    test_a_call_alarm()
    test_survives_broken_data()
    print("\nwszystkie testy sondy pokrycia przeszly")
