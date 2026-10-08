#!/usr/bin/env python3
"""Build and structurally verify the Kaggle submission.zip using stdlib only."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys
import zipfile

BASE_DIR = Path(__file__).resolve().parent
SUBMISSION_DIR = BASE_DIR / "submission"
DEFAULT_OUTPUT = BASE_DIR / "submission.zip"
MODEL_ID = "gemma-4-31b-it-qat-w4a16-ct"
ALLOWED_SUFFIXES = {".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"}
REQUIRED_ROOT_TOOLS = {
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
    "sub_agents/analyzer.yaml",
    "sub_agents/analyzer.md",
    "skills/targeted-tests/SKILL.md",
    "skills/targeted-tests/scripts/run_pytest.py",
    "skills/patch-validation/SKILL.md",
    "skills/patch-validation/scripts/validate_patch.py",
}


def fail(message: str) -> None:
    raise ValueError(message)


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        fail(f"Could not read UTF-8 file {path}: {exc}")


def validate_skill(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    text = read_utf8(skill_md)
    if not text.startswith("---\n"):
        fail(f"Missing YAML frontmatter in {skill_md.relative_to(SUBMISSION_DIR)}")
    frontmatter, separator, _ = text[4:].partition("\n---")
    if not separator:
        fail(f"Unclosed YAML frontmatter in {skill_md.relative_to(SUBMISSION_DIR)}")
    name_match = re.search(r"(?m)^name:\s*([a-z0-9-]+)\s*$", frontmatter)
    description_match = re.search(r"(?m)^description:\s*(\S.*)$", frontmatter)
    if name_match is None:
        fail(f"Missing or invalid skill name in {skill_md.relative_to(SUBMISSION_DIR)}")
    if name_match.group(1) != skill_dir.name:
        fail(
            f"Skill directory {skill_dir.name!r} must match frontmatter name "
            f"{name_match.group(1)!r}."
        )
    if description_match is None or len(description_match.group(1)) > 1024:
        fail(f"Missing/invalid skill description in {skill_md.relative_to(SUBMISSION_DIR)}")
    if len(name_match.group(1)) > 64:
        fail(f"Skill name exceeds 64 characters in {skill_md.relative_to(SUBMISSION_DIR)}")


def optional_yaml_syntax_check(yaml_files: list[Path]) -> bool:
    """Parse YAML if PyYAML is installed, accepting the competition's !include tag."""
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return False

    class IncludeLoader(yaml.SafeLoader):
        pass

    def include(loader: object, node: object) -> str:
        # Return the scalar path: the check is syntax-only, not ADK compilation.
        return "!include " + IncludeLoader.construct_scalar(loader, node)  # type: ignore[arg-type]

    IncludeLoader.add_constructor("!include", include)
    for path in yaml_files:
        try:
            yaml.load(read_utf8(path), Loader=IncludeLoader)
        except Exception as exc:  # PyYAML exposes several parse exception types.
            fail(f"Invalid YAML syntax in {path.relative_to(SUBMISSION_DIR)}: {exc}")
    return True


