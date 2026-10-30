"""Testy audytu eskalacji: reguły muszą być spójne wewnętrznie i odtwarzalne z fixtures.

Nie testujemy „która reguła jest lepsza" (to zależy od danych), tylko to, że narzędzie
liczy to, co deklaruje: liczba wtrąceń nie przekracza capa × poziomów, reguła względna
nigdy nie wypada przedwcześnie (z definicji progu), a self-pace przy braku historii
spada dokładnie do podłogi.
"""
import json
import unittest
from pathlib import Path

from arc3_local_candidate.tools import escalation_audit as ea

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "benchmarks"


class EscalationAuditTest(unittest.TestCase):
    def test_floor_when_no_history(self):
        rows = ea.policies([100, 100], [5, 40], done=2, floor=20, cap=2)
        self.assertEqual(rows["selfpace"][0][2], 20)  # brak historii -> podłoga

    def test_cap_limits_nudges_per_level(self):
        rows = ea.policies([500], [400], done=1, floor=20, cap=2)
        self.assertEqual(rows["abs20"][0][1], 20)     # absolutna bez capa
        self.assertEqual(rows["abs20cap2"][0][1], 2)  # z capem
        self.assertEqual(rows["selfpace"][0][1], 2)

    def test_relative_never_premature_by_definition(self):
        rows = ea.policies([30, 60], [90, 120], done=2, floor=20, cap=2)
        self.assertTrue(all(not r[3] for r in rows["relative"]))
        self.assertTrue(any(r[3] for r in rows["abs20"]))  # absolutna owszem

    def test_zero_action_levels_are_skipped(self):
        rows = ea.policies([10, 0], [0, 0], done=2)
        self.assertEqual(rows["abs20"], [])

    def test_median_int(self):
        self.assertEqual(ea.median_int([0, 5, 9]), 7)
        self.assertEqual(ea.median_int([4]), 4)
        self.assertEqual(ea.median_int([]), 0)

    @unittest.skipUnless((FIXTURES / "r085.json").exists(), "brak fixtures/benchmarks")
    def test_r085_reproduces_recorded_counts(self):
        totals = ea.audit(str(FIXTURES / "r085.json"))
        self.assertEqual(totals["abs20"][2], 32)          # 32 poziomy w populacji
        self.assertEqual((totals["relative"][0], totals["relative"][1]), (8, 0))
        self.assertEqual((totals["selfpace"][0], totals["selfpace"][1]), (22, 14))
        self.assertEqual((totals["abs20cap2"][0], totals["abs20cap2"][1]), (42, 26))

    @unittest.skipUnless((FIXTURES / "r085.json").exists(), "brak fixtures/benchmarks")
    def test_fixtures_are_real_benchmarks(self):
        for name in ("r085", "r093", "r110", "r118"):
            data = json.loads((FIXTURES / f"{name}.json").read_text())
            self.assertIn("game_runs", data)
            self.assertTrue(data["game_runs"])


if __name__ == "__main__":
    unittest.main()
