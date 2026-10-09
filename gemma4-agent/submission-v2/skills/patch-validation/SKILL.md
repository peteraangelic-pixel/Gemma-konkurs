---
name: patch-validation
description: Check that the final Git diff is non-empty, whitespace-clean, and limited to intended files before patch submission.
---
# Final patch validation

Use this skill after the post-edit tests and immediately before each `submit_patch()` call.

1. Run `scripts/validate_patch.py` through the competition's `run_skill_script` tool, using the tool's displayed argument schema. It stages only untracked-file intents, not file contents, then checks the diff against `HEAD`.
2. Confirm that the diff is non-empty, `git diff --check` reports no whitespace errors, and the listed files are the intended minimal repair. The validator rejects common generated cache/build artifacts. If it reports one, remove only the artifact created by the current test/build run (never reset or delete unrelated repository files), then validate again.
3. Review any test, configuration, generated, or unrelated file in the reported list; remove accidental changes. Do not delete or reset user/repository files to make the validator clean.
4. If you change anything after validation, rerun the relevant tests and this validator before submitting.

This check does not prove correctness. A passing targeted test and this clean-diff check are both required for a normal submission.
