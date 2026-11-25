"""Independent check of stair crowding in a finished plan.

This does not read the slot objects. It replays the plan with the same time model the domain
uses: every group starts in wave 0, and each stair descent or wait-a-wave moves that group one
wave on. For every (stair segment, wave) it counts how many groups cross, so it also works on
plans made without crowding, where it shows what the limit would have been.
"""
from collections import Counter


def stair_loads(plan):
    """Return Counter {(upper, lower, wave): groups crossing} for descents in the plan."""
    wave = Counter()
    loads = Counter()
    for act in plan:
        name, *args = act.strip("()").split()
        if name in ("descend-stairs", "descend-stairs-crowded"):
            g, upper, lower = args[0], args[1], args[2]
            loads[(upper, lower, wave[g])] += 1
            wave[g] += 1
        elif name == "wait-a-wave":
            wave[args[0]] += 1
    return loads


def check(plan, capacity):
    """Return (max_load, violations) where violations lists (upper, lower, wave, load) over capacity."""
    loads = stair_loads(plan)
    worst = max(loads.values(), default=0)
    bad = sorted((u, l, w, n) for (u, l, w), n in loads.items() if n > capacity)
    return worst, bad


def waits(plan):
    return sum(1 for a in plan if a.startswith("(wait-a-wave"))
