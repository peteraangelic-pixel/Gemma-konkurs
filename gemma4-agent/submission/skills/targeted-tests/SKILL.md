---
name: targeted-tests
description: Choose and run the narrowest relevant pytest targets after a code change, before submitting a patch.
---
# Targeted test verification

Use this skill after the final source edit and before every `submit_patch()` call.

1. Identify test targets from the issue, reproduced traceback, changed symbol, nearby tests, and project conventions. Prefer one exact node ID such as `tests/test_module.py::test_edge_case`; otherwise pass a specific test file. Do not choose the repository root, `.`, or an entire broad test directory.
2. If the test target is not known, use the issue and code neighbors to locate the closest existing test file. Do not invent a test path. A pre-edit failing result is useful baseline evidence but does not replace a post-edit run.
3. Run `scripts/run_pytest.py` using the competition's `run_skill_script` tool. Pass each pytest target as a separate argument using the argument schema shown by the tool. The script invokes `python -m pytest -q` from the repository root, disables pytest's cache and Python bytecode output, and enforces a short timeout.
4. Read the exit status and output. A non-zero exit is a failure, not a pass. Inspect relevant failures, revise the fix if warranted, and rerun the targeted test after the last edit.
5. If the environment lacks pytest or the relevant test cannot run, report the exact limitation. Do not claim verification. Use the narrowest available syntax/import check, then run the separate patch-validation skill before any best-effort submission.

Do not edit tests just to make them pass. The grader applies its own validation tests in a clean verification environment.
