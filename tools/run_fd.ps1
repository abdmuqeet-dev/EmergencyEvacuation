# Run Fast Downward (bundled in the up-fast-downward wheel) on a domain + problem.
# Usage: .\tools\run_fd.ps1 pddl\toy_domain.pddl pddl\problems\toy_problem.pddl [plan_file]
param([string]$Domain, [string]$Problem, [string]$PlanFile = "sas_plan")
$root = Split-Path -Parent $PSScriptRoot
$fd = Join-Path $root ".venv\Lib\site-packages\up_fast_downward\downward\fast-downward.py"
& (Join-Path $root ".venv\Scripts\python.exe") $fd --plan-file $PlanFile --build release $Domain $Problem --search "astar(blind())"
