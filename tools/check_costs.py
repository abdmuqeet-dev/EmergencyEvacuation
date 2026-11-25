"""Check the domain's cost thresholds against the real building.

Computes, for every room/restroom, the cheapest evacuation cost to an exit using the same
costs as pddl/domain.pddl (move 1, stairs 2, elevator 1, exit 1), with nothing blocked.
The shelter actions (90 and 100) must cost more than the worst of these, otherwise the
planner would shelter a group that could have walked out.

Run:  py tools/check_costs.py
"""
import heapq
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import graph  # noqa: E402

MOVE, STAIRS, ELEV, EXIT = 1, 2, 1, 1
SHELTER_IN_PLACE, SHELTER_AND_NOTIFY = 90, 100


def build_adj(b, elevators):
    adj = {i: [] for i in b.locations()}
    for a, c in b.walk_pairs():
        adj[a].append((c, MOVE))
        adj[c].append((a, MOVE))
    for up, lo in b.stairs_down():
        adj[up].append((lo, STAIRS))
    if elevators:
        for a, c in b.elevator_links():
            adj[a].append((c, ELEV))
    return adj


def costs_to_exit(b, elevators):
    """Dijkstra backwards from the exits: cost for every node to get out."""
    adj = build_adj(b, elevators)
    radj = {i: [] for i in adj}
    for a, outs in adj.items():
        for c, w in outs:
            radj[c].append((a, w))
    dist = {e: EXIT for e in b.exits()}
    pq = [(EXIT, e) for e in dist]
    heapq.heapify(pq)
    while pq:
        d, n = heapq.heappop(pq)
        if d > dist.get(n, 1e9):
            continue
        for m, w in radj[n]:
            if d + w < dist.get(m, 1e9):
                dist[m] = d + w
                heapq.heappush(pq, (d + w, m))
    return dist


def main():
    b = graph.Building()
    places = b.of_type("room", "restroom")
    ok = True
    for label, elev in (("walking/stairs only", False), ("with elevators (directed)", True)):
        dist = costs_to_exit(b, elev)
        unreachable = sorted(p for p in places if p not in dist)
        reach = {p: dist[p] for p in places if p in dist}
        worst = max(reach, key=reach.get)
        print("%s: %d places, %d unreachable, worst cost %d at %s"
              % (label, len(places), len(unreachable), reach[worst], worst))
        if unreachable and not elev:
            print("   unreachable:", unreachable)
        if reach[worst] >= SHELTER_IN_PLACE:
            ok = False
            print("   PROBLEM: worst evacuation cost is not below the shelter cost")
    print("thresholds: shelter-in-place %d, shelter-and-notify %d -> %s"
          % (SHELTER_IN_PLACE, SHELTER_AND_NOTIFY, "OK" if ok else "TOO LOW"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
