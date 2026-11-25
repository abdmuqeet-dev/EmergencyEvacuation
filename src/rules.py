"""Rule layer: emergency type -> the emergency facts the planner needs.

Scenario keys used here (all optional except "emergency"):
  emergency              "fire" | "earthquake" | "hazmat"
  hazard_locations       node ids where the hazard is (fire/smoke, indoor chemical release)
  hazard_radius          same-floor walking steps the hazard spreads from each location (default 0)
  block_stairwell        also block the same stair on every floor when a hazard sits on a stair node
  blocked                extra node ids that are blocked (used for re-planning later)
  glass_nodes            earthquake only: nodes with glass that become unsafe
  outdoor_release        hazmat only: the release is outside, so every exit is blocked
  directed_by_responders true if responders have authorized elevator use (default false)
"""
from dataclasses import dataclass, field

EMERGENCIES = ("fire", "earthquake", "hazmat")


@dataclass
class RuleResult:
    blocked: set = field(default_factory=set)
    directed_by_responders: bool = False
    shelter_in_place_ok: bool = False
    shaking: bool = False
    notes: list = field(default_factory=list)


def _check_ids(b, ids, what):
    for i in ids:
        if not b.has(i):
            raise ValueError("%s: unknown node id %r" % (what, i))


def hazard_region(b, scn):
    out = set()
    radius = int(scn.get("hazard_radius", 0))
    for loc in scn.get("hazard_locations", []):
        out |= b.within(loc, radius)
        if scn.get("block_stairwell") and b.nodes[loc]["type"] == "stair":
            prefix = loc.rsplit("_", 1)[0] + "_"  # e.g. "stair_5_"
            out |= {i for i in b.nodes if i.startswith(prefix) and b.nodes[i]["type"] == "stair"}
    return out


def apply(scn, b):
    kind = scn.get("emergency")
    if kind not in EMERGENCIES:
        raise ValueError("emergency must be one of %s, got %r" % (EMERGENCIES, kind))
    _check_ids(b, scn.get("hazard_locations", []), "hazard_locations")
    _check_ids(b, scn.get("blocked", []), "blocked")
    _check_ids(b, scn.get("glass_nodes", []), "glass_nodes")

    r = RuleResult(directed_by_responders=bool(scn.get("directed_by_responders", False)))
    r.blocked |= set(scn.get("blocked", []))

    if kind == "fire":
        r.blocked |= hazard_region(b, scn)
        r.notes.append("fire: hazard region blocked; elevators banned unless directed")
    elif kind == "earthquake":
        r.shaking = True
        flagged = {i for i, n in b.nodes.items() if n.get("glass")}
        r.blocked |= flagged | set(scn.get("glass_nodes", []))
        r.blocked |= hazard_region(b, scn)
        r.notes.append("earthquake: wait for shaking to stop; glass nodes blocked; elevators banned unless directed")
    elif kind == "hazmat":
        r.shelter_in_place_ok = True
        r.blocked |= hazard_region(b, scn)
        if scn.get("outdoor_release"):
            r.blocked |= set(b.of_type("exit"))
            r.notes.append("hazmat (outdoor release): every exit blocked, shelter in place")
        else:
            r.notes.append("hazmat (indoor release): hazard region blocked, shelter in place allowed")
    return r
