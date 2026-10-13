V6.4 full 30-task trigger (2026-10-13, pushed after the user chose "both").

What this runs: gemma-kaggle-v64-benchmark.yml - the same 30 tasks and seed (20261009) as
V3/V4/V5/V6.1/V6.2/V6.3, submission archive gemma4-agent/submission-v6.zip =
sha256 aaea34e439c8c36d..., outdir gemma4-agent/kaggle_results/v6-4-benchmark.

This run is INFORMATIONAL ONLY. It cannot lead to submitting V6.4: the rule frozen before the runs
requires G1-G3 = 0 in both screens, and the mini-screen already has G2 = 1 (rich_3105 ended empty
after 106.9 s). The question it answers is whether turning empty trees into patches changes the
solved count on this sample - the mini showed 0 -> 1348 B and 0 -> 377 B but no new solves.

The workflow deletes this file in its results commit; do not edit it afterwards.
