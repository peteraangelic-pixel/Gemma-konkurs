V6.4 trace-summary trigger (2026-10-13, after the mini-screen finished at 12:03 UTC).

What this runs: gemma-kaggle-v64-traces.yml - a READ-ONLY download of the mini-screen kernel
outputs plus summarise_agent_traces.py into kaggle_results/v6-4-miniscreen/traces. Operational
traces only (tool names, targets, call indices, timings); no raw reasoning is read or stored,
and the raw trace_*.json files are not committed.

Needed because P1 (repository edit within call 4), P3 (submit_patch absent) and P4 (edit loop
broken) cannot be evaluated from the result JSON alone. The workflow deletes this file in its
results commit.
