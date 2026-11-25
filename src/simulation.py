"""Stepped simulation with re-planning (Phase 6).

A Simulation owns the live state of an evacuation: where every group is, what is blocked, and
what each group still plans to do. You advance it one step at a time and change the situation
between steps; the plans are re-made from where the groups are now.

    sim = Simulation("tests/scenarios/s6_midrun_block_lower.json")
    sim.step()                          # every group does its next leg
    sim.block(["L0_c_w_e"])             # something becomes impassable -> affected groups re-plan
    sim.step(); ...                     # until sim.done
    sim.unblock([...])                  # reopened -> everyone who could do better re-plans

Time model
  Without crowding a step is ONE ACTION for every group at once: one walking move, one stair flight,
  one elevator ride, the exit, and so on, so groups visibly walk node by node and you can block
  something mid-route. With crowding a step is one LEG: a run of walking moves plus the stair flight
  or wait that ends it, because the crowding model counts stair waves and walking takes no wave
  (see docs/PROJECT_PLAN.md, Phase 4 limits). Override with Simulation(..., unit="action"|"leg").
  An earthquake adds one first step where everybody waits for the shaking to stop.
  A stair flight is one action: a group is always at a node, never half way down. A block takes
  effect before the next step, so a group at the top of a flight whose landing just got blocked
  must walk to another stair; a group already at the bottom is simply past it.

Re-planning
  Each group is re-planned from its current node with the new blocked set. Without crowding only
  groups whose remaining route touches the newly blocked places are re-planned (groups are
  independent). With crowding every walking group is re-planned together, because they share stair
  slots; the wave clock restarts at the re-plan. Every re-plan is checked with VAL; a rejected
  plan raises run.PlanInvalid. A group with no possible plan is marked "stuck" and the others go on.
"""
import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_problem  # noqa: E402
import graph  # noqa: E402
import planner  # noqa: E402
import prioritized  # noqa: E402
import rules  # noqa: E402
import run  # noqa: E402
import validate  # noqa: E402

WALK = "move"
TERMINAL = ("out", "sheltered", "stuck")
MAX_STEPS = 300


def verb(action):
    return action.strip("()").split()[0]


def destination(action):
    """The node an action moves a group into (or acts at), lower case; None for waits."""
    t = action.strip("()").split()
    if t[0] in ("move", "descend-stairs", "descend-stairs-crowded", "use-elevator"):
        return t[3]
    if t[0] in ("exit-building", "shelter-in-place", "shelter-and-notify"):
        return t[2]
    return None


PHRASE = {"move": "walks to", "descend-stairs": "takes the stairs down to", "descend-stairs-crowded": "takes the stairs down to",
          "use-elevator": "rides the elevator to", "exit-building": "leaves the building at",
          "shelter-in-place": "shelters in place at", "shelter-and-notify": "shelters and tells responders at"}


FLOOR_WORD = {"L0": "Lower floor", "L1": "1st floor", "L2": "2nd floor", "L3": "3rd floor", "L4": "4th floor",
              "L5": "5th floor", "L6": "6th floor"}


def describe(sim, action):
    """Plain English for one action, no node ids: 'walks to East corridor, middle'."""
    v = verb(action)
    if v == "wait-a-wave":
        return "waits for the stairs to clear"
    if v == "wait-for-shaking-to-stop":
        return "waits for the shaking to stop"
    node = sim.canon[destination(action)]
    where = sim.b.label(node)
    if sim.b.nodes[node]["type"] in ("stair", "elevator") and sim.b.floor(node):   # the same stair exists on every floor
        where += ", " + FLOOR_WORD[sim.b.floor(node)]
    return "%s %s" % (PHRASE[v], where)


def violations(sim):
    """Independent check on the action log: any action that enters a place that was blocked at the time."""
    bad = []
    for step, gid, action, blocked in sim.executed:
        d = destination(action)
        if d and d in {x.lower() for x in blocked}:
            bad.append((step, gid, action))
    return bad


