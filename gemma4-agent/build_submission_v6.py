#!/usr/bin/env python3
"""Build and structurally verify the V6 Kaggle submission.zip (stdlib only).

V6 = V5 + a measured locator-first localization step. The locator script lives in
tools/locate.py and is embedded verbatim in prompts/system.md so the agent can write it
to /tmp inside the sandbox; this packer fails if the embedded copy drifts from the file,
if the prompt grows past a sane size, or if the script contains triple quotes (which the
vLLM gemma4 tool parser can mangle inside tool-call arguments).

V6 is still a deliberately minimal submission: one LlmAgent, no skills, no sub-agents.
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
DEFAULT_SUBMISSION_DIR = BASE_DIR / "submission-v6"
DEFAULT_OUTPUT = BASE_DIR / "submission-v6.zip"
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
    "tools/locate.py",
}
MAX_PROMPT_CHARS = 24_000
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


def validate_tree(submission_dir: Path) -> list[Path]:
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
        fail("Missing required V6 files: " + ", ".join(missing))
    unexpected = sorted(files - REQUIRED_FILES)
    if unexpected:
        fail(
            "V6 must stay minimal (single agent, no skills/sub-agents); unexpected files: "
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
    for required_tool in ("run_command", "read_file", "edit_file", "write_file"):
        if required_tool not in declared_tools:
            fail(f"Root agent is missing required tool {required_tool!r}.")
    # V6.4: the submit tool must NOT be declared. Verified read-only on the V6.3 run: 17/30 tasks
    # never called it, 8 of those still had a graded diff and two PASSED without it (fastapi_14873,
    # fastapi_14458), while the sessions that did have it looped 42-48 times and died on the
    # 60-turn cap. Removing it deletes the whole failure mode instead of asking the model to avoid it.
    if "submit_patch" in declared_tools:
        fail("V6.4 removed the submit_patch tool deliberately; do not declare it in agent.yaml.")
    if "sub_agents" in root_text or "agent_tool" in root_text:
        fail("V6 is intentionally single-agent; remove sub_agents/agent_tool from agent.yaml.")
    if "skills:" in root_text:
        fail("V6 deliberately ships no skills; remove the skills: key.")

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
    if budget["max_time_minutes"] > MAX_SAFE_TIME_MINUTES:
        fail(
            f"max_time_minutes={budget['max_time_minutes']} exceeds the safe envelope "
            f"({MAX_SAFE_TIME_MINUTES}); ~120 tasks would not fit the 12-hour cap."
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

    # Locator contract: the prompt must ship the verified script verbatim.
    locator_text = read_utf8(submission_dir / "tools" / "locate.py")
    prompt_text = read_utf8(submission_dir / "prompts" / "system.md")
    if '"""' in locator_text:
        fail("tools/locate.py must not contain triple quotes (gemma4 tool-call parser bug).")
    if locator_text.rstrip("\n") not in prompt_text:
        fail("prompts/system.md must embed tools/locate.py verbatim; regenerate with "
             "tools/make_v6_prompt.py.")
    if prompt_text.count("## Locator script") != 1:
        fail("prompts/system.md must describe the locator exactly once.")
    for required in ("cat > /tmp/locate.py <<'LOCATE_PY'", "ISSUE_EOF",
                     "python3 /tmp/locate.py --root . --top 8",
                     "git status --porcelain",
                     "Never use `write_file` or shell redirection for scratch material",
                     # V6.4 removed the tool entirely, so the required sentence is now the
                     # "no submit tool" statement, not the old optional-submit wording.
                     "**There is no submit tool.**",
                     "**Documentation is not a fix.**",
                     "never end a session without a real edit on disk"):
        if required not in prompt_text:
            fail(f"prompts/system.md lost a V6.2 plumbing/hygiene instruction: {required!r}")
    if "`issue.txt`" not in prompt_text:
        fail("prompts/system.md must warn about bare scratch filenames landing in /workspace.")
    if len(prompt_text) > MAX_PROMPT_CHARS:
        fail(f"prompts/system.md is {len(prompt_text)} chars (> {MAX_PROMPT_CHARS}); "
             "keep the prompt lean so no step gets skipped.")
    # V6.3 prompt-quality guards (three real defects shipped once: a stale call budget, a
    # duplicated sentence and two bullets glued together by a Python line continuation).
    prose = prompt_text.split("## Locator script", 1)[0]
    if "45 tool calls" in prose:
        fail("prompts/system.md quotes the stale 45-call budget; the harness cap is 30.")
    if prose.count("narrowest test target, always bounded:") != 1:
        fail("prompts/system.md has a duplicated verification sentence.")
    if "\\n" in prose:
        fail("prompts/system.md contains a literal backslash-n outside the script block; "
             "a source line continuation probably glued two bullets together.")
    for marker in ("- Keep the diff small", "- If by tool call 4"):
        if not any(line.strip().startswith(marker) for line in prose.splitlines()):
            fail(f"prompts/system.md lost the line break before {marker!r} (bullets are glued).")
    # V6.4 mechanism guards: each rule is pinned to one measurement from the read-only diagnosis of
    # the V6.3 kernels (ANALYSIS_V6_3_MECHANISMS.md). If a rule silently disappears or its measured
    # number drifts, the build fails instead of shipping a prompt that only claims to be V6.4.
    v64_rules = {
        "No reading without writing, and no dummy edits": "M1 - sessions that never attempt an edit",
        "If an `edit_file` call does not change the file, do not repeat it.": "M2 - edit loop",
        "There is no submit tool": "M3 - the submit tool was removed after 42-48 call loops",
        "Scratch files are never your answer":
            "M4 - scratch files may not replace the edit (narrowed after rich_3006 passed using /tmp/repro.py)",
    }
    for phrase, label in v64_rules.items():
        if prose.count(phrase) != 1:
            fail(f"prompts/system.md must contain the V6.4 rule once ({label}): {phrase!r}")
    for number, label in {
        "31 calls": "M1 measurement",
        "nine consecutive": "M2 measurement",
        "48 times": "M3 measurement",
        "280 s": "M4 measurement (a scratch file replacing the edit)",
        "/tmp/repro.py": "M4 counter-example (a scratch file after the edit, in a passed task)",
    }.items():
        if number not in prose:
            fail(f"prompts/system.md lost the V6.4 measurement ({label}): {number!r}")
    if "must exist on disk by call 4" not in prose:
        fail("prompts/system.md lost the V6.4 write deadline (call 4).")
    if "never create a dummy edit" not in prose:
        fail("prompts/system.md lost the ban on placeholder edits, which is what makes the "
             "deadline a requirement of an intended change.")
    if "submit_patch()" in prompt_text:
        fail("prompts/system.md instructs calling submit_patch(), a tool V6.4 removed.")
    if "no submit tool" not in prompt_text.lower():
        fail("prompts/system.md must state that there is no submit tool.")
    if "48 times" not in prose:
        fail("prompts/system.md lost the M3 measurement behind removing the submit tool.")
    if "as your final action" in prompt_text:
        fail("prompts/system.md still carries the V5 tail that contradicts the optional-submit rule.")

    parsed = optional_yaml_parse(submission_dir / "agent.yaml")
    if parsed is not None and not isinstance(parsed, dict):
        fail("agent.yaml did not parse into a mapping.")
    if optional_yaml_parse(submission_dir / "eval_config.yaml") is not None:
        print("YAML syntax: parsed successfully with PyYAML (custom !include tags accepted).")
    else:
        print("YAML syntax: PyYAML not installed; structural checks only.")
    return [path for path in paths if path.is_file()]


