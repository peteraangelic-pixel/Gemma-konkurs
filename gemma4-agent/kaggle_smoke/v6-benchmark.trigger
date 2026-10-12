user-authorized private V6 screening (benchmark only, no official submission); account=petersharps
candidate: V6
archive: gemma4-agent/submission-v6.zip
archive_sha256: 7344f5d806b086746d45f4a389535494f193d25733721d441f08c6540b75942c
task_count: 30
task_id: fastapi_15588
seed: 20261009
comparison_baseline: V3 11/30, V4 11/30, V5 10/30 on this exact sample (kaggle_results/*-benchmark)
v6_changes: locator-first localization (measured 73.4% top-5 dev / 71.8% held-out vs ~15% for first grep); hard edit deadline from the V5 failure mode (5/6 empty patches died on the wall clock); verification bounded to timeout 45; measured small-patch rule (all resolved diffs <1900 chars, >2000 chars resolved 0/6)
official_submission: false
notes: same 30 task IDs and seed as V2/V3/V4/V5; records per-task localization diagnostics (touched files, gold files, localized flag) that the V5 run predates
