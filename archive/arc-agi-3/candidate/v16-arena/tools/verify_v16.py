#!/usr/bin/env python3
"""Offline verification for the v16-arena candidate notebook (no GPU, no Kaggle).

  python3 tools/verify_v16.py [--bundle <r033 bundle dir>] [--tests]

Without --bundle: notebook/metadata/switch/playbook/probe checks only.
With --bundle: extracts all nine patches from the notebook itself, applies them
in notebook order to a pristine copy of the bundle's ARC3-Inference tree,
compiles it, and (with --tests) runs the four test modules against the PATCHED
tree: 12 plan-commit, 6 escalate-relative, 21 priority-D', 11 winpath.

The last check in --tests mode is the one this candidate exists for: on the
patched tree, `select_priority` with ARC3_PRIORITY_DPRIME unset must return
exactly what the shipped `priority_value` returns, for every argument
combination the two call sites can produce. `tests/test_priority_dprime.py`
covers that too; here it is re-asserted against the freshly patched tree so a
patch-order accident cannot pass unnoticed.

Patch extraction mirrors Kaggle runtime faithfully (see verify_v11.py).
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
NB = PKG / "arc3-duck-v16.ipynb"

FAIL: list[str] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    print(("OK   " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))
    if not ok:
        FAIL.append(name)


def cells_of(nb: dict) -> list[str]:
    return ["".join(c.get("source", [])) for c in nb.get("cells", [])]


def extract_patches(cells: list[str]) -> dict[str, str]:
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
    check("notebook parses (42 cells)", len(cells) == 42, len(cells))

    bad, compiled = [], 0
    for i, (c, s) in enumerate(zip(nb["cells"], cells)):
        if c.get("cell_type") != "code" or s.lstrip().startswith("%%"):
            continue
        s2 = "\n".join("pass" if ln.lstrip().startswith("!") else ln for ln in s.splitlines())
        try:
            compile(s2, f"<cell {i}>", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            compiled += 1
        except SyntaxError as exc:
            bad.append(f"{i}: {exc}")
    check(f"code cells compile ({compiled})", not bad, "; ".join(bad))

    joined = "\n".join(cells)
    # --- inherited v13.4 machinery (must still be exactly there) -------------
    check("concurrency fix present", 'ARC3_TRUE_CONCURRENCY", "10"' in joined)
    check("cap off in variant env", '"ARC3_LEVEL_TOKEN_CAP": "0"' in joined)
    check("winpath on in variant env",
          '"ARC3_WINPATH": "1"' in joined and '"ARC3_DEAD_SKIP": "1"' in joined)
    check("opener commit hint on in variant env", '"ARC3_OPENER_COMMIT_HINT": "1"' in joined)
    check("relative escalation on in variant env",
          '"ARC3_ESCALATE_RELATIVE": "1"' in joined
          and '"ARC3_ESCALATE_RATE": "1.2"' in joined
          and '"ARC3_ESCALATE_MAX_PER_LEVEL": "2"' in joined)
    check("escalation floor measured (20, not 10)",
          re.search(r"^ESCALATE_ACTIONS = 20$", joined, flags=re.M) is not None
          and "ESCALATE_ACTIONS = 10" not in joined)
    check("roster-probe hook guarded (v14/v13.4 fix)",
          "except AttributeError as exc" in joined and "probe: BLAD" in joined)
    check("budget probe present (v13.4)",
          "v13.4 budget probe" in joined and "budget_probe.json" in joined)
    check("roster probe present (v13.4, own file)",
          "v13.4 roster probe" in joined and "roster_probe_runs.jsonl" in joined)
    check("all eight inherited patches registered",
          all(f"/kaggle/duck-extra-0{i}.patch" in joined for i in range(7))
          and all(f"000{i}-" in joined for i in range(1, 9)))
    # --- the one new variable ------------------------------------------------
    check("D' switch on in variant env", '"ARC3_PRIORITY_DPRIME": "1"' in joined)
    check("legacy cost factor kept off", '"ARC3_PRIORITY_PACE": "0"' in joined)
    check("patch 0009 registered",
          "/kaggle/duck-extra-07.patch" in joined and "0009-priority-dprime" in joined)
    check("D' probe present", "v16 D' priority probe" in joined)
    check("D' metering present", "v16 dprime metering" in joined
          and "dprime_metering.jsonl" in joined)
    check("v16 version print", "v16-arena profile" in joined)

    switch = next(s for s in cells if "v13 switch" in s)
    check('switch assignment is PLAN_COMMIT = "1"',
          re.search(r'^PLAN_COMMIT = "1"', switch, flags=re.M) is not None)
    for plan, expect in [("1", True), ("0", False)]:
        ns: dict = {}
        src = re.sub(r'^PLAN_COMMIT = "1"', f'PLAN_COMMIT = "{plan}"', switch,
                     count=1, flags=re.M)
        import io
        buf, real = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            exec(compile(src, "<switch>", "exec"), ns)
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

    proc = subprocess.run([sys.executable, str(PKG / "tools" / "test_v16_probes.py")],
                          capture_output=True, text=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    check("D' probe/metering stub tests pass", proc.returncode == 0,
          (proc.stderr or proc.stdout)[-400:])

    patches = extract_patches(cells)
    order = ["harness-changes.patch", "duck-extra-00.patch", "duck-extra-01.patch",
             "duck-extra-02.patch", "duck-extra-03.patch", "duck-extra-04.patch",
             "duck-extra-05.patch", "duck-extra-06.patch", "duck-extra-07.patch"]
    check("all nine patches extracted", all(p in patches for p in order),
          [p for p in order if p not in patches])

    if args.bundle:
        bundle = Path(args.bundle)
        tmp = Path(tempfile.mkdtemp(prefix="v16-verify-"))
        try:
            work = tmp / "src"
            shutil.copytree(bundle / "src", work)
            subprocess.run(["git", "init", "-q"], cwd=work, check=True)
            subprocess.run(["git", "add", "-A", "-f"], cwd=work, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.email=v@v", "-c", "user.name=v", "commit", "-qm", "base"],
                           cwd=work, check=True, capture_output=True)
            applied_all = True
            for name in order:
                body = patches[name]
                (tmp / name).write_text(body if body.endswith("\n") else body + "\n")
                proc = subprocess.run(["git", "apply", "--include=ARC3-Inference/*", str(tmp / name)],
                                      cwd=work, capture_output=True, text=True)
                check(f"applies: {name}", proc.returncode == 0,
                      proc.stderr.strip().splitlines()[-1] if proc.stderr else "")
                if proc.returncode != 0:
                    applied_all = False
                    break
            if applied_all:
                proc = subprocess.run([sys.executable, "-m", "compileall", "-q", "ARC3-Inference/inference"],
                                      cwd=work, capture_output=True, text=True)
                check("patched tree compiles", proc.returncode == 0, proc.stderr[-300:])
                check("winpath module present in tree",
                      (work / "ARC3-Inference/inference/framework/arc3_winpath.py").exists())
                sched = work / "ARC3-Inference/inference/agent/priority_scheduler.py"
                agent = work / "ARC3-Inference/inference/agent/tool_agent.py"
                sched_src = sched.read_text()
                agent_src = agent.read_text()
                check("D' formula in patched tree", "def dprime_value(" in sched_src
                      and "def select_priority(" in sched_src)
                check("both call sites route through select_priority",
                      agent_src.count("select_priority(") == 2
                      and "mean_tokens_per_cleared_level=mean_tokens" in agent_src)
                check("raw pace recorded when D' is on", "or dprime_enabled()" in agent_src)
                check("legacy priority_value kept verbatim",
                      "def priority_value(" in sched_src and "tail_lookup" in sched_src)
                snapshot = PKG / "src" / "priority_scheduler_v16.py"
                check("src/priority_scheduler_v16.py == patched tree (replay input)",
                      snapshot.exists() and snapshot.read_text() == sched_src)
                if args.tests:
                    tdir = work / "ARC3-Inference" / "tests"
                    tdir.mkdir(exist_ok=True)
                    (tdir / "__init__.py").write_text("")
                    for src_name, dst_name in (
                        ("test_plan_commit.py", "test_plan_commit.py"),
                        ("test_escalate_relative.py", "test_escalate_relative.py"),
                        ("test_priority_dprime.py", "test_priority_dprime.py"),
                    ):
                        source = PKG / "tests" / src_name
                        if not source.exists():
                            source = PKG.parent / "v134-src-tests" / src_name
                        shutil.copyfile(source, tdir / dst_name)
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
                    check("12 plan-commit + 6 escalate-relative + 21 D' tests pass",
                          proc.returncode == 0, (proc.stderr or proc.stdout)[-400:])
                    wtest = tmp / "test_winpath_tree.py"
                    shutil.copyfile(PKG / "tests" / "test_winpath.py", wtest)
                    env2 = dict(os.environ)
                    env2["PYTHONPATH"] = (str(work / "ARC3-Inference" / "inference" / "framework")
                                          + os.pathsep + env2.get("PYTHONPATH", "")).rstrip(os.pathsep)
                    proc = subprocess.run([sys.executable, str(wtest), "-v"],
                                          capture_output=True, text=True, env=env2)
                    check("11 winpath tests pass on patched tree", proc.returncode == 0,
                          (proc.stderr or proc.stdout)[-300:])
                    # The single-variable guarantee, re-asserted on this tree.
                    script = r'''
import itertools, json, os
from inference.agent import priority_scheduler as ps
for k in ("ARC3_PRIORITY_DPRIME", "ARC3_PRIORITY_PACE"):
    os.environ.pop(k, None)
snaps = [ps.PrioritySnapshot(1, 0, 0.0), ps.PrioritySnapshot(3, 40, 90000.0, 1.4, 7, 31000.0),
         ps.PrioritySnapshot(10, 226, 480000.0, total_levels=10)]
kw = [{}, {"endgame": True}, {"tail_fraction": 0.0}, {"tail_fraction": 0.35},
      {"normalize_score": True}, {"tail_lookup": True}, {"tail_lookup": "remaining"},
      {"normalize_score": True, "tail_lookup": "remaining", "tail_fraction": 0.2}]
bad = [(s, k) for s in snaps for k in kw
       if ps.select_priority(s, **k) != ps.priority_value(s, **k)]
print(json.dumps({"mismatches": len(bad), "cases": len(snaps) * len(kw)}))
raise SystemExit(1 if bad else 0)
'''
                    env3 = dict(env)
                    proc = subprocess.run([sys.executable, "-c", script],
                                          cwd=work / "ARC3-Inference", capture_output=True,
                                          text=True, env=env3)
                    check("switch-off == shipped priority_value on the patched tree",
                          proc.returncode == 0, (proc.stderr or proc.stdout)[-300:])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        print("SKIP patch-chain checks (pass --bundle <r033 bundle dir>)")

    print()
    if FAIL:
        print(f"{len(FAIL)} FAILURES: {FAIL}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
