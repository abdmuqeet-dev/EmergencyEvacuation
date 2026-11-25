# EvacPlan-CSUF

An emergency evacuation planner for the Education Classroom building at CSUF (7 levels: Lower, 1st-6th).
A classical planner (Fast Downward, PDDL) chooses routes for groups of people. An independent validator
(VAL) checks every plan. A Streamlit app lets you build a scenario by clicking the floor map, then step
through the evacuation, block a stair or corridor mid-run, and watch the affected groups re-plan.

Team: Abdul Muqeet Ahmed, Ammar Mohiuddin, Siddhi Mane.

## What it does

- **Emergencies:** fire (primary), earthquake (wait for the shaking to stop, avoid glass) and hazmat
  (shelter in place when no exit is safe).
- **Planning:** one group per room or zone. Groups walk, use stairs, use elevators only when responders
  authorise them, leave the building, or shelter in place and notify police when no route exists.
- **Crowding:** each stair segment carries at most K groups per wave. Groups wait a wave or take the
  other stair.
- **Re-planning:** the simulation is stepped. Block or unblock places between steps and the affected groups
  re-plan from where they stand. Every re-plan is VAL-checked.
- **UI:** set up the scenario by clicking the map (add groups, set the hazard, block places, remove), then
  Next step / Play / Run to end, timeline replay, a before/after re-route view, a whole-building overview
  and a presenter mode for a projector.

## Setup (Windows)

The project runs natively on Windows. Python 3.14 is used via `py`; `python` on this machine is the Windows
Store shortcut.

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Fast Downward comes from the `up-fast-downward` wheel, which bundles `downward.exe`. VAL has no release
binaries, so it is built from source:

1. Install the Visual Studio "Desktop development with C++" workload.
2. Clone KCL-Planning/VAL into `third_party\VAL` (gitignored).
3. Run `tools\build_val.bat`, then copy `third_party\VAL\build\bin\Validate2.exe` to `tools\bin\validate.exe`
   (also gitignored). The paths in `build_val.bat` are specific to this machine; edit them for yours.

Check the toolchain: `tools\check_toy.ps1` solves a toy problem with Fast Downward and validates the plan with VAL.

## Run it

Start the app:

```powershell
.venv\Scripts\streamlit run src\app.py
```

1. Pick a preset scenario in the sidebar, or choose "(start blank)".
2. Adjust it. Choose a tool above the map (Add a group, Set hazard, Block a place, Remove) and click places
   on the floor map. The sidebar controls (emergency type, elevators, crowding limit, groups) still work.
3. Press **Start**. Step or play the evacuation.
4. Click places on the map, or choose them by name, and press **Block** / **Unblock**. Drag the timeline
   to replay an earlier moment.

Plan a single scenario from the command line:

```powershell
.venv\Scripts\python src\run.py tests\scenarios\s1_fire_floor4_near_stair5.json
```

This writes `problem.pddl` and `plan.txt` to `runs\<scenario name>\`, validates the plan with VAL and prints
it with room names.

## Tests and results

```powershell
.venv\Scripts\python src\suite.py                         # all scenarios; rewrites docs\RESULTS.md
.venv\Scripts\python -m unittest tests.test_phase7 -v     # UI tests (about 2 minutes); also test_phase2 .. test_phase6
.venv\Scripts\python tools\check_costs.py                 # checks evacuation costs stay below the shelter costs
```

The scenario suite runs every file in `tests\scenarios\` against its `expect` block. A plan that VAL
rejects is a hard failure. Latest results: [docs/RESULTS.md](docs/RESULTS.md) (11 of 11 scenarios pass).
Rerun `tools\check_costs.py` after changing `data\building.json` or the action costs.

## Repository layout

| Path | Contents |
|---|---|
| `src/` | Graph loader, rule layer, problem generator, planner wrapper, crowding, stepped simulation, schematic layout and map drawing, Streamlit app |
| `pddl/` | `domain.pddl`, hand-written problems, the toy domain |
| `data/building.json` | The hand-built building graph: all 7 levels, rooms, stairs, elevators, exits |
| `tests/` | Per-phase tests and `scenarios/` (JSON scenario files with expectations) |
| `tools/` | Toolchain scripts (VAL build, Fast Downward runner) and checks |
| `docs/` | `PROJECT_PLAN.md` (plan, assumptions, progress log), `RESULTS.md`, floor-plan maps |
| `llm/` | Reserved for the LLM layer (not started) |

## Status

Phases 0-7 are done: setup, building graph, PDDL domain, problem generator and rule layer, crowding,
validation and scenario suite, re-planning, and the Streamlit UI. Phase 8 (LLM announcements and an
LLM-plan-versus-VAL comparison) and Phase 9 (report, demo script) are not started. See
[docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) for details and the progress log.

## Known limits and placeholders

- The assembly area (A1), stair capacities (A4) and group sizes (A5) are placeholders until real values are supplied.
- `building.json` was read from posted evacuation maps. It still needs on-site checks: the exterior stairs,
  the unnumbered 2nd-floor stair, the east edge of the 1st floor and the Lower-floor "east" arrow.
- The glass location in the earthquake scenario is illustrative. Glass corridors are not on the maps.
- Plans with many groups can take 30 seconds or more (the 12-group crowding scenario takes about 36 s).