def validate_tree() -> list[Path]:
    if not SUBMISSION_DIR.is_dir():
        fail(f"Missing submission source directory: {SUBMISSION_DIR}")

    paths = sorted(SUBMISSION_DIR.rglob("*"))
    for path in paths:
        if path.is_symlink():
            fail(f"Symlinks are not allowed in a submission: {path.relative_to(SUBMISSION_DIR)}")
        if not path.is_file():
            continue
        relative = path.relative_to(SUBMISSION_DIR)
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            fail(f"Unsupported submission file extension: {relative}")
        if relative.is_absolute() or ".." in relative.parts:
            fail(f"Unsafe submission path: {relative}")

    actual_files = {path.relative_to(SUBMISSION_DIR).as_posix() for path in paths if path.is_file()}
    missing = sorted(REQUIRED_FILES - actual_files)
    if missing:
        fail("Missing required MVP files: " + ", ".join(missing))

    config_files = sorted(path for path in paths if path.is_file() and path.suffix in {".yaml", ".yml"})
    for config in config_files:
        text = read_utf8(config)
        for include_path in re.findall(r"!include\s+([^\s#]+)", text):
            candidate = (config.parent / include_path).resolve()
            try:
                candidate.relative_to(SUBMISSION_DIR.resolve())
            except ValueError:
                fail(f"!include escapes submission root in {config.relative_to(SUBMISSION_DIR)}")
            if not candidate.is_file():
                fail(
                    f"Missing !include target {include_path!r} in "
                    f"{config.relative_to(SUBMISSION_DIR)}"
                )

    eval_config = read_utf8(SUBMISSION_DIR / "eval_config.yaml")
    if re.search(r"(?m)^evaluation:\s*$", eval_config) is None:
        fail("eval_config.yaml must use the official top-level evaluation: mapping.")
    for key in ("timeout_seconds", "max_tool_calls", "max_time_minutes", "max_turns"):
        if re.search(r"(?m)^  " + re.escape(key) + r":\s*\d+(?:\.\d+)?\s*$", eval_config) is None:
            fail(f"eval_config.yaml is missing a numeric evaluation.{key} value.")

    root_config_path = SUBMISSION_DIR / "agent.yaml"
    root_config = read_utf8(root_config_path)
    if re.search(r"(?m)^model:\s*['\"]?" + re.escape(MODEL_ID) + r"['\"]?\s*$", root_config) is None:
        fail(f"Root agent must use the required model {MODEL_ID!r}.")
    for tool in sorted(REQUIRED_ROOT_TOOLS):
        if re.search(r"(?m)^\s*-\s*" + re.escape(tool) + r"\s*$", root_config) is None:
            fail(f"Root agent is missing required harness tool {tool!r}.")

    agent_tool_path = re.search(r"(?m)^\s*config_path:\s*([^\s#]+)\s*$", root_config)
    if agent_tool_path is None or agent_tool_path.group(1) != "sub_agents/analyzer.yaml":
        fail("Root AgentTool must reference sub_agents/analyzer.yaml.")
    if re.search(r"(?m)^\s*skip_summarization:\s*true\s*$", root_config) is None:
        fail("Root AgentTool must set skip_summarization: true.")

    analyzer_config = read_utf8(SUBMISSION_DIR / "sub_agents/analyzer.yaml")
    if re.search(r"(?m)^model:\s*['\"]?" + re.escape(MODEL_ID) + r"['\"]?\s*$", analyzer_config) is None:
        fail("Analyzer must use the same required base model as the root agent.")
    if re.search(r"(?m)^\s*-\s*(edit_file|write_file|submit_patch|run_command)\s*$", analyzer_config):
        fail("Analyzer is intended to be read-only; it must not have write/shell tools.")

    for skill_name in ("targeted-tests", "patch-validation"):
        validate_skill(SUBMISSION_DIR / "skills" / skill_name)

    yaml_ok = optional_yaml_syntax_check(config_files)
    if yaml_ok:
        print("YAML syntax: parsed successfully with PyYAML (custom !include tag accepted).")
    else:
        print("YAML syntax: PyYAML not installed; structural checks only.")
    return [path for path in paths if path.is_file()]


def build_zip(output: Path, files: list[Path]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, arcname=path.relative_to(SUBMISSION_DIR).as_posix())

    with zipfile.ZipFile(output, "r") as archive:
        names = archive.namelist()
        if "agent.yaml" not in names:
            fail("Built ZIP is missing agent.yaml at its root.")
        if any(name.startswith("submission/") for name in names):
            fail("Built ZIP incorrectly nests files beneath submission/.")
        if any(name.startswith("/") or ".." in Path(name).parts for name in names):
            fail("Built ZIP contains an unsafe archive path.")
        corrupted = archive.testzip()
        if corrupted is not None:
            fail(f"ZIP CRC verification failed for {corrupted}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output archive path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else (Path.cwd() / args.output).resolve()

    try:
        files = validate_tree()
        build_zip(output, files)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
