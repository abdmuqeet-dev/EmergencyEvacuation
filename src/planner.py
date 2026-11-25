"""Run Fast Downward on a PDDL domain + problem and return the plan."""
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
FD = ROOT / ".venv" / "Lib" / "site-packages" / "up_fast_downward" / "downward" / "fast-downward.py"
UNSOLVABLE = (11, 12)  # Fast Downward exit codes: 11 = proven unsolvable by the heuristic, 12 = search space exhausted
OPTIMAL = "astar(lmcut())"      # exact, fine for a few groups
FAST = "lama-first"             # greedy but ignores action costs on its first pass: it may shelter
                                # groups that could walk out. Not used by default.
ALIAS_PREFIXES = ("lama", "seq-")


class PlannerError(RuntimeError):
    pass


def solve(domain, problem, search=OPTIMAL, timeout=120):
    """Return (actions, cost) or None if the problem is unsolvable.

    actions is a list of strings such as "(move g1 a b)". `search` is either a Fast Downward
    search expression ("astar(lmcut())") or an alias name ("lama-first"). Optimal search gives
    deterministic shortest plans; it is fast for one group but not for many competing groups
    (see prioritized.py).
    """
    with tempfile.TemporaryDirectory() as tmp:
        plan = Path(tmp) / "plan"
        cmd = [str(VENV_PY), str(FD), "--plan-file", str(plan), "--sas-file", str(Path(tmp) / "out.sas"),
               "--build", "release"]
        files = [str(Path(domain).resolve()), str(Path(problem).resolve())]
        if search.startswith(ALIAS_PREFIXES):
            cmd += ["--alias", search] + files
        else:
            cmd += files + ["--search", search]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=tmp)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # kill the whole tree: the launcher script starts downward.exe as a child
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            proc.communicate()
            raise PlannerError("Fast Downward timed out after %ss with search %r" % (timeout, search))
        if proc.returncode in UNSOLVABLE:
            return None
        if proc.returncode != 0 or not plan.exists():
            raise PlannerError("Fast Downward failed (exit %d):\n%s" % (proc.returncode, stdout[-2000:] + stderr[-2000:]))
        # lama writes the best plan to `plan` (and numbered copies for anytime search)
        text = plan.read_text()
    actions = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith(";")]
    m = re.search(r"; cost = (\d+)", text)
    return actions, int(m.group(1)) if m else None


def write_plan(actions, path):
    Path(path).write_text("\n".join(actions) + "\n")
