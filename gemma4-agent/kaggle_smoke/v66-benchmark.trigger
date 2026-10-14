V6.6 full 30-task trigger (2026-10-14 02:46 UTC, pushed after the L4x4 quota reset).

What this runs: gemma-kaggle-v66-benchmark.yml - the same 30 tasks and seed (20261009) as
V3/V4/V5/V6.1/V6.2/V6.3/V6.4, submission archive gemma4-agent/submission-v6.6.zip =
sha256 b6686c5323dfac9013470c5849efba36e790c170090fc7ac166c19ca884e8dd6, outdir
gemma4-agent/kaggle_results/v6-6-benchmark.

The lever under test (V6.6 = V6.4 + one change): the locator step no longer writes a scratch file.
The same script runs inline as the -c argument in ONE command, with the issue text on stdin.
Reason it is being tested: in the V6.4 full run four sessions wrote /tmp/locate.py and then never
edited the repository at all - fastapi_15588 and fastapi_15745 stopped after THREE tool calls,
treating the finished script as the work - and versions without a locator step (V3/V4/V5) had 6
empty trees against 11 for V6.x.

Pre-registered expectations (GATES_V6_6.md): R1 tasks whose only write is a file outside the
repository drop from 4 to 0; R2 solved tasks >= 11/30 (V6.4 and V6.3: 10/30). Also reported: the
G1/G2/G3 gates, empty trees, and the paired comparison against V6.4.

The workflow deletes this file in its results commit; do not edit it afterwards.
