r"""Phase 6 done-check: stepped simulation and re-planning after a block or unblock.

Run from the project root:  .venv\Scripts\python -m unittest tests.test_phase6 -v   (about 2 minutes)
"""
import collections
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
import simulation  # noqa: E402
import suite  # noqa: E402

B = graph.Building()
SCN = ROOT / "tests" / "scenarios"


def load(name):
    return json.loads((SCN / (name + ".json")).read_text())


def sim_for(scn, **kw):
    tmp = tempfile.TemporaryDirectory()
    s = simulation.Simulation(scn, building=B, workdir=Path(tmp.name), **kw)
    s._tmp = tmp  # keep the folder alive as long as the simulation
    return s


def finish(sim):
    while not sim.done and sim.step_no < 200:
        sim.step()
    return sim


def one_group(loc, gid="g1", **extra):
    return dict({"name": "t", "emergency": "fire",
                 "groups": [{"id": gid, "location": loc, "mobility_impaired": False, "size": 10}]}, **extra)


class Stepping(unittest.TestCase):
    def test_a_step_is_one_action_per_group_without_crowding(self):
        sim = sim_for(load("s0_fire_ground_floor_baseline"))
        before = sim.groups["g1"]["location"]
        rec = sim.step()
        self.assertEqual(len(rec["actions"]["g1"]), 1)
        self.assertNotEqual(sim.groups["g1"]["location"], before)
        self.assertEqual(sim.snapshot()["step"], 1)
        finish(sim)
        self.assertTrue(sim.done)
        self.assertEqual(sim.groups["g1"]["status"], "out")
        self.assertIsNone(sim.step())   # nothing left to do

    def test_the_unit_can_be_a_leg(self):
        sim = sim_for(load("s0_fire_ground_floor_baseline"), unit="leg")
        rec = sim.step()
        self.assertGreater(len(rec["actions"]["g1"]), 1)   # all the walking plus the exit in one step
        self.assertTrue(sim.done)

    def test_bad_unit_is_rejected(self):
        with self.assertRaises(ValueError):
            sim_for(load("s0_fire_ground_floor_baseline"), unit="minute")

    def test_earthquake_starts_with_everybody_waiting(self):
        sim = sim_for(load("s7_earthquake_floor3_glass"))
        where = sim.groups["g1"]["location"]
        rec = sim.step()
        self.assertTrue(rec["shaking"])
        self.assertEqual(rec["actions"], {})
        self.assertEqual(sim.groups["g1"]["location"], where)
        finish(sim)
        self.assertEqual(sim.groups["g1"]["status"], "out")
        self.assertEqual(simulation.violations(sim), [])

    def test_a_block_before_the_shaking_stops_still_waits_first(self):
        sim = sim_for(load("s7_earthquake_floor3_glass"))
        sim.block(["L3_c_w_mid"])
        self.assertTrue(sim.step()["shaking"])
        finish(sim)
        self.assertEqual(sim.groups["g1"]["status"], "out")


