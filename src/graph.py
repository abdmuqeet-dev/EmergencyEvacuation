"""Load data/building.json and derive the facts the PDDL domain needs."""
import json
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOOR_ORDER = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]
# edge kinds a group can walk along (stairs and elevators are handled separately)
WALK_KINDS = {"corridor", "door", "open", "exit", "outside"}


class Building:
    def __init__(self, path=None):
        data = json.loads(Path(path or ROOT / "data" / "building.json").read_text())
        self.meta = data["meta"]
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = data["edges"]
        self._assembly = {i for i, n in self.nodes.items() if n["type"] == "assembly"}

    # ---- lookups
    def label(self, node_id):
        return self.nodes[node_id].get("label", node_id)

    def floor(self, node_id):
        return self.nodes[node_id].get("floor")

    def has(self, node_id):
        return node_id in self.nodes

    def of_type(self, *types):
        return [i for i, n in self.nodes.items() if n["type"] in types]

    # ---- facts for the domain
    def locations(self):
        """Every node except the assembly placeholder (exits are the way out)."""
        return [i for i in self.nodes if i not in self._assembly]

    def walk_pairs(self):
        """Undirected walkable pairs. Edges to the assembly placeholder are left out."""
        for e in self.edges:
            if e["kind"] in WALK_KINDS and e["from"] not in self._assembly and e["to"] not in self._assembly:
                yield e["from"], e["to"]

    def stairs_down(self):
        """(upper, lower) pairs: a stair node and the same stair one floor lower."""
        rank = FLOOR_ORDER.index
        for e in self.edges:
            if e["kind"] == "stairs":
                a, b = e["from"], e["to"]
                yield (a, b) if rank(self.floor(a)) > rank(self.floor(b)) else (b, a)

    def elevator_links(self):
        """Both directions between adjacent elevator-car nodes."""
        for e in self.edges:
            if e["kind"] == "elevator":
                yield e["from"], e["to"]
                yield e["to"], e["from"]

    def exits(self, trust_uncertain=False):
        """Exit nodes. Uncertain ones (e.g. the Lower-floor 'east' arrow) are skipped by default."""
        return [i for i in self.of_type("exit") if trust_uncertain or not self.nodes[i].get("uncertain")]

    def refuges(self):
        """Areas of refuge (assumption A3): the elevator lobby on floors 2 and up."""
        out = set()
        for e in self.edges:
            if e["kind"] != "door":
                continue
            for a, b in ((e["from"], e["to"]), (e["to"], e["from"])):
                if self.nodes[a]["type"] == "elevator" and FLOOR_ORDER.index(self.floor(a)) >= 2:
                    out.add(b)
        return sorted(out)

    # ---- hazard geometry
    def neighbors_on_floor(self, node_id):
        floor = self.floor(node_id)
        for a, b in self.walk_pairs():
            if a == node_id and self.floor(b) == floor:
                yield b
            elif b == node_id and self.floor(a) == floor:
                yield a

    def within(self, node_id, hops):
        """Nodes within `hops` same-floor walkable steps of node_id (including itself)."""
        seen = {node_id}
        frontier = deque([(node_id, 0)])
        while frontier:
            n, d = frontier.popleft()
            if d == hops:
                continue
            for m in self.neighbors_on_floor(n):
                if m not in seen:
                    seen.add(m)
                    frontier.append((m, d + 1))
        return seen
