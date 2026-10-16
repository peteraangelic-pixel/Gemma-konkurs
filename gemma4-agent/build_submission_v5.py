#!/usr/bin/env python3
"""Build and structurally verify the V5 Kaggle submission.zip (stdlib only).

V5 is a deliberately minimal submission: one LlmAgent, no skills, no sub-agents.
This packer therefore validates a closed file set instead of the V1-V4 layout, and
adds guards for the settings that the 0.03 -> V5 diagnosis identified as decisive:

* the single allowed base model on every agent config,
* only harness-provided tools,
* an `evaluation:` budget that cannot silently exceed the 12-hour competition cap,
* thinking enabled *with* thought summaries (`include_thoughts: true`), which a peer
  ablation on the same 129 public tasks showed to be worth ~12 points of resolution rate.

Usage:
    python gemma4-agent/build_submission_v5.py
    python gemma4-agent/build_submission_v5.py --source-dir ... --output ...
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys
import zipfile

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SUBMISSION_DIR = BASE_DIR / "submission-v5"
DEFAULT_OUTPUT = BASE_DIR / "submission-v5.zip"
MODEL_ID = "gemma-4-31b-it-qat-w4a16-ct"
ALLOWED_SUFFIXES = {".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"}
ALLOWED_TOOLS = {
    "run_command",
    "submit_patch",
    "get_status",
    "read_file",
    "edit_file",
    "write_file",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
}
REQUIRED_FILES = {
    "agent.yaml",
    "eval_config.yaml",
    "configs/sampling.yaml",
    "prompts/system.md",
}
# The scored split is ~120 private-repository tasks; 12 h / 120 tasks = 6 min including
# container setup, so a per-task agent cap above 5.5 minutes cannot fit the whole split.
MAX_SAFE_TIME_MINUTES = 5.5
MIN_SAFE_TOOL_CALLS = 30


def fail(message: str) -> None:
    raise ValueError(message)


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        fail(f"Could not read UTF-8 file {path}: {exc}")


def optional_yaml_parse(path: Path):
    """Return the parsed document when PyYAML is available, else None."""
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return None

    class IncludeLoader(yaml.SafeLoader):
        pass

    IncludeLoader.add_constructor(
        "!include", lambda loader, node: loader.construct_scalar(node)  # type: ignore[arg-type]
    )
    return yaml.load(read_utf8(path), Loader=IncludeLoader)


def validate_tree(submission_dir: Path, clock_arm_minutes: float | None = None) -> list[Path]:
    submission_dir = submission_dir.resolve()
    if not submission_dir.is_dir():
        fail(f"Missing submission source directory: {submission_dir}")

    paths = sorted(submission_dir.rglob("*"))
    for path in paths:
        if path.is_symlink():
            fail(f"Symlinks are not allowed in a submission: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(submission_dir)
        if relative.is_absolute() or ".." in relative.parts:
            fail(f"Unsafe submission path: {relative}")
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            fail(f"Unsupported submission file extension: {relative}")

    files = {path.relative_to(submission_dir).as_posix() for path in paths if path.is_file()}
    missing = sorted(REQUIRED_FILES - files)
    if missing:
        fail("Missing required V5 files: " + ", ".join(missing))
    unexpected = sorted(files - REQUIRED_FILES)
    if unexpected:
        fail(
            "V5 must stay minimal (single agent, no skills/sub-agents); unexpected files: "
            + ", ".join(unexpected)
        )

    # !include targets must exist and stay inside the submission root.
    for config in sorted(path for path in paths if path.is_file() and path.suffix in {".yaml", ".yml"}):
        text = read_utf8(config)
        for include_path in re.findall(r"!include\s+([^\s#]+)", text):
            candidate = (config.parent / include_path).resolve()
            try:
                candidate.relative_to(submission_dir)
            except ValueError:
                fail(f"!include escapes submission root in {config.name}: {include_path}")
            if not candidate.is_file():
                fail(f"Missing !include target {include_path!r} referenced by {config.name}")

    # Root agent contract.
    root_text = read_utf8(submission_dir / "agent.yaml")
    if re.search(r"(?m)^model:\s*['\"]?" + re.escape(MODEL_ID) + r"['\"]?\s*$", root_text) is None:
        fail(f"Root agent must use the required model {MODEL_ID!r}.")
    declared_tools = set(re.findall(r"(?m)^\s*-\s*([a-z_]+)\s*$", root_text))
    if not declared_tools:
        fail("Root agent declares no tools.")
    unknown = sorted(declared_tools - ALLOWED_TOOLS)
    if unknown:
        fail("Root agent declares tools outside the harness registry: " + ", ".join(unknown))
    for required_tool in ("run_command", "read_file", "edit_file", "write_file", "submit_patch"):
        if required_tool not in declared_tools:
            fail(f"Root agent is missing required tool {required_tool!r}.")
    if "sub_agents" in root_text or "agent_tool" in root_text:
        fail("V5 is intentionally single-agent; remove sub_agents/agent_tool from agent.yaml.")
    if "skills:" in root_text:
        fail("V5 deliberately ships no skills; remove the skills: key.")

    # Budget contract: must fit the 12-hour competition envelope.
    eval_text = read_utf8(submission_dir / "eval_config.yaml")
    if re.search(r"(?m)^evaluation:\s*$", eval_text) is None:
        fail("eval_config.yaml must use the official top-level evaluation: mapping.")
    budget: dict[str, float] = {}
    for key in ("timeout_seconds", "max_tool_calls", "max_time_minutes", "max_turns"):
        match = re.search(r"(?m)^  " + re.escape(key) + r":\s*(\d+(?:\.\d+)?)\s*$", eval_text)
        if match is None:
            fail(f"eval_config.yaml is missing a numeric evaluation.{key} value.")
        budget[key] = float(match.group(1))
    if clock_arm_minutes is None:
        if budget["max_time_minutes"] > MAX_SAFE_TIME_MINUTES:
            fail(
                f"max_time_minutes={budget['max_time_minutes']} exceeds the safe envelope "
                f"({MAX_SAFE_TIME_MINUTES}); ~120 tasks would not fit the 12-hour cap."
            )
    else:
        # Measurement-only escape hatch, deliberately narrow: exactly one directory name, exactly
        # one clock value, and a banner that says out loud what the archive is for. The whole point
        # of the V7-c screen is to learn the MEAN task duration at a raised clock, because the mean
        # (not the cap) decides whether ~120-150 tasks fit the competition's 12-hour run limit
        # (host 743063: a breach errors the entire submission, not just the last task).
        if submission_dir.name != "submission-v7c":
            fail(
                "a raised clock is only allowed for the V7-c measurement tree "
                f"(got {submission_dir.name!r})"
            )
        if budget["max_time_minutes"] != clock_arm_minutes:
            fail(
                f"V7-c must carry the requested clock exactly: got "
                f"{budget['max_time_minutes']}, expected {clock_arm_minutes}"
            )
    if budget["max_tool_calls"] < MIN_SAFE_TOOL_CALLS:
        fail(
            f"max_tool_calls={budget['max_tool_calls']:.0f} is below the measured useful "
            f"range (>= {MIN_SAFE_TOOL_CALLS}); a peer ablation lost 14/129 tasks at 25 calls."
        )

    # Sampling contract: thinking summaries on is the single largest measured factor.
    sampling_text = read_utf8(submission_dir / "configs/sampling.yaml")
    if re.search(r"(?m)^\s*include_thoughts:\s*true\s*$", sampling_text) is None:
        fail("configs/sampling.yaml must set thinking_config.include_thoughts: true.")
    thinking = re.search(r"(?m)^\s*thinking_budget:\s*(\d+)\s*$", sampling_text)
    if thinking is None or int(thinking.group(1)) < 2048:
        fail("configs/sampling.yaml needs thinking_config.thinking_budget >= 2048.")

    parsed = optional_yaml_parse(submission_dir / "agent.yaml")
    if parsed is not None and not isinstance(parsed, dict):
        fail("agent.yaml did not parse into a mapping.")
    if optional_yaml_parse(submission_dir / "eval_config.yaml") is not None:
        print("YAML syntax: parsed successfully with PyYAML (custom !include tags accepted).")
    else:
        print("YAML syntax: PyYAML not installed; structural checks only.")
    return [path for path in paths if path.is_file()]


def build_zip(output: Path, files: list[Path], submission_dir: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, arcname=path.relative_to(submission_dir).as_posix())

    with zipfile.ZipFile(output, "r") as archive:
        names = archive.namelist()
        if "agent.yaml" not in names:
            fail("Built ZIP is missing agent.yaml at its root.")
        if any(name.startswith("submission/") or name.startswith("submission-v5/") for name in names):
            fail("Built ZIP incorrectly nests files beneath a wrapper directory.")
        if any(name.startswith("/") or ".." in Path(name).parts for name in names):
            fail("Built ZIP contains an unsafe archive path.")
        if archive.testzip() is not None:
            fail("ZIP CRC verification failed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SUBMISSION_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--clock-arm-minutes",
        type=float,
        default=None,
        help="measurement-only: allow exactly this raised per-task clock, and only in submission-v7c (never for a submission)",
    )
    args = parser.parse_args()
    submission_dir = (
        args.source_dir if args.source_dir.is_absolute() else (Path.cwd() / args.source_dir).resolve()
    )
    output = args.output if args.output.is_absolute() else (Path.cwd() / args.output).resolve()

    try:
        files = validate_tree(submission_dir, args.clock_arm_minutes)
        build_zip(output, files, submission_dir)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with zipfile.ZipFile(output, "r") as archive:
        print(f"Built: {output}")
        print(f"Files: {len(archive.namelist())}")
        print(f"Size: {output.stat().st_size:,} bytes")
        print(f"SHA-256: {digest}")
        print("Archive root includes: " + ", ".join(archive.namelist()[:6]))
        if args.clock_arm_minutes is not None:
            print(
                f"MEASUREMENT ARM ONLY - clock {args.clock_arm_minutes} min: this archive exists "
                "to measure the mean task duration on the 30-task screen. Do not submit it to "
                "Kaggle as an official entry."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