class Simulation:
    def __init__(self, scenario, building=None, workdir=None, search=planner.OPTIMAL, timeout=120, check=True, unit=None):
        self.scn = scenario if isinstance(scenario, dict) else json.loads(Path(scenario).read_text())
        self.b = building or graph.Building()
        self.search, self.timeout, self.check = search, timeout, check
        name = self.scn.get("name", "scenario")
        self.workdir = Path(workdir) if workdir else graph.ROOT / "runs" / name / "sim"
        self.workdir.mkdir(parents=True, exist_ok=True)
        base = rules.apply(self.scn, self.b)
        self.base_blocked = set(base.blocked)       # blocked by the emergency itself
        self.manual = set()                         # blocked by the user during the run
        self.shaking = base.shaking
        self.crowded = bool(self.scn.get("crowding"))
        self.unit = unit or ("leg" if self.crowded else "action")
        if self.unit not in ("action", "leg"):
            raise ValueError("unit must be 'action' or 'leg'")
        self.canon = {i.lower(): i for i in self.b.nodes}
        generate_problem._validate_groups(self.b, self.scn)
        self.groups = {g["id"]: {"id": g["id"], "location": g["location"], "status": "walking", "kind": None,
                                 "mobility": bool(g.get("mobility_impaired")), "size": g.get("size"), "queue": []}
                       for g in self.scn["groups"]}
        self.start = {i: g["location"] for i, g in self.groups.items()}
        self.step_no = 0
        self.log = []          # step and event records, in order
        self.executed = []     # (step, group id, action, blocked set at the time)
        self.replans = 0
        self.all_valid = True
        self.ghost = {}        # group id -> the route it had before its latest re-plan (for the UI)
        self.frames = []       # one snapshot per step and per change of situation, for replay
        self._replan(list(self.groups), "initial plan")
        self._snap("Start")

    # ---- state -------------------------------------------------------------------------
    @property
    def blocked(self):
        return self.base_blocked | self.manual

    @property
    def done(self):
        return all(g["status"] in TERMINAL for g in self.groups.values())

    def snapshot(self):
        return {"step": self.step_no, "done": self.done, "shaking": self.shaking, "blocked": sorted(self.blocked),
                "groups": {i: {"location": g["location"], "status": g["status"], "kind": g["kind"],
                               "remaining": len(g["queue"])} for i, g in self.groups.items()}}

    # ---- stepping ----------------------------------------------------------------------
    def step(self):
        """Advance every group one step (one action, or one leg when crowded). Returns the step record, or None if everyone is finished."""
        if self.done:
            return None
        self.step_no += 1
        rec = {"type": "step", "n": self.step_no, "shaking": False, "actions": {}, "blocked": sorted(self.blocked)}
        if self.shaking:
            self.shaking = False
            rec["shaking"] = True
            self.executed.append((self.step_no, None, "(wait-for-shaking-to-stop)", frozenset(self.blocked)))
        else:
            for gid, g in self.groups.items():
                if g["status"] != "walking":
                    continue
                if not g["queue"]:
                    g["status"] = "stuck"
                    continue
                leg = []
                while g["queue"]:
                    a = g["queue"].pop(0)
                    leg.append(a)
                    self.executed.append((self.step_no, gid, a, frozenset(self.blocked)))
                    self._apply(g, a)
                    if self.unit == "action" or verb(a) != WALK:
                        break
                rec["actions"][gid] = leg
        rec["locations"] = {i: g["location"] for i, g in self.groups.items()}
        rec["statuses"] = {i: g["status"] for i, g in self.groups.items()}
        self.log.append(rec)
        self._snap("Step %d" % self.step_no)
        return rec

    def _snap(self, label):
        """Remember how everything looks now, so the UI can replay any moment."""
        self.frames.append({
            "label": label, "step": self.step_no, "shaking": self.shaking, "blocked": sorted(self.blocked),
            "ghost": {k: list(v) for k, v in self.ghost.items()},
            "groups": {gid: {"location": g["location"], "status": g["status"], "kind": g["kind"],
                             "remaining": len(g["queue"]), "route": self.route(gid), "trail": self.trail(gid)}
                       for gid, g in self.groups.items()}})

    def _apply(self, g, action):
        t = action.strip("()").split()
        v = t[0]
        if v in ("move", "descend-stairs", "descend-stairs-crowded", "use-elevator"):
            g["location"] = self.canon[t[3]]
        elif v == "exit-building":
            g["status"] = "out"
        elif v in ("shelter-in-place", "shelter-and-notify"):
            g["status"], g["kind"] = "sheltered", v

    # ---- changes to the situation --------------------------------------------------------
    def block(self, nodes):
        return self.update(block=nodes)

    def unblock(self, nodes):
        return self.update(unblock=nodes)

    def update(self, block=(), unblock=()):
        """Block and/or unblock places now, then re-plan whoever is affected. Returns the event record."""
        block, unblock = set(block), set(unblock)
        for n in block | unblock:
            if not self.b.has(n):
                raise ValueError("unknown node id %r" % n)
        stuck_by_emergency = unblock & self.base_blocked
        if stuck_by_emergency:
            raise ValueError("%s blocked by the emergency itself, not by the user" % sorted(stuck_by_emergency))
        before = self.blocked
        self.manual = (self.manual | block) - unblock
        new_block = self.blocked - before
        opened = before - self.blocked
        low_new = {n.lower() for n in new_block}
        affected = []
        for gid, g in self.groups.items():
            if g["status"] == "out":
                continue
            if opened:                      # something reopened: anyone who is not out may do better
                affected.append(gid)
            elif g["status"] == "walking":
                if self.crowded and new_block:
                    affected.append(gid)    # they share stair slots, so re-plan together
                elif any(destination(a) in low_new for a in g["queue"]):
                    affected.append(gid)
            elif g["status"] == "sheltered" and g["location"] in new_block:
                affected.append(gid)        # the place they shelter in is no longer safe
        event = {"type": "event", "after_step": self.step_no, "block": sorted(block), "unblock": sorted(unblock),
                 "blocked": sorted(self.blocked), "replanned": [], "stuck": [], "seconds": 0.0, "changes": {}}
        if affected:
            old = {gid: (self.route(gid), len(self.groups[gid]["queue"]), self.groups[gid]["status"]) for gid in affected}
            event.update(self._replan(affected, "blocked %s, unblocked %s" % (sorted(block), sorted(unblock))))
            for gid in affected:
                route, n_before, status = old[gid]
                new_route = self.route(gid)
                if route != new_route or status != self.groups[gid]["status"]:
                    if len(route) > 1:
                        self.ghost[gid] = route
                    event["changes"][gid] = {"before": n_before, "after": len(self.groups[gid]["queue"]),
                                             "was": status, "now": self.groups[gid]["status"]}
        self.log.append(event)
        what = []
        if block:
            what.append("blocked")
        if unblock:
            what.append("unblocked")
        self._snap("Step %d, %s" % (self.step_no, " and ".join(what) or "no change"))
        return event

    # ---- planning ------------------------------------------------------------------------
    def _replan(self, gids, reason):
        t0 = time.time()
        self.replans += 1
        rdir = self.workdir / ("replan_%02d" % self.replans)
        rdir.mkdir(parents=True, exist_ok=True)
        gl = [{"id": g["id"], "location": g["location"], "mobility_impaired": g["mobility"], "size": g["size"]}
              for g in (self.groups[i] for i in gids)]
        scn = {k: v for k, v in self.scn.items() if k not in ("script", "expect", "description")}
        scn["groups"] = gl
        scn["blocked"] = sorted(set(self.scn.get("blocked", [])) | self.manual)
        if self.crowded:
            cap, n_waves = generate_problem.crowding_config(self.b, scn, gl)
            scn["crowding"] = {"stair_capacity": cap, "waves": n_waves}  # explicit, so dropping a group keeps slot names
        r = rules.apply(scn, self.b)
        r_plan = dataclasses.replace(r, shaking=False)   # shaking is handled by step()
        plans, stuck, joined = {}, [], []
        if self.crowded:
            joined, _, stuck = prioritized.solve_partial(self.b, scn, r_plan, run.DOMAIN, rdir, self.search, self.timeout)
            lower = {g["id"].lower(): g["id"] for g in gl}
            plans = {g["id"]: [] for g in gl if g["id"] not in stuck}
            for a in joined:
                plans[lower[a.strip("()").split()[1]]].append(a)
        else:
            for g in gl:
                sub = dict(scn, groups=[g])
                path = rdir / ("p_%s.pddl" % g["id"])
                path.write_text(generate_problem.build_problem(self.b, sub, r_plan, shaking=False))
                res = planner.solve(run.DOMAIN, path, self.search, self.timeout)
                if res is None:
                    stuck.append(g["id"])
                else:
                    plans[g["id"]] = res[0]
                    joined += res[0]
        valid = None
        solved = [g for g in gl if g["id"] not in stuck]
        if solved and self.check:
            prob = rdir / "problem.pddl"
            prob.write_text(generate_problem.build_problem(self.b, dict(scn, groups=solved), r, shaking=self.shaking))
            plan_file = rdir / "plan.txt"
            planner.write_plan((["(wait-for-shaking-to-stop)"] if self.shaking else []) + joined, plan_file)
            valid, out = validate.validate(run.DOMAIN, prob, plan_file)
            if not valid:
                self.all_valid = False
                raise run.PlanInvalid("VAL rejected the re-plan (%s):\n%s" % (reason, out[-1500:]))
        for gid in gids:
            g = self.groups[gid]
            if gid in stuck:
                g["status"], g["kind"], g["queue"] = "stuck", None, []
                continue
            acts = plans[gid]
            if (g["status"] == "sheltered" and len(acts) == 1 and verb(acts[0]).startswith("shelter")
                    and destination(acts[0]) == g["location"].lower()):
                continue                    # still best to stay where they are sheltering
            g["status"], g["kind"], g["queue"] = "walking", None, list(acts)
        return {"replanned": list(gids), "stuck": stuck, "seconds": time.time() - t0, "valid": valid,
                "reason": reason}

    # ---- running a script ------------------------------------------------------------------
    def run_script(self, script=None):
        """Run to the end, applying scripted events: [{"after_step": 2, "block": [...], "unblock": [...]}]."""
        events = sorted(script if script is not None else self.scn.get("script", []), key=lambda e: e["after_step"])
        for ev in events:
            while self.step_no < ev["after_step"] and not self.done:
                self.step()
            self.update(block=ev.get("block", ()), unblock=ev.get("unblock", ()))
        while not self.done and self.step_no < MAX_STEPS:
            self.step()
        return self

    def trail(self, gid):
        """Nodes a group has walked through so far, start first (for drawing)."""
        nodes = [self.start[gid]]
        for _, g, a, _b in self.executed:
            d = destination(a) if g == gid else None
            if d and self.canon[d] != nodes[-1]:
                nodes.append(self.canon[d])
        return nodes

    def route(self, gid):
        """Where a walking group is going: its current node, then every node left on its plan."""
        g = self.groups[gid]
        nodes = [g["location"]]
        if g["status"] == "walking":
            for a in g["queue"]:
                d = destination(a)
                if d and self.canon[d] != nodes[-1]:
                    nodes.append(self.canon[d])
        return nodes

    def executed_actions(self):
        return [a for _, _, a, _ in self.executed]


