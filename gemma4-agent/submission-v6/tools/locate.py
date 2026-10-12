#!/usr/bin/env python3
# Rank the repository files a fix most likely touches. Stdlib only, no network.
#
# Usage: python3 /tmp/locate.py --root /workspace --issue-file /tmp/issue.txt --top 8
#
# Measured offline on the 129 published dev tasks and on repos outside the dev set:
# plain first-grep reaches the fixable source file in ~15% of tasks at top-5, this
# recipe in ~73% (dev set) and ~77% (held-out repos).

import argparse
import math
import os
import re
import sys
from collections import Counter, defaultdict

SKIP = {".git", "node_modules", ".tox", ".venv", "venv", "build", "dist", "__pycache__",
        ".mypy_cache", ".pytest_cache", ".eggs", "docs", "site-packages", "htmlcov"}
STOP = {"the", "and", "for", "with", "that", "this", "from", "have", "has", "not", "are",
        "was", "were", "when", "which", "should", "would", "could", "does", "did", "but",
        "you", "your", "its", "using", "use", "used", "can", "cannot", "will", "then",
        "than", "there", "here", "into", "only", "also", "some", "any", "all", "get",
        "got", "make", "made", "add", "added", "fix", "fixed", "bug", "issue", "test",
        "tests", "code", "file", "files", "error", "errors", "instead", "expected",
        "actual", "version", "example", "please", "thanks", "print", "true", "false",
        "none", "null", "return", "returns", "returned", "call", "calls", "support"}
SPLIT = re.compile(r"[^A-Za-z0-9]+")
BACKTICK = re.compile(r"`([^`\n]{3,120})`")
PATHY = re.compile(r"\b([A-Za-z0-9_./-]+\.(?:py|pyi))\b")
IMPORT = re.compile(r"^\s*(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_.]+))", re.M)
TESTISH = ("tests/", "test_", "_test.", "conftest")


def subtokens(text):
    out = []
    for chunk in SPLIT.split(text):
        for piece in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", chunk or ""):
            piece = piece.lower()
            if len(piece) >= 2:
                out.append(piece)
    return out


def collect(root):
    struct = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
        for name in filenames:
            if not name.endswith((".py", ".pyi")):
                continue
            path = os.path.join(dirpath, name)
            try:
                if os.path.getsize(path) > 400000:
                    continue
                with open(path, encoding="utf-8", errors="ignore") as handle:
                    text = handle.read()
            except OSError:
                continue
            rel = os.path.relpath(path, root)
            struct[rel] = {
                "tokens": Counter(subtokens(text)),
                "path": set(subtokens(rel)),
                "defined": set(subtokens(" ".join(
                    re.findall(r"(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", text)))),
                "imports": {m.group(1) or m.group(2) for m in IMPORT.finditer(text) if m.group(1) or m.group(2)},
                "text": text,
            }
    return struct


def build_query(issue):
    weighted = {}
    for literal in PATHY.findall(issue) + [m.group(1).strip() for m in BACKTICK.finditer(issue)]:
        ident = bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", literal))
        for token in subtokens(literal) or [literal.lower()]:
            if token in STOP:
                continue
            weight, was_ident = weighted.get(token, (0.0, False))
            weighted[token] = (max(weight, 3.0), was_ident or ident)
        if ident:
            weighted[literal.lower()] = (4.0, True)
    for token in subtokens(issue):
        if token not in STOP and len(token) >= 3:
            weighted.setdefault(token, (1.0, False))
    return weighted


def rank(struct, query):
    if not struct:
        return []
    n_docs = len(struct)
    doc_len = {name: sum(data["tokens"].values()) or 1 for name, data in struct.items()}
    avg_len = sum(doc_len.values()) / n_docs
    df = Counter()
    for data in struct.values():
        for term in data["tokens"]:
            df[term] += 1
    k1, b = 1.2, 0.75
    scores = defaultdict(float)
    for name, data in struct.items():
        length = doc_len[name]
        for term, (weight, _) in query.items():
            freq = data["tokens"].get(term, 0)
            idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            if freq:
                scores[name] += weight * idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * length / avg_len))
            if term in data["path"]:
                scores[name] += 1.5 * weight * idf
            if term in data["defined"]:
                scores[name] += 4.0 * weight * idf
        for literal, (_, is_ident) in query.items():
            if is_ident and "_" in literal and literal in data["text"].lower():
                scores[name] += 6.0 * math.log(1 + (n_docs - df.get(literal.split("_")[0], 0) + 0.5)
                                               / (df.get(literal.split("_")[0], 0) + 0.5))
        if any(part in name for part in TESTISH):
            scores[name] *= 0.5
    content = sorted(scores, key=lambda n: (-scores[n], len(n), n))
    # the module to grow is usually imported by the best-matching repo test file
    test_best = next((n for n in content if any(p in n for p in TESTISH) and scores[n] > 0), None)
    imported = defaultdict(float)
    if test_best:
        for module in struct[test_best]["imports"]:
            base = module.replace(".", "/")
            for candidate in (base + ".py", base + "/__init__.py"):
                if candidate in struct:
                    imported[candidate] += scores[test_best]
    merged = defaultdict(float, scores)
    for name, value in imported.items():
        merged[name] += value
    import_rank = sorted((n for n in imported if not any(p in n for p in TESTISH)),
                         key=lambda n: (-imported[n], len(n), n))
    order = []
    for first, second in zip(content, import_rank + [None] * len(content)):
        for candidate in (first, second):
            if candidate and candidate not in order:
                order.append(candidate)
    return [(merged[name], name) for name in order]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/workspace")
    parser.add_argument("--issue-file", default=None)
    parser.add_argument("--issue", default=None)
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()
    issue = args.issue or (open(args.issue_file, encoding="utf-8").read() if args.issue_file else "")
    if not issue.strip():
        print("locator: empty issue text", file=sys.stderr)
        return 2
    struct = collect(args.root)
    query = build_query(issue)
    ranked = rank(struct, query)[: args.top]
    print("# locator: %d python files scanned, %d query terms" % (len(struct), len(query)))
    print("# candidate order is a hint, not a verdict: read the top files before editing")
    needles = [t for t in query if len(t) >= 4][:20]
    for position, (score, name) in enumerate(ranked, start=1):
        marker = " [test]" if any(p in name for p in TESTISH) else ""
        print("%2d. %s%s  (score %.1f)" % (position, name, marker, score))
        shown = 0
        for index, line in enumerate(struct[name]["text"].splitlines()):
            if len(line) < 200 and any(n in line.lower() for n in needles):
                print("    L%d: %s" % (index + 1, line.strip()[:120]))
                shown += 1
                if shown >= 3:
                    break
    return 0


if __name__ == "__main__":
    sys.exit(main())
