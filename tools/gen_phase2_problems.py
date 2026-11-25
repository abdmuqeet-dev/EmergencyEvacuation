"""Emit the Phase 2 hand-written test problems into pddl/problems/.

All four problems use the same abbreviated four-floor mini-building so that they
are small and readable. Node ids follow data/building.json naming. The 4th floor
is a 7-node ring; floors 3, 2 and 1 are cut down to a lobby-to-stair-5 path.
Real-building problems come from the generator in Phase 3.

Run:  py tools/gen_phase2_problems.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "pddl" / "problems"

# (floor, nodes in ring/path order, closed ring?)
L4 = ["L4_c_nw_lobby", "L4_c_n_e", "L4_c_e_mid", "L4_c_s_e", "L4_c_s_stair", "L4_c_s_w", "L4_c_w_mid"]
L3 = ["L3_c_nw_lobby", "L3_c_mid", "L3_c_s_stair"]
L2 = ["L2_z_nw", "L2_z_center"]
L1 = ["L1_c_elev", "L1_c_s_mid", "L1_c_spur"]

walk = []  # undirected walkable pairs
for a, b in zip(L4, L4[1:] + L4[:1]):
    walk.append((a, b))
for path in (L3, L2, L1):
    for a, b in zip(path, path[1:]):
        walk.append((a, b))

# stair and elevator nodes attach to (lobby for stair 2 and elevator, stair-5 corridor for stair 5)
lobby = {"L4": L4[0], "L3": L3[0], "L2": L2[0], "L1": L1[0]}
s5 = {"L4": "L4_c_s_stair", "L3": "L3_c_s_stair", "L2": "L2_z_center", "L1": "L1_c_spur"}
floors = ["L4", "L3", "L2", "L1"]
stairs, elevs = [], []
for f in floors:
    for n, at in (("stair_2_" + f, lobby[f]), ("stair_5_" + f, s5[f]), ("elev_1_" + f, lobby[f])):
        walk.append((n, at))
        (elevs if n.startswith("elev") else stairs).append(n)

exits = {"exit_L1_S": "L1_c_elev", "exit_L1_N": "L1_c_spur"}
for e, at in exits.items():
    walk.append((e, at))

refuges = [lobby[f] for f in ("L4", "L3", "L2")]  # elevator lobbies (assumption A3)

locations = L4 + L3 + L2 + L1 + stairs + elevs + list(exits)


def build(name, comment, groups, rooms, blocked, directed, goal_extra=""):
    """groups: [(id, room, impaired)], rooms: {room_id: corridor}"""
    locs = locations + list(rooms)
    L = []
    L.append("; " + comment.replace("\n", "\n; "))
    L.append("(define (problem %s)" % name)
    L.append("  (:domain evac)")
    L.append("  (:objects")
    L.append("    " + " ".join(locs) + " - location")
    L.append("    " + " ".join(g for g, _, _ in groups) + " - group)")
    L.append("  (:init")
    L.append("    (= (total-cost) 0)")
    for a, b in walk + [(r, c) for r, c in rooms.items()]:
        L.append("    (connected %s %s) (connected %s %s)" % (a, b, b, a))
    for f_hi, f_lo in zip(floors, floors[1:]):
        for s in ("stair_2_", "stair_5_"):
            L.append("    (stairs-down %s%s %s%s)" % (s, f_hi, s, f_lo))
        L.append("    (elevator-link elev_1_%s elev_1_%s) (elevator-link elev_1_%s elev_1_%s)" % (f_hi, f_lo, f_lo, f_hi))
    for e in exits:
        L.append("    (exit %s)" % e)
    for r in refuges:
        L.append("    (refuge %s)" % r)
    for b in blocked:
        L.append("    (blocked %s)" % b)
    if directed:
        L.append("    (directed-by-responders)")
    for g, room, imp in groups:
        L.append("    (at %s %s)" % (g, room))
        if imp:
            L.append("    (mobility-impaired %s)" % g)
    L.append("  )")
    L.append("  (:goal (and " + " ".join("(safe %s)" % g for g, _, _ in groups) + "))")
    L.append("  (:metric minimize (total-cost)))")
    return "\n".join(L) + "\n"


OUT.mkdir(parents=True, exist_ok=True)

# P1 = test scenario 1: fire at stair 5 on the 4th floor; the group must use stair 2, no elevators.
(OUT / "p1_fire_stair5_use_stair2.pddl").write_text(build(
    "p1-fire-stair5", "Scenario 1: fire on 4th floor near stair 5. Group in room 446 must reach stair 2.\n"
    "Stair 5 side is blocked and elevators are not authorized.",
    [("g1", "L4_r446", False)], {"L4_r446": "L4_c_s_e"},
    blocked=["L4_c_s_stair", "stair_5_L4"], directed=False))

# P2 = test scenario 3: wheelchair group, no responder direction -> shelter and notify.
(OUT / "p2_wheelchair_shelter_and_notify.pddl").write_text(build(
    "p2-wheelchair-shelter", "Scenario 3: mobility-impaired group on the 4th floor, elevators not authorized.\n"
    "No stairs, no elevator: walk to the refuge (elevator lobby) and shelter-and-notify.",
    [("g2", "L4_r414", True)], {"L4_r414": "L4_c_n_e"},
    blocked=[], directed=False))

# P3 = test scenario 4: same group, responders direct elevator use -> evacuate by elevator.
(OUT / "p3_wheelchair_elevator_directed.pddl").write_text(build(
    "p3-wheelchair-elevator", "Scenario 4: as P2 but directed-by-responders is true, so the elevator is legal.\n"
    "Expect: walk to the elevator, ride down, exit. No stairs.",
    [("g2", "L4_r414", True)], {"L4_r414": "L4_c_n_e"},
    blocked=[], directed=True))

# P4 = test scenario 2: both stairs blocked -> shelter and notify.
(OUT / "p4_both_stairs_blocked.pddl").write_text(build(
    "p4-both-stairs-blocked", "Scenario 2: stairs 2 and 5 are both blocked on the 4th floor.\n"
    "Group in room 446 walks to the refuge and shelters-and-notifies.",
    [("g1", "L4_r446", False)], {"L4_r446": "L4_c_s_e"},
    blocked=["stair_2_L4", "stair_5_L4"], directed=False))

print("wrote 4 problems to", OUT)
