"""Plan many groups with stair crowding, one group at a time (prioritized planning).

Searching all groups at once does not scale: groups that wait for stair slots can swap places in
huge numbers of equivalent ways, and the search runs out of time or memory at about six competing
groups. Planning one group at a time is fast (a few seconds each) and still respects the limit:

  1. plan group 1 alone with every stair slot free,
  2. mark the slots its plan used, then plan group 2 with the rest, and so on,
  3. join the plans. The joined plan is valid for the full problem because each action touches
     only its own group and its own slots. run.py then checks it with VAL.

Groups are planned in the order they appear in the scenario, so earlier groups get the best
slots. The result is valid but not guaranteed to be globally optimal.
"""
import sys
from pathlib import Path

import generate_problem
import planner


def solve_partial(b, scn, rule_result, domain, workdir, search=planner.OPTIMAL, timeout=120, verbose=False):
    """Like solve(), but a group with no plan is skipped instead of failing everything.

    Returns (plan, total_cost, stuck_ids). Stuck groups use no slots, so the plan for the others
    is still valid for a problem that contains only them (give the crowding config an explicit
    "waves" so the slot names do not change when a group drops out).
    """
    groups = scn["groups"]
    cap, n_waves = generate_problem.crowding_config(b, scn, groups)
    workdir = Path(workdir)
    plan, total, used, stuck = [], 0, set(), []
    if rule_result.shaking:
        # the shaking is global: pay for it once, then plan every group after it has stopped
        plan.append("(wait-for-shaking-to-stop)")
        total += 1
    for i, g in enumerate(groups, 1):
        sub = dict(scn, groups=[g], crowding={"stair_capacity": cap, "waves": n_waves})
        path = workdir / ("sub_%s.pddl" % g["id"])
        path.write_text(generate_problem.build_problem(b, sub, rule_result, used_slots=used, shaking=False))
        if verbose:
            print("  planning group %s (%d/%d)..." % (g["id"], i, len(groups)), file=sys.stderr, flush=True)
        result = planner.solve(domain, path, search, timeout)
        if result is None:
            stuck.append(g["id"])
            continue
        actions, cost = result
        plan += actions
        total += cost
        # the slot is the last argument of descend-stairs-crowded
        used |= {a.strip("()").split()[-1] for a in actions if a.startswith("(descend-stairs-crowded")}
    return plan, total, stuck


def solve(b, scn, rule_result, domain, workdir, search=planner.OPTIMAL, timeout=120, verbose=False):
    """Return (actions, cost) for the whole scenario, or None if some group has no plan."""
    plan, total, stuck = solve_partial(b, scn, rule_result, domain, workdir, search, timeout, verbose)
    return None if stuck else (plan, total)
