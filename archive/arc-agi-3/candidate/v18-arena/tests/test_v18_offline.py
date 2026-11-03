"""Testy opakowujace zestaw akceptacyjny v18-arena.

Wymagaja zrodla Smaka (read-only) wskazanego zmienna ARC3_SMAK_ANALYSIS.
Bez niej testy sa pomijane - repo nie zawiera cudzego kodu i nie udaje, ze go ma.

  ARC3_SMAK_ANALYSIS=/sciezka/arc-agi-3/analysis pytest tests/test_v18_offline.py -q
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

V18 = pathlib.Path(__file__).resolve().parents[1]
ANALYSIS = os.environ.get("ARC3_SMAK_ANALYSIS")

pytestmark = pytest.mark.skipif(
    not ANALYSIS or not pathlib.Path(ANALYSIS).is_dir(),
    reason="brak ARC3_SMAK_ANALYSIS - zestaw v18 wymaga zrodla kontrolera (read-only)",
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("v18build")
    subprocess.run([sys.executable, str(V18 / "tools" / "build_v18.py"),
                    "--analysis", ANALYSIS, "--out", str(out)],
                   check=True, capture_output=True)
    return out


def test_build_is_deterministic_and_complete(built):
    for name in ("template_transfer.py", "template_hook.py", "v18-arena.diff"):
        assert (built / name).exists(), name


def test_acceptance_suite_passes(built):
    proc = subprocess.run([sys.executable, str(V18 / "tools" / "verify_v18.py"),
                           "--analysis", ANALYSIS, "--build", str(built),
                           "--trials", "60"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-2000:]
    assert "WERDYKT: OK" in proc.stdout
    assert "rozbieznosci = 0" in proc.stdout
