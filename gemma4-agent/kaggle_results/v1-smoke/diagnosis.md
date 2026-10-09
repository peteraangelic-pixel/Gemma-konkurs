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

The assertion followed a call to the wheelhouse's `adk_submission.discover_adapters`. The exact V1 ZIP has ten entries and no `adapters/` directory, so this is another smoke-harness/helper mismatch; vLLM startup, official Evaluator loading, and V1 agent configuration were not reached. The runner has now been adjusted to verify the archive has no `adapters/` directory and pass an explicit empty adapter list with LoRA disabled. All generated notebook code cells compile locally, and a local check confirmed the exact ZIP still has its expected SHA-256 and no adapter directory. This fix has not yet run on Kaggle.

None of the three attempts created an official competition submission or score. The exact V1 archive remains unchanged (`af4fbb0170a8e191a81881fabb1fa18856e0bff71975499248243cc99a66c3f6`). Kaggle reported `RUNNING` during the second and third attempts, but actual GPU quota use remains unconfirmed.
