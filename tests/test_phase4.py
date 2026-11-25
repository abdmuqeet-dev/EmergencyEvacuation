"""Phase 4 done-check: with crowding on, no plan sends more groups across a stair segment in one
wave than the limit, and VAL accepts the plan.

Run from the project root:  .venv\\Scripts\\python -m unittest tests.test_phase4 -v   (about 2 minutes)
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import crowding  # noqa: E402
import generate_problem  # noqa: E402
import graph  # noqa: E402
import planner  # noqa: E402
import rules  # noqa: E402
import run  # noqa: E402

B = graph.Building()
S5 = json.loads((ROOT / "tests" / "scenarios" / "s5_crowding_floors3to6.json").read_text())


def go(scn):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scn.json"
        path.write_text(json.dumps(scn))
        res = run.run_scenario(path, out_dir=Path(tmp) / "out", building=B)
    assert res["plan"] is not None, "no plan"
    return res


def verbs(res):
    return [a.strip("()").split()[0] for a in res["plan"]]


def uncrowded_plan(scn):
    """What each group would do with no stair limit: plan every group alone, join the plans."""
    plan = []
    for g in scn["groups"]:
        one = {k: v for k, v in scn.items() if k != "crowding"}
        one["groups"] = [g]
        problem = generate_problem.build_problem(B, one, rules.apply(one, B))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "p.pddl"
            p.write_text(problem)
            actions, _ = planner.solve(run.DOMAIN, p)
        plan += actions
    return plan


class CrowdingChecker(unittest.TestCase):
    """The checker replays a plan on its own; it must not depend on slot names."""

    def test_counts_groups_per_segment_and_wave(self):
        plan = ["(descend-stairs g1 a b)", "(descend-stairs g2 a b)", "(descend-stairs g3 a b)",
                "(descend-stairs g1 b c)"]
        loads = crowding.stair_loads(plan)
        self.assertEqual(loads[("a", "b", 0)], 3)
        self.assertEqual(loads[("b", "c", 1)], 1)  # g1 is one wave later on the next flight
        self.assertEqual(crowding.check(plan, 2)[0], 3)
        self.assertEqual(crowding.check(plan, 2)[1], [("a", "b", 0, 3)])
        self.assertEqual(crowding.check(plan, 3)[1], [])

    def test_waiting_moves_a_group_to_a_later_wave(self):
        plan = ["(descend-stairs-crowded g1 a b w0 w1 s1)", "(wait-a-wave g2 w0 w1)",
                "(descend-stairs-crowded g2 a b w1 w2 s2)"]
        loads = crowding.stair_loads(plan)
        self.assertEqual(loads[("a", "b", 0)], 1)
        self.assertEqual(loads[("a", "b", 1)], 1)
        self.assertEqual(crowding.waits(plan), 1)


class Generator(unittest.TestCase):
    def test_crowding_facts_only_when_requested(self):
        scn = {k: v for k, v in S5.items() if k != "crowding"}
        self.assertNotIn("(crowding)", generate_problem.build_problem(B, scn))
        text = generate_problem.build_problem(B, S5)
        self.assertIn("(crowding)", text)
        cap, n_waves = generate_problem.crowding_config(B, S5, S5["groups"])
        segments = len(list(B.stairs_down()))
        self.assertEqual(text.count("(slot-of "), segments * (n_waves - 1) * cap)
        self.assertEqual(text.count("(slot-free "), segments * (n_waves - 1) * cap)
        self.assertEqual(text.count("(group-time "), len(S5["groups"]))

    def test_used_slots_leave_the_free_pool(self):
        text = generate_problem.build_problem(B, S5, used_slots={"slot0", "slot1"})
        self.assertNotIn("(slot-free slot0)", text)
        self.assertIn("(slot-of slot0 ", text)  # the slot still exists, it is just taken
        self.assertIn("(slot-free slot2)", text)

    def test_capacity_must_be_positive(self):
        with self.assertRaises(ValueError):
            generate_problem.build_problem(B, dict(S5, crowding={"stair_capacity": 0}))


class Plans(unittest.TestCase):
    def test_s5_twelve_groups_never_exceed_the_limit(self):
        res = go(S5)
        self.assertTrue(res["valid"], res["val_output"])
        cap = S5["crowding"]["stair_capacity"]
        worst, bad = crowding.check(res["plan"], cap)
        self.assertEqual(bad, [])
        self.assertLessEqual(worst, cap)
        self.assertEqual(res["crowding"]["max_load"], worst)
        self.assertGreater(crowding.waits(res["plan"]), 0)             # the limit forced waiting
        self.assertNotIn("shelter-and-notify", verbs(res))             # everyone still got out
        self.assertEqual(verbs(res).count("exit-building"), len(S5["groups"]))
        slots = [a.split()[-1].strip(")") for a in res["plan"] if a.startswith("(descend-stairs-crowded")]
        self.assertEqual(len(slots), len(set(slots)))                  # no slot used twice

    def test_the_limit_really_matters(self):
        """Same six groups: with no limit the plan overloads a stair, with the limit it does not."""
        scn = dict(S5, groups=S5["groups"][:6])  # three groups on floor 3, three on floor 4
        cap = scn["crowding"]["stair_capacity"]
        free_worst, free_bad = crowding.check(uncrowded_plan(scn), cap)
        self.assertGreater(free_worst, cap)
        self.assertTrue(free_bad)
        res = go(scn)
        self.assertTrue(res["valid"], res["val_output"])
        self.assertEqual(crowding.check(res["plan"], cap)[1], [])

    def test_capacity_one_serialises_a_floor(self):
        scn = dict(S5, groups=S5["groups"][:3], crowding={"stair_capacity": 1})
        res = go(scn)
        self.assertTrue(res["valid"], res["val_output"])
        self.assertEqual(crowding.check(res["plan"], 1)[0], 1)
        self.assertGreaterEqual(crowding.waits(res["plan"]), 1)

    def test_a_generous_limit_changes_nothing(self):
        scn = dict(S5, groups=S5["groups"][:2], crowding={"stair_capacity": 5})
        res = go(scn)
        self.assertTrue(res["valid"], res["val_output"])
        self.assertEqual(crowding.waits(res["plan"]), 0)

    def test_earthquake_with_crowding_waits_for_shaking_once(self):
        scn = {"name": "quake_crowd", "emergency": "earthquake", "crowding": {"stair_capacity": 2},
               "groups": S5["groups"][:2]}
        res = go(scn)
        self.assertTrue(res["valid"], res["val_output"])
        self.assertEqual(res["plan"][0], "(wait-for-shaking-to-stop)")
        self.assertEqual(verbs(res).count("wait-for-shaking-to-stop"), 1)


if __name__ == "__main__":
    unittest.main()
