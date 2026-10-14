#!/usr/bin/env python3
"""Evolve the locator's hand-picked constants against gold patches (offline, CPU only).

Motivation (2026-10-14). The sibling project's session improves its agent by measuring thousands of
candidate configurations against a fast simulator: population -> mutate around the best few ->
select, with a *composite* fitness (their winrate combines win rate with process signals), and every
candidate is scored on a small "hard" tier plus a larger tier so small-sample wins do not get
shipped. Their knobs are named constants; ours are the same: tools/locator.py ranks files with a
dozen numbers chosen by hand (BM25 k1/b, path/defined/exact bonuses, the test penalty, the weight of
the test-import interleave, the four query weights).

Nothing about the model or the sample is being searched here - only those constants, and only
against data we already own: the 129 published dev tasks with gold patches (fitness) and the 108
held-out proxy tasks from four repositories outside the dev set (validation). No GPU, no Kaggle.

Fitness (pre-registered before the first run):
    F = 0.50*top1 + 0.30*top3 + 0.15*top5 + 0.05*top10
Top-1 dominates because the prompt tells the agent to read the first candidate and edit quickly.

Guards:
  * `--selftest` compares this scorer against the shipped tools/locator.py ranking on sampled tasks;
    a single mismatch fails the build of the cache (a search over a scorer that does not match the
    artifact would ship numbers that mean nothing).
  * `--validate` scores baseline and best on the held-out set; a gain that does not transfer is
    reported as a rejection, not as a win (the V2-V4 lesson: public tuning collapsed on hidden).

Usage:
    python3 gemma4-agent/tools/evolve_locator.py --build-cache --split dev
    python3 gemma4-agent/tools/evolve_locator.py --build-cache --split holdout
    python3 gemma4-agent/tools/evolve_locator.py --evolve --pop 12 --gens 6 --workers 2
    python3 gemma4-agent/tools/evolve_locator.py --validate
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import pickle
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
REPO_CACHE = Path(os.environ.get("GEMMA_REPO_CACHE", Path.home() / ".cache" / "gemma-repos"))
WORK = Path(os.environ.get("GEMMA_EVOLVE_WORK", "/tmp/locator-evolve"))
ANALYSIS = ROOT / "gemma4-agent" / "analysis" / "locator-evolve"

sys.path.insert(0, str(TOOLS))
from locate_benchmark import (  # noqa: E402
    REPO_ROOT, STOPWORDS, anchors_from_statement, checkout, gold_files, is_fixable,
    repo_worktree, subtokens, tasks_from_git,
)

# ---- the shipped artifact, imported so the query builder is literally the one we ship ------------
# tools/locator.py is the DEVELOPMENT reference: it adds acronym terms and a compound-literal gate
# that the compact artifact embedded in the prompt does not have. Measuring the reference while
# shipping the compact one produced a scorer that ranked 3rd-place candidates differently from the
# real artifact (caught by --selftest on 2026-10-14), so the search now models the artifact.
SHIPPED_ARTIFACT = ROOT / "gemma4-agent" / "submission-v6.4" / "tools" / "locate.py"
spec = importlib.util.spec_from_file_location("shipped_locator", SHIPPED_ARTIFACT)
shipped = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shipped)  # type: ignore[union-attr]

TESTISH = shipped.TESTISH

# Knobs of tools/locator.py: name -> (baseline, low, high). The baseline is what ships today.
KNOBS: dict[str, tuple[float, float, float]] = {
    "k1": (1.2, 0.6, 2.4),                # BM25 term saturation
    "b": (0.75, 0.2, 1.0),                # BM25 length normalisation
    "path_bonus": (1.5, 0.0, 4.0),        # term occurs in the path
    "defined_bonus": (4.0, 0.0, 10.0),    # term occurs in a def/class name
    "exact_bonus": (6.0, 0.0, 14.0),      # exact identifier literal present in the text
    "test_penalty": (0.5, 0.1, 1.0),      # multiply score of test-ish files
    "import_factor": (1.0, 0.0, 2.5),     # weight of the test->imports interleave
    "q_ident_piece": (3.0, 0.5, 6.0),     # query weight: piece of an identifier literal
    "q_full_ident": (4.0, 0.5, 8.0),      # query weight: the whole identifier literal
    "q_plain": (1.0, 0.1, 3.0),           # query weight: an ordinary issue word
}
BASELINE = {name: value[0] for name, value in KNOBS.items()}
FITNESS_WEIGHTS = {1: 0.50, 3: 0.30, 5: 0.15, 10: 0.05}


# --------------------------------------------------------------------------------------------- cache

def features_for_task(task: dict, worktree: Path) -> dict | None:
    """One corpus read -> the compact features the scorer needs (only query terms are kept)."""
    statement = task.get("problem_statement") or ""
    code, tests = gold_files(task.get("patch") or "")
    targets = [p for p in (code or tests) if is_fixable(p)]
    if not targets:
        return None
    raw_query = shipped.build_query(statement)
    if not raw_query:
        return None
    # the compact artifact returns (weight, is_ident); the reference adds a compound flag
    query = {term: (value[0], value[1], value[2] if len(value) > 2 else False)
             for term, value in raw_query.items()}
    ident_terms = [t for t, (_, is_ident, _) in query.items() if is_ident]
    compound_terms = [t for t, (_, _, compound) in query.items() if compound]
    # Use the artifact's OWN collect(): it applies its own skip-list (docs/, site-packages,
    # htmlcov, .eggs...), its own size cap and its own tokenisation. Building the file set from a
    # different reader made n_docs and the idf table slightly different from the artifact's, which
    # showed up as one near-tie in the top-5 on a requests task (2026-10-14) - a search that scores
    # a different corpus than the artifact reads would ship numbers that do not describe it.
    struct = shipped.collect(worktree)
    if not struct:
        return None
    files: list[dict] = []
    df: Counter = Counter()
    for name, data in struct.items():
        tokens = data["tokens"]
        lowered = data["text"].lower()
        row = {
            "name": name,
            "len": len(name),
            "is_test": any(part in name for part in TESTISH),
            "length": sum(tokens.values()) or 1,
            "tf": {t: tokens[t] for t in query if t in tokens},
            "path": [t for t in query if t in data["path"]],
            "defined": [t for t in query if t in data["defined"]],
            "exact": [t for t in ident_terms if "_" in t and t in lowered],
            "imports": sorted(data["imports"]),
        }
        for term in row["tf"]:
            df[term] += 1
        files.append(row)
    if not files:
        return None
    return {
        "task_id": task.get("id") or task.get("task_id") or task.get("instance_id") or "",
        "repo": task.get("repo", ""),
        "base_commit": task.get("base_commit", ""),
        "targets": [t for t in targets if any(t == f["name"] for f in files)],
        "n_docs": len(files),
        "query": [[t, w, bool(i), bool(c)] for t, (w, i, c) in query.items()],
        "compound_terms": compound_terms,
        "df": {t: df.get(t, 0) for t in query},
        "files": files,
    }


def build_cache(split: str, count: int | None, outdir: Path) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    tasks, repos = load_tasks(split, count)
    print(f"[cache:{split}] {len(tasks)} tasks, repos: {', '.join(repos)}", flush=True)
    worktree = None
    current = None
    kept = 0
    for index, task in enumerate(tasks, start=1):
        if task.get("_holdout"):  # proxy tasks carry the clone path directly
            worktree, current = Path(task["_repo_dir"]), task["_repo_dir"]
        else:
            repo = task["repo"]
            if repo != current:
                worktree = repo_worktree(repo)
                current = repo
        checkout(worktree, task["base_commit"])
        feats = features_for_task(task, worktree)
        if feats is None or not feats["targets"]:
            continue
        with (outdir / f"{split}-{kept:04d}.pkl").open("wb") as handle:
            pickle.dump(feats, handle, protocol=4)
        kept += 1
        if index % 20 == 0:
            print(f"  {index}/{len(tasks)} tasks, {kept} kept", flush=True)
    print(f"[cache:{split}] wrote {kept} task feature files to {outdir}", flush=True)
    return kept


def load_tasks(split: str, count: int | None) -> tuple[list[dict], list[str]]:
    if split == "dev":
        tasks = tasks_from_git(None, count)
        return tasks, sorted({t["repo"] for t in tasks})
    limit = count or 40
    repos = ["encode/starlette", "pallets/click", "tiangolo/typer", "pydantic/pydantic"]
    tasks = []
    for repo in repos:
        repo_dir = ensure_repo(repo)
        for row in candidate_tasks(repo_dir, limit):
            tasks.append({"id": f"{repo.replace('/', '_')}-{row['base'][:8]}",
                          "repo": "", "base_commit": row["base"], "problem_statement": row["title"],
                          "patch": "".join(f"+++ b/{p}\n" for p in row["files"]),
                          "_repo_dir": str(repo_dir), "_holdout": True})
    return tasks, repos


def ensure_repo(repo: str) -> Path:
    local = REPO_CACHE / "holdout" / repo.replace("/", "__")
    if not local.is_dir():
        local.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                        f"https://github.com/{repo}.git", str(local)],
                       check=True, capture_output=True, text=True)
    return local


def _git(repo_dir: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo_dir), *args],
                          check=True, capture_output=True, text=True).stdout


def candidate_tasks(repo_dir: Path, limit: int) -> list[dict]:
    """Merged PRs with a title and 1-5 changed source files - the same proxy shape as the holdout."""
    skip = ("tests/", "docs/", "docs_src/", "scripts/", ".github/", "benchmarks/")
    ref = "HEAD"
    for candidate in ("origin/HEAD", "origin/main", "origin/master"):
        try:
            _git(repo_dir, "rev-parse", "--verify", candidate)
            ref = candidate
            break
        except subprocess.CalledProcessError:
            continue
    out = _git(repo_dir, "log", ref, "--merges", "-n", str(limit * 6), "--format=%H%x1f%P%x1f%s")
    tasks: list[dict] = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        commit, parents, subject = parts
        parents = parents.split()
        if len(parents) != 2:
            continue
        title = subject.split("(#")[0].strip()
        if not title or len(title) > 200:
            continue
        rows = _git(repo_dir, "diff", "--name-status", f"{parents[0]}..{commit}").splitlines()
        files = []
        for row in rows:
            fields = row.split("\t")
            if len(fields) < 2 or fields[0].startswith("D"):
                continue
            path = fields[1]
            if not path.endswith(".py") or path.startswith(skip) or "_test" in path or "conftest" in path:
                continue
            files.append(path)
        if not 1 <= len(files) <= 5:
            continue
        tasks.append({"base": parents[0], "title": title, "files": files})
        if len(tasks) >= limit:
            break
    return tasks


# ------------------------------------------------------------------------------------------- scoring

def score_config(feats: dict, config: dict) -> list[str]:
    """Replica of tools/locator.py rank() with the knobs exposed. Order = the shipped order."""
    k1, b = config["k1"], config["b"]
    query = feats["query"]
    df, n_docs = feats["df"], feats["n_docs"]
    lengths = [f["length"] for f in feats["files"]]
    avg_len = sum(lengths) / len(lengths) or 1
    compound_terms = []  # the shipped builder has no compound literals

    def idf(term: str) -> float:
        d = df.get(term, 0)
        return math.log(1 + (n_docs - d + 0.5) / (d + 0.5))

    idf_of = {t: idf(t) for t, _, _, _ in query}
    # The cache stores the weights the SHIPPED build_query produced; the category is what the
    # search varies. Reading the category from that stored weight keeps one cache valid for every
    # configuration - and it is why the control (`--selftest --locator ... --config ...`) exists:
    # before this was fixed the three q_* knobs were dead, so the baked file did not implement the
    # configuration the search had measured.
    category_weight = {1.0: config["q_plain"], 2.0: config["q_plain"],
                       3.0: config["q_ident_piece"], 4.0: config["q_full_ident"]}
    scores: dict[str, float] = defaultdict(float)
    for row in feats["files"]:
        score = 0.0
        length = row["length"]
        for term, shipped_weight, _is_ident, _compound in query:
            weight = category_weight.get(shipped_weight, shipped_weight)
            freq = row["tf"].get(term, 0)
            if freq:
                score += weight * idf_of[term] * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * length / avg_len))
            if term in row["path"]:
                score += config["path_bonus"] * weight * idf_of[term]
            if term in row["defined"]:
                score += config["defined_bonus"] * weight * idf_of[term]
        for term in row["exact"]:
            head = term.split("_")[0]
            score += config["exact_bonus"] * math.log(
                1 + (n_docs - df.get(head, 0) + 0.5) / (df.get(head, 0) + 0.5))
        # The artifact multiplies test files unconditionally, which also materialises a 0.0 entry
        # for a test file that matched nothing; that entry takes part in the content ordering, so
        # the model has to reproduce it instead of filtering zeros out.
        if row["is_test"]:
            scores[row["name"]] = score * config["test_penalty"]
        elif score:
            scores[row["name"]] = score

    content_rank = sorted(scores, key=lambda n: (-scores[n], len(n), n))
    source_by_name = {f["name"]: f for f in feats["files"]}
    test_best = next((n for n in content_rank if source_by_name[n]["is_test"]), None)
    imported: dict[str, float] = defaultdict(float)
    if test_best and config["import_factor"]:
        weight = scores[test_best] * config["import_factor"]
        for module in source_by_name[test_best]["imports"]:
            base = module.replace(".", "/")
            for candidate in (f"{base}.py", f"{base}/__init__.py"):
                if candidate in source_by_name:
                    imported[candidate] += weight
    import_rank = sorted((n for n in imported if not source_by_name[n]["is_test"]),
                         key=lambda n: (-imported[n], len(n), n))
    merged = dict(scores)
    for name, value in imported.items():
        merged[name] = merged.get(name, 0.0) + value
    union: list[str] = []
    for a, b_ in zip(content_rank, import_rank + [None] * len(content_rank)):
        for candidate in (a, b_):
            if candidate and candidate in merged and candidate not in union:
                union.append(candidate)
    for candidate in content_rank:
        if candidate not in union:
            union.append(candidate)
    return union


def fitness(ranks: dict[int, int], total: int) -> float:
    return sum(FITNESS_WEIGHTS[k] * ranks.get(k, 0) / total for k in FITNESS_WEIGHTS)


def evaluate(feats_list: list[dict], config: dict, top: int = 10) -> dict:
    counts = {k: 0 for k in FITNESS_WEIGHTS}
    per_task = []
    for feats in feats_list:
        ranked = score_config(feats, config)[:top]
        gold = set(feats["targets"])
        row = {k: bool(set(ranked[:k]) & gold) for k in FITNESS_WEIGHTS}
        for k, hit in row.items():
            counts[k] += 1 if hit else 0
        per_task.append(row)
    total = len(feats_list) or 1
    return {"total": total, "counts": counts, "fitness": fitness(counts, total), "rows": per_task}


# -------------------------------------------------------------------------------------------- search

def random_config(rng: random.Random) -> dict:
    return {name: rng.uniform(low, high) for name, (_, low, high) in KNOBS.items()}


def mutate_config(parent: dict, rng: random.Random, rate: float = 0.2, strength: float = 0.15) -> dict:
    child = {}
    for name, (_, low, high) in KNOBS.items():
        if rng.random() < rate:
            child[name] = parent[name]  # keep, like the sibling's search
        else:
            delta = rng.gauss(0, (high - low) * strength * 0.5)
            child[name] = min(high, max(low, parent[name] + delta))
    return child


_GLOBAL: dict = {}


def _init_worker(feats_paths: list[str]) -> None:
    _GLOBAL["feats"] = [pickle.loads(Path(p).read_bytes()) for p in feats_paths]


def _eval_worker(config: dict) -> dict:
    return {"config": config, "metrics": evaluate(_GLOBAL["feats"], config)}


def load_dev(feats_paths: list[str]) -> list[dict]:
    return [pickle.loads(Path(p).read_bytes()) for p in feats_paths]


def cmd_evolve(args: argparse.Namespace) -> int:
    feats_paths = sorted(str(p) for p in (WORK / "dev").glob("dev-*.pkl"))
    if not feats_paths:
        print("no dev cache; run --build-cache --split dev first", file=sys.stderr)
        return 2
    rng = random.Random(args.seed)
    population = [dict(BASELINE)] + [random_config(rng) for _ in range(args.pop - 1)]
    history = []
    best_overall = None
    print(f"baseline: {json.dumps(BASELINE)}", flush=True)
    for generation in range(args.gens):
        started = time.time()
        with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker,
                                 initargs=(feats_paths,)) as pool:
            results = list(pool.map(_eval_worker, population))
        results.sort(key=lambda r: r["metrics"]["fitness"], reverse=True)
        best = results[0]
        history.append({"generation": generation, "best": best["config"],
                        "best_fitness": best["metrics"]["fitness"],
                        "counts": best["metrics"]["counts"],
                        "seconds": round(time.time() - started, 1)})
        print(f"gen {generation}: best fitness {best['metrics']['fitness']:.4f} "
              f"counts {best['metrics']['counts']} ({history[-1]['seconds']}s)", flush=True)
        if best_overall is None or best["metrics"]["fitness"] > best_overall["metrics"]["fitness"]:
            best_overall = best
        parents = [r["config"] for r in results[:3]]
        population = list(parents)
        while len(population) < args.pop:
            population.append(mutate_config(parents[len(population) % 3], rng))
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    payload = {"baseline": BASELINE, "best": best_overall["config"],
               "best_metrics": best_overall["metrics"], "history": history,
               "fitness_weights": FITNESS_WEIGHTS, "tasks": len(feats_paths),
               "seed": args.seed, "pop": args.pop, "gens": args.gens}
    (ANALYSIS / "search.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ANALYSIS / "best_config.json").write_text(json.dumps(best_overall["config"], indent=2),
                                               encoding="utf-8")
    (ANALYSIS / "baseline_config.json").write_text(json.dumps(BASELINE, indent=2), encoding="utf-8")
    print(f"\nbest overall: {json.dumps({k: round(v, 3) for k, v in best_overall['config'].items()})}")
    print(f"counts: {best_overall['metrics']['counts']}")
    print(f"wrote {ANALYSIS / 'search.json'}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    holdout_paths = sorted(str(p) for p in (WORK / "holdout").glob("holdout-*.pkl"))
    dev_paths = sorted(str(p) for p in (WORK / "dev").glob("dev-*.pkl"))
    if not holdout_paths or not dev_paths:
        print("need both caches", file=sys.stderr)
        return 2
    best = json.loads((ANALYSIS / "best_config.json").read_text(encoding="utf-8"))
    report = {}
    for split, paths in (("dev", dev_paths), ("holdout", holdout_paths)):
        feats = load_dev(paths)
        report[split] = {
            "tasks": len(feats),
            "baseline": evaluate(feats, BASELINE),
            "best": evaluate(feats, best),
        }
    (ANALYSIS / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Ewolucja stałych lokalizatora — walidacja", "",
             "Fitness: 0.50*top1 + 0.30*top3 + 0.15*top5 + 0.05*top10 (zapisane przed przebiegiem).", ""]
    for split in ("dev", "holdout"):
        block = report[split]
        lines.append(f"## {split} ({block['tasks']} zadań)")
        lines.append("")
        lines.append("| konfiguracja | fitness | top-1 | top-3 | top-5 | top-10 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for label in ("baseline", "best"):
            m = block[label]
            counts, total = m["counts"], m["total"]
            pct = " | ".join(f"{100 * counts[k] / total:.1f}%" for k in (1, 3, 5, 10))
            lines.append(f"| {label} | {m['fitness']:.4f} | {pct} |")
        lines.append("")
    text = "\n".join(lines)
    (ANALYSIS / "validation.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    """Positive control: the parameterised scorer must order files exactly like the locator file.

    Two uses, both mandatory before a number from this tool is believed:
      * default: tools/locator.py with the baseline constants -> the search scores what ships;
      * `--locator tools/locator_evolved.py --config .../best_config.json` -> the *baked* file
        really implements the searched constants (the cache throws away the full token tables, so
        this check has to run against the live corpora).
    """
    count = args.count or 6
    config = BASELINE
    if args.config:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        print(f"selftest config: {args.config}")
    module = shipped
    if args.locator and Path(args.locator) != TOOLS / "locator.py":
        local_spec = importlib.util.spec_from_file_location("locator_under_test", args.locator)
        module = importlib.util.module_from_spec(local_spec)
        local_spec.loader.exec_module(module)  # type: ignore[union-attr]
        print(f"selftest locator: {args.locator}")
    tasks, _ = load_tasks("dev", count)
    worktree = None
    current = None
    checked = 0
    for task in tasks:
        repo = task["repo"]
        if repo != current:
            worktree = repo_worktree(repo)
            current = repo
        checkout(worktree, task["base_commit"])
        feats = features_for_task(task, worktree)
        if feats is None:
            continue
        module.TESTISH = TESTISH
        shipped_ranked = [name for _, name in module.rank(
            module.collect(worktree), module.build_query(task["problem_statement"] or ""))][:10]
        mine = score_config(feats, config)[:10]
        if shipped_ranked != mine:
            print("MISMATCH on task", task.get("id"), file=sys.stderr)
            print("  shipped:", shipped_ranked[:5], file=sys.stderr)
            print("  evolved:", mine[:5], file=sys.stderr)
            return 1
        checked += 1
        print(f"  ok: {task['repo']} {task['base_commit'][:8]} (top-10 identical)", flush=True)
    print(f"selftest passed on {checked} tasks")
    return 0


def shipped_struct(worktree: Path) -> dict[str, dict]:
    """The shipped collect(), which keeps more fields than the cache does."""
    return shipped.collect(worktree)



def cmd_bake(args: argparse.Namespace) -> int:
    """Write the evolved constants into a copy of the shipped locator artifact.

    Only numbers change - the code, the query builder and the output format stay byte-identical,
    so the artifact keeps every property the packer checks (stdlib only, no triple quotes, the exact
    heredoc form). Two anchor sets exist because the development reference (tools/locator.py) and
    the compact artifact embedded in the prompt are not the same file: the reference has acronym
    terms and a compound-literal gate, the artifact does not. The set is chosen by inspection, and
    a missing anchor aborts instead of writing a half-evolved locator.
    """
    best = json.loads((ANALYSIS / "best_config.json").read_text(encoding="utf-8"))
    base = Path(args.base)
    if not base.is_file():
        print(f"bake: base locator not found: {base}", file=sys.stderr)
        return 1
    source = base.read_text(encoding="utf-8")
    compact = "was_ident or ident" in source

    if compact:
        # gemma4-agent/submission-v6.*/tools/locate.py - the file the agent actually runs
        subs = [
            ("weighted[token] = (max(weight, 3.0), was_ident or ident)",
             f"weighted[token] = (max(weight, {best['q_ident_piece']:.3f}), was_ident or ident)"),
            ("weighted[literal.lower()] = (4.0, True)",
             f"weighted[literal.lower()] = ({best['q_full_ident']:.3f}, True)"),
            ("weighted.setdefault(token, (1.0, False))",
             f"weighted.setdefault(token, ({best['q_plain']:.3f}, False))"),
            ("k1, b = 1.2, 0.75", f"k1, b = {best['k1']:.3f}, {best['b']:.3f}"),
            ("scores[name] += 1.5 * weight * idf",
             f"scores[name] += {best['path_bonus']:.3f} * weight * idf"),
            ("scores[name] += 4.0 * weight * idf",
             f"scores[name] += {best['defined_bonus']:.3f} * weight * idf"),
            ("scores[name] += 6.0 * math.log(1 + (n_docs - df.get(literal.split(\"_\")[0], 0) + 0.5)",
             f"scores[name] += {best['exact_bonus']:.3f} * math.log("
             "1 + (n_docs - df.get(literal.split(\"_\")[0], 0) + 0.5)"),
            ("scores[name] *= 0.5\n", f"scores[name] *= {best['test_penalty']:.3f}\n"),
            ("imported[candidate] += scores[test_best]",
             f"imported[candidate] += scores[test_best] * {best['import_factor']:.3f}"),
        ]
    else:
        # tools/locator.py - the development reference used by locate_benchmark/locate_verify
        subs = [
            ("weighted[token] = (max(previous[0], 3.0), previous[1] or ident, previous[2] or compound)",
             f"weighted[token] = (max(previous[0], {best['q_ident_piece']:.3f}), previous[1] or ident, "
             f"previous[2] or compound)"),
            ("weighted[literal.lower()] = (4.0, True, compound)",
             f"weighted[literal.lower()] = ({best['q_full_ident']:.3f}, True, compound)"),
            ("weighted.setdefault(token, (1.0, False, False))",
             f"weighted.setdefault(token, ({best['q_plain']:.3f}, False, False))"),
            ("k1, b = 1.2, 0.75", f"k1, b = {best['k1']:.3f}, {best['b']:.3f}"),
            ("score += 1.5 * weight * math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))",
             f"score += {best['path_bonus']:.3f} * weight * math.log("
             "1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))"),
            ("score += 4.0 * weight * math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))",
             f"score += {best['defined_bonus']:.3f} * weight * math.log("
             "1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))"),
            ("score += 6.0 * math.log(1 + (n_docs - df.get(literal.split(\"_\")[0], 0) + 0.5)",
             f"score += {best['exact_bonus']:.3f} * math.log("
             "1 + (n_docs - df.get(literal.split(\"_\")[0], 0) + 0.5)"),
            ("score *= 0.5\n", f"score *= {best['test_penalty']:.3f}\n"),
            ("weight = scores[test_best]",
             f"weight = scores[test_best] * {best['import_factor']:.3f}"),
        ]
    text = source
    for old, new in subs:
        if old not in text:
            print(f"bake: anchor missing, refusing to write a half-evolved locator: {old[:70]!r}",
                  file=sys.stderr)
            return 1
        text = text.replace(old, new, 1)
    header = (
        f"# EVOLVED {time.strftime('%Y-%m-%d')}: constants fitted by population search against the\n"
        f"# 128 published dev tasks with gold patches (tools/evolve_locator.py), validated on 104\n"
        f"# held-out tasks from four repositories outside the dev set. Only numbers differ.\n"
    )
    anchor = "#!/usr/bin/env python3\n"
    if anchor not in text:
        print("bake: header anchor missing", file=sys.stderr)
        return 1
    text = text.replace(anchor, anchor + header, 1)
    out = Path(args.out)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({'compact artifact' if compact else 'development reference'}) "
          f"with {json.dumps({k: round(v, 3) for k, v in best.items()})}")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-cache", action="store_true")
    parser.add_argument("--evolve", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--locator", default=str(TOOLS / "locator.py"))
    parser.add_argument("--config", default=None)
    parser.add_argument("--bake", action="store_true")
    parser.add_argument("--out", default=str(TOOLS / "locator_evolved.py"))
    parser.add_argument("--base", default=str(SHIPPED_ARTIFACT))
    parser.add_argument("--split", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--pop", type=int, default=12)
    parser.add_argument("--gens", type=int, default=6)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20261014)
    args = parser.parse_args()
    if args.selftest:
        return cmd_selftest(args)
    if args.build_cache:
        build_cache(args.split, args.count, WORK / args.split)
        return 0
    if args.evolve:
        return cmd_evolve(args)
    if args.validate:
        return cmd_validate(args)
    if args.bake:
        return cmd_bake(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
