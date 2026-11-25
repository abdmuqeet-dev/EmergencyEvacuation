r"""Phase 5 done-check: the suite catches wrong plans, and an invalid plan is a hard failure.

Run from the project root:  .venv\Scripts\python -m unittest tests.test_phase5 -v   (about 20 s)
Full scenario suite:        .venv\Scripts\python src\suite.py                       (about 1 min)
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import graph  # noqa: E402
import run  # noqa: E402
import suite  # noqa: E402

B = graph.Building()
SCN = ROOT / "tests" / "scenarios"


def fake(plan, cost=10, valid=True, crowding=None):
    return {"plan": plan, "cost": cost, "valid": valid, "crowding": crowding}


ONE = {"groups": [{"id": "g1"}]}
EXIT_PLAN = ["(move g1 a b)", "(exit-building g1 b out)"]


class Expectations(unittest.TestCase):
    def chk(self, expect, res, scn=ONE):
        return suite.check_expectations(dict(scn, expect=expect), res, B)

    def test_good_plan_passes(self):
        self.assertEqual(self.chk({"outcome": "exit", "uses": ["b"], "avoids": ["use-elevator"], "max_cost": 10},
                                  fake(EXIT_PLAN)), [])

    def test_missing_expect_block_fails(self):
        self.assertTrue(suite.check_expectations(ONE, fake(EXIT_PLAN), B))

    def test_no_plan_fails_unless_expected(self):
        self.assertTrue(self.chk({"outcome": "exit"}, fake(None)))
        self.assertEqual(self.chk({"outcome": "no-plan"}, fake(None)), [])

    def test_invalid_plan_fails(self):
        self.assertTrue(self.chk({"outcome": "exit"}, fake(EXIT_PLAN, valid=False)))

    def test_wrong_outcome_fails(self):
        self.assertTrue(self.chk({"outcome": "shelter-and-notify"}, fake(EXIT_PLAN)))
        self.assertTrue(self.chk({"outcome": "exit"}, fake(["(shelter-and-notify g1 a)"])))

    def test_every_group_must_finish(self):
        two = {"groups": [{"id": "g1"}, {"id": "g2"}]}
        self.assertTrue(self.chk({"outcome": "exit"}, fake(EXIT_PLAN), two))

    def test_forbidden_and_required_names(self):
        self.assertTrue(self.chk({"outcome": "exit", "avoids": ["B"]}, fake(EXIT_PLAN)))   # case-insensitive
        self.assertTrue(self.chk({"outcome": "exit", "uses": ["stair_2_L4"]}, fake(EXIT_PLAN)))

    def test_cost_first_action_and_waits(self):
        self.assertTrue(self.chk({"outcome": "exit", "max_cost": 5}, fake(EXIT_PLAN)))
        self.assertTrue(self.chk({"outcome": "exit", "first_action": "wait-for-shaking-to-stop"}, fake(EXIT_PLAN)))
        self.assertTrue(self.chk({"outcome": "exit", "min_waits": 1}, fake(EXIT_PLAN)))

    def test_crowding_violation_fails(self):
        c = {"capacity": 2, "max_load": 3, "violations": [("a", "b", 0, 3)], "waits": 0}
        self.assertTrue(self.chk({"outcome": "exit"}, fake(EXIT_PLAN, crowding=c)))

    def test_every_scenario_file_has_an_expect_block(self):
        for p in SCN.glob("*.json"):
            exp = json.loads(p.read_text()).get("expect")
            self.assertTrue(exp and exp.get("outcome"), p.name)


class HardFailure(unittest.TestCase):
    def test_invalid_plan_raises_when_strict(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(run.validate, "validate", return_value=(False, "Plan failed to execute")):
            with self.assertRaises(run.PlanInvalid):
                run.run_scenario(SCN / "s0_fire_ground_floor_baseline.json", out_dir=tmp, building=B, strict=True)
            # not strict: the caller gets the verdict instead
            res = run.run_scenario(SCN / "s0_fire_ground_floor_baseline.json", out_dir=tmp, building=B)
            self.assertFalse(res["valid"])

    def test_suite_marks_a_rejected_plan_as_failed(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(run.validate, "validate", return_value=(False, "Plan failed to execute")):
            r = suite.run_one(SCN / "s0_fire_ground_floor_baseline.json", B, Path(tmp))
        self.assertTrue(r["failures"])

    def test_missing_validator_is_an_error_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(run.validate, "VAL", Path(tmp) / "nope.exe"):
            r = suite.run_one(SCN / "s0_fire_ground_floor_baseline.json", B, Path(tmp))
        self.assertTrue(r["failures"])

    def test_wrong_expectation_on_a_real_run_is_reported(self):
        scn = json.loads((SCN / "s0_fire_ground_floor_baseline.json").read_text())
        scn["expect"] = {"outcome": "shelter-in-place"}   # s0 actually walks out
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.json"
            p.write_text(json.dumps(scn))
            r = suite.run_one(p, B, Path(tmp) / "out")
        self.assertTrue(r["failures"])
        self.assertIs(r["valid"], True)   # the plan was fine, the expectation was wrong


class Report(unittest.TestCase):
    def test_report_lists_pass_and_fail(self):
        results = [{"name": "a", "description": "d", "failures": [], "plan": ["x"], "cost": 3, "valid": True,
                    "crowding": None, "groups": 1, "seconds": 1.0},
                   {"name": "b", "description": "d", "failures": ["boom"], "plan": None, "cost": None, "valid": None,
                    "crowding": None, "groups": 1, "seconds": 1.0}]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "r.md"
            suite.write_report(results, p)
            text = p.read_text()
        self.assertIn("1 of 2 scenarios pass", text)
        self.assertIn("FAILED: boom", text)


if __name__ == "__main__":
    unittest.main()
