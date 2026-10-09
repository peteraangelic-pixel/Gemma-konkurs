#!/usr/bin/env python3
"""Launch a private Kaggle evaluation of a candidate ZIP on public tasks.

The dedicated GitHub Actions workflow uses the Kaggle CLI's existing
~/.kaggle/access_token file to create a private notebook attached to the
competition inputs. The notebook supports a fixed smoke task or a deterministic,
repo-stratified public sample; it never calls the competition submission API.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

COMPETITION = "gemma-4-developer-agent"
WHEELHOUSE = "metric/gemma-4-developer-agent-wheelhouse"
MODEL_SOURCE = "google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2"
MODEL_ID = "gemma-4-31b-it-qat-w4a16-ct"
TASK_ID = "fastapi_15588"
MACHINE_SHAPE = "NvidiaL4"
# The competition wheelhouse contains CPython 3.12 wheels. Kaggle's default
# notebook image moved to Python 3.13 in October 2026, so pin this private smoke
# kernel to the known Python 3.12 / CUDA 12.8 image used by the public starter.
DOCKER_IMAGE = (
    "gcr.io/kaggle-private-byod/python@sha256:"
    "37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461"
)
DOCKER_IMAGE_PINNING_TYPE = "original"
PYTHON_RUNTIME_VERSION = "3.12"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def kaggle_cli(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    """Run Kaggle CLI while keeping all raw authenticated output out of logs."""
    return subprocess.run(
        [sys.executable, "-m", "kaggle", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _owner_from_csv(text: str) -> str | None:
    text = text.removeprefix("\ufeff").strip()
    if not text:
        return None
    for row in csv.DictReader(io.StringIO(text)):
        lowered = {str(key).strip().lower(): str(value or "").strip() for key, value in row.items()}
        for key in ("ref", "kernelref", "datasetref", "dataset_ref"):
            value = lowered.get(key, "")
            if "/" in value:
                owner = value.split("/", 1)[0]
                if re.fullmatch(r"[a-z0-9-]+", owner):
                    return owner
    return None


def discover_owner() -> str:
    """Use the supplied public Kaggle slug, or infer it from an owned artifact."""
    configured_owner = os.environ.get("KAGGLE_USERNAME", "").strip().lower()
    if configured_owner:
        if not re.fullmatch(r"[a-z0-9-]+", configured_owner):
            raise RuntimeError("KAGGLE_USERNAME must be the public Kaggle profile slug, not a URL.")
        return configured_owner

    commands = (
        ["kernels", "list", "--mine", "--format", "csv", "--page-size", "100"],
        ["datasets", "list", "--mine", "--format", "csv", "--page-size", "100"],
    )
    for command in commands:
        try:
            result = kaggle_cli(command, timeout=90)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            owner = _owner_from_csv(result.stdout)
            if owner:
                return owner
    raise RuntimeError(
        "Could not infer the Kaggle account slug from owned notebooks or datasets. "
        "No GPU run was started; provide the Kaggle username if this account has no owned artifacts."
    )


def _markdown_cell(source: str) -> dict[str, Any]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }


def _code_cell(source: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def build_notebook(
    submission_zip: bytes,
    submission_sha256: str,
    task_count: int = 1,
    seed: int = 20261009,
    task_id: str = TASK_ID,
) -> dict[str, Any]:
    encoded_zip = json.dumps(base64.b64encode(submission_zip).decode("ascii"))
    encoded_selection = json.dumps(
        json.dumps({"task_count": task_count, "seed": seed, "task_id": task_id})
    )
    extract_cell = r'''import base64
import hashlib
import io
import json
import math
import random
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from swegemma.models import load_tasks

DATA_DIR = Path('/kaggle/input/competitions/gemma-4-developer-agent')
WORKING_DIR = Path('/kaggle/working')
WORKING_DIR.mkdir(parents=True, exist_ok=True)
TASKS_PATH = DATA_DIR / 'tasks.jsonl'
AGENT_DIR = WORKING_DIR / 'candidate_submission'
TASK_SELECTION = json.loads(__TASK_SELECTION_JSON__)

SUBMISSION_ZIP_B64 = __SUBMISSION_B64__
EXPECTED_SUBMISSION_SHA256 = '__SUBMISSION_SHA256__'
submission_bytes = base64.b64decode(SUBMISSION_ZIP_B64, validate=True)
actual_sha256 = hashlib.sha256(submission_bytes).hexdigest()
assert actual_sha256 == EXPECTED_SUBMISSION_SHA256, 'Embedded submission archive hash mismatch.'

if AGENT_DIR.exists():
    shutil.rmtree(AGENT_DIR)
AGENT_DIR.mkdir(parents=True)
with zipfile.ZipFile(io.BytesIO(submission_bytes)) as archive:
    entries = archive.infolist()
    total_size = sum(entry.file_size for entry in entries)
    assert total_size <= 3 * 1024**3, 'Submission archive exceeds the competition size limit.'
    for entry in entries:
        member = PurePosixPath(entry.filename)
        assert not member.is_absolute() and '..' not in member.parts, f'Unsafe archive path: {entry.filename}'
    archive.extractall(AGENT_DIR)
assert (AGENT_DIR / 'agent.yaml').is_file(), 'Submission archive missing root agent.yaml.'

all_tasks = load_tasks(TASKS_PATH)
assert all_tasks, 'Competition task list is empty.'
task_by_id = {item.instance_id: item for item in all_tasks}
requested_count = max(1, min(int(TASK_SELECTION['task_count']), len(all_tasks)))
fixed_task = task_by_id.get(TASK_SELECTION['task_id'])
assert fixed_task is not None, f"Reference public task {TASK_SELECTION['task_id']} is missing."
if requested_count == 1:
    selected_tasks = [fixed_task]
else:
    grouped = {}
    for item in all_tasks:
        grouped.setdefault(item.repo, []).append(item)
    candidate_groups = {
        repo: [item for item in group if item.instance_id != fixed_task.instance_id]
        for repo, group in grouped.items()
    }
    candidate_groups = {repo: group for repo, group in candidate_groups.items() if group}
    remaining_count = requested_count - 1
    candidate_total = sum(len(group) for group in candidate_groups.values())
    exact_quotas = {
        repo: remaining_count * len(group) / candidate_total
        for repo, group in candidate_groups.items()
    }
    quotas = {repo: math.floor(value) for repo, value in exact_quotas.items()}
    if remaining_count >= len(candidate_groups):
        for repo in candidate_groups:
            if quotas[repo] == 0:
                quotas[repo] = 1
    while sum(quotas.values()) < remaining_count:
        repo = max(
            (key for key in candidate_groups if quotas[key] < len(candidate_groups[key])),
            key=lambda key: exact_quotas[key] - quotas[key],
        )
        quotas[repo] += 1
    while sum(quotas.values()) > remaining_count:
        candidates = [key for key in candidate_groups if quotas[key] > 1]
        repo = min(candidates, key=lambda key: exact_quotas[key] - quotas[key])
        quotas[repo] -= 1
    rng = random.Random(int(TASK_SELECTION['seed']))
    selected_tasks = [fixed_task]
    for repo in sorted(candidate_groups):
        candidates = sorted(candidate_groups[repo], key=lambda item: item.instance_id)
        rng.shuffle(candidates)
        selected_tasks.extend(candidates[:quotas[repo]])
    assert len(selected_tasks) == requested_count, f'Stratified selector chose {len(selected_tasks)}, expected {requested_count}.'
    rng.shuffle(selected_tasks)

repo_counts = {}
for item in selected_tasks:
    repo_counts[item.repo] = repo_counts.get(item.repo, 0) + 1
print(f'Submission SHA-256: {actual_sha256}')
print(f'Public development tasks available: {len(all_tasks)}')
print(f'Seeded stratified sample ({len(selected_tasks)} tasks, seed={TASK_SELECTION["seed"]}): {repo_counts}')
print('Selected task IDs: ' + ', '.join(item.instance_id for item in selected_tasks))
'''.replace("__TASK_SELECTION_JSON__", encoded_selection).replace(
        "__SUBMISSION_B64__", encoded_zip
    ).replace("__SUBMISSION_SHA256__", submission_sha256)

    setup_cell = r'''import glob
import importlib
import os
import platform
import subprocess
import sys
from pathlib import Path

# The attached competition wheelhouse contains CPython 3.12 binaries. Fail
# early with a clear message if Kaggle ignores the pinned notebook image.
if sys.version_info[:2] != (3, 12):
    raise RuntimeError(
        f'Expected pinned Python 3.12 runtime; received {platform.python_version()} '
        f'from {sys.executable}.'
    )
print(f'Pinned Kaggle Python runtime: {platform.python_version()}')

# Offline vLLM setup used by the competition's public starter notebook.
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['TRANSFORMERS_NO_TF'] = '1'
os.environ['VLLM_WORKER_MULTIPROC_METHOD'] = 'spawn'
os.environ['VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS'] = '1'
os.environ['VLLM_ENGINE_READY_TIMEOUT_S'] = '1200'
os.environ['VLLM_NO_USAGE_STATS'] = '1'
os.environ['OTEL_SDK_DISABLED'] = 'true'
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'

WHEELHOUSE_DIR = Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')
assert WHEELHOUSE_DIR.is_dir(), f'Wheelhouse not mounted: {WHEELHOUSE_DIR}'

for pth_pattern in (
    '/usr/local/lib/python*/dist-packages/*cutlass*.pth',
    '/usr/local/lib/python*/site-packages/*cutlass*.pth',
):
    for pth in glob.glob(pth_pattern):
        try:
            os.unlink(pth)
        except OSError:
            pass

tmp_whl = Path('/tmp/wheelhouse')
tmp_whl.mkdir(parents=True, exist_ok=True)
for wheel in WHEELHOUSE_DIR.glob('*.whl'):
    if 'cutlass' in wheel.name.lower():
        continue
    target_name = (
        wheel.name.replace('cu128', '+cu128')
        if ('cu128' in wheel.name and '+' not in wheel.name)
        else wheel.name
    )
    target = tmp_whl / target_name
    if not target.exists():
        os.symlink(wheel, target)

wheels = sorted(str(wheel) for wheel in tmp_whl.glob('*.whl'))
print(f'Installing {len(wheels)} offline wheels from competition wheelhouse...')
subprocess.run(
    [sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels],
    check=True,
)
importlib.invalidate_caches()
print('Offline wheelhouse installation complete.')
'''

    model_cell = r'''import litellm
import torch
import yaml
from pathlib import Path
from adk_submission import VllmConfig, VllmServer

litellm.drop_params = True
TARGET_MODEL_NAME = 'gemma-4-31b-it-qat-w4a16-ct'
MODEL_PATH = Path('/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2')
assert MODEL_PATH.is_dir(), f'Gemma model input not mounted: {MODEL_PATH}'

gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
gpu_names = [torch.cuda.get_device_name(i) for i in range(gpu_count)]
print(f'Visible GPUs ({gpu_count}): {gpu_names}')
assert gpu_count == 4, f'Expected the competition L4x4 machine; got {gpu_count} visible GPUs.'
assert all('L4' in name.upper() for name in gpu_names), f'Expected L4 GPUs, got {gpu_names}'

# Avoid an optional swegemma.models.discovery helper that is absent from the
# current wheelhouse. Read model IDs from declarative YAML; the official
# Evaluator still loads and validates the submission.
class _IncludeLoader(yaml.SafeLoader):
    pass

_IncludeLoader.add_constructor('!include', lambda loader, node: loader.construct_scalar(node))

declared_models = set()
for config_path in AGENT_DIR.rglob('*.yaml'):
    config = yaml.load(config_path.read_text(encoding='utf-8'), Loader=_IncludeLoader)
    if isinstance(config, dict) and isinstance(config.get('model'), str):
        declared_models.add(config['model'])
assert declared_models == {TARGET_MODEL_NAME}, f'Expected only {TARGET_MODEL_NAME}; found {sorted(declared_models)}'
declared_model = TARGET_MODEL_NAME
# The exact V1 archive has no adapters/ directory. Avoid optional adapter
# discovery here; the installed submission helper can report a non-empty
# manifest even when this stage is explicitly no-LoRA.
assert not (AGENT_DIR / 'adapters').exists(), 'No-LoRA V1 archive unexpectedly contains adapters/.'
adapters = []

vllm_cfg = VllmConfig(
    model=str(MODEL_PATH),
    port=8000,
    host='127.0.0.1',
    tool_call_parser='gemma4',
    reasoning_parser='gemma4',
    max_model_len=32768,
    dtype='bfloat16' if torch.cuda.is_bf16_supported() else 'auto',
    gpu_memory_utilization=0.90,
    enable_auto_tool_choice=True,
    enable_lora=False,
    tensor_parallel_size=4,
    startup_timeout=60 * 20,
)
server_instance = VllmServer(vllm_cfg, adapter_manifest=adapters)
server_instance.start()
print(f'vLLM server started on {server_instance.base_url} (tensor parallelism=4).')
models = server_instance.create_model_registry(
    aliases=[declared_model, TARGET_MODEL_NAME],
    model_prefix='openai/',
    api_key='EMPTY',
)
'''

    eval_cell = r'''import asyncio
import concurrent.futures
import json
import math
import time
import yaml
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.config import EvalConfig, build_submission_limits
from swegemma.evaluate import Evaluator


def run_sync(coro_or_fn, *args, **kwargs):
    fn = (lambda: coro_or_fn(*args, **kwargs)) if callable(coro_or_fn) else (lambda: coro_or_fn)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(fn())).result()
    return asyncio.run(fn())


def wilson_interval(successes, trials, z=1.96):
    if not trials:
        return [0.0, 1.0]
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]

raw_eval_cfg = yaml.safe_load((AGENT_DIR / 'eval_config.yaml').read_text(encoding='utf-8'))
eval_section = raw_eval_cfg.get('evaluation', raw_eval_cfg)
timeout_seconds = int(eval_section.get('timeout_seconds', 300))
max_tool_calls = int(eval_section.get('max_tool_calls', 100))
max_time_minutes = float(eval_section.get('max_time_minutes', 60.0))
turns_raw = eval_section.get('max_turns', eval_section.get('max_llm_calls'))
max_turns = int(turns_raw) if turns_raw is not None else None

limits, gen_constraints = build_submission_limits()
eval_config = EvalConfig(
    tasks_path=TASKS_PATH,
    snapshots_dir=DATA_DIR / 'snapshots',
    results_dir=WORKING_DIR / 'candidate_eval_results',
    submission_dir=AGENT_DIR,
    models=models,
    sandbox='subprocess',
    timeout_seconds=timeout_seconds,
    max_time_minutes=max_time_minutes,
    max_tool_calls=max_tool_calls,
    max_turns=max_turns,
    limits=limits,
    generation_constraints=gen_constraints,
    adapter_manifest=adapters,
    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=15,
        overlap_size=2,
        token_threshold=14336,
        event_retention_size=5,
    ),
    graph_dir=DATA_DIR / 'graphs',
    embeddings_dir=DATA_DIR / 'embeddings',
    wheels_dir=DATA_DIR / 'wheels',
    verbose=False,
)

evaluator = Evaluator(eval_config)
per_task_results = []
patches = []
benchmark_started = time.monotonic()
result_path = WORKING_DIR / 'agent_benchmark_result.json'
patch_path = WORKING_DIR / 'agent_benchmark_patches.txt'


def persist_results():
    trials = len(per_task_results)
    resolved_count = sum(bool(row.get('resolved')) for row in per_task_results)
    durations = [row['duration_seconds'] for row in per_task_results if row.get('duration_seconds') is not None]
    score = resolved_count / trials if trials else 0.0
    summary = {
        'task_count_requested': int(TASK_SELECTION['task_count']),
        'task_count_selected': len(selected_tasks),
        'tasks_completed_or_failed': trials,
        'resolved_count': resolved_count,
        'score_estimate': score,
        'score_ci95_wilson': wilson_interval(resolved_count, trials),
        'per_task_max_time_minutes': max_time_minutes,
        'mean_task_duration_seconds': sum(durations) / len(durations) if durations else None,
        'total_task_duration_seconds': sum(durations),
        'benchmark_wall_seconds': time.monotonic() - benchmark_started,
        'model': 'gemma-4-31b-it-qat-w4a16-ct',
        'visible_gpu_count': torch.cuda.device_count(),
        'submission_sha256': actual_sha256,
        'sample_seed': int(TASK_SELECTION['seed']),
        'repo_counts': repo_counts,
        'task_ids': [item.instance_id for item in selected_tasks],
        'tasks': per_task_results,
        'official_submission': False,
        'score_scope': 'seeded stratified public development sample; not a leaderboard score',
    }
    result_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    patch_path.write_text('\n\n'.join(patches), encoding='utf-8')
    return summary


for task_index, task in enumerate(selected_tasks, start=1):
    print(f'Benchmark task {task_index}/{len(selected_tasks)}: {task.instance_id} ({task.repo})')
    try:
        result = run_sync(evaluator.evaluate_task, task=task, task_index=task_index, total_tasks=len(selected_tasks))
        patch = result.agent_patch or ''
        exit_code = result.test_exit_code
        row = {
            'task_id': task.instance_id,
            'repo': task.repo,
            'resolved': bool(result.resolved),
            'test_exit_code': None if exit_code is None else int(exit_code),
            'patch_chars': len(patch),
            'tool_calls': int(result.tool_calls or 0),
            'duration_seconds': float(result.duration_seconds),
        }
        if patch:
            patches.append(f"===== {task.instance_id} | resolved={row['resolved']} | {len(patch)} chars =====\n{patch}")
    except Exception as exc:
        row = {
            'task_id': task.instance_id,
            'repo': task.repo,
            'resolved': False,
            'error': f'{type(exc).__name__}: {str(exc)[:500]}',
            'duration_seconds': None,
        }
    per_task_results.append(row)
    summary = persist_results()
    print(json.dumps({key: summary[key] for key in ('tasks_completed_or_failed', 'resolved_count', 'score_estimate', 'score_ci95_wilson')}))

final_summary = persist_results()
print(json.dumps(final_summary, indent=2, ensure_ascii=False))
'''

    cells = [
        _markdown_cell(
            "# Private Gemma agent benchmark\n\n"
            "Runs the exact candidate ZIP through the competition evaluator on a deterministic, stratified sample of public development tasks. "
            "This notebook is private, has internet disabled, and does not submit to the competition or produce an official score."
        ),
        _code_cell(setup_cell),
        _code_cell(extract_cell),
        _code_cell(model_cell),
        _code_cell(eval_cell),
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def parse_kernel_status(text: str) -> str | None:
    match = re.search(r'has status\s+["\']([^"\']+)["\']', text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def normalized_status(status: str | None) -> str:
    if not status:
        return "UNKNOWN"
    value = status.rsplit(".", 1)[-1].strip().upper()
    if value in {"COMPLETE", "COMPLETED", "SUCCESS", "SUCCEEDED"}:
        return "COMPLETE"
    if value in {"ERROR", "FAILED", "FAILURE"}:
        return "ERROR"
    if value in {"CANCELLED", "CANCELED"}:
        return "CANCELED"
    if value in {"QUEUED", "PENDING", "RUNNING", "CREATED", "INITIALIZING"}:
        return value
    return value


def update_state(outdir: Path, state: dict[str, Any]) -> None:
    state["updated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_json(outdir / "run.json", state)
    print(
        f"Kaggle private benchmark: status={state.get('status')} "
        f"kernel={state.get('kernel_ref', 'not-created')}"
    )


def download_results(kernel_ref: str, outdir: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="gemma-agent-benchmark-output-") as temporary:
        output = kaggle_cli(
            ["kernels", "output", kernel_ref, "--path", temporary, "--force"],
            timeout=300,
        )
        if output.returncode != 0:
            raise RuntimeError(f"Could not download Kaggle kernel output (exit code {output.returncode}).")
        folder = Path(temporary)
        result_files = list(folder.rglob("agent_benchmark_result.json"))
        if not result_files:
            raise RuntimeError("Kernel completed but produced no agent_benchmark_result.json output.")
        raw_result = json.loads(result_files[0].read_text(encoding="utf-8"))
        write_json(outdir / "agent_benchmark_result.json", raw_result)
        patch_files = list(folder.rglob("agent_benchmark_patches.txt"))
        if patch_files:
            (outdir / "agent_benchmark_patches.txt").write_text(
                patch_files[0].read_text(encoding="utf-8"), encoding="utf-8"
            )
        return raw_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--task-count", type=int, default=1, help="public tasks: 1 selects --task-id; >1 is stratified by repository")
    parser.add_argument("--task-id", default=TASK_ID, help="fixed public task used when --task-count=1 and reserved in larger samples")
    parser.add_argument("--seed", type=int, default=20261009, help="deterministic sample seed")
    parser.add_argument("--max-wait-minutes", type=int, default=300)
    parser.add_argument("--poll-interval-seconds", type=int, default=45)
    args = parser.parse_args()
    if args.task_count < 1:
        parser.error("--task-count must be at least 1")
    if args.max_wait_minutes < 1:
        parser.error("--max-wait-minutes must be at least 1")
    # Kaggle's CLI --timeout controls kernel runtime, not merely HTTP response wait.
    kernel_timeout_seconds = args.max_wait_minutes * 60 + 300

    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    submission_path = args.submission
    if not submission_path.is_file():
        raise SystemExit(f"Submission archive not found: {submission_path}")
    submission_bytes = submission_path.read_bytes()
    submission_sha256 = hashlib.sha256(submission_bytes).hexdigest()
    state: dict[str, Any] = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "preparing",
        "submission_sha256": submission_sha256,
        "fixed_task_id": args.task_id,
        "task_count_requested": args.task_count,
        "sample_seed": args.seed,
        "kernel_timeout_seconds": kernel_timeout_seconds,
        "model": MODEL_ID,
        "machine_shape": MACHINE_SHAPE,
        "docker_image": DOCKER_IMAGE,
        "docker_image_pinning_type": DOCKER_IMAGE_PINNING_TYPE,
        "python_runtime_expected": PYTHON_RUNTIME_VERSION,
        "private_notebook": True,
        "internet_enabled": False,
        "competition_submission_created": False,
        "gpu_quota_used": None,
        "gpu_quota_usage_status": "unconfirmed",
        "kaggle_running_status_observed": False,
    }
    update_state(outdir, state)

    try:
        owner = discover_owner()
        run_tag = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        slug = f"gemma-agent-benchmark-{submission_sha256[:8]}-{run_tag}"
        title = f"Gemma Agent Benchmark {submission_sha256[:8]} {run_tag}"
        kernel_ref = f"{owner}/{slug}"
        state.update(
            {
                "status": "prepared",
                "kernel_ref": kernel_ref,
                "kernel_url": f"https://www.kaggle.com/code/{kernel_ref}",
            }
        )
        update_state(outdir, state)

        with tempfile.TemporaryDirectory(prefix="gemma-agent-benchmark-kernel-") as temporary:
            kernel_dir = Path(temporary)
            notebook = build_notebook(
                submission_bytes,
                submission_sha256,
                task_count=args.task_count,
                seed=args.seed,
                task_id=args.task_id,
            )
            notebook_path = kernel_dir / "agent-benchmark.ipynb"
            notebook_path.write_text(json.dumps(notebook, ensure_ascii=False), encoding="utf-8")
            metadata = {
                "id": kernel_ref,
                "title": title,
                "code_file": notebook_path.name,
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_tpu": False,
                "enable_internet": False,
                "machine_shape": MACHINE_SHAPE,
                "docker_image": DOCKER_IMAGE,
                "docker_image_pinning_type": DOCKER_IMAGE_PINNING_TYPE,
                "dataset_sources": [WHEELHOUSE],
                "competition_sources": [COMPETITION],
                "kernel_sources": [],
                "model_sources": [MODEL_SOURCE],
            }
            (kernel_dir / "kernel-metadata.json").write_text(
                json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
            )
            with notebook_path.open(encoding="utf-8") as handle:
                json.load(handle)  # Validate notebook JSON before upload.

            state.update({"status": "pushing", "gpu_quota_used": None})
            update_state(outdir, state)
            try:
                pushed = kaggle_cli(
                    ["kernels", "push", "--path", str(kernel_dir), "--timeout", str(kernel_timeout_seconds)],
                    timeout=300,
                )
                state["push_exit_code"] = pushed.returncode
                if pushed.returncode != 0:
                    state["push_warning"] = (
                        f"Kaggle CLI returned exit code {pushed.returncode}; checking whether the run was created."
                    )
            except (OSError, subprocess.TimeoutExpired) as exc:
                # Do not push a second version: the server may have accepted the first request.
                state["push_warning"] = f"Kaggle push response was inconclusive ({type(exc).__name__}); checking status."
            state.update({"status": "queued_or_starting", "gpu_requested": True, "gpu_quota_used": None})
            update_state(outdir, state)

        deadline = time.monotonic() + max(1, args.max_wait_minutes) * 60
        final_status = "UNKNOWN"
        consecutive_api_errors = 0
        while time.monotonic() < deadline:
            try:
                status_result = kaggle_cli(["kernels", "status", kernel_ref], timeout=90)
            except (OSError, subprocess.TimeoutExpired):
                status_result = None
            if status_result is None or status_result.returncode != 0:
                consecutive_api_errors += 1
                state["status_api_errors"] = consecutive_api_errors
                if consecutive_api_errors >= 5:
                    state.update({"status": "status_poll_failed", "error": "Five consecutive Kaggle status API calls failed."})
                    update_state(outdir, state)
                    return 3
            else:
                consecutive_api_errors = 0
                raw_status = parse_kernel_status(status_result.stdout + "\n" + status_result.stderr)
                final_status = normalized_status(raw_status)
                state["kaggle_status"] = raw_status or "unparsed"
                if final_status == "COMPLETE":
                    state.update({"status": "complete", "gpu_quota_used": None})
                    update_state(outdir, state)
                    try:
                        smoke_result = download_results(kernel_ref, outdir)
                    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
                        state.update({"status": "output_download_failed", "error": f"{type(exc).__name__}: {exc}"})
                        update_state(outdir, state)
                        return 4
                    state.update(
                        {
                            "status": "complete",
                            "result": {
                                "tasks_completed_or_failed": smoke_result.get("tasks_completed_or_failed"),
                                "task_count_selected": smoke_result.get("task_count_selected"),
                                "resolved_count": smoke_result.get("resolved_count"),
                                "score_estimate": smoke_result.get("score_estimate"),
                                "score_ci95_wilson": smoke_result.get("score_ci95_wilson"),
                                "benchmark_wall_seconds": smoke_result.get("benchmark_wall_seconds"),
                                "task_ids": smoke_result.get("task_ids"),
                            },
                        }
                    )
                    update_state(outdir, state)
                    return 0
                if final_status in {"ERROR", "CANCELED"}:
                    state.update({"status": final_status.lower(), "error": "Kaggle notebook ended without a successful run."})
                    update_state(outdir, state)
                    return 5
                state["status"] = final_status.lower()
                if final_status == "RUNNING":
                    state["kaggle_running_status_observed"] = True
                    state["gpu_quota_used"] = None
                update_state(outdir, state)
            time.sleep(max(5, args.poll_interval_seconds))

        state.update(
            {
                "status": "wait_timeout",
                "last_kaggle_status": final_status,
                "error": "Notebook was not complete before the monitoring window ended; it may still be queued or running on Kaggle.",
            }
        )
        update_state(outdir, state)
        return 6
    except RuntimeError as exc:
        state.update({"status": "preflight_failed", "error": str(exc)})
        update_state(outdir, state)
        return 7


if __name__ == "__main__":
    raise SystemExit(main())
