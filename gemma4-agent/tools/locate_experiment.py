#!/usr/bin/env python3
"""Fast experiment loop over localization ranking variants (offline, CPU only).

Reuses one corpus read per task and evaluates several scoring variants, so ranking
ideas can be compared on all 129 published dev tasks in a couple of minutes instead
of guessing in the prompt. Target = a *fixable* source file from the gold patch
(.py, not under docs/, tests/, scripts/).

Usage:
    python3 gemma4-agent/tools/locate_experiment.py --outdir gemma4-agent/analysis/locate-experiment
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from locate_benchmark import (  # noqa: E402
    REPO_ROOT, STOPWORDS, anchors_from_statement, gold_files, is_fixable,
    read_corpus, repo_worktree, subtokens, tasks_from_git, checkout,
)

TESTISH = ("tests/", "test_", "_test.", "conftest")


def structures(corpus: dict[str, str]) -> dict[str, dict]:
    struct = {}
    for name, text in corpus.items():
        if not name.endswith((".py", ".pyi")):
            continue
        struct[name] = {
            "tokens": Counter(subtokens(text)),
            "path": set(subtokens(name)),
            "defined": set(subtokens(" ".join(
                __import__("re").findall(r"(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", text)))),
            "exact": text,
            "imports": _imports(text),
        }
    return struct


IMPORT_RE = re.compile(r"^\s*(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_.]+))", re.MULTILINE)


def _imports(text: str) -> set[str]:
    found: set[str] = set()
    for match in IMPORT_RE.finditer(text):
        module = match.group(1) or match.group(2) or ""
        if module:
            found.add(module)
    return found


def module_to_paths(module: str) -> list[str]:
    base = module.replace(".", "/")
    return [f"{base}.py", f"{base}/__init__.py"]


def df_table(struct: dict[str, dict]) -> Counter:
    df: Counter = Counter()
    for data in struct.values():
        for term in data["tokens"]:
            df[term] += 1
    return df


def query_terms(statement: str, anchors: list[str]) -> dict[str, tuple[float, bool]]:
    """term -> (weight, is_exact_identifier_literal)."""
    weighted: dict[str, tuple[float, bool]] = {}
    for anchor in anchors:
        literal = anchor.lower()
        ident = bool(__import__("re").fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", anchor))
        pieces = subtokens(anchor) or [literal]
        for token in pieces:
            if token in STOPWORDS:
                continue
            weight = 3.0 if ident else 2.0
            weighted[token] = (max(weighted.get(token, (0.0, False))[0], weight),
                               weighted.get(token, (0.0, False))[1] or ident)
        if ident and "_" in anchor:
            weighted[literal] = (4.0, True)
    for token in subtokens(statement):
        if token in STOPWORDS or len(token) < 3:
            continue
        weighted.setdefault(token, (1.0, False))
    return weighted


def score_variant(struct, query, df, n_docs, doc_len, avg_len, *, exact_bonus, test_penalty,
                  path_bonus, defined_bonus, exact_gate, import_boost=0.0,
                  union_boost=0.0, union_top1_only=0.0):
    k1, b = 1.2, 0.75
    exacts = {term for term, (_, is_exact) in query.items() if is_exact}
    scores = defaultdict(float)
    for name, data in struct.items():
        score = 0.0
        length = doc_len[name]
        for term, (weight, _) in query.items():
            freq = data["tokens"].get(term, 0)
            if freq:
                idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
                score += weight * idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * length / avg_len))
            if term in data["path"]:
                score += path_bonus * weight * math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            if term in data["defined"]:
                score += defined_bonus * weight * math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
        # exact identifier literal present in the source text: strongest single signal
        if exact_bonus:
            for literal in exacts:
                if literal in data["exact"].lower():
                    score += exact_bonus * math.log(1 + (n_docs - df[literal.split("_")[0]] + 0.5)
                                                     / (df[literal.split("_")[0]] + 0.5))
        if score and any(part in name for part in TESTISH):
            score *= test_penalty
        if score:
            scores[name] = score
    if import_boost:
        scores = defaultdict(float, propagate_imports(struct, dict(scores), import_boost=import_boost))
    if union_boost or union_top1_only:
        # propagate only from the single best-matching test file, then interleave the two
        # rankings so the shortlist keeps both the content and the import signal
        content_rank = sorted(scores, key=lambda n: (-scores[n], len(n), n))
        test_best = next((n for n in content_rank if any(part in n for part in TESTISH)), None)
        source_only = {n: v for n, v in scores.items() if not any(part in n for part in TESTISH)}
        imported = defaultdict(float)
        if test_best:
            imported = defaultdict(float, propagate_imports(
                struct, {test_best: union_top1_only or scores[test_best] * union_boost},
                import_boost=1.0 / max(1e-9, scores[test_best]) if union_top1_only == 0 else 1.0))
        import_rank = sorted((n for n in imported if not any(part in n for part in TESTISH)),
                             key=lambda n: (-imported[n], len(n), n))
        merged = dict(source_only)
        for name, value in imported.items():
            if name in merged:
                merged[name] += value
        union_order = []
        for a, b in zip(content_rank, import_rank + [None] * len(content_rank)):
            for candidate in (a, b):
                if candidate and candidate not in union_order and candidate in merged:
                    union_order.append(candidate)
        for candidate in content_rank:
            if candidate not in union_order:
                union_order.append(candidate)
        scores = defaultdict(float, merged)
        ranked_order = union_order
    else:
        ranked_order = None
    if exact_gate:
        gated = {n: s for n, s in scores.items()
                 if any(lit in struct[n]["exact"].lower() for lit in exacts)} if exacts else scores
        if gated:
            scores = gated
    if ranked_order is not None:
        return ranked_order
    return sorted(scores, key=lambda n: (-scores[n], len(n), n))


def propagate_imports(struct, base_scores, *, import_boost: float, test_only: bool = True) -> dict[str, float]:
    """Hidden tests import the module under test; repo tests are the visible proxy for that.

    For each test file that scores well, push part of its score onto the modules it imports,
    which is how a *source* file gets surfaced for feature-add tasks where the new module
    does not exist yet at the base commit.
    """
    scores = dict(base_scores)
    plain = lambda n: [p for p in struct if p == n]  # noqa: E731
    index = {name: name for name in struct}
    for name, data in struct.items():
        is_test = any(part in name for part in TESTISH)
        if test_only and not is_test:
            continue
        weight = base_scores.get(name, 0.0)
        if weight <= 0:
            continue
        for module in data.get("imports", ()):  # type: ignore[attr-defined]
            for candidate in module_to_paths(module):
                if candidate in struct:
                    scores[candidate] = scores.get(candidate, 0.0) + import_boost * weight
                elif candidate.removesuffix("/__init__.py") in index:
                    target = candidate.removesuffix("/__init__.py")
                    scores[target] = scores.get(target, 0.0) + import_boost * weight
    return scores


VARIANTS = {
    "V_base": dict(exact_bonus=0.0, test_penalty=1.0, path_bonus=1.5, defined_bonus=2.5, exact_gate=False),
    "V_exact": dict(exact_bonus=6.0, test_penalty=1.0, path_bonus=1.5, defined_bonus=2.5, exact_gate=False),
    "V_exact_src": dict(exact_bonus=6.0, test_penalty=0.5, path_bonus=1.5, defined_bonus=2.5, exact_gate=False),
    "V_exact_src_def": dict(exact_bonus=6.0, test_penalty=0.5, path_bonus=1.0, defined_bonus=5.0, exact_gate=False),
    "V_gate_src": dict(exact_bonus=6.0, test_penalty=0.5, path_bonus=1.5, defined_bonus=2.5, exact_gate=True),
    "V_gate_src_def": dict(exact_bonus=6.0, test_penalty=0.5, path_bonus=1.5, defined_bonus=4.0, exact_gate=True),
    "V_import_light": dict(exact_bonus=6.0, test_penalty=0.5, path_bonus=1.0, defined_bonus=5.0,
                           exact_gate=False, import_boost=0.05),
    "V_union_light": dict(exact_bonus=6.0, test_penalty=0.5, path_bonus=1.0, defined_bonus=5.0,
                          exact_gate=False, import_boost=0.0, union_boost=0.05),
    "V_union_top1": dict(exact_bonus=6.0, test_penalty=0.5, path_bonus=1.0, defined_bonus=5.0,
                         exact_gate=False, import_boost=0.0, union_boost=0.05, union_top1_only=0.3),
    "V_import_mid": dict(exact_bonus=6.0, test_penalty=0.5, path_bonus=1.0, defined_bonus=5.0,
                         exact_gate=False, import_boost=0.15),
    "V_import_strong": dict(exact_bonus=6.0, test_penalty=0.5, path_bonus=1.0, defined_bonus=5.0,
                            exact_gate=False, import_boost=0.4),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path,
                        default=REPO_ROOT / "gemma4-agent" / "analysis" / "locate-experiment")
    parser.add_argument("--count", type=int, default=None)
    args = parser.parse_args()

    tasks = tasks_from_git(None, args.count)
    hits = {variant: {1: 0, 5: 0, 10: 0} for variant in VARIANTS}
    scored = 0
    repo_scored: Counter = Counter()
    per_repo_hits: dict[str, Counter] = {variant: Counter() for variant in VARIANTS}
    worktree = None
    current_repo = None
    per_variant_top1 = defaultdict(int)

    for index, task in enumerate(tasks, start=1):
        repo = task["repo"]
        statement = task.get("problem_statement") or ""
        code, tests = gold_files(task.get("patch") or "")
        targets = [p for p in (code or tests) if is_fixable(p)]
        if not targets:
            continue
        if repo != current_repo:
            worktree = repo_worktree(repo)
            current_repo = repo
        checkout(worktree, task["base_commit"])
        corpus = read_corpus(worktree)
        struct = structures(corpus)
        if not struct:
            continue
        n_docs = len(struct)
        doc_len = {name: sum(d["tokens"].values()) or 1 for name, d in struct.items()}
        avg_len = sum(doc_len.values()) / n_docs
        df = df_table(struct)
        query = query_terms(statement, anchors_from_statement(statement))
        scored += 1
        repo_scored[repo] += 1
        for variant, kwargs in VARIANTS.items():
            ranked = score_variant(struct, query, df, n_docs, doc_len, avg_len, **kwargs)
            for k in (1, 5, 10):
                if set(ranked[:k]) & set(targets):
                    hits[variant][k] += 1
            if set(ranked[:5]) & set(targets):
                per_repo_hits[variant][repo] += 1
            if ranked and ranked[0] in targets:
                per_variant_top1[variant] += 1
        if index % 25 == 0:
            print(f"  {index}/{len(tasks)} tasks", flush=True)

    summary = {
        "tasks_scored": scored,
        "per_repo_scored": dict(repo_scored),
        "per_repo_top5": {v: dict(counts) for v, counts in per_repo_hits.items()},
        "target": "fixable gold source file (.py, not docs/tests/scripts)",
        "variants": VARIANTS,
        "hit_rates": {
            variant: {f"top{k}": round(hits[variant][k] / max(1, scored), 4) for k in (1, 5, 10)}
            for variant in VARIANTS
        },
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "experiment_result.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary["hit_rates"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
