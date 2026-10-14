V6.5/V6.6 raw-output diagnostic trigger (2026-10-14 03:00 UTC).

Both benchmark workflows died with "Five consecutive Kaggle status API calls failed", and the
recovery fetch aborted after one second on a status string containing ERROR. Job logs cannot be
read from the session sandbox, so this workflow captures the raw Kaggle CLI output to
gemma4-agent/kaggle_results/v65v66-diagnostics/raw-cli.txt and commits it.

What it prints: the kaggle CLI version, 'kernels list --mine' (so the kernels' real states are
visible), 'kernels status' and 'kernels files' for
  petersharps/gemma-agent-benchmark-cb847599-20261014-024522 (V6.5)
  petersharps/gemma-agent-benchmark-b6686c53-20261014-024548 (V6.6)
Read-only: no kernel is started, stopped or modified; no competition submission is created.
The workflow deletes this file in its results commit.
