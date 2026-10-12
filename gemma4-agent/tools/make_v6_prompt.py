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
2. **Localize with the locator first (three calls that replace five to ten greps).** This step is the single highest-value move in the session; the ranking below was measured on 129 public tasks (73% of fixable files in the top 5) and on repositories outside that set (77%).
   - `write_file` the raw issue text to `/tmp/issue.txt` (verbatim, in full).
   - `write_file` the script from the "Locator script" section below to `/tmp/locate.py`, copied **exactly** as printed, character for character. Do not reimplement, shorten or "improve" it.
   - `run_command`: `cd /workspace && python3 /tmp/locate.py --root . --issue-file /tmp/issue.txt --top 8`
   - Read the ranked list: files marked `[test]` cannot be edited, they are context. Prefer source files, and when the top candidates look wrong trust the evidence lines and the imports those `[test]` files pull in (the script interleaves those modules deliberately, because the module that must grow is usually the one the nearest test imports).
3. **Fallback search (only if the locator could not run).** One combined shell call:
   `cd /workspace && grep -rn --include='*.py' -E "Name1|Name2|'exact message'" . | head -30; echo ---; grep -rni "distinctive phrase" . | head -20; echo ---; ls; echo ---; git log --oneline -5`"""

READ_STEP = """4. **Read narrowly.** Read the definitions you will change, and when it exists the test file nearest to that module (it reveals the expected API shape and behaviours). Two to four `read_file` calls (or `sed -n 'A,Bp'` inside a shell call) are usually enough."""

EDIT_STEP = """5. **Edit minimally and correctly.**"""

VERIFY_STEP = """6. **Verify cheaply, once.** If a relevant test file exists, spend a single call on syntax plus the narrowest test target, always bounded:"""

SUBMIT_STEP = """7. **Submit.** Call `submit_patch()` as your final action, then write two short sentences: what you changed and what remains uncertain. The session ends there."""


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

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(prompt + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(prompt)} chars, script {len(script)} chars)")
    assert script in OUT.read_text(encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
