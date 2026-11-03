#!/usr/bin/env python3
"""Bramka CI: czy do repo nie wklejono poświadczeń. Kod wyjścia 1 = przerywamy.

Osobny skrypt, bo w workflow byłby heredoc (patrz komentarz w `summary.py`).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nask.tools.credentials import assert_no_plaintext_credentials  # noqa: E402


def main() -> int:
    hits = assert_no_plaintext_credentials("nask")
    if hits:
        print("PODEJRZANE MIEJSCA (możliwe poświadczenia w plikach):")
        print("\n".join(hits))
        return 1
    print("czysto — brak poświadczeń w plikach")
    return 0


if __name__ == "__main__":
    sys.exit(main())
