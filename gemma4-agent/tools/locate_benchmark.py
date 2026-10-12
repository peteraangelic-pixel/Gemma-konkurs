#!/usr/bin/env python3
"""Offline issue -> file localization benchmark on the 129 published dev tasks.

Why this exists: DIAGNOSIS.md 4.7 identifies localization as the real bottleneck
(a peer measured 30% first-grep hit rate, 61% top-5 with grep + BM25, and 35/128
issues containing no code identifier at all). Localization is fully deterministic,
so it can be measured offline on CPU: no GPU, no Kaggle slot, no agent run.

For every task the script checks out its base_commit in a blobless partial clone,
extracts anchors from the problem statement, ranks repository files with several
deterministic recipes, and scores whether a file touched by the gold patch lands in
the top-1/5/10 of that ranking. The winning recipe is what we bake into the agent
prompt as an explicit grep/search procedure.

Usage:
    python3 gemma4-agent/tools/locate_benchmark.py --outdir gemma4-agent/analysis/locate-benchmark
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_CACHE = Path(os.environ.get("GEMMA_REPO_CACHE", Path.home() / ".cache" / "gemma-repos"))
TASKS_COMMIT = "c0256ba"
TEXT_SUFFIXES = {
    ".py", ".pyi", ".pyx", ".rst", ".md", ".txt", ".toml", ".cfg", ".ini",
    ".yaml", ".yml", ".json", ".sh", ".in",
}
SKIP_DIR_PARTS = {".git", "node_modules", ".tox", ".venv", "build", "dist", "__pycache__"}
MAX_FILE_BYTES = 400_000

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
BACKTICK_RE = re.compile(r"`([^`\n]{3,120})`")
QUOTED_RE = re.compile(r"[\"'']([^\"'\n]{6,120})[\"''']")
DOTTED_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){1,6})\b")
UNDERSCORE_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]{2,})\b")
CAMEL_RE = re.compile(r"\b([a-z]+[A-Z][A-Za-z0-9]{2,})\b")
EXC_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:Error|Exception|Warning|Exit))\b")
CALL_RE = re.compile(r"\b([a-zA-Z_][A-Za-z0-9_]{2,})\s*\(")
PATH_RE = re.compile(r"\b([A-Za-z0-9_./-]+\.(?:py|pyi|rst|md|txt|toml|cfg|ini|yml|yaml))\b")

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "not", "are",
    "was", "were", "when", "which", "should", "would", "could", "does", "did", "but",
    "you", "your", "its", "it's", "using", "use", "used", "can", "cannot", "will",
    "then", "than", "there", "here", "into", "only", "also", "some", "any", "all",
    "get", "got", "make", "made", "add", "added", "fix", "fixed", "bug", "issue",
    "test", "tests", "code", "file", "files", "error", "errors", "instead", "expected",
    "actual", "version", "example", "please", "thanks", "hello", "print", "true",
    "false", "none", "null", "return", "returns", "returned", "call", "calls",
}


def tasks_from_git(path: Path | None, count: int | None) -> list[dict]:
    if path is not None:
        raw = path.read_text(encoding="utf-8")
    else:
        raw = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", f"{TASKS_COMMIT}:tasks.jsonl"],
            check=True, capture_output=True, text=True,
        ).stdout
    tasks = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if count:
        tasks = tasks[:count]
    return tasks


def repo_worktree(repo: str) -> Path:
    local = REPO_CACHE / repo.replace("/", "_")
    if not local.is_dir():
        REPO_CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
             f"https://github.com/{repo}.git", str(local)],
            check=True, capture_output=True, text=True,
        )
    return local


def checkout(worktree: Path, sha: str) -> None:
    subprocess.run(["git", "-C", str(worktree), "checkout", "-q", "-f", sha],
                   check=True, capture_output=True, text=True)


LEARN_SUFFIXES = (".md", ".rst", ".txt")


def is_fixable(path: str) -> bool:
    """True for files the agent could legitimately edit to change test behaviour."""
    return (path.endswith((".py", ".pyi"))
            and not path.startswith(("docs/", "tests/", "scripts/"))
            and "/docs/" not in path and "/tests/" not in path)


def gold_files(patch: str) -> tuple[list[str], list[str]]:
    """Split gold patch paths into code files and test files."""
    code, tests = [], []
    for line in patch.splitlines():
        if not line.startswith("+++ "):
            continue
        raw = line[4:].strip()
        if raw.startswith("b/"):
            raw = raw[2:]
        if raw in ("/dev/null", ""):
            continue
        path = raw.split("\t")[0]
        if "_test" in path or path.startswith("tests/") or "/tests/" in path:
            tests.append(path)
        else:
            code.append(path)
    return sorted(set(code)), sorted(set(tests))


def anchors_from_statement(statement: str) -> list[str]:
    """Ordered, de-duplicated anchors: exactly what a careful grep session would try."""
    found: list[str] = []
    seen: set[str] = set()

    def push(value: str, weight: int = 0) -> None:
        value = value.strip().strip(".,;:()[]{}'\"")
        if len(value) < 3 or value.lower() in STOPWORDS:
            return
        if value.isdigit():
            return
        if value in seen:
            return
        seen.add(value)
        found.append(value)

    for match in PATH_RE.finditer(statement):
        push(match.group(1), 5)
    for match in EXC_RE.finditer(statement):
        push(match.group(1), 4)
    for match in BACKTICK_RE.finditer(statement):
        span = match.group(1).strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{2,}", span):
            push(span, 4)
        else:
            push(span, 2)
            for token in IDENT_RE.finditer(span):
                push(token.group(0), 1)
    for match in DOTTED_RE.finditer(statement):
        push(match.group(1), 4)
    for match in UNDERSCORE_RE.finditer(statement):
        push(match.group(1), 3)
    for match in CAMEL_RE.finditer(statement):
        push(match.group(1), 3)
    for match in CALL_RE.finditer(statement):
        push(match.group(1), 3)
    for match in QUOTED_RE.finditer(statement):
        push(match.group(1), 2)
    return found


def read_corpus(worktree: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for root, dirs, names in os.walk(worktree):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_PARTS]
        for name in names:
            path = Path(root) / name
            if path.suffix not in TEXT_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                files[str(path.relative_to(worktree))] = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
    return files


def bm25_scores(corpus: dict[str, str], query_terms: list[str], k1: float = 1.2, b: float = 0.75) -> dict[str, float]:
    docs = {}
    for name, text in corpus.items():
        tokens = [t.lower() for t in IDENT_RE.findall(text)]
        docs[name] = Counter(tokens)
    n_docs = max(1, len(docs))
    avg_len = sum(sum(c.values()) for c in docs.values()) / n_docs
    df = Counter()
    for counts in docs.values():
        for term in set(query_terms):
            if counts.get(term.lower()):
                df[term] += 1
    scores: dict[str, float] = {}
    for name, counts in docs.items():
        length = sum(counts.values()) or 1
        score = 0.0
        for term in set(query_terms):
            freq = counts.get(term.lower(), 0)
            if not freq:
                continue
            idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * length / avg_len))
        if score:
            scores[name] = score
    return scores


SPLIT_RE = re.compile(r"[^A-Za-z0-9]+")


def subtokens(text: str) -> list[str]:
    """Split identifiers/words into lowercase subtokens: strict_content_type -> strict,content,type."""
    out: list[str] = []
    for chunk in SPLIT_RE.split(text):
        if not chunk:
            continue
        for piece in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", chunk):
            piece = piece.lower()
            if len(piece) >= 2:
                out.append(piece)
    return out


def acronyms(text: str) -> list[str]:
    """'Server Sent Events' -> 'sse', so titles can match module/file names."""
    found = []
    for run in re.findall(r"\b(?:[A-Z][a-z0-9]*\s+){1,4}[A-Z][a-z0-9]*\b", text):
        words = run.split()
        if len(words) >= 2 and all(w[0].isupper() for w in words):
            acr = "".join(w[0] for w in words).lower()
            if len(acr) >= 2:
                found.append(acr)
    return found


def subtokenize_corpus(corpus: dict[str, str]) -> dict[str, dict]:
    struct: dict[str, dict] = {}
    for name, text in corpus.items():
        if not name.endswith((".py", ".pyi", ".pyx")):
            continue
        struct[name] = {
            "tokens": Counter(subtokens(text)),
            "path": set(subtokens(name)),
            "defined": set(subtokens(" ".join(
                re.findall(r"(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", text)))),
        }
    return struct


def query_terms(statement: str, anchors: list[str]) -> list[tuple[str, float]]:
    """Weighted subtoken query: literal identifiers outrank prose words."""
    weighted: dict[str, float] = {}
    for anchor in anchors:
        weight = 3.0 if any(ch in anchor for ch in "_.:()$") or any(
            c.isupper() for c in anchor[1:]) else 2.0
        for token in subtokens(anchor) or [anchor.lower()]:
            if token in STOPWORDS:
                continue
            weighted[token] = max(weighted.get(token, 0.0), weight)
    for token in subtokens(statement):
        if token in STOPWORDS or len(token) < 3:
            continue
        weighted.setdefault(token, 1.0)
    for acr in acronyms(statement):
        weighted[acr] = max(weighted.get(acr, 0.0), 2.0)
    return sorted(weighted.items(), key=lambda kv: -kv[1])


def rank_subtoken(corpus: dict[str, str], anchors: list[str], statement: str) -> dict[str, float]:
    struct = subtokenize_corpus(corpus)
    if not struct:
        return {}
    n_docs = len(struct)
    doc_len = {name: sum(d["tokens"].values()) or 1 for name, d in struct.items()}
    avg_len = sum(doc_len.values()) / n_docs
    df: Counter = Counter()
    terms = query_terms(statement, anchors)
    for term, _ in terms:
        for name, data in struct.items():
            if data["tokens"].get(term):
                df[term] += 1
    k1, b = 1.2, 0.75
    scores: dict[str, float] = {}
    for name, data in struct.items():
        score = 0.0
        length = doc_len[name]
        for term, weight in terms:
            idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            freq = data["tokens"].get(term, 0)
            if freq:
                score += weight * idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * length / avg_len))
            if term in data["path"]:
                score += 1.5 * weight * idf
            if term in data["defined"]:
                score += 2.5 * weight * idf
        if score:
            scores[name] = score
    return scores


def basename_bonus(path: str, anchor: str) -> float:
    stem = Path(path).stem.lower()
    parts = [p.lower() for p in Path(path).parts]
    anchor_l = anchor.lower()
    bonus = 0.0
    if anchor_l == stem:
        bonus += 6.0
    elif anchor_l in stem or stem in anchor_l:
        bonus += 3.0
    if any(anchor_l == part or anchor_l == Path(part).stem for part in parts):
        bonus += 2.0
    if any(anchor_l in part for part in parts[:-1]):
        bonus += 0.5
    return bonus


def rank_recipes(corpus: dict[str, str], anchors: list[str], statement: str) -> dict[str, list[str]]:
    names = list(corpus)
    low = {name: corpus[name].lower() for name in names}

    # R0: first identifier that matches anything wins (peer's baseline "grep hit").
    first_hit: list[str] = []
    for anchor in anchors:
        needle = anchor.lower()
        hits = [name for name in names if needle in low[name]]
        if hits:
            first_hit = hits
            break

    # R1: vote by number of distinct anchors present in the file.
    votes: dict[str, float] = defaultdict(float)
    matched: dict[str, int] = defaultdict(int)
    for index, anchor in enumerate(anchors):
        needle = anchor.lower()
        weight = 1.0 / (1.0 + 0.05 * index)
        for name in names:
            if needle in low[name]:
                votes[name] += weight + basename_bonus(name, anchor)
                matched[name] += 1

    # R2: anchor votes + BM25 over statement terms.
    terms = [t for t in IDENT_RE.findall(statement) if len(t) > 2 and t.lower() not in STOPWORDS]
    bm = bm25_scores(corpus, terms[:400])
    combined = dict(votes)
    for name, score in bm.items():
        combined[name] = combined.get(name, 0.0) + 2.5 * score

    # R3: R2 restricted to files that match at least one anchor (precision guard),
    # falling back to BM25-only ranking when no anchor matches anything.
    anchored = {name: score for name, score in combined.items() if matched.get(name)}
    seen_rank = lambda table: sorted(  # noqa: E731
        table, key=lambda n: (-table[n], -matched.get(n, 0), len(n), n))

    def rank_scores(table: dict[str, float]) -> list[str]:
        return sorted(table, key=lambda n: (-table[n], len(n), n))

    return {
        "R0_first_grep": first_hit,
        "R1_anchor_votes": seen_rank(votes),
        "R2_votes_bm25": seen_rank(combined),
        "R3_guarded": seen_rank(anchored) if anchored else seen_rank(combined),
        "R4_subtoken": rank_scores(rank_subtoken(corpus, anchors, statement)) if corpus else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path, default=REPO_ROOT / "gemma4-agent" / "analysis" / "locate-benchmark")
    parser.add_argument("--tasks", type=Path, default=None, help="tasks.jsonl (default: read from git commit)")
    parser.add_argument("--count", type=int, default=None, help="limit number of tasks")
    args = parser.parse_args()

    tasks = tasks_from_git(args.tasks, args.count)
    print(f"tasks: {len(tasks)}", flush=True)

    recipes = ["R0_first_grep", "R1_anchor_votes", "R2_votes_bm25", "R3_guarded", "R4_subtoken"]
    targets = ["fixable", "any_py", "any"]
    hits = {r: {t: {1: 0, 5: 0, 10: 0} for t in targets} for r in recipes}
    target_counts = Counter()
    scored = 0
    per_task = []
    no_anchor = 0
    started = time.time()

    current_repo = None
    worktree = None
    for index, task in enumerate(tasks, start=1):
        repo = task["repo"]
        statement = task.get("problem_statement") or ""
        gold_code, gold_tests = gold_files(task.get("patch") or "")
        gold_targets = gold_code or gold_tests
        if not gold_targets:
            continue
        target_sets = {
            "fixable": [p for p in gold_targets if is_fixable(p)],
            "any_py": [p for p in gold_targets if p.endswith((".py", ".pyi"))],
            "any": list(gold_targets),
        }
        for kind, paths in target_sets.items():
            if paths:
                target_counts[kind] += 1
        if repo != current_repo:
            worktree = repo_worktree(repo)
            current_repo = repo
        try:
            checkout(worktree, task["base_commit"])
        except subprocess.CalledProcessError as exc:
            print(f"  ! checkout failed {task['instance_id']}: {exc.stderr[:120]}", flush=True)
            continue
        corpus = read_corpus(worktree)
        anchors = anchors_from_statement(statement)
        if not anchors:
            no_anchor += 1
        rankings = rank_recipes(corpus, anchors, statement)
        scored += 1
        row = {"instance_id": task["instance_id"], "repo": repo, "gold_code": gold_code,
               "anchor_count": len(anchors)}
        for recipe in recipes:
            ranked = rankings[recipe]
            row[recipe] = {}
            for kind, paths in target_sets.items():
                if not paths:
                    continue
                for k in (1, 5, 10):
                    if set(ranked[:k]) & set(paths):
                        hits[recipe][kind][k] += 1
                row[recipe][kind] = {"top1": ranked[0] if ranked and ranked[0] in paths else None,
                                     "top5": ranked[:5], "hit5": bool(set(ranked[:5]) & set(paths))}
        per_task.append(row)
        if index % 10 == 0 or index == len(tasks):
            print(f"  {index}/{len(tasks)} tasks, {time.time() - started:.0f}s", flush=True)

    summary = {
        "tasks_scored": scored,
        "tasks_without_anchors": no_anchor,
        "repos": sorted({t["repo"] for t in tasks}),
        "target_counts": dict(target_counts),
        "hit_rates": {
            r: {f"{t}_top{k}": round(hits[r][t][k] / max(1, target_counts[t]), 4)
                for t in targets for k in (1, 5, 10)}
            for r in recipes
        },
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "locate_result.json").write_text(
        json.dumps({"summary": summary, "tasks": per_task}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
