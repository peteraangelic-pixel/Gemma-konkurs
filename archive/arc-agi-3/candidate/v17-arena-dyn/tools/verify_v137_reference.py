#!/usr/bin/env python3
"""Offline verification for the v13 package (no GPU, no Kaggle).

  python3 tools/verify_v13.py [--bundle <r033 bundle dir>] [--tests]

Without --bundle: notebook/metadata/switch/playbook checks only.
With --bundle: also extracts all ten patches from the notebook itself,
applies them in notebook order to a pristine bundle copy, compiles the tree.
With --tests: also runs the 12 plan-commit tests, the 11 winpath tests and
the escalate-relative tests against the PATCHED tree, plus the probe stub
tests (interpreter needs arcengine/requests/pillow/pydantic - e.g. a venv
with those installed; PYTHONPATH is preserved).
v13.4-unified: opener hint (v13.3), ESCALATE=20 + relative trigger +
extra-05/06 + guarded hook + budget/roster probes (v14) checks.
v13.6-final: patch 0009 self-pace (works in the rerun), dead < 1.5
a/call alarm replaced by an unconditional base/targets/gate print (c87
"warstwa 8"), slug pinned, self-pace tests run against the shipped patch.

Patch extraction mirrors Kaggle runtime faithfully (see verify_v11.py).
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
NB = PKG / "arc3-duck-v13.ipynb"
META = PKG / "kernel-metadata.json"

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
    check("notebook parses (41 cells)", len(cells) == 41, len(cells))

    bad = []
    compiled = 0
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
    check("concurrency fix present", 'ARC3_TRUE_CONCURRENCY", "10"' in joined)
    check("concurrency 120 gone", "concurrency = 120" not in joined)
    check("extra-04 registered", '"/kaggle/duck-extra-04.patch"' in joined
          and "0006-winpath-replay" in joined)
    check("cap off in variant env", '"ARC3_LEVEL_TOKEN_CAP": "0"' in joined)
    check("winpath on in variant env", '"ARC3_WINPATH": "1"' in joined
          and '"ARC3_DEAD_SKIP": "1"' in joined)
    check("opener commit hint on in variant env",
          '"ARC3_OPENER_COMMIT_HINT": "1"' in joined)
    check("degradation documented in switch cell",
          "engine HIDES" in joined and "42 injections" in joined)
    check("extra-05 registered", '"/kaggle/duck-extra-05.patch"' in joined
          and "0007-arena-replay-log" in joined)
    check("extra-06 registered", '"/kaggle/duck-extra-06.patch"' in joined
          and "0008-arena-escalate-relative" in joined)
    check("extra-07 registered (0009 self-pace, byte-for-byte from Gemma duck-v16)",
          '"/kaggle/duck-extra-07.patch"' in joined and "0009-arena-self-pace" in joined)
    check("self-pace on in variant env",
          '"ARC3_ESCALATE_SELF_PACE": "1"' in joined
          and '"ARC3_ESCALATE_SELF_RATE": "1.5"' in joined)
    check("v13.7-final version print", 'v13.7-final profile' in joined)
    check("extra-08 registered (0010 dyn-level-budget, byte-for-byte from handoff arc-v16-package)",
          '"/kaggle/duck-extra-08.patch"' in joined and "0010-dyn-level-budget" in joined)
    check("0010 DORMANT: variant keeps ARC3_LEVEL_TOKEN_CAP=0 (arming = one value 60000)",
          '"ARC3_LEVEL_TOKEN_CAP": "0"' in joined)
    check("instrument fix: dead < 1.5 alarm gone, unconditional a/call print with base/gate",
          'if _acpc and _summary["mean_actions_per_call"] < 1.5' not in joined
          and "baza r019 = 4.357" in joined
          and ">= 6.0" in joined and "v13.7 batch: a/call" in joined)
    check("slug: kernel-metadata points at v13-6-final (no Gemma-style slug drift)",
          json.loads((NB.parent / "kernel-metadata.json").read_text())
          .get("id") == "petersharps/arc3-duck-v13-7-final")
    check("escalation floor measured (20, not 10)",
          re.search(r'^ESCALATE_ACTIONS = 20$', joined, flags=re.M) is not None
          and 'ESCALATE_ACTIONS = 10' not in joined)
    check("relative escalation on in variant env",
          '"ARC3_ESCALATE_RELATIVE": "1"' in joined
          and '"ARC3_ESCALATE_RATE": "1.2"' in joined
          and '"ARC3_ESCALATE_MAX_PER_LEVEL": "2"' in joined)
    check("roster-probe hook guarded (v14 fix)",
          "except AttributeError as exc" in joined
          and "probe: BLAD" in joined)
    check("budget probe present", "v13.7 budget probe" in joined
          and "budget_probe.json" in joined)
    check("roster probe present (own file, no clobber)",
          "v13.7 roster probe" in joined and "roster_probe_runs.jsonl" in joined
          and joined.count("roster_probe_runs.jsonl") >= 1)
    check("baseline visibility + coverage logged",
          '"baseline"' in joined and '"coverage_pct"' in joined
          and "score <= 100 x pokrycie" in joined)
    check("metering cell present", "v11_metrics.json" in joined)
    check("ONLY_RESET_LEVELS pinned", 'os.environ["ONLY_RESET_LEVELS"] = "true"' in joined)

    switch = next(s for s in cells if "v13 switch" in s)
    check("switch assignment is PLAN_COMMIT = \"1\"",
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
    on_disk = json.loads((PKG / "playbook.json").read_text())
    n_emb = sum(len(g["levels"]) for g in embedded.get("games", {}).values())
    n_disk = sum(len(g["levels"]) for g in on_disk.get("games", {}).values())
    check("playbook embedded == playbook.json (9 gier)",
          embedded == on_disk and len(embedded.get("games", {})) == 9
          and n_emb == n_disk == 14,
          f"embedded {len(embedded.get('games', {}))} gier/{n_emb} poziomów")

    meta = json.loads(META.read_text())
    check("metadata id/title/code_file",
          meta["id"].endswith("/arc3-duck-v13-7-final") and meta["title"] == "arc3-duck-v13-7-final"
          and meta["code_file"] == NB.name)
    declared = {d.lower() for d in meta.get("dataset_sources", [])}
    declared |= {mm.lower().split("/transformers")[0] for mm in meta.get("model_sources", [])}
    declared |= {c.lower() for c in meta.get("competition_sources", [])}
    missing = []
    for mm in re.finditer(r"/kaggle/input/(?:datasets|models|competitions)/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)", joined):
        ref = mm.group(1).lower()
        if not any(ref == d or ref.startswith(d + "/") for d in declared):
            missing.append(ref)
    check("all /kaggle/input paths declared", not missing, sorted(set(missing)))

    proc = subprocess.run([sys.executable, str(PKG / "tools" / "test_probes.py")],
                          capture_output=True, text=True)
    check("probe stub tests pass (budget/roster/guard)",
          proc.returncode == 0, (proc.stderr or proc.stdout)[-300:])

    patches = extract_patches(cells)
    order = ["harness-changes.patch", "duck-extra-00.patch", "duck-extra-01.patch",
             "duck-extra-02.patch", "duck-extra-03.patch", "duck-extra-04.patch",
             "duck-extra-05.patch", "duck-extra-06.patch", "duck-extra-07.patch",
             "duck-extra-08.patch"]
    check("all ten patches extracted", all(p in patches for p in order),
          [p for p in order if p not in patches])

    if args.bundle:
        bundle = Path(args.bundle)
        tmp = Path(tempfile.mkdtemp(prefix="v13-verify-"))
        try:
            work = tmp / "src"
            shutil.copytree(bundle / "src", work)
            subprocess.run(["git", "init", "-q"], cwd=work, check=True)
            subprocess.run(["git", "add", "-A", "-f"], cwd=work, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.email=v@v", "-c", "user.name=v", "commit", "-qm", "base"],
                           cwd=work, check=True, capture_output=True)
            for name in order:
                body = patches[name]
                (tmp / name).write_text(body if body.endswith("\n") else body + "\n")
                proc = subprocess.run(["git", "apply", "--include=ARC3-Inference/*", str(tmp / name)],
                                      cwd=work, capture_output=True, text=True)
                check(f"applies: {name}", proc.returncode == 0,
                      proc.stderr.strip().splitlines()[-1] if proc.stderr else "")
                if proc.returncode != 0:
                    break
            else:
                proc = subprocess.run([sys.executable, "-m", "compileall", "-q", "ARC3-Inference/inference"],
                                      cwd=work, capture_output=True, text=True)
                check("patched tree compiles", proc.returncode == 0, proc.stderr[-300:])
                check("winpath module present in tree",
                      (work / "ARC3-Inference/inference/framework/arc3_winpath.py").exists())
                if args.tests:
                    import os as _os
                    tdir = work / "ARC3-Inference" / "tests"
                    tdir.mkdir(exist_ok=True)
                    # plan-commit tests (from the v11 package layout)
                    src_tests = PKG / "tests" / "test_plan_commit.py"
                    if not src_tests.exists():
                        src_tests = PKG.parent / "duck-v11" / "tests" / "test_plan_commit.py"
                    shutil.copyfile(src_tests, tdir / "test_plan_commit.py")
                    shutil.copyfile(PKG / "tests" / "test_escalate_relative.py",
                                    tdir / "test_escalate_relative.py")
                    env = dict(_os.environ)
                    env["ARC3_PLAN_COMMIT"] = "1"
                    proc = subprocess.run([sys.executable, "-m", "unittest",
                                           "tests.test_plan_commit", "tests.test_escalate_relative"],
                                          cwd=work / "ARC3-Inference", capture_output=True,
                                          text=True, env=env)
                    check("12 plan-commit + 6 escalate-relative tests pass",
                          proc.returncode == 0, (proc.stderr or proc.stdout)[-300:])
                    # self-pace tests: fixtures == shipped patch text (Gemma's proof
                    # harness), run from the package dir where tests/fixtures live
                    proc = subprocess.run([sys.executable, str(PKG / "tests" / "test_self_pace.py")],
                                          capture_output=True, text=True)
                    check("self-pace tests pass (22/14 on r085, 1:1 from shipped code)",
                          proc.returncode == 0 and "wszystkie testy 0009 przeszly" in (proc.stdout or ""),
                          (proc.stderr or proc.stdout)[-300:])
                    # dyn-budget (0010): reconstruction == patched tree bytes, then their 16 tests
                    rec = PKG / "src" / "arc3_level_budget_v13_2.py"
                    tree_mod = work / "ARC3-Inference" / "inference" / "framework" / "arc3_level_budget.py"
                    check("0010 reconstruction == patched tree bytes (cmp)",
                          rec.exists() and tree_mod.exists() and rec.read_bytes() == tree_mod.read_bytes())
                    proc = subprocess.run([sys.executable, str(PKG / "tests" / "test_arc3_dyn_budget.py")],
                                          capture_output=True, text=True)
                    check("16 dyn-budget tests pass (on shipped bytes)",
                          proc.returncode == 0, (proc.stderr or proc.stdout)[-300:])
                    # winpath tests against the PATCHED module
                    wtest = tmp / "test_winpath_tree.py"
                    shutil.copyfile(PKG / "tests" / "test_winpath.py", wtest)
                    env2 = dict(_os.environ)
                    env2["PYTHONPATH"] = (str(work / "ARC3-Inference" / "inference" / "framework")
                                          + _os.pathsep + env2.get("PYTHONPATH", "")).rstrip(_os.pathsep)
                    proc = subprocess.run([sys.executable, str(wtest), "-v"],
                                          capture_output=True, text=True, env=env2)
                    check("11 winpath tests pass on patched tree", proc.returncode == 0,
                          (proc.stderr or proc.stdout)[-300:])
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
