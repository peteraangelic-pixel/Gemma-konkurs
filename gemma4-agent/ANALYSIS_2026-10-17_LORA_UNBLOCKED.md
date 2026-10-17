# LoRA is not blocked — the wall was a stale module

**Date:** 2026-10-17 · **Status:** the LoRA arm is open; no GPU was spent to establish this.

## What we believed this morning

Four GPU smoke kernels died at the same line:

```
ValueError: The checkpoint you are trying to load has model type `gemma4` but Transformers does
not recognize this architecture
```

Installed: `transformers 5.0.0`, no `trl`, and installing all 41 competition wheels did not change
the reported version (`gemma4 recognised: False`). The working assumption was that the checkpoint
was unloadable and the LoRA arm was dead.

## What was actually happening

A CPU probe on the **competition image itself** (same BYOD digest, `enable_gpu: false`, no quota)
installed the same 41 wheels and printed:

```
Successfully installed ... transformers-5.13.1 ...
```

and then, one line later, still `transformers 5.0.0`. Both are true: pip replaced the files on disk,
but the notebook's own preflight cell had already imported transformers 5.0.0, and **pip never
replaces a module that is already in `sys.modules`**. `transformers 5.13.1` ships
`transformers/models/gemma4/`, `gemma4_assistant/`, `gemma4_unified/` — the architecture was there
all along.

After purging the cached modules and importing again, on the same image, same wheels, same
checkpoint:

```
python: 3.12.13
after_install: transformers 5.13.1, vllm 0.19.1, swegemma 0.2.11, peft 0.19.1,
               bitsandbytes 0.46.1, compressed-tensors 0.15.0.1
config_model_type: gemma4
config_architectures: ["Gemma4ForConditionalGeneration"]
autoconfig_plain: OK (Gemma4Config)
transformers_gemma_dirs: gemma, gemma2, gemma3, gemma3n, gemma4, gemma4_assistant,
                         gemma4_unified, gemma4_unified_assistant
```

The same trap exists for `safetensors`: the probe's version table imports 0.7.0, the wheelhouse
installs 0.8.0, and the stale module rejects the `backend=` keyword that transformers 5.13.1 passes
to `safe_open`. Both purges are now in `tools/diagnose_gemma4_env.py` and in the SFT launcher's
wheelhouse cell.

## The submission can carry an adapter — verified, not assumed

Read out of the organisers' own wheels (`adk_submission 0.2.13`, `swegemma 0.2.11`), and reproduced
on CPU with a real `adapters/main_lora/` directory:

| check | result |
| --- | --- |
| `discover_adapters(submission)` | `{"main_lora": {path: .../adapter_model.safetensors, rank: 8}}` |
| `validate_directory(submission)` | accepted; adapter file listed in `adapter_files` |
| `agent.yaml` with `adapter: main_lora` | loads; parsed config returns `adapter == "main_lora"` |
| agent schema fields | include `adapter` — *"Name of a discovered adapter from `adapters/` to attach to the base model"* |
| `adk_submission.server.VllmConfig` | `enable_lora: bool = True`, `max_loras`, `max_lora_rank` |
| vLLM command built by `VllmServer` | `--max-lora-rank <rounded-up>`, `--lora-modules name=path` |
| submission size cap | 3 GiB total, **including adapters**; `.safetensors` is an allowed extension |
| rank inference | read from `adapter_config.json` or safetensors metadata, rounded up to a vLLM bucket |

So the scoring path is: the submission ships `adapters/<name>/adapter_model.safetensors` +
`adapter_config.json`, `agent.yaml` declares `adapter: <name>`, the harness's vLLM server mounts it,
and `resolve_swegemma_adapter` points the agent's model alias at it.

## The checkpoint

From the CPU probe of the real files:

| property | value |
| --- | --- |
| text layers | 60 |
| hidden size | 5376 |
| attention heads | 32 (16 KV) |
| quantization | compressed-tensors `pack-quantized`, 4-bit, group size 32, symmetric |
| tensor naming | `model.language_model.layers.N.self_attn.{q,k,v,o}_proj` |
| ignored (bf16) | vision tower, `embed_vision`, `lm_head` |
| weights on disk | 2009 tensors, 820 of them packed/scaled |

That naming matters twice: it is what peft must attach to, and it is what vLLM must map an adapter
onto.

## Plan and cost

1. **CPU (free):** load the checkpoint, attach LoRA, one backward pass. Running now. If peft cannot
   wrap compressed-tensors layers, the arm closes without GPU spend.
2. **GPU canary (~20-30 min wall ≈ 1-2 h of quota):** train a few steps, save the adapter, start
   `VllmServer` exactly as the harness does with the adapter mounted, and verify the served model
   changes. This is the risky half: a bad adapter must never reach a scored submission.
3. **GPU training (only if 2 passes):** 1-2 epochs over the public tasks' reference patches at rank
   8 on q/k/v/o, 60 layers. Model load dominates; the step count is small.
4. **Gate:** the adapter ships only if it beats the base model on held-out tasks with the same
   prompt (G-holdout), and only after the vLLM mount test passes on the exact adapter file.

## What this does not fix

An adapter is one lever and it is not free: it changes the model under every prompt we have
measured, so V5's 0.13 is not a valid baseline for it. The empty-tree problem (7/30 in the V7-c
screen, 4 of them ending well before the clock) is an agent-behaviour problem and stays with V7-b
and its successors. The two can be combined later, but not in the same measured step.
