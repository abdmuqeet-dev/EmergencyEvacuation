"""Check a plan with VAL (tools/bin/validate.exe)."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAL = ROOT / "tools" / "bin" / "validate.exe"


def validate(domain, problem, plan_file):
    """Return (ok, output). ok is True only if VAL reports 'Plan valid'."""
    r = subprocess.run([str(VAL), "-v", str(domain), str(problem), str(plan_file)],
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    return ("Plan valid" in out and "Plan failed" not in out), out
