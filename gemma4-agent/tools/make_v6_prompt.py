#!/usr/bin/env python3
"""Assemble gemma4-agent/submission-v6/prompts/system.md from the V5 prompt plus the
measured locator script, so the embedded copy is byte-identical to tools/locate.py.

The packer (build_submission_v6.py) re-checks that the built prompt still contains the
script verbatim, which makes drift impossible.

    python3 gemma4-agent/tools/make_v6_prompt.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V5_PROMPT = ROOT / "gemma4-agent" / "submission-v5" / "prompts" / "system.md"
V6_DIR = ROOT / "gemma4-agent" / "submission-v6"
LOCATOR = V6_DIR / "tools" / "locate.py"
OUT = V6_DIR / "prompts" / "system.md"

LOCALIZE_STEP = """## Workflow
1. **Extract the exact specification from the issue.** Write down every identifier (class, function, method, attribute, module), file or directory name, exception type, exact message string, CLI flag, config key, and quoted code fragment. Hidden tests usually assert exactly these names, messages and edge cases, so reuse them verbatim. Many issues are only a merged-PR title plus a link: then the title's words name the feature, and its most likely symbol is a snake_case rendering of those words (e.g. "Validate SSE fields" -> `sse.py`, `_check_...`, `ServerSentEvent`).
2. **Localize with the locator first (three calls that replace five to ten greps).** This step is the single highest-value move in the session; the script below was verified on 128 published tasks (the fixable source file lands in the top 3 for 66% of them, in the top 5 for 73%) and on 188 tasks from repositories outside that set (65% and 72%), against ~15% for a plain first grep.
   - `write_file` the raw issue text to `/tmp/issue.txt` (verbatim, in full).
   - `write_file` the script from the "Locator script" section below to `/tmp/locate.py`, copied **exactly** as printed, character for character. Do not reimplement, shorten or "improve" it.
   - `run_command`: `cd /workspace && python3 /tmp/locate.py --root . --issue-file /tmp/issue.txt --top 8`
   - Read the ranked list and open the first two or three source candidates (that range covers about two thirds of cases, while the single top hit covers only about a half, so do not stop after one file when its evidence lines do not match the issue wording). Files marked `[test]` cannot be edited, they are context - but note the imports they pull in: the script interleaves those modules deliberately, because the module that must grow is usually the one the nearest test imports.
