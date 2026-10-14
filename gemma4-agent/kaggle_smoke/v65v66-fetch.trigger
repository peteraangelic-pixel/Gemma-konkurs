V6.5/V6.6 recovery fetch trigger (2026-10-14 03:05 UTC).

Context: the two benchmark workflows pushed their kernels successfully but died at the status-poll
step ("Five consecutive Kaggle status API calls failed") because both polled at once. The kernel
references are already recorded:
  V6.5 -> petersharps/gemma-agent-benchmark-cb847599-20261014-024522
  V6.6 -> petersharps/gemma-agent-benchmark-b6686c53-20261014-024548

What this runs: gemma-kaggle-v65v66-fetch.yml - a READ-ONLY re-attach: wait for each kernel to reach
COMPLETE (up to 240 min, tolerating transient API failures), download outputs with
`kaggle kernels output`, copy agent_benchmark_result.json back, summarise the operational traces, and
evaluate the pre-registered expectations mechanically:
  V6.5: repository edit within call 4 >= 12/30 (baseline 1/30)
  V6.6: solved >= 11/30; tasks whose ONLY writes are files outside the repo == 0 (baseline 4)

No GPU work is started and no competition submission is created by this workflow: status checks and
output downloads do not touch the kernels. The workflow deletes this file in its results commit.
