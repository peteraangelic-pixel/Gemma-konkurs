#!/usr/bin/env python3
"""Wypisuje wyniki rekonesansu jako adnotacje GitHuba — czyli w miejsce, do którego dociera agent.

Artefakt Actions (`nask-recon-*.zip`) i logi kroku lecą z hostów, do których agent
nie ma dostępu (`blob.core.windows.net`, `results-receiver.actions...`). Adnotacje
(`check-runs/{id}/annotations`) są w `api.github.com` i tam docieram. Bez tego kanału
wynik rekonesansu zostaje w artefakcie, którego nikt nie otwiera.

GitHub pokazuje tylko ~10 adnotacji danego typu na krok, więc pakujemy po kilka
wpisów w jedną adnotację (rozdzielone ` | `). To nie jest kosmetyka: przy 14 celach
i 12 bundlach pojedyncze wpisy ucinały się w połowie i pierwszy przebieg pokazał
mi tylko 10 z 14 celów.

Pełne dane i tak trafiają do repo jako `nask/findings/recon.json` (krok w workflow),
więc adnotacje są tylko podglądem.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_NOTICES = 8          # ~10 to limit GitHuba, zostawiamy zapas na ostrzeżenia
PACK_CHARS = 3000        # jeden wpis adnotacji może być długi — pakujemy
PACK_ENTRIES = 12


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

    # Pakowanie: łączymy wpisy tego samego poziomu, dopóki mieszczą się w limicie.
    packed: list[tuple[str, str]] = []
    for level, msg in out:
        if packed and packed[-1][0] == level and len(packed[-1][1]) + len(msg) < PACK_CHARS \
                and packed[-1][1].count(" | ") < PACK_ENTRIES:
            packed[-1] = (level, packed[-1][1] + " | " + msg)
        else:
            packed.append((level, msg))

    shown = packed[:max_notices]
    for level, msg in shown:
        print(f"::{level}::{msg}")
    if len(packed) > len(shown):
        print(f"::notice::obcięto {len(packed) - len(shown)} adnotacji (limit GitHuba)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
