user-authorized V6.3 mini-screen (benchmark only, no official submission); account=petersharps
candidate: V6.3
archive: gemma4-agent/submission-v6.zip
archive_sha256: abf22bac2c67c639342f56e890fd77cb36c91811d07cf1c239c84ef28fa1216e
tasks: rich_3105,rich_3934,rich_3006,fastapi_14487 (explicit --task-ids; 4 diagnosed cases, not a sample)
why these four: rich_3105 + rich_3934 = V6.2 empty trees from premature submit_patch (fix a);
  fastapi_14487 = V6.2 docs-only diff for a behaviour issue (fix c);
  rich_3006 = CONTROL: a long-call clock death that (a) and (c) do not target, expected to stay unresolved
seed: 20261009
comparison_baseline: V6.2 results for the same four tasks are in kaggle_results/v6-benchmark/
pre_registered_gates: gemma4-agent/GATES_V6_3.md (G1 zero scratch files, G2 zero premature submits without edits, G3 zero docs-only diffs)
cost_note: ~1/5 of a full 30-task screen; gates are checked before deciding on the full run
official_submission: false
