# V1 private smoke — failure diagnosis

The private notebook failed in its first setup cell, before extracting `submission.zip`, loading the V1 ADK configuration, or starting Gemma. The log shows Python 3.13 executing the wheelhouse install, which aborts on the CPython 3.12-only wheel:

```text
ERROR: apache_tvm_ffi-0.1.13.post3-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl is not a supported wheel on this platform.
```

This identifies a Kaggle runtime / competition-wheelhouse mismatch in the smoke notebook, not a demonstrated V1 loader defect. The V1 archive itself was unchanged. The runner is now pinned to the known Python 3.12 / CUDA 12.8 Kaggle image used by the public starter and checks the Python version before installing wheels; that remote pin has not yet been tested.

GPU quota use for this failed run remains **unconfirmed**: the runner did not observe a `RUNNING` status, and that observation is not proof that Kaggle charged no quota. No competition submission was created.
