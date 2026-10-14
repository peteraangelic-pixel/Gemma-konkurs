V6.4 raw-trace diagnosis trigger (2026-10-14, no GPU, read-only).

Downloads the output of the completed V6.4 kernel
petersharps/gemma-agent-benchmark-aaea34e4-20261013-122940 and extracts every tool call with its
arguments plus the observation that followed it, then commits
gemma4-agent/analysis/diagnostics-2026-10-14/v64-raw-calls.md.

Questions it answers, both from ANALYSIS_2026-10-14_FAILURE_MAP.md:
- the 11 "no change in the repository" tasks: three of them called edit_file and still produced an
  empty diff (fastapi_14851 -> fastapi/routing.py, fastapi_14487 -> a docs file, requests_6757 ->
  tox.ini twice). Did the call error out (old_string not found), or was the change reverted?
- the 8 "gold file edited, tests failed" tasks: which commands ran before the edit, in what order,
  and what did the edits carry (lengths only, no content).

No kernel is started or stopped; no model prose is committed; the raw traces stay out of git.