# A fixed entry timestamp makes the archive reproducible: the same tree always yields the same
# sha256. Found the hard way on 2026-10-13 - a no-op rebuild produced 4ed7221e while the tested
# archive was 650e1dba, with byte-identical contents and only prompts/system.md's mtime differing,
# which would have made the submitter's integrity pin meaningless.
ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def build_zip(output: Path, files: list[Path], submission_dir: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(submission_dir).as_posix(), ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())

    with zipfile.ZipFile(output, "r") as archive:
        names = archive.namelist()
        if "agent.yaml" not in names:
            fail("Built ZIP is missing agent.yaml at its root.")
        if any(name.startswith(("submission/", "submission-v5/", "submission-v6/")) for name in names):
            fail("Built ZIP incorrectly nests files beneath a wrapper directory.")
        if any(name.startswith("/") or ".." in Path(name).parts for name in names):
            fail("Built ZIP contains an unsafe archive path.")
        if archive.testzip() is not None:
            fail("ZIP CRC verification failed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SUBMISSION_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    submission_dir = (
        args.source_dir if args.source_dir.is_absolute() else (Path.cwd() / args.source_dir).resolve()
    )
    output = args.output if args.output.is_absolute() else (Path.cwd() / args.output).resolve()

    try:
        files = validate_tree(submission_dir)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
