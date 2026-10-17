Run the LoRA pipeline in SMOKE mode: the canary, a four-example micro-training and a two-task
holdout. This is the gate that decides whether the whole adapter road is real for us, and it is
deliberately cheap.

The canary builds a random rank-8 adapter over every layer's q_proj and o_proj and checks that it
moves the model's top-5 logprobs. peft zero-initialises the B matrix, so an adapter that "looks
inert" usually means the serving path never applied it - and the sample adapter in the host's
response patched only layer 0 of 60, which is exactly how that mistake survives unnoticed.
Then QLoRA rank 8 on q/k/v/o in 4-bit over four examples, then the paired holdout check: the same
prompts with and without the adapter, comparing which files the produced diffs touch against the
gold files.

Base: submission-v5 (the only configuration with a positive official score, 0.13), so the adapter
learns the prompt it will be served with. The dataset builder's locator argument points at the
evolved locator from another tree because V5 ships none.

Nothing here creates a competition submission. The adapter and metrics come back as artifacts.
If the canary fails, the answer is "adapters do not work through our path" and we stop - which is
worth knowing for the cost of one cheap GPU run.

Retry after recording the CLI stderr: the first push exited 1 with no stdout, so we could not see why.

Third attempt: the notebook is now nbformat-4.5 valid.
