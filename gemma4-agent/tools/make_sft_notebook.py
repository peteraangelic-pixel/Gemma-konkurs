#!/usr/bin/env python3
"""Emit kaggle_smoke/gemma-lora-sft-v1.ipynb - the canary + QLoRA pipeline for the LoRA lever.

Why a generator and not a hand-written notebook: the notebook must stay reproducible from the
repository (the prompt, the locator and the dataset builder are read from this branch), and a
generator keeps the cells reviewable in a diff. The emitted notebook is deliberately defensive:
every heavy step is wrapped, prints what it found, and stops with a clear message instead of
burning a GPU session on a broken assumption.

What the notebook does, in order (see SFT_PLAN.md for the gates):

  0. environment + build fingerprint (swegemma/adk_submission file hashes; kaggle discussion 748323
     shows the harness changes between wheelhouse builds without a version bump)
  1. clone this branch (prompt + locator + tools/build_sft_dataset.py come from the repo, not from
     a copy pasted into the notebook)
  2. build the SFT dataset from tasks.jsonl + snapshots/  (CPU; prints locator gold ranks)
  3. CANARY: write a rank-8 adapter over every layer of q_proj/o_proj with non-zero random weights,
     start vLLM with enable_lora=True, and require a measurable logprob shift against the base
     model - the host confirmed on 2026-10-15 that adapters are applied in scoring, but the whole
     cost of training is wasted if our own serving path silently ignores them
  4. QLoRA SFT on the train split (4-bit, rank 8, attention-only, assistant-only loss)
  5. holdout check: does the adapter make the model produce patches that touch the gold file, and
     does it beat the untuned model on the same prompts?
  6. package adapters/main_lora into a submission.zip and print its sha256. It does NOT submit.

    python3 gemma4-agent/tools/make_sft_notebook.py            # writes the notebook
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "gemma4-agent" / "kaggle_smoke" / "gemma-lora-sft-v1.ipynb"
BRANCH = "arena/c4eeb067-gemma-konkurs"
REPO = "https://github.com/peteraangelic-pixel/Gemma-konkurs"

HEADER = """\
# Gemma 4 Developer Agent — LoRA pipeline v1 (canary + QLoRA + holdout check)

**Why:** every public measurement we could find (see `RESEARCH_2026-10-15_EXTERNAL.md`) says
prompt/scaffold work plateaus at 0.10–0.14 — the score we already have — and that the entries above
0.18 post-trained the model. The competition allows PEFT LoRA adapters in the submission, and the
host confirmed (discussion 749528) that adapters **are** applied in scoring: the sample adapter only
looked inert because it touches layer 0 of 60.

**What this notebook is not:** it is not a submission. It does not push anything to Kaggle scoring.
It builds data, proves the adapter path works end to end, trains one small adapter and measures it on
a held-out split. Submitting is a separate, explicit decision.

**Cost:** step 2 and 3 are CPU/serving; step 4 is the only training step. With `SMOKE = True` the
whole notebook should fit in a few minutes; set `SMOKE = False` for the real run (~1–2 h on L4×4
for 129 examples at rank 8, plus serving time for the canary and the holdout check).

**Gates (pre-registered, from `SFT_PLAN.md`):**
- G-canary: with a random rank-8 adapter over all layers, the top-5 logprobs must move by > 0.05
  nats on at least one token, or the adapter ranking must change. Otherwise: STOP, the training
  would be wasted.
- G-holdout: on the held-out tasks, the adapter must raise the share of generated patches that
  touch the gold file above the untuned model's share on the *same* prompts (paired, same seed).
- G-screen: only after both, the adapter goes into a V6.11 submission and runs the official 30-task
  screen — the same gate every prompt arm had to pass.
