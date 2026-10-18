"""Fail before a GPU run if the generated Kaggle notebook can only crash.

Twice in a row a "knob" added to the launcher was written into `run.json` but never reached the
notebook: `concurrency` was missing from the encoded TASK_SELECTION (the cell silently read 1), and
`_excluded` was referenced by persist_results() while never being defined (NameError after the
first task, i.e. after the quota was already spent). Both are invisible to `ast.parse` on the
launcher, because the notebook is a string.

This check imports the launcher's build_notebook, extracts the generated cell bodies, and reports:

  * syntax errors in the generated code;
  * names read at module level and never bound anywhere and not builtins (the `_excluded` class);
  * TASK_SELECTION keys that the launcher accepts but does not forward.

Run: python3 gemma4-agent/tools/check_notebook_names.py
Exit code 0 = the notebook is at least name-clean; 1 = do not launch.
"""
from __future__ import annotations

import ast
import builtins
import importlib.util
import json
import sys
import symtable
from pathlib import Path

LAUNCHER = Path(__file__).with_name("run_kaggle_v1_smoke.py")

# Plumbed through build_notebook(...) and expected inside TASK_SELECTION.
REQUIRED_SELECTION_KEYS = ("task_count", "seed", "task_id", "concurrency")


def load_launcher():
    spec = importlib.util.spec_from_file_location("run_kaggle_v1_smoke", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def notebook_source(notebook: dict) -> str:
    return "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )


def undefined_names(source: str) -> list[str]:
    """Module-level names that are read but never bound anywhere and are not builtins."""
    tree = ast.parse(source)
    bound: set[str] = set()
    parameters: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            parameters.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
    table = symtable.symtable(source, "<notebook>", "exec")
    module_bound = {
        symbol.get_name()
        for symbol in table.get_symbols()
        if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()
    }

    missing: dict[str, None] = {}
    stack = [table]
    while stack:
        current = stack.pop()
        stack.extend(current.get_children())
        for symbol in current.get_symbols():
            if not symbol.is_referenced():
                continue
            if symbol.is_assigned() or symbol.is_imported() or symbol.is_parameter():
                continue
            name = symbol.get_name()
            if name in module_bound or name in bound or name in parameters:
                continue
            if hasattr(builtins, name) or name.startswith("__"):
                continue
            missing[name] = None
    return sorted(missing)


def forwarded_keys(notebook: dict) -> set[str]:
    source = notebook_source(notebook)
    marker = "TASK_SELECTION = json.loads("
    for line in source.splitlines():
        if marker in line:
            payload = line.split(marker, 1)[1].rstrip(")")
            try:
                return set(json.loads(json.loads(payload)))
            except Exception:  # the cell holds the JSON as a Python string literal
                pass
    return set()


def main() -> int:
    launcher = load_launcher()
    notebook = launcher.build_notebook(
        b"PK\x05\x06" + b"\x00" * 18,
        "0" * 64,
        task_count=3,
        seed=1,
        concurrency=3,
        excluded_repos=["psf/requests"],
        task_ids=["a", "b"],
    )
    source = notebook_source(notebook)
    problems: list[str] = []

    try:
        compile(source, "<notebook>", "exec")
    except SyntaxError as exc:
        problems.append(f"generated notebook does not compile: {exc}")

    for name in undefined_names(source):
        problems.append(f"name {name!r} is read but never defined in the notebook")

    keys = forwarded_keys(notebook)
    for key in REQUIRED_SELECTION_KEYS:
        if key not in keys:
            problems.append(
                f"TASK_SELECTION never receives {key!r}: the cell falls back to a default "
                "and the knob is dead"
            )
    if "excluded_repos" not in keys:
        problems.append("TASK_SELECTION never receives 'excluded_repos'")

    if problems:
        print("NOT NOTEBOOK-SAFE — do not launch:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"Notebook names OK ({len(source.splitlines())} lines, selection keys: {sorted(keys)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
