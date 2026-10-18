"""Stage a screen config for the live carrier, with the checks that keep a bad launch off the GPU.

The carrier (`.github/workflows/gemma-kaggle-v64-benchmark.yml`) reads exactly one file,
`gemma4-agent/kaggle_smoke/screen-v8.json`, when `screen-v8.trigger` is pushed. This tool is the
only sanctioned way to change that file: it validates the config, refuses while another screen is
armed, refuses to reuse an output directory that already holds a result, and prints the two git
commands that arm the run (it never touches the trigger itself - arming is a human decision).

Usage:
    python3 gemma4-agent/tools/stage_screen.py gemma4-agent/kaggle_smoke/screen-holdout-fastapi.json
    python3 gemma4-agent/tools/stage_screen.py --show
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SMOKE_DIR = Path("gemma4-agent/kaggle_smoke")
LIVE_CONFIG = SMOKE_DIR / "screen-v8.json"
TRIGGER = SMOKE_DIR / "screen-v8.trigger"
MAX_CONCURRENCY = 4  # full 30-task screens ran fine at 3; 4 is the most that has ever been tried
KNOWN_KEYS = {
    "label",
    "why",
    "submission",
    "outdir",
    "task_ids",
    "task_count",
    "concurrency",
    "exclude_repos",
    "seed",
    "max_wait_minutes",
    "start_now",
    "staged_from",
}


def fail(message: str) -> int:
    print(f"REFUSED: {message}")
    return 1


def validate(config: dict) -> list[str]:
    problems: list[str] = []
    unknown = sorted(set(config) - KNOWN_KEYS)
    if unknown:
        problems.append(f"unknown keys {unknown} - the carrier would silently ignore them")
    missing = [key for key in ("submission", "outdir", "concurrency", "seed") if key not in config]
    if missing:
        problems.append(f"missing required keys {missing}")
        return problems

    submission = Path(str(config["submission"]))
    if not submission.is_file():
        problems.append(f"submission archive does not exist: {submission}")
    elif submission.suffix != ".zip":
        problems.append(f"submission is not a zip: {submission}")

    outdir = Path(str(config["outdir"]))
    if not str(outdir).startswith("gemma4-agent/kaggle_results/"):
        problems.append(f"outdir must live under gemma4-agent/kaggle_results/, got {outdir}")
    if (outdir / "agent_benchmark_result.json").is_file():
        problems.append(f"{outdir} already holds a result - pick a new outdir, do not overwrite it")

    concurrency = int(config.get("concurrency", 1))
    if not 1 <= concurrency <= MAX_CONCURRENCY:
        problems.append(f"concurrency {concurrency} outside 1..{MAX_CONCURRENCY}")

    ids = config.get("task_ids") or []
    excluded = config.get("exclude_repos") or []
    if ids and excluded:
        problems.append("give task_ids or exclude_repos, not both - the holdout is meaningless on a fixed list")
    if not ids and int(config.get("task_count", 0)) < 1:
        problems.append("either task_ids or task_count must be set")
    if len(ids) != len(set(ids)):
        problems.append("task_ids contains duplicates")

    wait = int(config.get("max_wait_minutes", 120))
    if wait < 15:
        problems.append(f"max_wait_minutes {wait} is too short for a 30-task screen")
    return problems


def show() -> int:
    if not LIVE_CONFIG.is_file():
        print(f"{LIVE_CONFIG} does not exist")
        return 1
    config = json.loads(LIVE_CONFIG.read_text())
    print(json.dumps(config, indent=2))
    print("\nArmed:", TRIGGER.is_file())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", help="screen config to stage as screen-v8.json")
    parser.add_argument("--show", action="store_true", help="print the currently staged config")
    args = parser.parse_args()
    if args.show or not args.config:
        return show()

    if TRIGGER.is_file():
        return fail(
            f"{TRIGGER} exists - a screen is already armed. Let it run (the workflow deletes the "
            "trigger when it starts), then stage the next one."
        )

    source = Path(args.config)
    if not source.is_file():
        return fail(f"no such config: {source}")
    if source.resolve() == LIVE_CONFIG.resolve():
        return fail("that is already the live config")
    config = json.loads(source.read_text())
    problems = validate(config)
    if problems:
        for problem in problems:
            print(f"  - {problem}")
        return fail(f"{len(problems)} problem(s) in {source}")

    config["staged_from"] = source.name
    LIVE_CONFIG.write_text(json.dumps(config, indent=2) + "\n")

    label = config.get("label", "(no label)")
    ids = config.get("task_ids") or []
    excluded = config.get("exclude_repos") or []
    print(f"Staged: {label}")
    print(f"  archive   {config['submission']}")
    print(f"  outdir    {config['outdir']}")
    task_summary = "named: " + ", ".join(ids) if ids else f"stratified, up to {config.get('task_count', 30)}"
    print(f"  tasks     {task_summary}")
    print(f"  holdout   {', '.join(excluded) if excluded else 'none'}")
    print(f"  clock     concurrency {config['concurrency']}, seed {config['seed']}, wait cap {config.get('max_wait_minutes', 120)} min")
    print()
    print("To arm (human decision, ~40-60 min of GPU):")
    print(f"  git add {LIVE_CONFIG} && git commit -m 'chore(gemma): stage {label}' && git push origin HEAD")
    print(f"  printf 'screen\\n' > {TRIGGER} && git add {TRIGGER} && git commit -m 'chore(gemma): arm' && git push origin HEAD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
