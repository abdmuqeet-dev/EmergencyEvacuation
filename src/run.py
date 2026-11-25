"""One command from scenario to plan.

    .venv\\Scripts\\python src\\run.py tests\\scenarios\\s1_fire_floor4_near_stair5.json
    .venv\\Scripts\\python src\\run.py <scenario.json> --out runs\\my_run --search "lama-first"

Writes problem.pddl and plan.txt into the output folder (default runs/<scenario name>/),
validates the plan with VAL, and prints the plan with room names.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crowding  # noqa: E402
import generate_problem  # noqa: F811,E402
import graph  # noqa: E402
import planner  # noqa: E402
import prioritized  # noqa: E402
import rules  # noqa: E402
import validate  # noqa: E402

ROOT = graph.ROOT


class PlanInvalid(RuntimeError):
    """VAL rejected a plan the planner produced: a bug, never something to show a user."""


DOMAIN = ROOT / "pddl" / "domain.pddl"


def pretty(b, action):
    """'(move g1 l1_r109 l1_c_w_mid)' -> 'move g1: Room 109 -> West spine, middle (...)'"""
    lab = {i.lower(): "%s [%s]" % (b.label(i), i) for i in b.nodes}
    name, *args = action.strip("()").split()
    if not args:
        return name
    g, places = args[0], [lab.get(a, a) for a in args[1:]]
    return "%s %s: %s" % (name, g, " -> ".join(places))


def run_scenario(scenario_path, out_dir=None, search=None, check=True, building=None, verbose=False, strict=False):
    scn = json.loads(Path(scenario_path).read_text())
    b = building or graph.Building()
    r = rules.apply(scn, b)
    problem = generate_problem.build_problem(b, scn, r)
    out = Path(out_dir) if out_dir else ROOT / "runs" / scn.get("name", Path(scenario_path).stem)
    out.mkdir(parents=True, exist_ok=True)
    problem_path, plan_path = out / "problem.pddl", out / "plan.txt"
    problem_path.write_text(problem)
    crowded = bool(scn.get("crowding"))
    if crowded:  # many groups competing for stair slots: plan them one at a time
        result = prioritized.solve(b, scn, r, DOMAIN, out, search or planner.OPTIMAL, verbose=verbose)
    else:
        result = planner.solve(DOMAIN, problem_path, search or planner.OPTIMAL)
    res = {"scenario": scn, "rules": r, "problem": problem_path, "plan": None, "cost": None,
           "valid": None, "val_output": "", "plan_file": plan_path, "crowding": None}
    if result is None:
        return res
    actions, cost = result
    planner.write_plan(actions, plan_path)
    res.update(plan=actions, cost=cost)
    if crowded:
        cap = generate_problem.crowding_config(b, scn, scn["groups"])[0]
        worst, bad = crowding.check(actions, cap)
        res["crowding"] = {"capacity": cap, "max_load": worst, "violations": bad, "waits": crowding.waits(actions)}
    if check:
        res["valid"], res["val_output"] = validate.validate(DOMAIN, problem_path, plan_path)
        if strict and not res["valid"]:
            raise PlanInvalid("VAL rejected the plan for %s:\n%s" % (scn.get("name"), res["val_output"][-1500:]))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenario")
    ap.add_argument("--out")
    ap.add_argument("--search", help='Fast Downward search expression, default astar(lmcut()). Avoid lama-first: it ignores costs and may shelter groups that could walk out')
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args()
    b = graph.Building()
    res = run_scenario(a.scenario, a.out, a.search, not a.no_validate, b, verbose=True)
    print("scenario:", res["scenario"].get("name"), "|", "; ".join(res["rules"].notes))
    if res["plan"] is None:
        print("NO PLAN: the goal cannot be reached (every group needs a way out or a refuge).")
        return 2
    for i, act in enumerate(res["plan"], 1):
        print("%3d. %s" % (i, pretty(b, act)))
    print("cost:", res["cost"], "| plan file:", res["plan_file"])
    c = res["crowding"]
    if c:
        print("stairs: busiest segment carried %d group(s) in one wave (limit %d), %d wait(s)%s"
              % (c["max_load"], c["capacity"], c["waits"], "" if not c["violations"] else " - OVER THE LIMIT"))
    if res["valid"] is not None:
        print("VAL:", "plan valid" if res["valid"] else "PLAN INVALID")
        return 0 if res["valid"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
