#!/usr/bin/env python3
"""Build and validate the offline Gemma V6.4 candidate archive.

No benchmark, Kaggle API call, or official submission is performed by this script.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBMISSION = HERE / "submission-v6.4"
DEFAULT_OUTPUT = HERE / "submission-v6.4.zip"
EXPECTED_FILES = (
    "agent.yaml",
    "configs/sampling.yaml",
    "eval_config.yaml",
    "prompts/system.md",
    "tools/locate.py",
)
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def fail(message: str) -> "NoReturn":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml_if_available(path: Path):
    """Parse YAML when PyYAML is installed; `!include` resolves to its scalar path."""
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return None

    class IncludeLoader(yaml.SafeLoader):
        pass

    IncludeLoader.add_constructor(
        "!include", lambda loader, node: loader.construct_scalar(node)
    )
    try:
        return yaml.load(path.read_text(encoding="utf-8"), Loader=IncludeLoader)
    except Exception as exc:  # PyYAML exposes several parser/constructor exception types.
        fail(f"invalid YAML in {path.relative_to(HERE)}: {exc}")


def validate_inputs() -> dict[str, bytes]:
    if not SUBMISSION.is_dir():
        fail(f"candidate directory is missing: {SUBMISSION}")

    for path in SUBMISSION.rglob("*"):
        if path.is_symlink():
            fail(f"symlinks are not allowed in the submission: {path.relative_to(SUBMISSION)}")

    actual = tuple(
        sorted(path.relative_to(SUBMISSION).as_posix() for path in SUBMISSION.rglob("*") if path.is_file())
    )
    if actual != EXPECTED_FILES:
        fail(
            "candidate file set differs from the expected five submission files; "
            f"expected {EXPECTED_FILES}, found {actual}"
        )

    files = {
        rel: (SUBMISSION / rel).read_bytes()
        for rel in EXPECTED_FILES
    }
    text = {rel: data.decode("utf-8") for rel, data in files.items()}

    agent = text["agent.yaml"]
    if "model: gemma-4-31b-it-qat-w4a16-ct" not in agent:
        fail("agent.yaml model differs from the V6.3 baseline")
    if "instruction: !include prompts/system.md" not in agent:
        fail("agent.yaml must include prompts/system.md")
    tool_block = re.search(
        r"(?ms)^tools:\s*\n(.*?)(?=^generate_content_config:)", agent
    )
    if not tool_block:
        fail("could not locate the tools list in agent.yaml")
    tools = re.findall(r"^\s*-\s*([A-Za-z_][A-Za-z0-9_]*)\s*$", tool_block.group(1), re.MULTILINE)
    if "submit_patch" in tools:
        fail("submit_patch must not be registered in the V6.4 candidate")
    required_tools = {
        "run_command",
        "read_file",
        "edit_file",
        "write_file",
        "get_status",
        "get_code_neighbors",
        "search_similar_code",
        "get_code_subgraph",
    }
    if set(tools) != required_tools:
        fail(f"unexpected V6.4 tool list: {tools}")

    prompt = text["prompts/system.md"]
    if "intended source or configuration edit must exist by tool call 4" not in prompt:
        fail("the V6.4 first-edit deadline is missing from prompts/system.md")
    if "The one explicit `/tmp/locate.py` heredoc above is permitted" not in prompt:
        fail("the scratch-file rule does not resolve the locator heredoc exception")
    if "V6.4 does not expose `submit_patch()`" not in prompt:
        fail("the prompt does not explain the removed submit_patch tool")

    locator = files["tools/locate.py"].decode("utf-8")
    try:
        ast.parse(locator, filename="tools/locate.py")
    except SyntaxError as exc:
        fail(f"tools/locate.py has invalid Python syntax: {exc}")
    if locator.rstrip() not in prompt:
        fail("the locator in the prompt differs from tools/locate.py")

    eval_config = text["eval_config.yaml"]
    for expected in (
        "timeout_seconds: 150",
        "max_tool_calls: 30",
        "max_turns: 60",
        "max_time_minutes: 5.25",
    ):
        if expected not in eval_config:
            fail(f"evaluation settings changed unexpectedly: missing {expected!r}")
    sampling = text["configs/sampling.yaml"]
    for expected in (
        "temperature: 0.4",
        "top_p: 0.95",
        "top_k: 40",
        "max_output_tokens: 16384",
        "thinking_budget: 4096",
        "include_thoughts: true",
    ):
        if expected not in sampling:
            fail(f"sampling settings changed unexpectedly: missing {expected!r}")

    parsed_agent = load_yaml_if_available(SUBMISSION / "agent.yaml")
    parsed_eval = load_yaml_if_available(SUBMISSION / "eval_config.yaml")
    parsed_sampling = load_yaml_if_available(SUBMISSION / "configs/sampling.yaml")
    if parsed_agent is not None:
        if parsed_agent.get("tools") != tools:
            fail("parsed agent.yaml tools do not match the validated tool list")
        if parsed_eval.get("evaluation", {}).get("max_tool_calls") != 30:
            fail("parsed eval_config.yaml has an unexpected max_tool_calls value")
        if parsed_sampling.get("thinking_config", {}).get("thinking_budget") != 4096:
            fail("parsed sampling.yaml has an unexpected thinking budget")

    return files


def build_archive(files: dict[str, bytes], output: Path) -> str:
    output = output.resolve()
    try:
        output.relative_to(SUBMISSION.resolve())
    except ValueError:
        pass
    else:
        fail("archive output cannot be placed inside the candidate directory")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel in EXPECTED_FILES:
            info = zipfile.ZipInfo(rel, date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.flag_bits |= 0x800
            archive.writestr(info, files[rel], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    with zipfile.ZipFile(output, "r") as archive:
        names = tuple(archive.namelist())
        if names != EXPECTED_FILES:
            fail(f"archive entries differ from the expected files: {names}")
        for rel in EXPECTED_FILES:
            if archive.read(rel) != files[rel]:
                fail(f"archive content mismatch for {rel}")
        bad_member = archive.testzip()
        if bad_member is not None:
            fail(f"ZIP CRC check failed for {bad_member}")

    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"archive path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    files = validate_inputs()
    digest = build_archive(files, args.output)
    print(f"Validated {len(files)} files: {', '.join(EXPECTED_FILES)}")
    print(f"Archive: {args.output.resolve()}")
    print(f"SHA-256: {digest}")
    print("Scope: offline build only; no benchmark or submission was run.")


if __name__ == "__main__":
    main()
