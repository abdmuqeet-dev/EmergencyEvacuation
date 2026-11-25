"""Phase 3 done-check: scenario -> problem -> plan -> VAL, on the real building graph.

Run from the project root:  .venv\\Scripts\\python -m unittest tests.test_phase3 -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import generate_problem  # noqa: E402
import graph  # noqa: E402
import rules  # noqa: E402
import run  # noqa: E402

SCN = ROOT / "tests" / "scenarios"
B = graph.Building()


def go(name):
    with tempfile.TemporaryDirectory() as tmp:
        res = run.run_scenario(SCN / name, out_dir=tmp, building=B)
    assert res["plan"] is not None, "no plan for " + name
    return res


def verbs(res):
    return [a.strip("()").split()[0] for a in res["plan"]]


def text(res):
    return " ".join(res["plan"])


class Scenarios(unittest.TestCase):
    def test_s0_baseline_walks_out(self):
        res = go("s0_fire_ground_floor_baseline.json")
        self.assertTrue(res["valid"], res["val_output"])
        self.assertEqual(verbs(res)[-1], "exit-building")
        self.assertNotIn("descend-stairs", verbs(res))

    def test_s1_fire_near_stair5_routes_to_stair2(self):
        res = go("s1_fire_floor4_near_stair5.json")
        self.assertTrue(res["valid"], res["val_output"])
        self.assertIn("stair_2_l4", text(res))
        self.assertNotIn("stair_5_l4", text(res))
        self.assertNotIn("use-elevator", verbs(res))
        self.assertEqual(verbs(res)[-1], "exit-building")

    def test_s2_both_stairs_blocked_shelters_and_notifies(self):
        res = go("s2_fire_floor5_both_stairs_blocked.json")
        self.assertTrue(res["valid"], res["val_output"])
        self.assertEqual(verbs(res)[-1], "shelter-and-notify")
        self.assertNotIn("descend-stairs", verbs(res))
        self.assertNotIn("use-elevator", verbs(res))

    def test_s3_wheelchair_shelters_no_stairs_no_elevator(self):
        res = go("s3_wheelchair_floor6.json")
        self.assertTrue(res["valid"], res["val_output"])
        self.assertEqual(verbs(res)[-1], "shelter-and-notify")
        self.assertNotIn("descend-stairs", verbs(res))
        self.assertNotIn("use-elevator", verbs(res))

    def test_s4_wheelchair_directed_uses_elevator(self):
        res = go("s4_wheelchair_floor6_directed.json")
        self.assertTrue(res["valid"], res["val_output"])
        self.assertEqual(verbs(res).count("use-elevator"), 5)  # L6 -> L1
        self.assertNotIn("descend-stairs", verbs(res))
        self.assertEqual(verbs(res)[-1], "exit-building")

    def test_s7_earthquake_waits_then_avoids_glass(self):
        res = go("s7_earthquake_floor3_glass.json")
        self.assertTrue(res["valid"], res["val_output"])
        self.assertEqual(verbs(res)[0], "wait-for-shaking-to-stop")
        self.assertEqual(verbs(res).count("wait-for-shaking-to-stop"), 1)
        self.assertNotIn("l3_c_nw_lobby", text(res))  # blocked glass node
        self.assertEqual(verbs(res)[-1], "exit-building")

    def test_s8_hazmat_outdoor_release_shelters_in_place(self):
        res = go("s8_hazmat_outdoor_release.json")
        self.assertTrue(res["valid"], res["val_output"])
        self.assertEqual(verbs(res), ["shelter-in-place"])


class RuleLayer(unittest.TestCase):
    def test_fire_blocks_hazard_radius_only_on_same_floor(self):
        r = rules.apply({"emergency": "fire", "hazard_locations": ["L4_c_s_stair"], "hazard_radius": 1}, B)
        self.assertIn("L4_c_s_stair", r.blocked)
        self.assertIn("L4_c_s_e", r.blocked)
        self.assertTrue(all(B.floor(i) == "L4" for i in r.blocked))
        self.assertFalse(r.directed_by_responders)
        self.assertFalse(r.shelter_in_place_ok)

    def test_stairwell_option_blocks_the_stair_on_every_floor(self):
        r = rules.apply({"emergency": "fire", "hazard_locations": ["stair_5_L4"], "block_stairwell": True}, B)
        self.assertEqual({i for i in r.blocked if i.startswith("stair_5_")},
                         {"stair_5_L%d" % n for n in range(7)})
        self.assertNotIn("stair_2_L4", r.blocked)

    def test_hazmat_allows_shelter_in_place_and_outdoor_blocks_exits(self):
        r = rules.apply({"emergency": "hazmat", "outdoor_release": True}, B)
        self.assertTrue(r.shelter_in_place_ok)
        self.assertTrue(set(B.of_type("exit")) <= r.blocked)

    def test_earthquake_sets_shaking_and_bans_elevators(self):
        r = rules.apply({"emergency": "earthquake"}, B)
        self.assertTrue(r.shaking)
        self.assertFalse(r.directed_by_responders)

    def test_bad_input_is_rejected(self):
        with self.assertRaises(ValueError):
            rules.apply({"emergency": "flood"}, B)
        with self.assertRaises(ValueError):
            rules.apply({"emergency": "fire", "hazard_locations": ["nope"]}, B)
        base = {"emergency": "fire"}
        with self.assertRaises(ValueError):
            generate_problem.build_problem(B, dict(base, groups=[]))
        with self.assertRaises(ValueError):
            generate_problem.build_problem(B, dict(base, groups=[{"id": "g1", "location": "nope"}]))
        with self.assertRaises(ValueError):
            generate_problem.build_problem(B, dict(base, groups=[{"id": "g1", "location": "exit_L1_W"}]))


class Generator(unittest.TestCase):
    def test_uncertain_exits_are_not_exits_by_default(self):
        scn = json.loads((SCN / "s0_fire_ground_floor_baseline.json").read_text())
        self.assertNotIn("(exit exit_L0_E)", generate_problem.build_problem(B, scn))
        scn["trust_uncertain_exits"] = True
        self.assertIn("(exit exit_L0_E)", generate_problem.build_problem(B, scn))

    def test_refuges_are_elevator_lobbies_on_floors_2_up(self):
        self.assertEqual(B.refuges(), ["L2_z_nw"] + ["L%d_c_nw_lobby" % n for n in range(3, 7)])


if __name__ == "__main__":
    unittest.main()
