# Read-only Kaggle V2 benchmark check

- Collected (UTC): `2026-10-09T23:49:24+00:00`
- Kernel: [`lauresowe3d/gemma-agent-benchmark-853fe984-20261009-204128`](https://www.kaggle.com/code/lauresowe3d/gemma-agent-benchmark-853fe984-20261009-204128)
- Kaggle status: **COMPLETE**
- Collection mode: read-only; no kernel was started, changed, or stopped.

## Log diagnostics

Fetched 735 raw log lines; decoded 633 messages and found 204 diagnostic lines.

Agent timeout warnings appeared for 17 task(s): `fastapi_14186`, `fastapi_14297`, `fastapi_14458`, `fastapi_14459`, `fastapi_14482`, `fastapi_14487`, `fastapi_14873`, `fastapi_15745`, `httpx_3672`, `requests_6644`, `requests_6757`, `requests_7309`, `rich_2725`, `rich_3043`, `rich_3105`, `rich_3518`, `rich_3934`.

- `[stderr] WARNING:swegemma.graph.retrieval_utils:Could not obtain embedding for node 3104 in repo Textualize/rich.`
- `[stderr] WARNING:swegemma.graph.retrieval_utils:Could not obtain embedding for node test_3104 in repo Textualize/rich.`
- `[stderr] WARNING:swegemma.graph.retrieval_utils:Could not obtain embedding for node test_issue_3104 in repo Textualize/rich.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task rich_3105 agent timed out.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task rich_3105 completed without explicit submit_patch call and no working tree modifications.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox f50ed481-11d, creating venv without pip: Command '['/tmp/swegemma_sandbox_f50ed481-11d_7mlblzvv/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task fastapi_14873 agent timed out.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox fbe4e978-25e, creating venv without pip: Command '['/tmp/swegemma_sandbox_fbe4e978-25e_nfh9uvyk/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox e5eeee7e-6e2, creating venv without pip: Command '['/tmp/swegemma_sandbox_e5eeee7e-6e2_lal6f3l7/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.graph.retrieval_utils:Could not obtain embedding for node EventSource in repo fastapi/fastapi.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox f0f7773a-20e, creating venv without pip: Command '['/tmp/swegemma_sandbox_f0f7773a-20e_7phvlcqg/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox af946c7b-7a8, creating venv without pip: Command '['/tmp/swegemma_sandbox_af946c7b-7a8_r633j7bt/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox eb8e0559-726, creating venv without pip: Command '['/tmp/swegemma_sandbox_eb8e0559-726_qvc4ntju/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 852c05c9-5a1, creating venv without pip: Command '['/tmp/swegemma_sandbox_852c05c9-5a1_hkl7acgc/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox b7851072-c23, creating venv without pip: Command '['/tmp/swegemma_sandbox_b7851072-c23_lzmpzq9n/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 4ede4a54-ddf, creating venv without pip: Command '['/tmp/swegemma_sandbox_4ede4a54-ddf_0qce039q/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task fastapi_14186 agent timed out.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task fastapi_14186 completed without explicit submit_patch call and no working tree modifications.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 742c8c0c-18e, creating venv without pip: Command '['/tmp/swegemma_sandbox_742c8c0c-18e_erxi65r8/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox adcd4aca-bf6, creating venv without pip: Command '['/tmp/swegemma_sandbox_adcd4aca-bf6_tcr5mx5x/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox d7d0d553-56c, creating venv without pip: Command '['/tmp/swegemma_sandbox_d7d0d553-56c_l6uspmua/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task fastapi_14459 agent timed out.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 1d13546c-63d, creating venv without pip: Command '['/tmp/swegemma_sandbox_1d13546c-63d_7ulii3zz/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 67b9ef1d-c91, creating venv without pip: Command '['/tmp/swegemma_sandbox_67b9ef1d-c91_xy_bv8w0/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task requests_6757 agent timed out.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task requests_6757 completed without explicit submit_patch call and no working tree modifications.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox a662b418-5c1, creating venv without pip: Command '['/tmp/swegemma_sandbox_a662b418-5c1_8nvyzxdz/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 3f527681-23e, creating venv without pip: Command '['/tmp/swegemma_sandbox_3f527681-23e_9irox8wm/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox c56f1faa-dc3, creating venv without pip: Command '['/tmp/swegemma_sandbox_c56f1faa-dc3_b33fawyn/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task rich_2725 agent timed out.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 9ba08021-e8c, creating venv without pip: Command '['/tmp/swegemma_sandbox_9ba08021-e8c_dabicr4c/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 19e50277-f88, creating venv without pip: Command '['/tmp/swegemma_sandbox_19e50277-f88_xoe0ky9f/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task requests_7309 agent timed out.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 68e4e38f-ac5, creating venv without pip: Command '['/tmp/swegemma_sandbox_68e4e38f-ac5_q0yo5tcp/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 63c7e887-3d9, creating venv without pip: Command '['/tmp/swegemma_sandbox_63c7e887-3d9_p38bz3db/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task fastapi_14482 agent timed out.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 6ed32bd2-cf4, creating venv without pip: Command '['/tmp/swegemma_sandbox_6ed32bd2-cf4_8v8nig0x/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 50029a69-9c8, creating venv without pip: Command '['/tmp/swegemma_sandbox_50029a69-9c8_l8nfllpt/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task fastapi_15745 agent timed out.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task fastapi_15745 completed without explicit submit_patch call and no working tree modifications.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 96cdc0c1-31f, creating venv without pip: Command '['/tmp/swegemma_sandbox_96cdc0c1-31f_a_s8sg8_/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task fastapi_14458 agent timed out.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox acb87755-f2a, creating venv without pip: Command '['/tmp/swegemma_sandbox_acb87755-f2a_2zamftne/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox e63af4b4-cd5, creating venv without pip: Command '['/tmp/swegemma_sandbox_e63af4b4-cd5_4tdigz_e/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox fddc41e1-22e, creating venv without pip: Command '['/tmp/swegemma_sandbox_fddc41e1-22e_iki_y65d/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 701d1e67-04c, creating venv without pip: Command '['/tmp/swegemma_sandbox_701d1e67-04c_lic6zv43/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`
- `[stderr] WARNING:swegemma.harness.agent_runner:Task httpx_3672 agent timed out.`
- `[stderr] WARNING:swegemma.sandbox.subprocess:ensurepip unavailable in sandbox 73a3453b-aad, creating venv without pip: Command '['/tmp/swegemma_sandbox_73a3453b-aad_alv_2qkz/venv/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.`

## Benchmark output

- Tasks completed/failed: 30 / 30
- Resolved: 10
- Sample estimate (not a Kaggle leaderboard score): `0.3333333333333333`
- 95% Wilson interval: `[0.19230295526846194, 0.5122027418616973]`
- Benchmark wall time: `7779.604047871001` seconds

### Per-task summary

| Task | Repo | Resolved | Tool calls | Error |
|---|---|---:|---:|---|
| requests_6644 | psf/requests | True | 27 |  |
| rich_3934 | Textualize/rich | False | 8 |  |
| fastapi_14851 | fastapi/fastapi | True | 34 |  |
| rich_3718 | Textualize/rich | False | 27 |  |
| fastapi_14266 | fastapi/fastapi | False | 35 |  |
| fastapi_14487 | fastapi/fastapi | False | 20 |  |
| fastapi_14953 | fastapi/fastapi | False | 18 |  |
| rich_3518 | Textualize/rich | True | 35 |  |
| fastapi_14297 | fastapi/fastapi | False | 30 |  |
| rich_3894 | Textualize/rich | True | 13 |  |
| fastapi_14303 | fastapi/fastapi | False | 14 |  |
| rich_3052 | Textualize/rich | False | 17 |  |
| rich_3043 | Textualize/rich | True | 18 |  |
| rich_3105 | Textualize/rich | False | 17 |  |
| fastapi_14873 | fastapi/fastapi | False | 26 |  |
| fastapi_15030 | fastapi/fastapi | False | 19 |  |
| fastapi_15588 | fastapi/fastapi | False | 15 |  |
| rich_3006 | Textualize/rich | True | 20 |  |
| fastapi_14186 | fastapi/fastapi | False | 10 |  |
| rich_3882 | Textualize/rich | True | 16 |  |
| fastapi_14459 | fastapi/fastapi | False | 17 |  |
| requests_6757 | psf/requests | False | 14 |  |
| fastapi_14262 | fastapi/fastapi | False | 32 |  |
| rich_2725 | Textualize/rich | True | 31 |  |
| requests_7309 | psf/requests | False | 33 |  |
| fastapi_14482 | fastapi/fastapi | False | 25 |  |
| fastapi_15745 | fastapi/fastapi | False | 21 |  |
| fastapi_14458 | fastapi/fastapi | True | 20 |  |
| fastapi_14077 | fastapi/fastapi | True | 21 |  |
| httpx_3672 | encode/httpx | False | 7 |  |
