# V1 private smoke attempts — diagnosis

## Attempt 1: Kaggle image / wheelhouse mismatch

The first private notebook failed in its setup cell, before extracting `submission.zip`, loading the V1 ADK configuration, or starting Gemma. The log shows Python 3.13 executing the wheelhouse install, which aborts on a CPython 3.12-only wheel:

```text
ERROR: apache_tvm_ffi-0.1.13.post3-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl is not a supported wheel on this platform.
```

The runner was changed to pin the known Python 3.12 / CUDA 12.8 image and to fail early if the requested Python version is not active.

## Attempt 2: stale smoke-helper import

The pinned image worked: the Python 3.12 preflight, wheel installation, V1 ZIP extraction/hash check, and public task selection all completed. The notebook then failed before vLLM startup with:

```text
ModuleNotFoundError: No module named 'swegemma.models.discovery'
```

A read-only inspection of the current Kaggle wheelhouse found `swegemma-0.2.11-py3-none-any.whl`, which does not contain `swegemma/models/discovery.py`. This was a stale smoke-runner helper import, not evidence of a V1 loader defect. The runner was changed to read model declarations from the ZIP's YAML files and leave official submission validation to the Evaluator.

## Attempt 3: adapter-discovery assumption in the smoke runner

The Python 3.12 preflight, offline wheel installation, exact V1 ZIP hash/extraction, public task selection, L4x4 checks, and YAML model preflight all completed. The runner then stopped at its own no-LoRA assertion:

```text
AssertionError: This V1 smoke run is configured without LoRA adapters.
```

The assertion followed a call to the wheelhouse's `adk_submission.discover_adapters`. The exact V1 ZIP has ten entries and no `adapters/` directory, so this was another smoke-harness/helper mismatch; vLLM startup, official Evaluator loading, and V1 agent configuration were not reached. The runner was adjusted to verify that the archive has no `adapters/` directory and pass an explicit empty adapter list with LoRA disabled.

## Attempt 4: end-to-end one-task run

The final authorized private run passed the corrected preflight, loaded the exact V1 archive, started model-backed evaluation on four L4 GPUs, and completed the notebook without hanging. Kaggle reported `KernelWorkerStatus.COMPLETE`. The evaluator ran public task `fastapi_15588`, recorded 22 tool calls over 251.3 seconds, and generated a 1,672-character patch (`v1_smoke_patch.diff`).

The task was **not resolved** (`resolved: false`; `test_exit_code: 1`). The read-only notebook log identifies the cause:

```text
WARNING:swegemma.harness.agent_runner:Task fastapi_15588 agent timed out.
```

The configured **per-task** limit was 4 minutes; the reported duration was about 4 minutes 11 seconds. This is evidence of a task-agent timeout, not a Kaggle loader hang. The partial patch attempted newline validation for Server-Sent Event `event` and `id` fields in `fastapi/sse.py`, but the task was not resolved. This smoke does not establish that V1 solves the task, only that it loads and runs through the evaluator on this public example before hitting its per-task budget.

## Scope and artifacts

All four attempts were private one-task simulations, not competition submissions. None created an official submission or score. The exact V1 archive is unchanged, with SHA-256 `af4fbb0170a8e191a81881fabb1fa18856e0bff71975499248243cc99a66c3f6`. Actual GPU quota use remains unconfirmed; Kaggle reported `RUNNING` during attempts 2–4, but this workflow cannot query quota billing. No further GPU run is authorized or being started. The final run record and one-task output are in `run.json`, `v1_smoke_result.json`, and `v1_smoke_patch.diff` in this directory.
