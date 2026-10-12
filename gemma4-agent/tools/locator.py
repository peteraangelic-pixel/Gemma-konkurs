#!/usr/bin/env python3
"""Agent-facing issue->file locator (stdlib only, no network, runs inside the Kaggle sandbox).

This is the V6 localization step: instead of the model guessing greps, it writes this
script to /tmp, runs it once with the raw problem statement, and gets a ranked list of
the repository files most likely to need the fix, each with matching evidence lines.

Measured offline on the 129 published dev tasks (gemma4-agent/tools/locate_benchmark.py):
plain first-grep hits the fixable source file in ~15% of tasks at top-5, this recipe in ~54%
(53.9% top-5, 61.7% top-10). The recipes are identical, so the prompt can rely on it.

Usage:
    python3 /tmp/locate.py --root . --issue-file /tmp/issue.txt --top 10
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".tox", ".venv", "venv", "build", "dist",
             "__pycache__", ".mypy_cache", ".pytest_cache", "docs", "site-packages"}
TEXT_SUFFIXES = {".py", ".pyi"}
MAX_FILE_BYTES = 400_000
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "not", "are",
    "was", "were", "when", "which", "should", "would", "could", "does", "did", "but",
    "you", "your", "its", "using", "use", "used", "can", "cannot", "will", "then",
    "than", "there", "here", "into", "only", "also", "some", "any", "all", "get",
    "got", "make", "made", "add", "added", "fix", "fixed", "bug", "issue", "test",
    "tests", "code", "file", "files", "error", "errors", "instead", "expected",
    "actual", "version", "example", "please", "thanks", "hello", "print", "true",
    "false", "none", "null", "return", "returns", "returned", "call", "calls",
    "should", "support", "update", "updated", "change", "changed", "new", "old",
}
SPLIT_RE = re.compile(r"[^A-Za-z0-9]+")
BACKTICK_RE = re.compile(r"`([^`\n]{3,120})`")
PATH_RE = re.compile(r"\b([A-Za-z0-9_./-]+\.(?:py|pyi))\b")


def subtokens(text: str) -> list[str]:
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
    found = []
    for run in re.findall(r"\b(?:[A-Z][a-z0-9]*\s+){1,4}[A-Z][a-z0-9]*\b", text):
        words = run.split()
        if len(words) >= 2:
            acr = "".join(w[0] for w in words).lower()
            if len(acr) >= 2:
                found.append(acr)
    return found


def collect(root: Path) -> dict[str, dict]:
    struct: dict[str, dict] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix not in TEXT_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = str(path.relative_to(root))
            lower = text.lower()
            struct[rel] = {
                "tokens": Counter(subtokens(text)),
                "path": set(subtokens(rel)),
                "defined": set(subtokens(" ".join(
                    re.findall(r"(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", text)))),
                "lines": lower.splitlines(),
                "raw_lines": text.splitlines(),
                "exact": text,
                "size": len(text),
            }
    return struct


def build_query(issue: str) -> dict[str, tuple[float, bool, bool]]:
    """term -> (weight, is_identifier_literal, is_compound_literal)."""
    weighted: dict[str, tuple[float, bool, bool]] = {}
    literals = PATH_RE.findall(issue) + [m.group(1).strip() for m in BACKTICK_RE.finditer(issue)]
    for literal in literals:
        ident = bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", literal))
        compound = ident and ("_" in literal or literal != literal.lower())
        for token in subtokens(literal) or [literal.lower()]:
            if token in STOPWORDS:
                continue
            previous = weighted.get(token, (0.0, False, False))
            weighted[token] = (max(previous[0], 3.0), previous[1] or ident, previous[2] or compound)
        if ident:
            weighted[literal.lower()] = (4.0, True, compound)
    for acr in acronyms(issue):
        previous = weighted.get(acr, (0.0, False, False))
        weighted[acr] = (max(previous[0], 2.0), previous[1], previous[2])
    for token in subtokens(issue):
        if token in STOPWORDS or len(token) < 3:
            continue
        weighted.setdefault(token, (1.0, False, False))
    return weighted


TESTISH = ("tests/", "test_", "_test.", "conftest")


def rank(struct: dict[str, dict], query: dict[str, tuple[float, bool, bool]]) -> list[tuple[float, str]]:
    if not struct:
        return []
    n_docs = len(struct)
    doc_len = {name: sum(d["tokens"].values()) or 1 for name, d in struct.items()}
    avg_len = sum(doc_len.values()) / n_docs
    df: Counter = Counter()
    for data in struct.values():
        for term in data["tokens"]:
            df[term] += 1
    k1, b = 1.2, 0.75
    scores: dict[str, float] = defaultdict(float)
    # compound literals (strict_content_type) only count when they really co-occur
    compound_terms = {t for t, (_, _, compound) in query.items() if compound}
    for name, data in struct.items():
        score = 0.0
        length = doc_len[name]
        for term, (weight, _, _) in query.items():
            freq = data["tokens"].get(term, 0)
            if freq:
                idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
                score += weight * idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * length / avg_len))
            if term in data["path"]:
                score += 1.5 * weight * math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            if term in data["defined"]:
                score += 4.0 * weight * math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
        if score:
            lowered = data["exact"].lower()
            for literal in (t for t, (_, is_ident, _) in query.items() if is_ident and "_" in t):
                if literal in lowered:
                    score += 6.0 * math.log(1 + (n_docs - df.get(literal.split("_")[0], 0) + 0.5)
                                             / (df.get(literal.split("_")[0], 0) + 0.5))
            if compound_terms and sum(1 for t in compound_terms if data["tokens"].get(t)) < 2:
                score *= 0.35
            if any(part in name for part in TESTISH):
                score *= 0.5
        if score:
            scores[name] = score
    return sorted(((score, name) for name, score in scores.items()), key=lambda p: (-p[0], len(p[1])))


def evidence(data: dict, query: dict[str, tuple[float, bool, bool]], limit: int = 3) -> list[str]:
    needles = [term for term, (_, _, _) in query.items() if len(term) >= 4][:20]
    out: list[str] = []
    for index, line in enumerate(data["lines"]):
        if len(line) > 200:
            continue
        if any(needle in line for needle in needles):
            snippet = data["raw_lines"][index].strip()[:120]
            out.append(f"    L{index + 1}: {snippet}")
            if len(out) >= limit:
                break
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--issue-file", type=Path, default=None)
    parser.add_argument("--issue", type=str, default=None)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--evidence", type=int, default=3)
    args = parser.parse_args()

    issue = args.issue or (args.issue_file.read_text(encoding="utf-8") if args.issue_file else "")
    if not issue.strip():
        print("locator: empty issue text", file=sys.stderr)
        return 2

    struct = collect(args.root)
    query = build_query(issue)
    ranked = rank(struct, query)[: args.top]
    print(f"# locator: {len(struct)} python files scanned, {len(query)} query terms")
    print("# note: candidate order is a hint, not a verdict; read the top files before editing")
    print(f"# top {len(ranked)} candidates for the fix:")
    for position, (score, name) in enumerate(ranked, start=1):
        print(f"{position:2d}. {name}  (score {score:.1f})")
        for line in evidence(struct[name], query, args.evidence):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
