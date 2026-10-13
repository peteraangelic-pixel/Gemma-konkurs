#!/usr/bin/env python3
"""Assemble gemma4-agent/submission-v6/prompts/system.md from the V5 prompt plus the
measured locator script, so the embedded copy is byte-identical to tools/locate.py.

V6.2 design notes (all measured, see kaggle_results/v6-benchmark/analysis.md):
* The V6.1 run regressed to 6/30 because the prompt asked the agent to `write_file`
  /tmp/issue.txt and /tmp/locate.py; the agent wrote bare filenames, they landed in
  /workspace, and the graded diff became 7.7 KB of script plus issue text. 9/30 tasks were
  affected, 7 of them had no code edit at all, and clock deaths rose from 9/30 to 17/30.
* V6.2 therefore never uses write_file: the script and the issue are delivered through a
  single `run_command` with two heredocs that only ever write to /tmp, and a final hygiene
  check deletes anything unexpected from /workspace before submit_patch().
* tool_call cap drops 45 -> 30 so the harness's free budget_warning arrives at call 20
  instead of 35 (measured sessions die on the 315 s clock, not on the call budget).

    python3 gemma4-agent/tools/make_v6_prompt.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V5_PROMPT = ROOT / "gemma4-agent" / "submission-v5" / "prompts" / "system.md"
V6_DIR = ROOT / "gemma4-agent" / "submission-v6"
LOCATOR = V6_DIR / "tools" / "locate.py"
OUT = V6_DIR / "prompts" / "system.md"

LOCALIZE_STEP = """## Workflow
1. **Extract the exact specification from the issue.** Write down every identifier (class, function, method, attribute, module), file or directory name, exception type, exact message string, CLI flag, config key, and quoted code fragment. Hidden tests usually assert exactly these names, messages and edge cases, so reuse them verbatim. Many issues are only a merged-PR title plus a link: then the title's words name the feature, and its most likely symbol is a snake_case rendering of those words (e.g. "Validate SSE fields" -> `sse.py`, `_check_...`, `ServerSentEvent`).
2. **Localize with the locator: ONE `run_command`, then start editing.** This is the highest-value move in the session. The script below was verified on 128 published tasks (the fixable source file lands in the top 3 for 66% of them, in the top 5 for 73%) and on 188 tasks from repositories outside that set (65% and 72%), against ~15% for a plain first grep. Build the single command exactly like this:

```
cd /workspace && cat > /tmp/locate.py <<'LOCATE_PY'
[the whole locator script from the section at the end of this prompt, copied character for character]
LOCATE_PY
python3 /tmp/locate.py --root . --top 8 <<'ISSUE_EOF'
[the issue text, verbatim and complete]
ISSUE_EOF
```

   - **Never use `write_file` or shell redirection for scratch material, and never let a bare filename like `locate.py`, `issue.txt` or `repro.py` be created in `/workspace`.** Measured on the previous run: bare filenames are resolved inside `/workspace`, so the graded diff became the 7.7 KB script plus the issue text instead of a fix - 9 of 30 sessions were destroyed that way and 7 of them produced no code change at all. Everything you create outside the fix belongs under `/tmp` with an absolute path, and `/tmp` never appears in the diff.
   - Do not debug the locator. If that command fails, skip it and go straight to the fallback in step 3; a retry here costs a tenth of your session.