class Replanning(unittest.TestCase):
    def test_block_ahead_reroutes_and_never_enters_the_blocked_place(self):
        sim = sim_for(load("s6_midrun_block_lower"))
        sim.step()
        sim.step()
        ev = sim.block(["L0_c_c_n"])
        self.assertEqual(ev["replanned"], ["g1"])
        self.assertTrue(ev["valid"])
        finish(sim)
        self.assertEqual(sim.groups["g1"]["status"], "out")
        self.assertEqual(simulation.violations(sim), [])
        visited = {simulation.destination(a) for a in sim.executed_actions()}
        self.assertNotIn("l0_c_c_n", visited)
        self.assertIn("exit_l0_s6", visited)

    def test_a_group_whose_route_is_untouched_is_not_replanned(self):
        scn = one_group("L0_r62")
        scn["groups"].append({"id": "g2", "location": "L1_r109", "mobility_impaired": False, "size": 10})
        sim = sim_for(scn)
        queue_before = list(sim.groups["g2"]["queue"])
        ev = sim.block(["L0_c_c_n"])          # on g1's route, nowhere near g2
        self.assertEqual(ev["replanned"], ["g1"])
        self.assertEqual(sim.groups["g2"]["queue"], queue_before)

    def test_a_block_nobody_needs_causes_no_replan(self):
        sim = sim_for(one_group("L1_r109"))
        n = sim.replans
        ev = sim.block(["L6_c_w_mid"])
        self.assertEqual(ev["replanned"], [])
        self.assertEqual(sim.replans, n)

    def test_a_group_standing_in_a_blocked_place_can_leave_it(self):
        sim = sim_for(load("s6_midrun_block_lower"))
        sim.step()
        here = sim.groups["g1"]["location"]
        sim.block([here])
        finish(sim)
        self.assertEqual(sim.groups["g1"]["status"], "out")
        self.assertEqual(simulation.violations(sim), [])

    def test_blocking_both_stairs_makes_the_group_shelter(self):
        sim = sim_for(one_group("L5_r510"))
        sim.step()
        sim.block(["stair_2_L5", "stair_5_L5"])
        finish(sim)
        g = sim.groups["g1"]
        self.assertEqual((g["status"], g["kind"]), ("sheltered", "shelter-and-notify"))

    def test_unblocking_lets_a_sheltering_group_walk_out(self):
        sim = sim_for(load("s6b_unblock_after_shelter")).run_script()
        self.assertEqual(sim.groups["g1"]["status"], "out")
        verbs = [simulation.verb(a) for a in sim.executed_actions()]
        self.assertIn("shelter-and-notify", verbs)
        self.assertLess(verbs.index("shelter-and-notify"), verbs.index("exit-building"))
        self.assertEqual(simulation.violations(sim), [])
        self.assertTrue(sim.all_valid)

    def test_a_group_with_no_way_out_is_stuck_until_something_reopens(self):
        sim = sim_for(one_group("L1_r109"))
        ev = sim.block(list(B.of_type("exit")))
        self.assertEqual(ev["stuck"], ["g1"])
        self.assertTrue(sim.done)
        self.assertEqual(sim.groups["g1"]["status"], "stuck")
        ev = sim.unblock(["exit_L1_W"])
        self.assertEqual(ev["stuck"], [])
        finish(sim)
        self.assertEqual(sim.groups["g1"]["status"], "out")

    def test_one_stuck_group_does_not_stop_the_others(self):
        scn = one_group("L5_r510")
        scn["groups"].append({"id": "g2", "location": "L0_r62", "mobility_impaired": False, "size": 10})
        sim = sim_for(scn)
        ev = sim.block(list(B.of_type("exit")))     # every exit shut: nobody can leave
        # g2 on the Lower floor has no refuge, so it is stuck; g1 can shelter on level 5
        self.assertEqual(ev["stuck"], ["g2"])
        finish(sim)
        self.assertEqual(sim.groups["g1"]["status"], "sheltered")
        self.assertEqual(sim.groups["g2"]["status"], "stuck")

    def test_hazmat_shelter_stays_put_when_something_irrelevant_reopens(self):
        sim = sim_for(load("s8_hazmat_outdoor_release"))
        sim.step()
        self.assertEqual(sim.groups["g1"]["status"], "sheltered")
        sim.block(["L6_c_w_mid"])
        ev = sim.unblock(["L6_c_w_mid"])
        self.assertEqual(sim.groups["g1"]["status"], "sheltered")
        self.assertTrue(sim.done)
        self.assertEqual(sim.groups["g1"]["queue"], [])
        self.assertEqual(ev["valid"], True)

    def test_the_emergency_itself_cannot_be_unblocked_by_the_user(self):
        sim = sim_for(load("s1_fire_floor4_near_stair5"))
        with self.assertRaises(ValueError):
            sim.unblock(["stair_5_L4"])

    def test_unknown_nodes_are_rejected(self):
        sim = sim_for(one_group("L1_r109"))
        with self.assertRaises(ValueError):
            sim.block(["nowhere"])

    def test_a_rejected_replan_is_a_hard_failure(self):
        sim = sim_for(load("s6_midrun_block_lower"))
        sim.step()
        with mock.patch.object(simulation.validate, "validate", return_value=(False, "Plan failed")):
            with self.assertRaises(run.PlanInvalid):
                sim.block(["L0_c_c_n"])
        self.assertFalse(sim.all_valid)


class Crowded(unittest.TestCase):
    def test_wave_loads_stay_within_the_limit_across_a_replan(self):
        sim = sim_for(load("s6c_crowded_midrun_block")).run_script()
        cap = sim.scn["crowding"]["stair_capacity"]
        loads = collections.Counter()
        for step, _g, a, _b in sim.executed:
            if a.startswith("(descend-stairs"):
                t = a.strip("()").split()
                loads[(step, t[2], t[3])] += 1
        self.assertLessEqual(max(loads.values()), cap)
        self.assertEqual({g["status"] for g in sim.groups.values()}, {"out"})
        self.assertEqual(simulation.violations(sim), [])
        self.assertTrue(sim.all_valid)
        self.assertEqual(sim.unit, "leg")
        # the groups still above the blocked stair went round by stair 5
        self.assertIn("stair_5_l3", {simulation.destination(a) for a in sim.executed_actions()})


class Checker(unittest.TestCase):
    def test_violation_checker_flags_entering_a_blocked_place(self):
        sim = sim_for(one_group("L1_r109"))
        sim.executed.append((3, "g1", "(move g1 a l1_c_w_mid)", frozenset({"L1_c_w_mid"})))
        self.assertEqual(simulation.violations(sim), [(3, "g1", "(move g1 a l1_c_w_mid)")])

    def test_leaving_a_blocked_place_is_not_a_violation(self):
        sim = sim_for(one_group("L1_r109"))
        sim.executed.append((3, "g1", "(move g1 l1_c_w_mid b)", frozenset({"L1_c_w_mid"})))
        self.assertEqual(simulation.violations(sim), [])


class SuiteIntegration(unittest.TestCase):
    def test_scripted_scenarios_pass_in_the_suite(self):
        for name in ("s6_midrun_block_lower", "s6b_unblock_after_shelter"):
            with tempfile.TemporaryDirectory() as tmp:
                r = suite.run_one(SCN / (name + ".json"), B, Path(tmp))
            self.assertEqual(r["failures"], [], name)
            self.assertGreaterEqual(r["sim"]["replans"], 1)

    def test_suite_catches_a_missing_replan_a_violation_and_a_stuck_group(self):
        scn = {"groups": [{"id": "g1"}], "expect": {"outcome": "exit", "min_replans": 2}}
        res = {"plan": ["(exit-building g1 e)"], "cost": None, "valid": True, "crowding": None,
               "sim": {"violations": [(1, "g1", "x")], "replans": 1, "steps": 1, "stuck": ["g1"]}}
        bad = suite.check_expectations(scn, res, B)
        self.assertEqual(len(bad), 3, bad)


if __name__ == "__main__":
    unittest.main()
