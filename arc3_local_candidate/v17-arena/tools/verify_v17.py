#!/usr/bin/env python3
"""Offline verification for the v17-arena candidate notebook (no GPU, no Kaggle).

  python3 tools/verify_v17.py [--bundle <r033 bundle dir>] [--tests]

Without --bundle: notebook/metadata/switch/playbook/probe checks only.
With --bundle: extracts all ten patches from the notebook itself, applies them
in notebook order to a pristine copy of the bundle's ARC3-Inference tree,
compiles it, and (with --tests) runs the five test modules against the PATCHED
tree: 12 plan-commit, 6 escalate-relative, self-pace (22/14 on r085), 21
priority-D', 11 winpath.

Two invariants are re-asserted on the freshly patched tree, because they are the
whole reason this candidate is a single-variable experiment:

  * `select_priority` with ARC3_PRIORITY_DPRIME unset returns exactly what the
    shipped `priority_value` returns;
  * the self-pace escalation of patch 0009 still produces 22 nudges / 14
    premature on r085 with D' switched on (D' must not touch escalation).

Environment needed for --tests: a `requests`/`PIL` stub or the real packages (the
agent module imports both at module level) and R085_BENCH pointing at a real
benchmark.json, otherwise the r085 tests skip or the data-driven ones error.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
NB = PKG / "arc3-duck-v17.ipynb"
CELLS = 43
PATCH_ORDER = ["harness-changes.patch"] + [f"duck-extra-0{i}.patch" for i in range(9)]

FAIL: list[str] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    print(("OK   " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))
    if not ok:
        FAIL.append(name)


def cells_of(nb: dict) -> list[str]:
    return ["".join(c.get("source", [])) for c in nb.get("cells", [])]


def extract_patches(cells: list[str]) -> dict[str, str]:
    """Same extraction as the Kaggle runtime: %%writefile first, then write_text."""
    patches: dict[str, str] = {}
    for src in cells:
        if src.startswith("%%writefile"):
            head, _, body = src.partition("\n")
            patches[Path(head.split(maxsplit=1)[1].strip()).name] = body
            continue
        if ".write_text(" not in src or ".patch" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "write_text" and node.args):
                try:
                    body = ast.literal_eval(node.args[0])
                except Exception:
                    continue
                m = re.search(r"""['"]([^'"]+\.patch)['"]""", src)
                if m and isinstance(body, str):
                    patches[Path(m.group(1)).name] = body
    return patches


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default="")
    ap.add_argument("--tests", action="store_true")
    args = ap.parse_args()

    nb = json.loads(NB.read_text())
    cells = cells_of(nb)
    check(f"notebook parses ({CELLS} cells)", len(cells) == CELLS, len(cells))

    bad, compiled = [], 0
    for i, (cell, src) in enumerate(zip(nb["cells"], cells)):
        if cell.get("cell_type") != "code" or src.lstrip().startswith("%%"):
            continue
        body = "\n".join("pass" if ln.lstrip().startswith("!") else ln
                         for ln in src.splitlines())
        try:
            compile(body, f"<cell {i}>", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            compiled += 1
        except SyntaxError as exc:
            bad.append(f"{i}: {exc}")
    check(f"code cells compile ({compiled})", not bad, "; ".join(bad))

    joined = "\n".join(cells)
    # --- inherited v13.6 machinery (must still be exactly there) -------------
    check("concurrency fix present", 'ARC3_TRUE_CONCURRENCY", "10"' in joined)
    check("cap off in variant env", '"ARC3_LEVEL_TOKEN_CAP": "0"' in joined)
    check("winpath + dead-skip on", '"ARC3_WINPATH": "1"' in joined
          and '"ARC3_DEAD_SKIP": "1"' in joined)
    check("opener commit hint on", '"ARC3_OPENER_COMMIT_HINT": "1"' in joined)
    check("relative escalation still declared", '"ARC3_ESCALATE_RELATIVE": "1"' in joined
          and '"ARC3_ESCALATE_RATE": "1.2"' in joined
          and '"ARC3_ESCALATE_MAX_PER_LEVEL": "2"' in joined)
    check("self-pace escalation armed (0009)", '"ARC3_ESCALATE_SELF_PACE": "1"' in joined)
    check("escalation floor 20", re.search(r"^ESCALATE_ACTIONS = 20$", joined, flags=re.M)
          is not None and "ESCALATE_ACTIONS = 10" not in joined)
    check("guarded roster hook", "except AttributeError as exc" in joined)
    check("budget probe present", "budget probe" in joined and "budget_probe.json" in joined)
    check("roster probe present (own file)", "roster probe" in joined
          and "roster_probe_runs.jsonl" in joined)
    check("weighted coverage + baseline visibility in the roster probe (v13.5)",
          "coverage_pct" in joined and "sufit wyniku" in joined)
    check("live a/call instrument (v13.6)", "a/call" in joined)
    check("nine inherited patches registered",
          all(f"/kaggle/duck-extra-0{i}.patch" in joined for i in range(8))
          and all(f"000{i}-" in joined for i in range(1, 10)))
    # --- the one new variable ------------------------------------------------
    check("D' switch on in variant env", '"ARC3_PRIORITY_DPRIME": "1"' in joined)
    check("legacy cost factor kept off", '"ARC3_PRIORITY_PACE": "0"' in joined)
    check("patch 0010 registered", "/kaggle/duck-extra-08.patch" in joined
          and "0010-priority-dprime" in joined)
    check("D' probe present", "v17 D' priority probe" in joined)
    check("D' metering present", "v17 dprime metering" in joined
          and "dprime_metering.jsonl" in joined)
    check("v17 version print", "v17-arena profile" in joined)

    switch = next(s for s in cells if "v13 switch" in s)
    check('switch assignment is PLAN_COMMIT = "1"',
          re.search(r'^PLAN_COMMIT = "1"', switch, flags=re.M) is not None)
    import io
    for plan, expect in (("1", True), ("0", False)):
        ns: dict = {}
        body = re.sub(r'^PLAN_COMMIT = "1"', f'PLAN_COMMIT = "{plan}"', switch,
                      count=1, flags=re.M)
        buf, real = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            exec(compile(body, "<switch>", "exec"), ns)
        finally:
            sys.stdout = real
        env = ns["_v11_os"].environ
        check(f"switch PLAN_COMMIT={plan}",
              env.get("ARC3_TRUE_CONCURRENCY") == "10"
              and (("ARC3_PLAN_COMMIT" in env) == expect)
              and ns.get("V11_PROFILE") == ("plan" if expect else "c45fix"),
              {k: env.get(k) for k in ("ARC3_PLAN_COMMIT", "ARC3_TRUE_CONCURRENCY")})

    pb_cell = next(s for s in cells if "_PB = _pb_json.loads" in s)
    m = re.search(r"_pb_json\.loads\(r'''(.*?)'''\)", pb_cell, re.S)
    embedded = json.loads(m.group(1)) if m else {}
    on_disk = json.loads((PKG / "src" / "playbook.json").read_text())
    n_emb = sum(len(g["levels"]) for g in embedded.get("games", {}).values())
    check("playbook embedded == certified playbook.json (9 gier/14 poziomów)",
          embedded == on_disk and len(embedded.get("games", {})) == 9 and n_emb == 14,
          f"embedded {len(embedded.get('games', {}))} gier/{n_emb} poziomów")

    proc = subprocess.run([sys.executable, str(PKG / "tools" / "test_v17_probes.py")],
                          capture_output=True, text=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    check("D' probe/metering stub tests pass", proc.returncode == 0,
          (proc.stderr or proc.stdout)[-400:])

    patches = extract_patches(cells)
    check("all ten patches extracted", all(p in patches for p in PATCH_ORDER),
          [p for p in PATCH_ORDER if p not in patches])

    if not args.bundle:
        print("SKIP patch-chain checks (pass --bundle <r033 bundle dir>)")
    else:
        bundle = Path(args.bundle)
        tmp = Path(tempfile.mkdtemp(prefix="v17-verify-"))
        try:
            work = tmp / "src"
            shutil.copytree(bundle / "src", work,
                            ignore=shutil.ignore_patterns(".git", "__pycache__"))
            subprocess.run(["git", "init", "-q"], cwd=work, check=True)
            subprocess.run(["git", "add", "-A", "-f"], cwd=work, check=True,
                           capture_output=True)
            subprocess.run(["git", "-c", "user.email=v@v", "-c", "user.name=v",
                            "commit", "-qm", "base"], cwd=work, check=True,
                           capture_output=True)
            for name in PATCH_ORDER:
                body = patches[name]
                (tmp / name).write_text(body if body.endswith("\n") else body + "\n")
                proc = subprocess.run(["git", "apply", "--include=ARC3-Inference/*",
                                       str(tmp / name)],
                                      cwd=work, capture_output=True, text=True)
                check(f"applies: {name}", proc.returncode == 0,
                      proc.stderr.strip().splitlines()[-1] if proc.stderr else "")
                if proc.returncode != 0:
                    print(f"{len(FAIL)} FAILURES: {FAIL}")
                    return 1
            proc = subprocess.run([sys.executable, "-m", "compileall", "-q",
                                   "ARC3-Inference/inference"],
                                  cwd=work, capture_output=True, text=True)
            check("patched tree compiles", proc.returncode == 0, proc.stderr[-300:])
            check("winpath module present",
                  (work / "ARC3-Inference/inference/framework/arc3_winpath.py").exists())
            sched = (work / "ARC3-Inference/inference/agent/priority_scheduler.py").read_text()
            agent = (work / "ARC3-Inference/inference/agent/tool_agent.py").read_text()
            check("D' formula in patched tree",
                  "def dprime_value(" in sched and "def select_priority(" in sched)
            check("both call sites route through select_priority",
                  agent.count("select_priority(") == 2
                  and "mean_tokens_per_cleared_level=mean_tokens" in agent)
            check("self-pace survives the composition",
                  "_escalate_self_pace" in agent and "ARC3_ESCALATE_SELF_PACE" in agent)
            snapshot = PKG / "src" / "priority_scheduler_v17.py"
            check("src/priority_scheduler_v17.py == patched tree (replay input)",
                  snapshot.exists() and snapshot.read_text() == sched)

            if args.tests:
                tdir = work / "ARC3-Inference" / "tests"
                (tdir / "fixtures").mkdir(parents=True, exist_ok=True)
                (tdir / "__init__.py").write_text("")
                for name in ("test_plan_commit.py", "test_escalate_relative.py",
                             "test_self_pace.py", "test_priority_dprime.py"):
                    shutil.copyfile(PKG / "tests" / name, tdir / name)
                for fixture in (PKG / "tests" / "fixtures").glob("*.py"):
                    shutil.copyfile(fixture, tdir / "fixtures" / fixture.name)
                env = dict(os.environ)
                env["ARC3_PLAN_COMMIT"] = "1"
                env["PYTHONPATH"] = os.pathsep.join(
                    [str(work / "ARC3-Inference"), env.get("PYTHONPATH", "")]
                ).rstrip(os.pathsep)
                proc = subprocess.run(
                    [sys.executable, "-m", "unittest",
                     "tests.test_plan_commit", "tests.test_escalate_relative",
                     "tests.test_priority_dprime"],
                    cwd=work / "ARC3-Inference", capture_output=True, text=True, env=env)
                check("12 plan-commit + 5 escalate-relative + 21 D' tests pass",
                      proc.returncode == 0, (proc.stderr or proc.stdout)[-400:])

                proc = subprocess.run(
                    [sys.executable, str(tdir / "test_self_pace.py")],
                    cwd=work / "ARC3-Inference", capture_output=True, text=True, env=env)
                check("self-pace reproduces 22/14 on r085 from the patched tree",
                      proc.returncode == 0
                      and "self-pace=22/14" in (proc.stdout or ""),
                      (proc.stdout or proc.stderr)[-400:])

                wtest = tmp / "test_winpath_tree.py"
                shutil.copyfile(PKG / "tests" / "test_winpath.py", wtest)
                env2 = dict(os.environ)
                env2["PYTHONPATH"] = (
                    str(work / "ARC3-Inference" / "inference" / "framework")
                    + os.pathsep + env2.get("PYTHONPATH", "")).rstrip(os.pathsep)
                proc = subprocess.run([sys.executable, str(wtest)],
                                      capture_output=True, text=True, env=env2)
                check("11 winpath tests pass on patched tree", proc.returncode == 0,
                      (proc.stderr or proc.stdout)[-300:])

                script = r'''
import json, os
from inference.agent import priority_scheduler as ps
for k in ("ARC3_PRIORITY_DPRIME", "ARC3_PRIORITY_PACE"):
    os.environ.pop(k, None)
snaps = [ps.PrioritySnapshot(1, 0, 0.0),
         ps.PrioritySnapshot(3, 40, 90000.0, 1.4, 7, 31000.0),
         ps.PrioritySnapshot(10, 226, 480000.0, total_levels=10)]
kw = [{}, {"endgame": True}, {"tail_fraction": 0.0}, {"tail_fraction": 0.35},
      {"normalize_score": True}, {"tail_lookup": True}, {"tail_lookup": "remaining"},
      {"normalize_score": True, "tail_lookup": "remaining", "tail_fraction": 0.2}]
bad = [(s, k) for s in snaps for k in kw
       if ps.select_priority(s, **k) != ps.priority_value(s, **k)]
print(json.dumps({"mismatches": len(bad), "cases": len(snaps) * len(kw)}))
raise SystemExit(1 if bad else 0)
'''
                proc = subprocess.run([sys.executable, "-c", script],
                                      cwd=work / "ARC3-Inference", capture_output=True,
                                      text=True, env=env)
                check("switch-off == shipped priority_value on the patched tree",
                      proc.returncode == 0, (proc.stderr or proc.stdout)[-300:])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print(f"{len(FAIL)} FAILURES: {FAIL}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