3. **Fallback search (only if the locator could not run).** One combined shell call:
   `cd /workspace && grep -rn --include='*.py' -E "Name1|Name2|'exact message'" . | head -30; echo ---; grep -rni "distinctive phrase" . | head -20; echo ---; ls; echo ---; git log --oneline -5`"""

READ_STEP = """4. **Read narrowly.** Open the first one or two source candidates from the ranking, then edit - do not survey the repository. Measured recall of the locator: opening only the top hit covers 48% of tasks, the top two 52%, the top three 66%, so add the third candidate only when the first two show nothing related to the issue wording. Files marked `[test]` cannot be edited; they are context, but note the imports they pull in, because the script interleaves those modules deliberately - the module that must grow is usually the one the nearest test imports."""

EDIT_STEP = """5. **Edit minimally and correctly.**
   - **Documentation is not a fix.** A markdown change under `docs/` can never change test outcomes. If the issue is about behaviour and the best candidate you have is such a file, open the source module it documents instead (or the next source candidate from the ranking). A docs edit may accompany the fix, never replace it. The only exception is an issue that is explicitly about the documentation itself.
   - Files under `docs_src/`, `examples/` or `tutorials/` are executable code that some projects import in their tests (FastAPI does): editing those can fix behaviour, so treat them as source."""

VERIFY_STEP = """6. **Verify cheaply, once, or not at all.**"""

SUBMIT_STEP = """7. **Final check, then decide whether to submit at all.**
   `cd /workspace && git status --porcelain && git diff --stat`
   - The list must contain only files you changed as part of the fix. Scratch files, logs, repro scripts and `.txt` notes are never part of a fix: delete them with `rm -f` in the same call and check again.
   - **An edit that does not address the issue is not a fix.** If the only change is a scratch file, or a markdown file under `docs/` while the issue is about behaviour, do not submit - keep working. Measured: sessions that ended this way scored zero on tasks that were otherwise solvable.
   - **`submit_patch()` is optional.** The harness extracts the working-tree diff itself (`git add -N . && git diff`), so your edits are captured even if you never call it; calling it early only ends your session. Call it once the fix is on disk and you are done (or out of time) - never before a real edit exists, and never just to be sure something was submitted."""


POST_EDITS = [
    # Measured on the 30-task V5 screening: 6/30 sessions produced no edit at all and 5 of
    # those died on the wall clock; every resolved patch stayed under 1900 characters while
    # diffs over 2000 characters resolved 0/6. Measured on the V6.1 screening: clock deaths
    # rose to 17/30 because scratch files were written into /workspace.
    (
        "An **empty patch is a guaranteed zero**, while a plausible, minimal patch has a real chance of passing. Therefore: **never end a session without calling `submit_patch()`**.",
        "An **empty patch is a guaranteed zero**, while a plausible, minimal patch has a real chance of passing. Therefore: **never end a session without a real edit on disk** - the harness captures the working-tree diff even if you never call `submit_patch()`, and it ends the session when you do call it. A session that runs out of time with an unrelated or empty diff scores zero just the same.",
    ),
    (
        "- You have roughly 5 minutes of wall clock and a budget of about 45 tool calls, but on this hardware each model call costs about 10 seconds, so **every tool call is expensive**. A good run uses only 12-20 calls.",
        "- You have roughly 5 minutes of wall clock and a budget of about 30 tool calls (the ceiling a 5.25-minute session can actually reach), and on this hardware each model call costs about 10 seconds, so **every tool call is expensive**. A good run uses only 12-20 calls.",
    ),
    (
        "- Pace by call count: after ~12 calls you should already have a candidate edit; after ~20 calls stop searching; after ~30 calls submit immediately with whatever you have.",
        "- **Hard edit deadline.** The graded artifact is the diff in `/workspace`: the harness extracts it even when you never call `submit_patch()`, so the only guaranteed zero is a tree you never edited. The locator is one call; an edit must exist on disk by call 8; stop searching by call 14; submit by call 18. A session that dies on the clock with an empty tree scores zero no matter how good the analysis was.",
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
        "   Never run bare `pytest`, a whole directory or a long suite, and never retry a command that timed out: on measured runs a single runaway test command consumed half the session. Pre-existing failures unrelated to your change are not your problem - never try to repair tests. Past call 18, skip verification entirely and submit.",
    ),
    (
        "- If you cannot identify the defect with confidence, pick the most plausible location from your search results and implement the smallest change that matches the issue's wording, even untested. A partial or speculative fix costs nothing and can pass; an empty diff cannot.",
        "- If you cannot identify the defect with confidence, pick the most plausible location from your search results and implement the smallest change that matches the issue's wording, even untested. A partial or speculative fix costs nothing and can pass; an empty diff cannot.\n- If by call 10 the tree still has no edit, stop reading and investigating: open the top locator candidate and make the smallest sensible change - a wrong guess still beats submitting nothing.",
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

    # Remove the V5 tail that contradicts the V6.3 "submit_patch is optional" rule.
    prompt = prompt.replace(
        "Call `submit_patch()` as your final action, then write two short sentences: what you changed "
        "and what remains uncertain. The session ends there.",
        " When you do finish, write two short sentences: what you changed and what remains uncertain.",
        1,
    )

    script_block = (
        "\n\n## Locator script (copy this verbatim into the `LOCATE_PY` heredoc in step 2)\n\n"
        "```python\n" + script + "\n```\n"
    )
    prompt = prompt[:start] + LOCALIZE_STEP + "\n\n" + tail.rstrip("\n") + script_block
    prompt = apply_post_edits(prompt)

    # V6.3: the V5 tail "Call submit_patch() as your final action ... The session ends there."
    # contradicts the new rule that submit_patch is optional; strip it robustly (it spans lines
    # differently depending on how the V5 prompt was wrapped).
    prompt = re.sub(r"\s*Call `submit_patch\(\)` as your final action.*?The session ends there\.",
                    "", prompt, count=1, flags=re.S)
    if "as your final action" in prompt:
        raise SystemExit("failed to strip the contradictory V5 submit tail")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(prompt + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(prompt)} chars, script {len(script)} chars)")
    assert script in OUT.read_text(encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
