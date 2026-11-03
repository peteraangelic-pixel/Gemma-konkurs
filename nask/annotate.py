#!/usr/bin/env python3
"""Wypisuje wyniki rekonesansu jako adnotacje GitHuba — czyli w miejsce, do którego dociera agent.

Artefakt Actions (`nask-recon-*.zip`) i logi kroku lecą z hostów, do których agent
nie ma dostępu (`blob.core.windows.net`, `results-receiver.actions...`). Adnotacje
(`check-runs/{id}/annotations`) są w `api.github.com` i tam docieram. Bez tego kanału
wynik rekonesansu zostaje w artefakcie, którego nikt nie otwiera.

Limit adnotacji na krok: 50, stąd twardy `--max-notices`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_NOTICES = 45


def _esc(text: str, limit: int = 850) -> str:
    return (text.replace("%", "%25").replace("\r", " ")
                .replace("\n", " / "))[:limit]


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else Path("nask/findings/recon.json")
    max_notices = MAX_NOTICES
    if "--max" in argv:
        max_notices = int(argv[argv.index("--max") + 1])

    if not path.exists():
        print("::warning ::Brak recon.json — rekonesans nie zapisał wyniku.")
        return 0

    r = json.loads(path.read_text(encoding="utf-8"))
    out: list[tuple[str, str]] = []

    out.append(("info", _esc(
        f"Rekonesans: cele={len(r.get('targets', []))} bundle={len(r.get('bundles', []))} "
        f"kandydaci={r.get('candidates', 0)} budżet={r.get('budget', '?')} "
        f"dry_run={r.get('dry_run')}")))

    for t in r.get("targets", []):
        if t.get("error"):
            out.append(("warning", _esc(f"{t['url']}: {t['error']}")))
            continue
        tech = ",".join(t.get("tech") or []) or "-"
        out.append(("notice", _esc(
            f"{t['url']} -> {t.get('status')} {t.get('bytes', 0)}B "
            f"server={t.get('server') or '-'} tech={tech} bundles={len(t.get('bundles') or [])}")))

    hot_kinds = {"hot_field", "endpoint", "internal_ip", "secret", "sourcemap", "url"}
    for b in r.get("bundles", []):
        picks = [c for c in b.get("top", []) if c["kind"] in hot_kinds][:6]
        if not picks:
            continue
        body = "; ".join(f"{c['kind']}={c['value']}" for c in picks)
        out.append(("notice", _esc(f"JS {b['url']} ({b.get('bytes', 0)}B): {body}")))

    for note in r.get("notes", []):
        out.append(("warning", _esc(note)))

    for level, msg in out[:max_notices]:
        print(f"::{level}::{msg}")
    if len(out) > max_notices:
        print(f"::notice::obcięto {len(out) - max_notices} adnotacji (limit GitHuba)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
