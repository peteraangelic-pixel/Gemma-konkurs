V6.5 full 30-task trigger (2026-10-14 02:45 UTC, pushed after the L4x4 quota reset).

What this runs: gemma-kaggle-v65-benchmark.yml - the same 30 tasks and seed (20261009) as
V3/V4/V5/V6.1/V6.2/V6.3/V6.4, submission archive gemma4-agent/submission-v6.5.zip =
sha256 cb847599fd64937c6781111ae221912400ec51f4319dfef09c87c5d1f3aceecd, outdir
gemma4-agent/kaggle_results/v6-5-benchmark.

The lever under test (V6.5 = V6.4 + one change): the edit-decision framing. The first edit is to be
made even without certainty that the file is right ("an edit to the wrong candidate is recoverable,
an untouched tree is not"), with the boundary spelled out - "the line between an intended edit and a
dummy is intent, not accuracy". Reason it is being tested: in the V6.4 full run the call-4 deadline
was ignored in 30/30 tasks (repository edit within call 4: 1/30), and the empty trees were not clock
deaths.

Pre-registered expectation R3 (GATES_V6_5.md): repository edits within call 4 rise from 1/30 to
>= 12/30. Also reported: G1/G2/G3 gates, empty trees, solved count, paired against V6.4 (10/30).

The workflow deletes this file in its results commit; do not edit it afterwards.
