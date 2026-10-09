# Public leader research — 2026-10-09

## Kaggle snapshot

Read-only GitHub Actions polls ran at 2026-10-09 11:12:26 UTC and 11:17:18 UTC. They read Kaggle through `KAGGLE_API_TOKEN` without recording its value or submitting anything.

- Our `submission.zip`, description `V1`, Kaggle submission ref `56974591`, remains `SubmissionStatus.PENDING`; it was registered at 2026-10-08 21:54:34 UTC and has no public or private score yet. The API row proves the upload was registered; the long spinner is now a pending evaluation/queue issue, not a missing ZIP upload.
- The public leaderboard snapshot has 2,172 rows. Top score is 0.24. The top 10 table is in [`kaggle_results/summary.md`](kaggle_results/summary.md); complete CSVs are alongside it.
- Our row cannot yet be matched by team name because the optional Actions variable `KAGGLE_TEAM` is unset. The account's own submission status is still visible in `submissions.csv`.

## Public material found for current leaders

The API query searched public competition notebooks authored by members of the current top 10. It found two notebooks by `mizeroluckygall`, a member of the team currently ranked 4th (`Mizero Lucky Gall`, leaderboard score 0.20). It returned no notebooks for other top-10 members in that competition/user-filtered query; that does not rule out notebooks published elsewhere or under another account.

- [Pathfinder | Gemma 4 Agent: EDA + Baseline+](https://www.kaggle.com/code/mizeroluckygall/pathfinder-gemma-4-agent-eda-baseline) — 51 votes; the page shows public score 0.12.
- [Gemma 4 Agent — EDA + Agent + Validator](https://www.kaggle.com/code/mizeroluckygall/gemma-4-agent-eda-agent-validator) — 3 votes; the page shows public score 0.08.

These notebooks are public research artifacts, **not proof of the exact ZIP currently earning the team's 0.20 leaderboard score**. In particular, the Pathfinder page's prose reports an earlier hard-4-minute variant at 0.08 and describes a later adaptive variant, while its rendered page shows 0.12. Treat the comparison as the author's preliminary evidence, not a controlled experiment.

## Strategy signals (not code copied into V1)

1. **Analyzer + coder.** The public approach uses a read-only code analyzer for localization and a separate coder for edits, tests, and `submit_patch()`. Our V1 already uses this architecture.
2. **Issue-derived rules.** The author reports 129 public tasks across FastAPI (67), Rich (48), Requests (13), and HTTPX (1); median reference-patch churn is 12 lines, 83% of test patches add a test function, and 19% of issue statements contain pull-request-template boilerplate. I independently recomputed those figures from the 1.98 MB `tasks.jsonl` already on `origin/main`; no 22 GB dataset download was needed. The useful prompt implications are to use exact names from the issue, ignore boilerplate, inspect the target tests, and keep edits focused.
3. **Adaptive task pacing.** The notebook recommends checking `get_status()` about every eight calls and switching from exploration to fix/verify/submit when roughly 25% of the *current task's* budget remains. It omits a custom `eval_config.yaml`; the harness defaults are 60 minutes, 100 tool calls, and 500 turns per task. Our V1's 4-minute / 35-call / 60-turn cap is much tighter. The author reports a hard-4-minute variant at 0.08 and a later public page score of 0.12, but multiple changes were made, so this is a hypothesis for V2—not proof that removing the cap alone improves score. Keep the competition-wide 12-hour limit separate; `get_status()` only reports the current task.
4. **Keep reasoning out of the carried conversation.** The notebook's generated root and analyzer configs set `include_thoughts: false`, with temperature 0.2, top-p 0.95, top-k 40, max output 8,192, and thinking budget 4,096. Our V1 currently sets `include_thoughts: true` and max output 16,384. This is another candidate ablation; do not change it at the same time as the budget policy if we want interpretable results.
5. **Search only after extracting identifiers.** The author recommends searching issue identifiers first and using graph/embedding tools on a confirmed symbol. This is consistent with our V1 prompt's symbol-name requirement. Their published graph-retrieval replay itself yielded zero usable task results, so it provides no quantitative evidence that embeddings beat text search.

The public notebook also contains LoRA adapters. We will **not** adopt those: the current Stage 1 constraint is the competition Gemma 31B base model only, with no training or LoRA.

## What can and cannot be benchmarked like Kagriculture/Pokémon

This is a software-repair benchmark, not a head-to-head game. Kaggle exposes the public score/leaderboard and our own submission status, but there are no last-seven-match replays, opponent move traces, or private leader ZIPs/prompts to download. We can inspect voluntarily published notebooks such as the two above. Actual variant scoring needs the competition task harness and Gemma inference on the Kaggle 4×L4 environment; standard GitHub Actions can poll Kaggle and run CPU-side analysis/preflight, but cannot faithfully run the 31B model.

## Next controlled experiment

Keep the pending V1 artifact unchanged until Kaggle resolves submission `56974591`. Once we have its score—or can establish it is still stuck—make a separate V2 hypothesis and change one main factor at a time. The strongest first candidate is the per-task cap/pacing policy; a later separate run can test `include_thoughts: false`. Preserve the 12-hour global limit as a distinct evaluation constraint, do not treat `get_status()` as a global-progress meter, and keep the no-LoRA/no-training Stage 1 rule.
