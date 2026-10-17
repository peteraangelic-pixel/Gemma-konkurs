Re-arm V7-b after the two-second guard failure.

The first attempt fired at 2026-10-17 00:05:05 UTC and was refused: V6.12 had gone up at
2026-10-16 00:05:07, exactly one day earlier, so the rolling 24-hour window was 23 h 59 m 58 s old
and the guard blocked the upload. Nothing was submitted (see kaggle_results/v7b-official-submission.json,
status daily_slot_guard_blocked). The guard now tolerates five minutes on the rolling window, and the
arming step reads the receipts instead of guessing: the newest recorded submission is V6.12 from
2026-10-16 00:05 UTC, more than 24 hours ago, so this push uploads immediately rather than sleeping.

Unchanged: submission-v7b.zip, sha256 e35f20ab1361450d1877010188620d130117e657492a7b48d2c49d681086886e,
message V7b. V7-b is the V5 archive - the only configuration with a positive official score, 0.13 -
plus exactly ONE appended sentence: put the edit on disk before verifying, and keep every command
bounded (timeout 45). agent.yaml, eval_config.yaml and configs/sampling.yaml are byte-identical to
V5; tools/check_v7b_delta.py proves that claim and its --mutate mode exercises all six checks.

The guard chain still runs before anything is uploaded: pinned sha256, duplicate-message check,
one-submission-per-day, rolling 24 h with tolerance, then post-upload history reconciliation.
