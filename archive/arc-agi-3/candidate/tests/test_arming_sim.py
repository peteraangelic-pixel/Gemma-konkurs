"""Testy symulatora uzbrojenia 0010 (tools/arming_sim.py).

Sprawdzają własności, które muszą zachodzić niezależnie od danych: cap=0 nie robi nic,
wyższy cap nie może ciąć częściej niż niższy, a moduł symulacji to prawdziwy moduł z patcha.
"""
import importlib.util
import unittest
from pathlib import Path

_ROOTS = Path(__file__).resolve().parents[1]
_SIM = _ROOTS / "v17-arena-dyn" / "tools" / "arming_sim.py"
MODULE = _ROOTS / "v17-arena-dyn" / "src" / "arc3_level_budget_v13_2.py"

_spec = importlib.util.spec_from_file_location("arming_sim_under_test", _SIM)
sim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sim)


class ArmingSimTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = sim.load_module(MODULE, "lb_sim_test")

    def test_cap_zero_is_inert(self):
        out = sim.simulate_run(self.mod, [5000] * 20, [10, 20], cap=0)
        self.assertEqual(out["resets"], 0)
        self.assertEqual(out["abandons"], 0)
        self.assertEqual(out["completed"], 2)

    def test_cap_cuts_only_with_budget_exhausted(self):
        out = sim.simulate_run(self.mod, [5000] * 20, [10, 20], cap=1000)
        self.assertGreater(out["abandons"], 0)
        self.assertLess(out["actions"], 20)

    def test_higher_cap_never_cuts_more(self):
        runs = [[9000] * 40, [2000] * 40, [30000] * 10]
        for tokens in runs:
            low = sim.simulate_run(self.mod, tokens, [20, 40], cap=20000)
            high = sim.simulate_run(self.mod, tokens, [20, 40], cap=60000)
            self.assertGreaterEqual(low["abandons"], high["abandons"])
            self.assertGreaterEqual(high["completed"], low["completed"])

    def test_resets_are_used_before_abandon(self):
        out = sim.simulate_run(self.mod, [4000] * 30, [30], cap=10000)
        self.assertTrue(out["abandons"] == 0 or out["resets"] >= 1)


if __name__ == "__main__":
    unittest.main()
