user-authorized private V6.2 screening (benchmark only, no official submission); account=petersharps
candidate: V6.2
archive: gemma4-agent/submission-v6.zip
archive_sha256: 8c1ea5b71a61b4d58a6b023596761abb9af37908af6d0ef441347353a2f860b8
task_count: 30
task_id: fastapi_15588
seed: 20261009
comparison_baseline: V3 11/30, V4 11/30, V5 10/30, V6.1 6/30 on this exact sample (kaggle_results/*-benchmark)
v6_2_changes: fixed the V6.1 regression (agent wrote bare scratch filenames into /workspace, so 9/30 diffs were 7.7 KB of locate.py+issue text and 7 had no code edit at all) - the locator is now delivered by a single run_command with /tmp-only heredocs and NO write_file; added a mandatory "git status --porcelain" hygiene check that deletes anything unexpected before submit_patch; lowered max_tool_calls 45->30 so the free budget_warning arrives at call 20; hard deadlines (edit on disk by call 8, submit by 18)
official_submission: false
notes: same 30 task IDs and seed as V2/V3/V4/V5/V6.1; per-task diagnostics recorded (touched files, gold files, localized flag, empty patches)
