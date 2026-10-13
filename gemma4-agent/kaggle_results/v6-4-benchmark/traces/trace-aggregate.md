# Mechanism metrics per kernel (read-only trace analysis)

Pre-registered as M5 in GATES_V6_4.md; reported next to the resolved count, never instead of it.

| kernel | tasks | write coverage | without any write | median first write | repo-edit coverage | median first repo edit | max consec. submit | max consec. edits | submit calls | repeated submits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `gemma-agent-benchmark-aaea34e4-20261013-122940` | 30 | **26/30** | 4 | 175.5 s (call 10, in-deadline 4/30) | **22/30** | 176.5 s (call 12, in-deadline 1/30) | 0 | 9 | 0 | — |

- `gemma-agent-benchmark-aaea34e4-20261013-122940` tasks with NO repository edit (scratch or nothing at all): fastapi_14266, fastapi_14459, fastapi_15588, fastapi_15745, httpx_3672, rich_3043, rich_3105, rich_3934

- `gemma-agent-benchmark-aaea34e4-20261013-122940` tasks without any write attempt: fastapi_14266, fastapi_14459, rich_3105, rich_3934
- `gemma-agent-benchmark-aaea34e4-20261013-122940` write targets outside the relative tree: /tmp/issue.txt, /tmp/locate.py, /tmp/repro.py
