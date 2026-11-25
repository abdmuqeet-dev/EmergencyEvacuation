"""Run every scenario in tests/scenarios/, check each against its "expect" block, report pass/fail.

    .venv\\Scripts\\python src\\suite.py                 run all, write docs/RESULTS.md
    .venv\\Scripts\\python src\\suite.py s1 s5           only scenarios whose file name starts with these
    .venv\\Scripts\\python src\\suite.py --no-report     do not touch docs/RESULTS.md

Exit code 0 only if every scenario passes. A plan that VAL rejects is always a failure.

"expect" keys (all optional except outcome):
  outcome       "exit" (every group leaves the building), "shelter-and-notify", "shelter-in-place",
                or "no-plan" (the goal must be unreachable)
  uses          action names or node ids that must appear in the plan
  avoids        action names or node ids that must not appear
  first_action  the plan must start with this action name
  max_cost      plan cost must not exceed this
  min_waits     at least this many wait-a-wave actions (crowding scenarios)
  allow         end actions that may also appear (e.g. a group that sheltered first, then got out)
  min_replans   at least this many mid-run re-plans (scripted scenarios)

A scenario with a "script" (block/unblock events between steps) runs as a stepped simulation; the
plan checked is the list of actions the groups actually executed, VAL has checked every re-plan,
and no group may ever have entered a place that was blocked at that moment.
"""
import argparse
import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crowding  # noqa: E402
import generate_problem  # noqa: E402
import graph  # noqa: E402
import run  # noqa: E402
import simulation  # noqa: E402

SCENARIOS = graph.ROOT / "tests" / "scenarios"
REPORT = graph.ROOT / "docs" / "RESULTS.md"
OUTCOME_VERB = {"exit": "exit-building", "shelter-and-notify": "shelter-and-notify",
                "shelter-in-place": "shelter-in-place"}


def _tokens(plan):
    """Every action name and argument, lower case."""
    return {t for a in plan for t in a.strip("()").lower().split()}


def check_expectations(scn, res, b):
    """Return a list of failure messages (empty means the scenario passed)."""
    exp, plan, bad = scn.get("expect"), res["plan"], []
    if not exp:
        return ["scenario has no expect block"]
    want = exp.get("outcome")
    if want == "no-plan":
        return [] if plan is None else ["expected no plan but got one"]
    if plan is None:
        return ["no plan found"]
    if res["valid"] is not True:
        bad.append("VAL did not accept the plan")
    n = len(scn["groups"])
    verbs = [a.strip("()").split()[0] for a in plan]
    if want not in OUTCOME_VERB:
        bad.append("unknown outcome %r" % want)
    else:
        if verbs.count(OUTCOME_VERB[want]) != n:
            bad.append("expected %d x %s, plan has %d" % (n, OUTCOME_VERB[want], verbs.count(OUTCOME_VERB[want])))
        others = {v for k, v in OUTCOME_VERB.items() if k != want} - set(exp.get("allow", []))
        stray = sorted(others & set(verbs))
        if stray:
            bad.append("unexpected end action(s): " + ", ".join(stray))
    toks = _tokens(plan)
    for u in exp.get("uses", []):
        if u.lower() not in toks:
            bad.append("plan never uses %s" % u)
    for a in exp.get("avoids", []):
        if a.lower() in toks:
            bad.append("plan uses %s but should not" % a)
    if "first_action" in exp and (not verbs or verbs[0] != exp["first_action"]):
        bad.append("first action is %s, expected %s" % (verbs[0] if verbs else None, exp["first_action"]))
    if "max_cost" in exp and res["cost"] is not None and res["cost"] > exp["max_cost"]:
        bad.append("cost %s exceeds %s" % (res["cost"], exp["max_cost"]))
    if "min_waits" in exp and crowding.waits(plan) < exp["min_waits"]:
        bad.append("expected at least %d wait(s), got %d" % (exp["min_waits"], crowding.waits(plan)))
    sim = res.get("sim")
    if sim:
        if sim["violations"]:
            bad.append("entered a blocked place: %s" % sim["violations"][:3])
        if sim["stuck"]:
            bad.append("groups stuck with no plan: %s" % sim["stuck"])
        if sim["replans"] < exp.get("min_replans", 0):
            bad.append("expected at least %d re-plan(s), got %d" % (exp["min_replans"], sim["replans"]))
    c = res.get("crowding")
    if c and c["violations"]:
        bad.append("stair limit %d exceeded: %s" % (c["capacity"], c["violations"][:3]))
    return bad


