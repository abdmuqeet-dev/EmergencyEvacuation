"""Phase 2 done-check: the domain solves the hand-written problems and VAL accepts every plan.

Run from the project root:  .venv\\Scripts\\python -m unittest tests.test_phase2 -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import planner  # noqa: E402
import validate  # noqa: E402

DOMAIN = ROOT / "pddl" / "domain.pddl"
PROBLEMS = ROOT / "pddl" / "problems"


def run(name):
    problem = PROBLEMS / name
    result = planner.solve(DOMAIN, problem)
    assert result is not None, "unsolvable: " + name
    actions, cost = result
    with tempfile.TemporaryDirectory() as tmp:
        plan = Path(tmp) / "plan.txt"
        planner.write_plan(actions, plan)
        ok, out = validate.validate(DOMAIN, problem, plan)
    return actions, cost, ok, out


def names(actions):
    return [a.strip("()").split()[0] for a in actions]


class Phase2(unittest.TestCase):
    def test_p1_fire_at_stair5_uses_stair2_no_elevator(self):
        actions, cost, ok, out = run("p1_fire_stair5_use_stair2.pddl")
        self.assertTrue(ok, out)
        text = " ".join(actions)  # Fast Downward lowercases all names
        self.assertIn("stair_2_l4", text)
        self.assertNotIn("stair_5", text)
        self.assertNotIn("use-elevator", names(actions))
        self.assertNotIn("elev_1_", text)
        self.assertEqual(names(actions)[-1], "exit-building")

    def test_p2_wheelchair_without_direction_shelters_and_notifies(self):
        actions, cost, ok, out = run("p2_wheelchair_shelter_and_notify.pddl")
        self.assertTrue(ok, out)
        self.assertEqual(names(actions)[-1], "shelter-and-notify")
        self.assertNotIn("descend-stairs", names(actions))
        self.assertNotIn("use-elevator", names(actions))
        self.assertNotIn("exit-building", names(actions))

    def test_p3_wheelchair_with_direction_uses_elevator(self):
        actions, cost, ok, out = run("p3_wheelchair_elevator_directed.pddl")
        self.assertTrue(ok, out)
        self.assertIn("use-elevator", names(actions))
        self.assertNotIn("descend-stairs", names(actions))
        self.assertEqual(names(actions)[-1], "exit-building")

    def test_p4_both_stairs_blocked_shelters_and_notifies(self):
        actions, cost, ok, out = run("p4_both_stairs_blocked.pddl")
        self.assertTrue(ok, out)
        self.assertEqual(names(actions)[-1], "shelter-and-notify")
        self.assertNotIn("descend-stairs", names(actions))
        self.assertNotIn("use-elevator", names(actions))


if __name__ == "__main__":
    unittest.main()
