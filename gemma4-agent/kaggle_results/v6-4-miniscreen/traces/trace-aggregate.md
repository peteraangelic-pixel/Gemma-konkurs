# Mechanism metrics per kernel (read-only trace analysis)

Pre-registered as M5 in GATES_V6_4.md; reported next to the resolved count, never instead of it.

| kernel | tasks | write coverage | without any write | median first write | repo-edit coverage | median first repo edit | max consec. submit | max consec. edits | submit calls | repeated submits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `gemma-agent-benchmark-aaea34e4-20261013-111908` | 6 | **3/6** | 3 | 181.4 s (call 7, in-deadline 0/6) | **3/6** | 181.4 s (call 7, in-deadline 0/6) | 0 | 6 | 0 | — |

- `gemma-agent-benchmark-aaea34e4-20261013-111908` tasks with NO repository edit (scratch or nothing at all): fastapi_15745, rich_3043, rich_3105

- `gemma-agent-benchmark-aaea34e4-20261013-111908` tasks without any write attempt: fastapi_15745, rich_3043, rich_3105
