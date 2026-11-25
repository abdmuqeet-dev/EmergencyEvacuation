# Phase 0 done-check: solve the toy problem with Fast Downward, then validate the plan with VAL.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
& "$PSScriptRoot\run_fd.ps1" pddl\toy_domain.pddl pddl\problems\toy_problem.pddl pddl\problems\toy_problem.plan | Select-Object -Last 3
& "$root\tools\bin\validate.exe" pddl\toy_domain.pddl pddl\problems\toy_problem.pddl pddl\problems\toy_problem.plan | Select-String "Plan valid|Plan failed"
