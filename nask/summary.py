#!/usr/bin/env python3
"""Podsumowanie rekonesansu do GitHub Step Summary (Markdown).

Osobny plik, a nie heredoc w YAML — bo wcięcia heredoca w `run: |` już raz
mnie kosztowały debugowanie workflow, a ten kod ma czytać człowiek.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PATH = Path("nask/findings/recon.json")


def main() -> int:
    if not PATH.exists():
        print("Brak `recon.json` — rekonesans nie doszedł do zapisu.")
        return 0
    r = json.loads(PATH.read_text(encoding="utf-8"))
    lines = [
        f"Cele w scope: **{len(r['targets'])}**, bundli: **{len(r['bundles'])}**, "
        f"kandydatów: **{r['candidates']}**",
        "",
        "| cel | status | bajty | tech | bundle |",
        "|---|---:|---:|---|---:|",
    ]
    for t in r["targets"]:
        if t.get("error"):
            lines.append(f"| `{t['url']}` | błąd | — | {t['error'][:60]} | 0 |")
            continue
        tech = ", ".join(t.get("tech") or []) or "—"
        lines.append(f"| `{t['url']}` | {t.get('status')} | {t.get('bytes', 0)} | "
                     f"{tech} | {len(t.get('bundles') or [])} |")
    if r.get("skipped"):
        lines += ["", "**Pominięte (poza scope lub wyłączone):**"]
        lines += [f"- `{s['url']}` — {s['reason']}" for s in r["skipped"]]
    hot = []
    for b in r["bundles"]:
        for c in b["top"]:
            if c["kind"] in ("hot_field", "endpoint", "internal_ip", "secret", "sourcemap"):
                hot.append(f"- `{c['value']}` ({c['kind']}) — {c['hint']}")
    if hot:
        lines += ["", "**Kandydaci z bundli JS** (do ręcznego sprawdzenia, to nie są podatności):"]
        lines += hot[:40]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
