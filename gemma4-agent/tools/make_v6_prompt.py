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

V6.4 design notes (read-only diagnosis of the V6.3 kernels, see ANALYSIS_V6_3_MECHANISMS.md):
* The 11 empty trees of V6.3 are four mechanisms, not one: 7 sessions never attempt any edit
  (one burned 31 calls on run_command/read_file, two stopped by themselves at 41 s and 108 s);
  fastapi_15030 fires nine consecutive edit_file calls at one file from 212 s to 307 s and writes
  nothing; requests_6757 (plus fastapi_14077 and rich_3894) loops submit_patch 42-48 times and dies
  on the 60-turn cap; fastapi_15745 writes /tmp/locate.py instead of editing the repository.
* V6.4 therefore adds four rules, each pinned to one of those measurements: a write-without-reading
  deadline, a fallback from a failing edit_file to write_file, submit_patch at most once, and a ban
  on creating any file to help yourself. No budget, threshold, tool or script changes.

    python3 gemma4-agent/tools/make_v6_prompt.py
"""

from __future__ import annotations

import re
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V5_PROMPT = ROOT / "gemma4-agent" / "submission-v5" / "prompts" / "system.md"
V6_DIR = ROOT / "gemma4-agent" / "submission-v6"
DEFAULT_OUT = V6_DIR / "prompts" / "system.md"
VARIANT = os.environ.get("V6_VARIANT", "v64")
V65_DIR = ROOT / "gemma4-agent" / "submission-v6.5"
V66_DIR = ROOT / "gemma4-agent" / "submission-v6.6"
V67_DIR = ROOT / "gemma4-agent" / "submission-v6.7"
V68_DIR = ROOT / "gemma4-agent" / "submission-v6.8"
VARIANT_DIR = {"v64": V6_DIR, "v65": V65_DIR, "v66": V66_DIR, "v67": V67_DIR,
               "v68": V68_DIR}[VARIANT]
OUT = VARIANT_DIR / "prompts" / "system.md"
LOCATOR = VARIANT_DIR / "tools" / "locate.py"

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


# V6.4: four rules, each pinned to a mechanism measured read-only in the V6.3 kernel traces
# (ANALYSIS_V6_3_MECHANISMS.md). Anchors are the V6.3 sentences, so these edits apply in order
# after POST_EDITS.
V64_EDITS = [
    # M1 - 7 of 30 sessions never attempted an edit; median first edit was 179 s of a 315 s budget.
    (
        "- **Hard edit deadline.** The graded artifact is the diff in `/workspace`: the harness extracts it even when you never call `submit_patch()`, so the only guaranteed zero is a tree you never edited. The locator is one call; an edit must exist on disk by call 8; stop searching by call 14; submit by call 18. A session that dies on the clock with an empty tree scores zero no matter how good the analysis was.",
        "- **Hard edit deadline.** The graded artifact is the diff in `/workspace`: the harness extracts it even when you never call `submit_patch()`, so the only guaranteed zero is a tree you never edited. The locator is one call; an edit must exist on disk by call 8; stop searching by call 14; submit by call 18. A session that dies on the clock with an empty tree scores zero no matter how good the analysis was.\n   - **No reading without writing.** Measured on the last run: 7 of 30 sessions never attempted a single edit and scored zero - one of them spent 31 calls on `run_command` and `read_file` and two stopped on their own after 41 s and 108 s. So: the first call after your first file read must be an edit attempt, and if call 6 arrives with no edit on disk your next call is `edit_file` or `write_file` - no more reading first. Opening a top candidate and editing it beats opening five and editing none.",
    ),
    # M2 - nine consecutive edit_file calls at one file, 212 s to 307 s, diff still empty.
    (
        "   - Make the first edit as soon as you have a plausible target and refine it with further `edit_file` calls; do not batch a large rewrite into one risky step.",
        "   - Make the first edit as soon as you have a plausible target and refine it with further `edit_file` calls; do not batch a large rewrite into one risky step.\n   - **If an `edit_file` call does not change the file, do not repeat it.** Try one different anchor; if that also fails, read the file once more and rewrite it whole with `write_file`. Measured: one session fired nine consecutive `edit_file` calls at the same file between 212 s and 307 s and the graded diff was still empty.",
    ),
    # M3 - submit_patch loops (48, 44, 42 calls) exhausted the 60-turn budget.
    (
        "   - **`submit_patch()` is optional.** The harness extracts the working-tree diff itself (`git add -N . && git diff`), so your edits are captured even if you never call it; calling it early only ends your session. Call it once the fix is on disk and you are done (or out of time) - never before a real edit exists, and never just to be sure something was submitted.",
        "   - **`submit_patch()` is optional, and you may call it at most once.** The harness extracts the working-tree diff itself (`git add -N . && git diff`), so your edits are captured even if you never call it; calling it early only ends your session. Call it once the fix is on disk and you are done (or out of time) - never before a real edit exists, and never just to be sure something was submitted. Measured: one session called it 48 times in a row and died on the 60-turn budget with an empty tree, and two more exhausted their turns the same way (44 and 42 calls). A `submit_patch` that reports no changes is a signal to go back and edit - never to retry it.",
    ),
    # M4 - a session wrote /tmp/locate.py at 280 s instead of editing the repository.
    (
        "- If by call 10 the tree still has no edit, stop reading and investigating: open the top locator candidate and make the smallest sensible change - a wrong guess still beats submitting nothing.",
        "- If by call 10 the tree still has no edit, stop reading and investigating: open the top locator candidate and make the smallest sensible change - a wrong guess still beats submitting nothing.\n- **Never create a file to help yourself, and never write outside the repository.** The locator is delivered inside the single `run_command` heredoc above and writes only to `/tmp`; nothing else you write may leave `/workspace`. Measured: one session spent 280 s writing `/tmp/locate.py` instead of editing the repository and scored zero. If you feel the need to create a helper file, that is your signal to edit the top candidate instead.",
    ),
]


V64B_EDITS = [
    ("the harness extracts it even when you never call `submit_patch()`, so the only guaranteed zero is a tree you never edited.",
     "the harness extracts it on its own, so the only guaranteed zero is a tree you never edited."),
    ('Therefore: **never end a session without a real edit on disk** - the harness captures the working-tree diff even if you never call `submit_patch()`, and it ends the session when you do call it. A session that runs out of time with an unrelated or empty diff scores zero just the same.',
     'Therefore: **never end a session without a real edit on disk**: there is no submit step to call - the harness captures the working-tree diff by itself - and a session that runs out of time with an unrelated or empty diff scores zero just the same.'),
    ('an edit must exist on disk by call 8; stop searching by call 14; submit by call 18.',
     'an edit must exist on disk by call 8; stop searching by call 14; be finished by call 18.'),
    ('Past call 18, skip verification entirely and submit.',
     'Past call 18, skip verification entirely and finish.'),
    ('7. **Final check, then decide whether to submit at all.**',
     '7. **Final check before you stop.**'),
    ('do not submit - keep working.',
     'keep working.'),
    ('   - **`submit_patch()` is optional, and you may call it at most once.** The harness extracts the working-tree diff itself (`git add -N . && git diff`), so your edits are captured even if you never call it; calling it early only ends your session. Call it once the fix is on disk and you are done (or out of time) - never before a real edit exists, and never just to be sure something was submitted. Measured: one session called it 48 times in a row and died on the 60-turn budget with an empty tree, and two more exhausted their turns the same way (44 and 42 calls). A `submit_patch` that reports no changes is a signal to go back and edit - never to retry it.',
     '   - **There is no submit tool.** Your tool list has no `submit_patch`: the harness extracts the working-tree diff itself (`git add -N . && git diff`), so the only thing that matters is what is on disk when the session ends, and there is no step to wait for. Measured: the sessions that had that tool looped on it - one called it 48 times in a row and died on the 60-turn budget with an empty tree, two more exhausted their turns the same way (44 and 42 calls) - which is why it is gone from this build.'),
    ('- If by call 10 the tree still has no edit, stop reading and investigating: open the top locator candidate and make the smallest sensible change - a wrong guess still beats submitting nothing.\n- **Never create a file to help yourself, and never write outside the repository.** The locator is delivered inside the single `run_command` heredoc above and writes only to `/tmp`; nothing else you write may leave `/workspace`.',
     '- If by call 10 the tree still has no edit, stop reading and investigating: open the top locator candidate and make the smallest sensible change - a wrong guess still beats finishing with nothing.\n- **Apart from the single locator heredoc in step 2, never create a file to help yourself, and never write outside the repository.** That one heredoc writes `/tmp/locate.py` and the issue text, and it is the only exception; everything else you write must be an edit inside `/workspace`.'),
    ('- If a test you ran fails, read the failure, make ONE targeted correction, and submit. Never revert to an empty diff.',
     '- If a test you ran fails, read the failure, make ONE targeted correction, and stop. Never revert to an empty diff.'),
]


V64C_EDITS = [
    ('The locator is one call; an edit must exist on disk by call 8; stop searching by call 14; be finished by call 18.',
     'The locator is one call: read the highest-ranked plausible candidate, then edit in the next call. An **intended** source or configuration edit must exist on disk by call 4; stop searching by call 14; be finished by call 18.'),
    ('   - **No reading without writing.** Measured on the last run: 7 of 30 sessions never attempted a single edit and scored zero - one of them spent 31 calls on `run_command` and `read_file` and two stopped on their own after 41 s and 108 s. So: the first call after your first file read must be an edit attempt, and if call 6 arrives with no edit on disk your next call is `edit_file` or `write_file` - no more reading first. Opening a top candidate and editing it beats opening five and editing none.',
     '   - **No reading without writing, and no dummy edits.** Measured on the last run: 7 of 30 sessions never attempted a single edit and scored zero - one of them spent 31 calls on `run_command` and `read_file`, and two stopped on their own after 41 s and 108 s. So the first call after your first file read must be an edit attempt, the deadline is call 4, and it must be a real attempt at the reported issue: **never write a dummy or placeholder edit merely to satisfy the deadline** - a wrong-but-sincere fix can pass, a placeholder cannot.'),
    ('   - Make the first edit as soon as you have a plausible target and refine it with further `edit_file` calls; do not batch a large rewrite into one risky step.',
     '   - The first intended edit must be on disk by tool call 4, even if it is a conservative, minimal fix that you will refine. It must address the reported issue; never create a dummy edit merely to satisfy the deadline. Refine it with further `edit_file` calls; do not batch a large rewrite into one risky step.'),
    ('- If by call 10 the tree still has no edit, stop reading and investigating: open the top locator candidate and make the smallest sensible change - a wrong guess still beats finishing with nothing.',
     '- If by tool call 4 the tree still has no intended edit, stop reading and investigating: open the top locator candidate and make the smallest sensible issue-related change. No placeholder edits - a sincere wrong guess beats finishing with nothing.'),
]

V64D_EDITS = [
    ('- **Apart from the single locator heredoc in step 2, never create a file to help yourself, and never write outside the repository.** That one heredoc writes `/tmp/locate.py` and the issue text, and it is the only exception; everything else you write must be an edit inside `/workspace`. Measured: one session spent 280 s writing `/tmp/locate.py` instead of editing the repository and scored zero. If you feel the need to create a helper file, that is your signal to edit the top candidate instead.',
     '- **Scratch files are never your answer.** The single `/tmp/locate.py` heredoc in step 2 is the only file you may create before your first edit. After the fix is already on disk you may write a repro script under `/tmp` to check it, but the repository diff is the only thing graded - measured: one session spent 280 s writing `/tmp/locate.py` instead of editing and scored zero, while another wrote `/tmp/repro.py` only after its edit and passed. Never use bare filenames (they land in `/workspace`), and never write anywhere except `/tmp` and `/workspace`.'),
]

V64E_EDITS = [
    ('   - **Never use `write_file` or shell redirection for scratch material, and never let a bare filename like `locate.py`, `issue.txt` or `repro.py` be created in `/workspace`.** Measured on the previous run: bare filenames are resolved inside `/workspace`, so the graded diff became the 7.7 KB script plus the issue text instead of a fix - 9 of 30 sessions were destroyed that way and 7 of them produced no code change at all. Everything you create outside the fix belongs under `/tmp` with an absolute path, and `/tmp` never appears in the diff.',
     '   - **Never let a bare filename like `locate.py`, `issue.txt` or `repro.py` be created in `/workspace`.** A bare relative path resolves inside `/workspace`, so the graded diff becomes your scratch material instead of a fix - measured on an earlier run: 9 of 30 sessions were destroyed that way and 7 of them produced no code change at all. Always give a scratch file an absolute `/tmp/...` path; `write_file` and shell redirection are both fine for that, and `/tmp` never appears in the diff.'),
    ('- **Scratch files are never your answer.** The single `/tmp/locate.py` heredoc in step 2 is the only file you may create before your first edit. After the fix is already on disk you may write a repro script under `/tmp` to check it, but the repository diff is the only thing graded - measured: one session spent 280 s writing `/tmp/locate.py` instead of editing and scored zero, while another wrote `/tmp/repro.py` only after its edit and passed. Never use bare filenames (they land in `/workspace`), and never write anywhere except `/tmp` and `/workspace`.',
     '- **A scratch file is never the answer, but it is also never forbidden.** Repro scripts under `/tmp` are allowed at any point in the session - a task that PASSED wrote `/tmp/repro.py` and then edited `rich/repr.py`, and a second one wrote its repro before its source edit and still patched the file. What is fatal is finishing with no repository edit: one session wrote only `/tmp/locate.py` at 279.8 s and ended with an empty tree. So if you have a helper script on disk and the tree is still untouched, stop and edit the top candidate now.'),
]

# V6.5 lever (2026-10-13): the deadline alone did not change behaviour. In the V6.4 mini-screen the
# explicit "intended edit by call 4" sentence was ignored in 6/6 tasks (repository edits within
# call 4: 0/6, median at call 7), and the three sessions that ended empty were not blocked by the
# clock: rich_3105 made 15 run_command calls in 107 s and then stopped on its own, rich_3043 ran
# 322.7 s and fastapi_15745 read fastapi/routing.py ten times over 336.7 s. Meanwhile every session
# that did edit produced a patch. So V6.5 changes the framing of the edit decision from a
# prohibition ("do not be slow") to an expectation ("a rough, revisable first edit is the job"),
# with the intent-vs-accuracy boundary spelled out so it cannot contradict the anti-dummy rule.
V65_EDITS = [
    # Append, never replace: every V6.4 sentence and measurement stays in place (the packer checks
    # them), and the new evidence is added after the rule it supports.
    (
        "**never write a dummy or placeholder edit merely to satisfy the deadline** - a "
        "wrong-but-sincere fix can pass, a placeholder cannot.",
        "**never write a dummy or placeholder edit merely to satisfy the deadline** - a "
        "wrong-but-sincere fix can pass, a placeholder cannot. That deadline was in this prompt on "
        "the next run too and was still ignored in every task: three sessions ended with an empty "
        "tree and none of them was stopped by the clock - one made 15 `run_command` calls in 107 s "
        "and then stopped by itself, one ran 322.7 s, one read a single file ten times over "
        "336.7 s. Every session that did edit produced a patch instead. If you have read the "
        "locator's top candidate and you are still reading, you are off track - edit now."
    ),
    (
        "   - The first intended edit must be on disk by tool call 4, even if it is a conservative, "
        "minimal fix that you will refine. It must address the reported issue; never create a dummy "
        "edit merely to satisfy the deadline. Refine it with further `edit_file` calls; do not batch "
        "a large rewrite into one risky step.",
        "   - The first intended edit must be on disk by tool call 4 - **make it even if you are not "
        "yet certain it is the right file.** A conservative, minimal fix that you refine afterwards "
        "is exactly what is asked for; an edit to the wrong candidate is recoverable (you revise or "
        "revert it), while an untouched tree is not. You do not need the root cause before your "
        "first edit, only a plausible one. It must address the reported issue as best you can: never "
        "create a dummy edit merely to satisfy the deadline. The line between an intended edit and a "
        "dummy is **intent, not accuracy** - a crude attempt at the real issue is expected, a change "
        "you know is unrelated is not. Refine it with further `edit_file` calls; do not batch a "
        "large rewrite into one risky step."
    ),
]


# V6.6 lever (2026-10-13, after the full V6.4 run): the locator step itself produced zeros. Four of
# 30 sessions wrote /tmp/locate.py and never edited the repository at all; fastapi_15745 and
# fastapi_15588 ended after THREE tool calls (243.8 s and 340.6 s), as if the finished script were
# the deliverable. Versions without a locator step (V3/V4/V5) had 6 empty trees, V6.x has 11. So
# V6.6 removes the file from the localisation path instead of asking the model not to stop there:
# the same script runs inline as the -c argument in ONE command, with the issue text on stdin.
V66_EDITS = [
    (
        "cd /workspace && cat > /tmp/locate.py <<'LOCATE_PY'\n"
        "[the whole locator script from the section at the end of this prompt, copied character for character]\n"
        "LOCATE_PY\n"
        "python3 /tmp/locate.py --root . --top 8 <<'ISSUE_EOF'\n"
        "[the issue text, verbatim and complete]\n"
        "ISSUE_EOF",
        "cd /workspace && python3 -c \"$(cat <<'LOCATE_PY'\n"
        "[the whole locator script from the section at the end of this prompt, copied character for character]\n"
        "LOCATE_PY\n"
        ")\" --root . --top 8 <<'ISSUE_EOF'\n"
        "[the issue text, verbatim and complete]\n"
        "ISSUE_EOF",
    ),
    (
        "So if you have a helper script on disk and the tree is still untouched, stop and edit the "
        "top candidate now.",
        "So if you have a helper script on disk and the tree is still untouched, stop and edit the "
        "top candidate now. Measured on the last full run, and this is why step 2 above no longer "
        "writes any file: **four sessions wrote `/tmp/locate.py` and then never edited the "
        "repository at all** - two of them stopped after only three tool calls, treating the "
        "finished script as the work, and every one of them scored zero.",
    ),
]
# V6.7 (2026-10-14): the raw-call diagnosis of the full V6.4 run (analysis/diagnostics-2026-10-14/
# v64-raw-calls.md) read the actual tool calls instead of the committed summaries and found that a
# large part of the run's waste was not strategy at all - it was our own prompt contradicting the
# harness tool contract. Each rule below is pinned to one counted measurement from that report.
V67_EDITS = [
    # A. The 30-call ceiling REFUSES work instead of warning, and comment-only shell calls burned
    #    32 calls across the run (8 of them in fastapi_14297's last stretch).
    (
        "A good run uses only 12-20 calls.",
        "A good run uses only 12-20 calls. The ceiling does not warn you, it refuses the work: on "
        "the last run two sessions reached call 31 with the tree still untouched and the answer to "
        "their first `edit_file` was `Tool call budget exhausted (30 calls)` - the tree stayed "
        "empty and both scored zero. Treat call 20 as the point after which only the fix matters. "
        "Thirty-two calls across that run were `run_command` lines whose entire content was a "
        "shell comment (`# Final`, `# Done.`, eight of them in one session); a comment does not "
        "end a session, does not change a file and does not score: to finish, write your final "
        "message with no tool call.",
    ),
    # B. 29 reads asked for line numbers past the end of the file; fastapi_14851 read lines
    #    4470-4520 of a ~1000-line file six times.
    (
        "- Do not narrate, do not call `get_status`, do not repeat a call that already failed, do "
        "not explore outside `/workspace`.",
        "- Do not narrate, do not call `get_status`, do not repeat a call that already failed, do "
        "not explore outside `/workspace`. `read_file` returns the whole file when you omit "
        "`start_line` and `end_line`, so omit them unless you have seen the numbers in a `grep -n` "
        "result: 29 reads in the last run asked for lines past the end of the file (one session "
        "asked six times for lines 4470-4520 of a file about 1000 lines long) and learned nothing.",
    ),
    # C. The harness refuses `write_file` outside the workspace root, while this prompt sends
    #    scratch material to /tmp; three sessions (fastapi_14186, fastapi_14303, requests_7309)
    #    lost calls to that contradiction. The shell inside run_command is not restricted.
    (
        "Always give a scratch file an absolute `/tmp/...` path; `write_file` and shell "
        "redirection are both fine for that, and `/tmp` never appears in the diff.",
        "Always give a scratch file an absolute `/tmp/...` path; `write_file` and shell "
        "redirection are both fine for that, and `/tmp` never appears in the diff. "
        "**Correction from the raw tool calls of the last full run: shell redirection is fine, "
        "`write_file` is not** - it refuses any path outside the workspace root with "
        "`Path traversal detected: '/tmp/repro.py' escapes workspace root.`, and three sessions "
        "lost calls to that. Deliver every scratch file as a `cat > /tmp/... <<'EOF'` heredoc "
        "inside a `run_command` call, exactly like the locator command above; `write_file` is for "
        "repository files only.",
    ),
    # D. fastapi_14262 got `Target string occurs 2 times in fastapi/param_functions.py`.
    (
        "- Use `edit_file` with a short `old_string` copied exactly from the code you just read.",
        "- Use `edit_file` with a short `old_string` copied exactly from the code you just read. "
        "If it answers `Target string occurs 2 times ...`, never resend the same string: extend it "
        "with the surrounding lines until the match is unique.",
    ),
    # E. requests_6757: two successful `edit_file` calls in tox.ini (the tool returned both diffs),
    #    graded tree still empty - a discarded file makes a successful edit invisible.
    (
        "- Never modify `tests/`, `test_*.py`, `*_test.py`, `conftest.py`, `pytest.ini`, "
        "`pyproject.toml`, `tox.ini`, `setup.cfg`: the grader resets them and such edits are "
        "discarded.",
        "- Never modify `tests/`, `test_*.py`, `*_test.py`, `conftest.py`, `pytest.ini`, "
        "`pyproject.toml`, `tox.ini`, `setup.cfg`: the grader resets them and such edits are "
        "discarded. Measured on the last run: one session made two `edit_file` calls in `tox.ini`, "
        "the tool confirmed both with a diff, and the graded tree was still empty. If your only "
        "change sits in `tox.ini`, `setup.cfg`, `pyproject.toml` or a test file, you have not "
        "started: the fix that counts belongs in the importable source (`src/...` or the package "
        "directory), even when the issue talks about dependencies or packaging.",
    ),
    # F. fastapi_14487 spent all 30 calls inside the rendered docs page; the graded file was the
    #    runnable example under docs_src/.
    (
        "The only exception is an issue that is explicitly about the documentation itself.",
        "The only exception is an issue that is explicitly about the documentation itself. When "
        "that exception applies, the fix still belongs in the runnable example under `docs_src/`, "
        "not the rendered page under `docs/en/`: on the last run a session spent all 30 calls "
        "rewriting `docs/en/docs/tutorial/handling-errors.md`, was refused its first edit by the "
        "call ceiling, and the graded file was `docs_src/handling_errors/tutorial004.py`.",
    ),
    # G. All 8 sessions of the run that edited a correct file and still failed had used 30 calls or
    #    run past 315 s (or both) with the fix incomplete - finishing the issue beats searching.
    (
        "- Keep the diff small. Measured on these tasks: every resolved session produced a diff "
        "under 1900 characters (most under 1500), while every diff over 2000 characters failed. "
        "Fix the reported behaviour and nothing else.",
        "- Keep the diff small. Measured on these tasks: every resolved session produced a diff "
        "under 1900 characters (most under 1500), while every diff over 2000 characters failed. "
        "Fix the reported behaviour and nothing else.\n"
        "   - **Finish the issue, not the search.** All eight sessions of the last run that edited "
        "a correct file and still failed had used 30 calls or run past 315 seconds, or both, with "
        "the fix unfinished. After the first edit, re-read the issue and cover every case it names "
        "- identifier, message, edge case - with one small edit per gap; only then verify. An "
        "incomplete fix and an empty tree score the same.",
    ),
]


# V6.8 (2026-10-14): the locator's ten hand-picked constants, replaced by a population search over
# the 128 published dev tasks with gold patches and validated on 104 held-out tasks from four
# repositories outside the dev set (tools/evolve_locator.py, analysis/locator-evolve/validation.md).
# One lever only: the script at the end of the prompt is the evolved one, and the sentences that
# quote its measured recall are updated to the numbers measured for THAT file. Nothing else changes.
V68_EDITS = [
    (
        "The script below was verified on 128 published tasks (the fixable source file lands in "
        "the top 3 for 66% of them, in the top 5 for 73%) and on 188 tasks from repositories "
        "outside that set (65% and 72%), against ~15% for a plain first grep.",
        "The script below was verified on 128 published tasks (the fixable source file lands in "
        "the top 3 for 67% of them, in the top 5 for 74%) and on 104 tasks from four repositories "
        "outside that set (74% and 84%), against ~15% for a plain first grep. Its scoring "
        "constants were fitted by a population search against those 128 tasks and re-measured on "
        "the held-out 104, so the recall improvement is not a tuning artefact.",
    ),
    (
        "Measured recall of the locator: opening only the top hit covers 48% of tasks, the top two "
        "52%, the top three 66%",
        "Measured recall of the locator: opening only the top hit covers 56% of tasks, the top two "
        "59%, the top three 67%",
    ),
]


def apply_post_edits(prompt: str) -> str:
    for old, new in POST_EDITS:
        assert old in prompt, "missing anchor: " + old[:60]
        prompt = prompt.replace(old, new, 1)
    for old, new in V64_EDITS:
        assert old in prompt, "missing V6.4 anchor: " + old[:60]
        prompt = prompt.replace(old, new, 1)
    # V64B: the submit tool is gone, so no sentence may instruct calling it, and the locator
    # heredoc is now an explicit exception to the "never create a file" rule (contradiction
    # reported by the second branch on 2026-10-13).
    for old, new in V64B_EDITS:
        assert old in prompt, "missing V64B anchor: " + old[:60]
        prompt = prompt.replace(old, new, 1)
    # V64C: the second branch's tighter formulation of the deadline (call 4) with its explicit
    # ban on placeholder edits - adopted because the review asked for a requirement of an early
    # *intended* change, and the ban is what makes "intended" enforceable rather than decorative.
    for old, new in V64C_EDITS:
        assert old in prompt, "missing V64C anchor: " + old[:60]
        prompt = prompt.replace(old, new, 1)
    # V64D: the blanket ban on helper files also forbade a pattern that a RESOLVED task used
    # (rich_3006 wrote /tmp/repro.py after its edit and passed). Narrowed to what the evidence
    # supports: scratch material may not be the answer and may not exist before the first edit.
    for old, new in V64D_EDITS:
        assert old in prompt, "missing V64D anchor: " + old[:60]
        prompt = prompt.replace(old, new, 1)
    # V64E (third revision of M4, after the second branch checked the trace order):
    # my counter-example was WRONG - rich_3006 wrote /tmp/repro.py at 161.5 s and edited rich/repr.py
    # at 180.6 s, i.e. the scratch file came FIRST and the task still passed, and fastapi_14303 did
    # the same before patching. So a pre-edit repro script is harmless. What killed fastapi_15745 was
    # finishing with no edit at all. The rule now says exactly that, and the blanket ban on
    # write_file/shell redirection for scratch material is gone - it contradicted both this rule and
    # the M2 fallback that relies on write_file.
    for old, new in V64E_EDITS:
        assert old in prompt, "missing V64E anchor: " + old[:60]
        prompt = prompt.replace(old, new, 1)
    if VARIANT == "v65":
        for old, new in V65_EDITS:
            assert old in prompt, "missing V65 anchor: " + old[:60]
            prompt = prompt.replace(old, new, 1)
    if VARIANT == "v66":
        for old, new in V66_EDITS:
            assert old in prompt, "missing V66 anchor: " + old[:60]
            prompt = prompt.replace(old, new, 1)
    if VARIANT == "v67":
        for old, new in V67_EDITS:
            assert old in prompt, "missing V67 anchor: " + old[:60]
            assert old not in new or new.startswith(old), "V67 edit must append, not replace"
            prompt = prompt.replace(old, new, 1)
    if VARIANT == "v68":
        for old, new in V68_EDITS:
            assert old in prompt, "missing V68 anchor: " + old[:60]
            prompt = prompt.replace(old, new, 1)
    return prompt


def main() -> int:
    print(f"variant: {VARIANT} -> {OUT.name}")
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
