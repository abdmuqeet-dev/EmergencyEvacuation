"""One-off: add an "expect" block to each scenario file."""
import json
from pathlib import Path
E = {
 "s0_fire_ground_floor_baseline": {"outcome": "exit", "avoids": ["use-elevator", "shelter-and-notify", "shelter-in-place"], "max_cost": 19},
 "s1_fire_floor4_near_stair5": {"outcome": "exit", "uses": ["stair_2_L4"], "avoids": ["stair_5_L4", "use-elevator"], "max_cost": 19},
 "s2_fire_floor5_both_stairs_blocked": {"outcome": "shelter-and-notify", "avoids": ["exit-building", "use-elevator"]},
 "s3_wheelchair_floor6": {"outcome": "shelter-and-notify", "avoids": ["descend-stairs", "use-elevator", "exit-building"]},
 "s4_wheelchair_floor6_directed": {"outcome": "exit", "uses": ["use-elevator"], "avoids": ["descend-stairs", "shelter-and-notify"]},
 "s5_crowding_floors3to6": {"outcome": "exit", "avoids": ["shelter-and-notify"], "min_waits": 1},
 "s7_earthquake_floor3_glass": {"outcome": "exit", "first_action": "wait-for-shaking-to-stop", "avoids": ["L3_c_nw_lobby", "use-elevator"]},
 "s8_hazmat_outdoor_release": {"outcome": "shelter-in-place", "avoids": ["exit-building"]},
}
for p in Path("tests/scenarios").glob("*.json"):
    d = json.loads(p.read_text())
    d["expect"] = E[d["name"]]
    p.write_text(json.dumps(d, indent=2) + "\n")
