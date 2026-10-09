# V1 private smoke attempts — diagnosis

## Attempt 1: Kaggle image / wheelhouse mismatch

The first private notebook failed in its setup cell, before extracting `submission.zip`, loading the V1 ADK configuration, or starting Gemma. The log shows Python 3.13 executing the wheelhouse install, which aborts on a CPython 3.12-only wheel:

```text
ERROR: apache_tvm_ffi-0.1.13.post3-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl is not a supported wheel on this platform.
```

The runner was changed to pin the known Python 3.12 / CUDA 12.8 image and to fail early if the requested Python version is not active.

## Attempt 2: smoke-helper import mismatch

The pinned image worked: the Python 3.12 preflight, wheel installation, V1 ZIP extraction/hash check, and public task selection all completed. The notebook then failed in the smoke runner's pre-model setup cell:

```text
ModuleNotFoundError: No module named 'swegemma.models.discovery'
```

This was an import used by the smoke runner to validate the declared model before vLLM startup; the official Evaluator and V1 agent configuration were not reached. A read-only inspection of the current Kaggle wheelhouse found `swegemma-0.2.11-py3-none-any.whl`, which does not contain `swegemma/models/discovery.py`; the imported starter helper is stale for this wheel. The runner has now been changed to read model declarations from the ZIP's YAML files and leave official submission validation to the Evaluator. That code change has only been checked statically; it has not been run on Kaggle.

Neither attempt produced an official competition submission or an official score. The V1 archive remains unchanged. GPU quota use is **unconfirmed** for both attempts; Kaggle reported `RUNNING` during the second, but this runner does not query quota billing.