def pretty_step(sim, rec):
    lines = []
    if rec["shaking"]:
        lines.append("  everyone waits for the shaking to stop")
    for gid, acts in rec["actions"].items():
        end = acts[-1]
        place = sim.b.label(sim.canon[destination(end)]) if destination(end) else "-"
        lines.append("  %s: %d action(s), ends with %s -> %s" % (gid, len(acts), verb(end), place))
    return lines


def main():
    ap = argparse.ArgumentParser(description="Run a scenario as a stepped simulation, applying its script of block events.")
    ap.add_argument("scenario")
    ap.add_argument("--out")
    a = ap.parse_args()
    sim = Simulation(a.scenario, workdir=a.out)
    print("scenario:", sim.scn.get("name"), "| groups:", ", ".join("%s at %s" % (i, g["location"]) for i, g in sim.groups.items()))
    script = sorted(sim.scn.get("script", []), key=lambda e: e["after_step"])
    pending = list(script)
    while not sim.done and sim.step_no < MAX_STEPS:
        while pending and pending[0]["after_step"] <= sim.step_no:
            ev = pending.pop(0)
            rec = sim.update(block=ev.get("block", ()), unblock=ev.get("unblock", ()))
            print("EVENT after step %d: block %s unblock %s -> re-planned %s%s (%.1fs, VAL %s)" % (
                sim.step_no, ev.get("block", []), ev.get("unblock", []), rec["replanned"] or "nobody",
                ", stuck %s" % rec["stuck"] if rec["stuck"] else "", rec["seconds"], rec.get("valid")))
        rec = sim.step()
        print("step %d" % rec["n"])
        print("\n".join(pretty_step(sim, rec)))
    for gid, g in sim.groups.items():
        print("%s: %s%s at %s" % (gid, g["status"], " (%s)" % g["kind"] if g["kind"] else "", sim.b.label(g["location"])))
    bad = violations(sim)
    print("steps: %d | re-plans: %d | entered a blocked place: %s" % (sim.step_no, sim.replans - 1, bad or "never"))
    return 0 if not bad and sim.all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
