#!/usr/bin/env python3
"""Zamienia log nieudanego kroku na adnotacje GitHuba (`::error ::...`).

Po co: logi i artefakty Actions lecą z `results-receiver.actions.githubusercontent.com`
i `blob.core.windows.net`, do których agent nie ma dostępu. Adnotacje (`check-runs
/annotations`) są w API GitHuba i tam docieram. Bez tego debugowanie sprowadza się
do „coś nie wyszło" — czyli do zgadywania.

Użycie: python nask/fail_annotation.py <plik_z_logiem> [--max-lines N]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Adnotacja ma limit długości; i tak chcemy tylko ogon logu (tam jest traceback).
MAX_CHARS = 900
MAX_LINES = 25


def main(argv: list[str]) -> int:
    if not argv:
        print("użycie: fail_annotation.py <log> [--max-lines N]", file=sys.stderr)
        return 2
    path = Path(argv[0])
    max_lines = MAX_LINES
    if "--max-lines" in argv:
        max_lines = int(argv[argv.index("--max-lines") + 1])

    if not path.exists():
        print("::error ::Brak pliku logu — krok padł przed zapisem logu.")
        return 0

    lines = [ln.rstrip() for ln in path.read_text(errors="replace").splitlines() if ln.strip()]
    if not lines:
        print("::error ::Log jest pusty — krok padł bez żadnego wyjścia.")
        return 0

    tail = lines[-max_lines:]
    # Escape wymagany przez protokół adnotacji: % → %25, CR → %0D, LF → %0A
    for i, line in enumerate(tail):
        msg = line.replace("%", "%25").replace("\r", "").replace("\n", " ")
        msg = msg[:MAX_CHARS]
        title = "ostatnie linie logu" if i < len(tail) - 1 else "ostatnia linia logu"
        print(f"::error title={title}::{msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