def run_one(path, b, out_dir):
    scn = json.loads(Path(path).read_text())
    t0 = time.time()
    try:
        if "script" in scn:
            sim = simulation.Simulation(scn, building=b, workdir=out_dir / scn["name"] / "sim").run_script()
            res = {"plan": sim.executed_actions(), "cost": None, "valid": sim.all_valid, "crowding": None,
                   "sim": {"violations": simulation.violations(sim), "replans": sim.replans - 1, "steps": sim.step_no,
                           "stuck": [i for i, g in sim.groups.items() if g["status"] == "stuck"]}}
        else:
            res = run.run_scenario(path, out_dir=out_dir / scn["name"], building=b, strict=True)
        failures = check_expectations(scn, res, b)
    except run.PlanInvalid as e:
        res, failures = {"plan": None, "cost": None, "valid": False, "crowding": None}, ["VAL rejected the plan"]
        print(e, file=sys.stderr)
    except Exception as e:  # planner crash or timeout: report it, keep going
        res, failures = {"plan": None, "cost": None, "valid": None, "crowding": None}, ["%s: %s" % (type(e).__name__, e)]
    return {"name": scn["name"], "description": scn.get("description", ""), "failures": failures,
            "plan": res["plan"], "cost": res["cost"], "valid": res["valid"], "crowding": res["crowding"],
            "sim": res.get("sim"),
            "groups": len(scn["groups"]), "seconds": time.time() - t0}


def write_report(results, path=REPORT):
    ok = sum(1 for r in results if not r["failures"])
    L = ["# Scenario suite results", "",
         "Generated by `src/suite.py` on %s. Do not edit by hand." % datetime.date.today().isoformat(), "",
         "**%d of %d scenarios pass.** A scenario passes when the planner finds a plan, VAL accepts it, "
         "and the plan matches the `expect` block in the scenario file." % (ok, len(results)), "",
         "| Scenario | Groups | Result | VAL | Cost | Actions | Time (s) |", "|---|---|---|---|---|---|---|"]
    for r in results:
        L.append("| %s | %d | %s | %s | %s | %s | %.0f |" % (
            r["name"], r["groups"], "PASS" if not r["failures"] else "FAIL",
            {True: "valid", False: "INVALID", None: "-"}[r["valid"]],
            r["cost"] if r["cost"] is not None else "-", len(r["plan"]) if r["plan"] else "-", r["seconds"]))
    L += ["", "## Details", ""]
    for r in results:
        L.append("### %s" % r["name"])
        L.append(r["description"])
        L.append("")
        if r["failures"]:
            L += ["- FAILED: " + f for f in r["failures"]]
        else:
            L.append("- passed all checks")
        if r.get("sim"):
            L.append("- simulation: %d steps, %d re-plan(s), entered a blocked place: %s"
                     % (r["sim"]["steps"], r["sim"]["replans"], r["sim"]["violations"] or "never"))
        c = r["crowding"]
        if c:
            L.append("- stairs: busiest segment %d group(s) per wave (limit %d), %d wait(s)"
                     % (c["max_load"], c["capacity"], c["waits"]))
        L.append("")
    Path(path).write_text("\n".join(L))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("only", nargs="*", help="file-name prefixes to run (default: all)")
    ap.add_argument("--no-report", action="store_true")
    a = ap.parse_args()
    files = sorted(p for p in SCENARIOS.glob("*.json") if not a.only or any(p.name.startswith(o) for o in a.only))
    if not files:
        print("no scenarios matched", file=sys.stderr)
        return 2
    b = graph.Building()
    out_dir = graph.ROOT / "runs"
    results = []
    for p in files:
        print("running %s ..." % p.stem, flush=True)
        r = run_one(p, b, out_dir)
        results.append(r)
        print("  %s  (%.0fs)%s" % ("PASS" if not r["failures"] else "FAIL", r["seconds"],
                                   "".join("\n    - " + f for f in r["failures"])), flush=True)
    ok = sum(1 for r in results if not r["failures"])
    print("\n%d/%d scenarios pass" % (ok, len(results)))
    if not a.no_report and not a.only:
        write_report(results)
        print("wrote", REPORT)
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
