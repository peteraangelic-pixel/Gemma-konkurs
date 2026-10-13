V6.4 full-benchmark trace-summary trigger (2026-10-13, after the 30-task kernel finished at 15:18 UTC).

What this runs: gemma-kaggle-v64-benchmark-traces.yml - a READ-ONLY download of the 30-task kernel
outputs plus summarise_agent_traces.py into kaggle_results/v6-4-benchmark/traces. Operational traces
only (tool names, targets, call indices, timings); raw trace_*.json files are not committed.

Purpose: close E6 from GATES_V6_4.md - did the M1-M4 prompt rules change behaviour (edit coverage,
first repository edit within call 4) even though the outcome (10/30) matched V6.3 exactly?
The workflow deletes this file in its results commit.