"""

SETUP = '''\
import hashlib, json, os, random, re, shutil, subprocess, sys, time, zipfile
from pathlib import Path

SMOKE = True                 # False = the real run (full dataset, full epochs)
REPO_BRANCH = "arena/c4eeb067-gemma-konkurs"
REPO_URL = "https://github.com/peteraangelic-pixel/Gemma-konkurs"
WORK = Path("/kaggle/working")
REPO_DIR = WORK / "repo"
DATA_DIR = Path("/kaggle/input/gemma-4-developer-agent")
TASKS = DATA_DIR / "tasks.jsonl"
SNAPSHOTS = DATA_DIR / "snapshots"
SFT_DIR = WORK / "sft"
ADAPTER_DIR = WORK / "main_lora"

def sh(cmd, check=True, **kw):
    print("$", cmd if isinstance(cmd, str) else " ".join(cmd), flush=True)
    return subprocess.run(cmd, shell=isinstance(cmd, str), check=check,
                          capture_output=True, text=True, **kw)

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

for p, label in ((TASKS, "tasks.jsonl"), (SNAPSHOTS, "snapshots/")):
    print(f"{label:14}: {'FOUND' if p.exists() else 'MISSING'}  {p}")

# Build fingerprint first: discussion 748323 shows the wheelhouse changes between builds without a
# version bump, so a rule measured on one build may not hold on the next.
for mod in ("swegemma", "adk_submission"):
    try:
        import importlib.util
        spec = importlib.util.find_spec(mod)
        print(f"{mod}: {spec.origin if spec else 'not importable here'}")
        if spec and spec.origin:
            print("   sha256:", sha256(spec.origin))
    except Exception as exc:
        print(f"{mod}: {exc}")
print("python:", sys.version.split()[0])
for mod in ("torch", "transformers", "peft", "trl", "vllm"):
    try:
        m = __import__(mod)
        print(f"{mod}: {getattr(m, '__version__', 'unknown')}")
    except Exception as exc:
        print(f"{mod}: not importable ({exc})")
'''

CLONE = '''\
if not REPO_DIR.exists():
    r = sh(["git", "clone", "--depth", "1", "--branch", REPO_BRANCH, REPO_URL, str(REPO_DIR)], check=False)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit("Could not clone the repository. Upload it as a private dataset and set "
                         "REPO_DIR by hand instead - the prompt, locator and dataset builder must "
                         "come from the same commit as the submitted artefact.")
print("prompt:", (REPO_DIR / "gemma4-agent/submission-v6.11/prompts/system.md").stat().st_size, "chars")
print("locator:", sha256(REPO_DIR / "gemma4-agent/submission-v6.11/tools/locate.py")[:16])
'''

DATASET = '''\
limit = 6 if SMOKE else 0        # a 6-task smoke set keeps the first run cheap
cmd = [sys.executable, str(REPO_DIR / "gemma4-agent/tools/build_sft_dataset.py"),
       "--tasks", str(TASKS), "--snapshots", str(SNAPSHOTS),
       "--locator", str(REPO_DIR / "gemma4-agent/submission-v6.11/tools/locate.py"),
       "--outdir", str(SFT_DIR)]
if limit:
    cmd += ["--limit", str(limit)]
r = sh(cmd, check=False)
print(r.stdout[-4000:])
print(r.stderr[-2000:])
summary = json.loads((SFT_DIR / "sft_summary.json").read_text()) if (SFT_DIR / "sft_summary.json").exists() else {}
print(json.dumps(summary, indent=2))
train_rows = [json.loads(l) for l in (SFT_DIR / "sft_train.jsonl").read_text().splitlines() if l.strip()]
holdout_rows = [json.loads(l) for l in (SFT_DIR / "sft_holdout.jsonl").read_text().splitlines() if l.strip()]
print("train examples:", len(train_rows), "holdout examples:", len(holdout_rows))
'''

CANARY = '''\
# --- CANARY: does OUR serving path actually apply an adapter? --------------------------------
# A random rank-8 adapter over every layer of q_proj/o_proj must move the model's top-5 logprobs.
# Zero-initialised LoRA (peft's default B=0) would change nothing, so the weights are randomised.
# Host confirmation (discussion 749528) says the scoring environment applies adapters; this checks
# that OUR path does, before any training time is spent.
import torch
from safetensors.torch import save_file

RANK = 8
def write_canary_adapter(dest: Path, layers: int, hidden: int, rank: int = RANK):
    dest.mkdir(parents=True, exist_ok=True)
    tensors = {}
    for layer in range(layers):
        for proj in ("q_proj", "o_proj"):
            base = f"base_model.model.model.language_model.layers.{layer}.self_attn.{proj}"
            tensors[f"{base}.lora_A.weight"] = torch.randn(rank, hidden) * 0.02
            tensors[f"{base}.lora_B.weight"] = torch.randn(hidden, rank) * 0.02
    save_file(tensors, str(dest / "adapter_model.safetensors"))
    (dest / "adapter_config.json").write_text(json.dumps({
        "peft_type": "LORA", "task_type": "CAUSAL_LM", "r": rank, "lora_alpha": 2 * rank,
        "lora_dropout": 0.0, "bias": "none", "target_modules": ["q_proj", "o_proj"],
        "base_model_name_or_path": "gemma-4-31b-it-qat-w4a16-ct",
    }, indent=2) + "\\n")
    return tensors

canary_dir = WORK / "canary_lora"
# read the real geometry from the config instead of trusting 60 layers / 4096 hidden states
from transformers import AutoConfig
cfg = AutoConfig.from_pretrained("gemma-4-31b-it-qat-w4a16-ct")
layers = getattr(getattr(cfg, "text_config", cfg), "num_hidden_layers")
hidden = getattr(getattr(cfg, "text_config", cfg), "hidden_size")
print("geometry: layers", layers, "hidden", hidden)
write_canary_adapter(canary_dir, layers, hidden)
print("canary adapter tensors:", len(list(canary_dir.rglob("*.safetensors"))))

canary_submission = WORK / "canary_submission"
shutil.rmtree(canary_submission, ignore_errors=True)
(canary_submission / "adapters").mkdir(parents=True, exist_ok=True)
shutil.copytree(canary_dir, canary_submission / "adapters" / "main_lora")

server = None
try:
    from swegemma.serving import VllmServer, VllmConfig           # organisers' wheelhouse
    server = VllmServer(VllmConfig(model="gemma-4-31b-it-qat-w4a16-ct", tensor_parallel_size=4,
                                   max_model_len=32768, gpu_memory_utilization=0.90,
                                   enable_lora=True, max_loras=8, max_lora_rank=128))
    server.start()
    base_url = server.base_url
except Exception as exc:
    print("swegemma serving helper unavailable (", exc, ") - falling back to the vLLM CLI")
    port = 8000
    proc = subprocess.Popen(
        ["python", "-m", "vllm.entrypoints.openai.api_server",
         "--model", "gemma-4-31b-it-qat-w4a16-ct", "--tensor-parallel-size", "4",
         "--max-model-len", "32768", "--gpu-memory-utilization", "0.90",
         "--enable-lora", "--max-loras", "8", "--max-lora-rank", "128",
         "--lora-modules", f"main_lora={canary_submission / 'adapters' / 'main_lora'}",
         "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base_url = f"http://127.0.0.1:{port}/v1"
    for _ in range(120):                                        # up to 20 minutes to load
        if "Uvicorn running" in (proc.stdout.readline() or ""):
            break
        time.sleep(10)
    class _S:
        def stop(self):
            proc.terminate()
    server = _S()

try:
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key="none")
    ids = [m.id for m in client.models.list().data]
    print("served model ids:", ids)
    base_id = next((i for i in ids if "gemma-4-31b" in i and "lora" not in i), ids[0])
    adapter_id = next((i for i in ids if "main_lora" in i), None)
    if adapter_id is None:
        raise SystemExit("G-canary: FAIL - the adapter is not registered as a served model id")
    prompt = "List the first ten prime numbers."
    def top5(model_id):
        r = client.completions.create(model=model_id, prompt=prompt, max_tokens=1,
                                      temperature=0, logprobs=5)
        return r.choices[0].logprobs.top_logprobs[0]
    b, t = top5(base_id), top5(adapter_id)
    names = list(b)[:5]
    deltas = [abs(b[n] - t.get(n, -99.0)) for n in names]
    print("base   :", b)
    print("adapter:", t)
    print("|delta|:", [round(d, 4) for d in deltas], "max:", round(max(deltas), 4))
    CANARY_OK = max(deltas) > 0.05 or names[0] != list(t)[0]
    print("G-canary:", "PASS" if CANARY_OK else "FAIL")
    if not CANARY_OK:
        raise SystemExit("G-canary FAILED - the adapter is ignored by this serving path. Stop: "
                         "training it would be wasted. Fix serving or the adapter layout first.")
finally:
    if server is not None:
        server.stop()
'''

TRAIN = '''\
# --- QLoRA: rank 8, attention-only, assistant-only loss --------------------------------------
import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
from trl import SFTTrainer

MODEL = "gemma-4-31b-it-qat-w4a16-ct"
tokenizer = AutoTokenizer.from_pretrained(MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

def to_text(row):
    # include the real system prompt so the adapter learns the deployed contract, not a summary
    system = (REPO_DIR / "gemma4-agent/submission-v6.11/prompts/system.md").read_text(encoding="utf-8")
    messages = [{"role": "system", "content": system}] + row["messages"][1:]
    return tokenizer.apply_chat_template(messages, tokenize=False)

rows = train_rows[:4] if SMOKE else train_rows
train_ds = Dataset.from_list([{"text": to_text(r)} for r in rows])
holdout_rows = holdout_rows[:2] if SMOKE else holdout_rows
print("train rows:", len(train_ds), "holdout rows:", len(holdout_rows))

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb, device_map="auto")
model = prepare_model_for_kbit_training(model)
lora = LoraConfig(r=8, lora_alpha=16, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
                  # attention-only on ALL layers: the sample adapter's layer-0-only config is why
                  # adapters looked inert; rank stays small because the KV cache shrinks with it
                  target_modules=["q_proj", "k_proj", "v_proj", "o_proj"])
model = get_peft_model(model, lora)
model.print_trainable_parameters()

args = TrainingArguments(
    output_dir=str(WORK / "sft_trainer"),
    per_device_train_batch_size=1, gradient_accumulation_steps=4,
    num_train_epochs=1 if SMOKE else 2, learning_rate=1e-4, lr_scheduler_type="cosine",
    warmup_ratio=0.03, logging_steps=1, save_strategy="no", bf16=True, max_grad_norm=1.0,
    gradient_checkpointing=True, report_to=[],
)
trainer = SFTTrainer(model=model, args=args, train_dataset=train_ds,
                     dataset_text_field="text", max_seq_length=4096, packing=False)
trainer.train()
model.save_pretrained(str(ADAPTER_DIR))
tokenizer.save_pretrained(str(ADAPTER_DIR))
print("adapter saved:", sorted(p.name for p in ADAPTER_DIR.iterdir()))
'''

HOLDOUT = '''\
# --- holdout check: does the adapter move the model towards the gold files? -------------------
# Cheap proxy for the harness: generate a patch for each held-out task with the adapter active and
# with it disabled (same prompts, greedy decoding), and compare which files the produced diffs
# touch against the gold files. Paired by construction: same model, same prompts, same seed.
meta = {}
if (SFT_DIR / "sft_meta.jsonl").exists():
    for line in (SFT_DIR / "sft_meta.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            meta[row.get("instance_id", "")] = row

def generate(model_ref, tok, messages, max_new_tokens=1024):
    ids = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt").to(model_ref.device)
    out = model_ref.generate(ids, max_new_tokens=max_new_tokens, do_sample=False)
    return tok.decode(out[0][ids.shape[-1]:], skip_special_tokens=True)

def touched_files(text):
    return {m.group(1) for m in re.finditer(r"^\\+\\+\\+ b/(.+?)\\s*$", text, re.MULTILINE)}

results = {"base": 0, "adapter": 0, "n": 0, "unparsed": 0}
for row in holdout_rows:
    gold = set(meta.get(row["instance_id"], {}).get("gold_files", []))
    messages = row["messages"][:2]
    with model.disable_adapter():
        base_text = generate(model, tokenizer, messages)
    adapter_text = generate(model, tokenizer, messages)
    parsed = touched_files(adapter_text) | touched_files(base_text)
    if not parsed:
        results["unparsed"] += 1
    results["n"] += 1
    base_hit = bool(touched_files(base_text) & gold)
    adapter_hit = bool(touched_files(adapter_text) & gold)
    results["base"] += int(base_hit)
    results["adapter"] += int(adapter_hit)
    print(f"{row['instance_id']}: gold={sorted(gold)[:2]} base_hit={base_hit} adapter_hit={adapter_hit}")
n = max(1, results["n"])
print(f"holdout n={results['n']} | gold-file hit: base {results['base']}/{n} "
      f"({results['base']/n:.0%}) vs adapter {results['adapter']}/{n} ({results['adapter']/n:.0%}) "
      f"| unparsable outputs: {results['unparsed']}")
print("G-holdout: the adapter must beat the base on THIS SAME prompt set. "
      f"{'PASS' if results['adapter'] > results['base'] else 'FAIL / inconclusive'}")
'''

PACKAGE = '''\
# --- package the submission (does NOT submit) -------------------------------------------------
# The adapter lives at adapters/main_lora/ and agent.yaml references it with `adapter: main_lora`.
# The repository packer refuses extra files by design (closed 5-file set), so this notebook builds
# the archive itself and prints the sha256 for review. A guarded --with-adapters mode has to be
# added to build_submission_v6.py before any adapter submission is allowed through CI.
staging = WORK / "adapter_submission"
shutil.rmtree(staging, ignore_errors=True)
shutil.copytree(REPO_DIR / "gemma4-agent/submission-v6.11", staging)
shutil.copytree(ADAPTER_DIR, staging / "adapters" / "main_lora")
agent_path = staging / "agent.yaml"
agent_text = agent_path.read_text(encoding="utf-8")
if not re.search(r"(?m)^adapter:", agent_text):
    agent_path.write_text(agent_text.rstrip("\\n") + "\\nadapter: main_lora\\n", encoding="utf-8")
print("agent.yaml tail:", agent_path.read_text(encoding="utf-8").strip().splitlines()[-1])
archive = WORK / "submission-with-adapter.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(staging.rglob("*")):
        if path.is_file():
            zf.write(path, path.relative_to(staging).as_posix())
print("archive:", archive, archive.stat().st_size, "bytes")
print("sha256 :", sha256(archive))
print("contents:", [n for n in zipfile.ZipFile(archive).namelist() if not n.startswith("adapters/")] , " + adapters/main_lora/*")
print("REMINDER: nothing has been submitted. G-canary and G-holdout must pass, and the packer needs "
      "an explicit --with-adapters mode, before this archive can go to Kaggle.")
'''

def code(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": [line + "\n" for line in source.strip("\n").split("\n")]}


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {},
            "source": [line + "\n" for line in source.strip("\n").split("\n")]}


def main() -> int:
    notebook = {
        "cells": [
            markdown(HEADER),
            code(SETUP),
            code(CLONE),
            markdown("## 1. Build the SFT dataset (CPU)"),
            code(DATASET),
            markdown("## 2. Canary — does the serving path apply the adapter?"),
            code(CANARY),
            markdown("## 3. QLoRA SFT (the only training step)"),
            code(TRAIN),
            markdown("## 4. Holdout check"),
            code(HOLDOUT),
            markdown("## 5. Package (no submission)"),
            code(PACKAGE),
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    OUT.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes, {len(notebook['cells'])} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
