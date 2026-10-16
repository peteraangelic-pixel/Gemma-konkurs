Arm the V7-b send for 2026-10-17 00:05 UTC (02:05 Warsaw), the moment the daily submission slot
refreshes. Pushing this file starts the job immediately; its first step sleeps until 00:05 UTC and
then uploads, so nothing needs to happen at 2 a.m. local time.

V7-b = the V5 archive (the only configuration with a positive official score, 0.13) plus exactly ONE
appended sentence: put the edit on disk before verifying, and keep every command bounded. Three of
the four files (agent.yaml, eval_config.yaml, configs/sampling.yaml) are byte-identical to V5 and
tools/check_v7b_delta.py proves that claim, with all six of its checks exercised by --mutate. The
sentence targets the measured mechanism behind V5's six guaranteed zeros: on the V5 screen every
empty-patch session had exit=-1, five of six died on the clock (298-325 s of the 315 s cap) and one
burned 227 s inside a single unbounded command.

Why one lever: V6.12 scored 0.08 against V5's 0.13 while moving five things at once, so the result
could not be attributed to any of them - see ANALYSIS_2026-10-16_V6_12_RESULT.md. The V5 base is
restored and from here each submission moves a single factor.

Guard chain, unchanged: pinned sha256 (e35f20ab1361450d1877010188620d130117e657492a7b48d2c49d681086886e),
duplicate-message check, one-submission-per-day and rolling 24 h guards, then a history reconciliation
that records kaggle_results/v7b-official-submission.json.

Retry note (2026-10-16 19:35 UTC): the first push of this file also carried the workflow change itself, and no run
was created for it - the hypothesis is that the push filter was evaluated with the previously
registered definition, whose paths list did not yet name this file. This commit touches only the
trigger, so the new definition is already in place.