3. **Fallback search (only if the locator could not run).** One combined shell call:
   `cd /workspace && grep -rn --include='*.py' -E "Name1|Name2|'exact message'" . | head -30; echo ---; grep -rni "distinctive phrase" . | head -20; echo ---; ls; echo ---; git log --oneline -5`"""

READ_STEP = """4. **Read narrowly.** Read the definitions you will change, and when it exists the test file nearest to that module (it reveals the expected API shape and behaviours). Two to four `read_file` calls (or `sed -n 'A,Bp'` inside a shell call) are usually enough."""

EDIT_STEP = """5. **Edit minimally and correctly.**"""

VERIFY_STEP = """6. **Verify cheaply, once.** If a relevant test file exists, spend a single call on syntax plus the narrowest test target, always bounded:"""

SUBMIT_STEP = """7. **Submit.** Call `submit_patch()` as your final action, then write two short sentences: what you changed and what remains uncertain. The session ends there."""


POST_EDITS = [
    # Measured on the 30-task V5 screening (kaggle_results/v5-benchmark): 6/30 sessions
    # produced no edit at all and 5 of those died on the wall clock; every resolved patch
    # stayed under 1900 characters, while diffs over 2000 characters resolved 0/6 times.
    (
        "- Pace by call count: the locator (step 2) costs three calls and replaces five to ten greps; after ~12 calls you should already have a candidate edit; after ~20 calls stop searching; after ~30 calls submit immediately with whatever you have.",
        "- **Hard edit deadline.** The graded artifact is the diff in `/workspace`: the harness extracts it even when you never call `submit_patch()`, so the only guaranteed zero is a tree you never edited. By call 12 an edit must already exist on disk; by call 18 stop investigating and write the smallest plausible fix; by call 24 run at most one short check and submit. A session that dies on the clock with an empty tree scores zero no matter how good the analysis was.",
    ),
    (
        "   - Implement precisely what the issue describes: same names, same exception types, same message wording, all mentioned edge cases, sane types and return values, project code style. If the issue describes invalid input, reject it with the exception type named or implied.",
        "   - Make the first edit as soon as you have a plausible target and refine it with further `edit_file` calls; do not batch a large rewrite into one risky step.\n   - Keep the diff small. Measured on these tasks: every resolved session produced a diff under 1900 characters (most under 1500), while every diff over 2000 characters failed. Fix the reported behaviour and nothing else.\n   - Implement precisely what the issue describes: same names, same exception types, same message wording, all mentioned edge cases, sane types and return values, project code style. If the issue describes invalid input, reject it with the exception type named or implied.",
    ),
    (
        "   `cd /workspace && python -c \"import ast;ast.parse(open('pkg/mod.py').read())\" && timeout 90 python -m pytest tests/test_mod.py -q 2>&1 | tail -20`",
        "   `cd /workspace && python -c \"import ast;ast.parse(open('pkg/mod.py').read())\" && timeout 45 python -m pytest tests/test_mod.py -q 2>&1 | tail -20`",
    ),
    (
        "   Never run bare `pytest`, a whole directory or a long suite. Pre-existing failures unrelated to your change are not your problem - never try to repair tests.",
        "   Never run bare `pytest`, a whole directory or a long suite, and never retry a command that timed out: on measured runs a single runaway test command consumed half the session. Pre-existing failures unrelated to your change are not your problem - never try to repair tests. If you are past call 24, skip verification entirely and submit.",
    ),
    (
        "- If you cannot identify the defect with confidence, pick the most plausible location from your search results and implement the smallest change that matches the issue's wording, even untested. A partial or speculative fix costs nothing and can pass; an empty diff cannot.",
        "- If you cannot identify the defect with confidence, pick the most plausible location from your search results and implement the smallest change that matches the issue's wording, even untested. A partial or speculative fix costs nothing and can pass; an empty diff cannot.\n- If by call 16 the tree still has no edit, stop reading and investigating: open the top locator candidate, make the smallest sensible change, and submit.",
    ),
]


def apply_post_edits(prompt: str) -> str:
    for old, new in POST_EDITS:
        assert old in prompt, "missing anchor: " + old[:60]
        prompt = prompt.replace(old, new, 1)
    return prompt


def main() -> int:
    prompt = V5_PROMPT.read_text(encoding="utf-8")
    script = LOCATOR.read_text(encoding="utf-8").rstrip("\n")

    if "## Locator script" in prompt or script in prompt:
        print("V6 prompt already assembled? Use the V5 prompt as the base.", file=sys.stderr)
        return 1

    # Replace the V5 workflow header + step 2 with the locator-first workflow, and
    # renumber the remaining steps.
    marker = "## Workflow\n1. **Extract the exact specification from the issue.**"
    start = prompt.index(marker)
    end = prompt.index("3. **Read narrowly.**")
    tail = prompt[end:]
    for old, new in (
        ("3. **Read narrowly.**", READ_STEP),
        ("4. **Edit minimally and correctly.**", EDIT_STEP),
        ("5. **Verify cheaply, once.**", VERIFY_STEP),
        ("6. **Submit.**", SUBMIT_STEP),
    ):
        tail = tail.replace(old, new, 1)

    script_block = (
        "\n\n## Locator script (write this to `/tmp/locate.py` exactly as printed)\n\n"
        "```python\n" + script + "\n```\n"
    )
    prompt = prompt[:start] + LOCALIZE_STEP + "\n\n" + tail.rstrip("\n") + script_block

    # Budget note: three calls here replace five to ten greps.
    prompt = prompt.replace(
        "- Pace by call count: after ~12 calls you should already have a candidate edit; after ~20 calls stop searching; after ~30 calls submit immediately with whatever you have.",
        "- Pace by call count: the locator (step 2) costs three calls and replaces five to ten greps; after ~12 calls you should already have a candidate edit; after ~20 calls stop searching; after ~30 calls submit immediately with whatever you have.",
    )

    prompt = apply_post_edits(prompt)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(prompt + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(prompt)} chars, script {len(script)} chars)")
    assert script in OUT.read_text(encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
