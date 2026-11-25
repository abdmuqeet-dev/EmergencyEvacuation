# EvacPlan-CSUF: Project Plan v1 (Education Classroom Building)

Source: `Project_Proposal.pdf` (Downloads) + 7 posted evacuation maps (Lower, 1st-6th floor), saved as `docs/maps/FloorPlans.pdf` (7 pages in floor order: Lower, 1st-6th; photos downscaled, full-resolution originals not stored in the repo).
Team: Abdul Muqeet Ahmed, Ammar Mohiuddin, Siddhi Mane.

## 1. Scope for v1
In scope:
- One building: Education Classroom, 7 levels (Lower, 1-6).
- Emergencies: fire (primary); earthquake and hazmat as rule-layer variants.
- One group per room/zone; some groups mobility-impaired.
- PDDL planning (Fast Downward), VAL validation, re-plan after a blocked corridor/stair.
- Stairwell crowding via slot objects (classical PDDL).
- Streamlit UI: floor-by-floor map + plan view.

Deferred: ENHSP numeric capacity, real occupancy data, vision-LLM map digitization,
LLM announcements, LLM-vs-planner comparison, other buildings (e.g. CS building).

## 2. Building facts read from the maps
| Level | Stairs | Elevators | Exits (green arrows) | Layout |
|---|---|---|---|---|
| Lower | 1,2,3,4,5,6 | 1,2 (+ elev mech room) | 6: west, east, north, 2x south (stairs 4 & 6), SW by elevators | Large irregular, rooms 7-69 |
| 1st | 1,2,3,5 | 1,2 | 4: west, east, north, south by elevators | Rooms 101-199, 130A-K, 194A-I; L/U corridor |
| 2nd | 1 (unnumbered on the map, poster top-right), 2,3,5 | 1,2 | 4: two NW, one at stair 5 (room 204), one at stair 1 (poster top-right) | Large open areas, rooms 201-211, 207A-K |
| 3rd-6th | 2 (NW), 5 (south-center) only | 1,2 (north, beside stair 2) | the stairs themselves | Identical ring-corridor plan on each floor |

- Restrooms: 304/306 (3rd), 404/406 (4th), unisex 504 (5th), all-gender 604A/B (6th).
- 6th-floor legend adds AED and Evacuation Chair symbols (locations not clear on plan).
- Map print dates: 2006, 2013, 2020, 2026.

## 3. Assumptions (replace later)
- A1: Assembly area is a placeholder point outside Lower/1st floor exits. -> real CSUF assembly area
- A2: Stairs 2 and 5 run Lower-6; stair 3 Lower-2; stair 1 Lower-1; stairs 4 and 6 Lower only. -> confirm with Facilities/on site
- A3: Elevator lobby beside stair 2 (floors 2-6) acts as refuge area. -> real area-of-refuge designation
- A4: Fixed small stair capacity (groups per stairwell). -> California Building Code values
- A5: Group sizes synthetic. -> class-schedule enrollment caps
- A6: Layouts consistent across floors despite different print dates. -> Facilities floor plans

## 4. Architecture
Scenario input -> Rule layer (emergency type -> smoke/blocked/elevator-ban facts)
-> Problem generator (+ building graph JSON) -> Fast Downward (domain + problem)
-> VAL (fail: report) -> plan -> UI. Blocked corridor/stair -> update facts -> re-plan.

## 5. Phases
0. Setup: repo, Fast Downward, VAL, Python deps. Done when a toy plan solves and validates. **[DONE 2026-11-24: toy plan solves with Fast Downward and validates with VAL; run `tools\check_toy.ps1`]**
1. Building graph: hand-build `building.json` (3rd-6th template first, then Lower/1st/2nd). Done when every room is reachable and stair links are consistent. **[DRAFT DONE: all 7 floors built and linked; needs on-site verification, see section 11]**
2. PDDL domain: move, descend-stairs, exit-building, shelter-in-place, shelter-and-notify, use-elevator (gated on `directed-by-responders`). Done when it solves 3 hand-written problems. **[DONE 2026-11-24: 4 problems solve and validate; run `tests.test_phase2`]**
3. Problem generator + rule layer (fire, earthquake, hazmat). Done when one command goes scenario -> plan. **[DONE 2026-11-24: `src\run.py <scenario.json>`; scenarios 1-4 and 7 plus baseline and hazmat in `tests/scenarios/`]**
4. Crowding: slot objects per stairwell. Done when no plan exceeds the stair limit. **[DONE 2026-11-24: wave/slot model + prioritized planning; scenario 5 (12 groups) verified]**
5. Validation + tests: VAL on every plan; scenario suite. **[DONE 2026-11-24: `src\suite.py` runs all scenarios against `expect` blocks, VAL failure is a hard failure; results in `docs/RESULTS.md`]**
6. Re-planning: block/unblock, read current group locations, re-run planner. **[DONE 2026-11-24: `src/simulation.py`, stepped simulation; scenarios s6, s6b, s6c]**
7. UI: Streamlit, floor selector, colored routes, block toggles, step list. **[DONE 2026-11-24: `streamlit run src/app.py`; schematic north-up floor maps from the graph]**
8. LLM layer (optional): announcements, then LLM-plan-vs-VAL comparison.
9. Stretch/report/demo: ENHSP if time; report; live demo with a mid-run block.

## 6. Minimum test scenarios
1. Fire on 4th floor near stair 5 -> route to stair 2, no elevators.
2. Stairs 2 and 5 both blocked on 5th floor -> shelter and notify police.
3. Wheelchair user on 6th floor -> shelter-and-notify; no stairs, no elevator.
4. Same, with `directed-by-responders` true -> elevator legal.
5. Many groups on floors 3-6 -> stair limit forces waiting / the other stair.
6. Mid-run blocked corridor on Lower floor -> plan updates.
7. Earthquake -> wait for shaking to stop; glass corridors blocked.

## 7. Suggested team split
- Abdul Muqeet Ahmed: PDDL domain, problem generator, Fast Downward/VAL integration, crowding.
- Ammar Mohiuddin: building graph, rule layer, test scenarios, data collection.
- Siddhi Mane: Streamlit UI, visualization, re-plan controls, then LLM layer.

## 8. Suggested repo layout
```
data/   building.json, groups_sample.json
pddl/   domain.pddl, problems/
src/    graph.py, rules.py, generate_problem.py, planner.py, validate.py, replan.py
ui/     app.py
llm/    announcements.py, llm_vs_planner.py
tests/  scenarios/
docs/   PROJECT_PLAN.md, proposal, maps, report
```

## 9. Risks
- Large 7-level graph slows planning -> corridor-segment nodes, one group per room/zone, abstraction pass.
- Map ambiguity (stairs, 2nd-floor open areas) -> mark uncertain items, verify on site.
- No official assembly area/capacities -> placeholders A1/A4, documented.
- Fast Downward/VAL on Windows -> WSL or Docker, decide in phase 0.
- LLM/ENHSP scope creep -> optional, last.

## 10. Open items
1. Real assembly area and any areas of refuge.
2. ~~WSL, Docker, or native Windows for the planner.~~ Decided: native Windows. Fast Downward ships as a prebuilt wheel (`up-fast-downward`). WSL, Docker and a C++ compiler are not installed on this machine.
3. Project deadline (to add dates).
4. ~~How to get VAL on Windows.~~ Resolved: built from source with the VS C++ toolchain (section 11).
5. On-site checks: exterior stairs 1/2/3, the number of the unnumbered 2nd-floor stair (identified as stair 1 by position) and that stair 1 stops at L2, the east edge of the 1st floor, the Lower-floor "east" arrow. (The upper-floor orientation question is resolved: see Phase 1 details.)

## 11. Status and progress log

### Current status (2026-11-24)
| Phase | Status |
|---|---|
| 0 Setup | Done. Fast Downward and VAL both work on native Windows; toy plan solves and validates. |
| 1 Building graph | Draft complete for L0-L6; reachability checks pass. Needs on-site verification. |
| 2 PDDL domain | Done. `pddl/domain.pddl` solves 4 hand-written problems; VAL accepts every plan. |
| 3 Generator + rule layer | Done. One command goes from scenario JSON to a VAL-validated plan on the real 7-floor graph. |
| 4 Crowding | Done. Stair segments carry at most K groups per wave; checked independently and by VAL. |
| 5 Validation + tests | Done. `src/suite.py` runs all 8 scenarios, checks each against its `expect` block, VAL rejection is a hard failure. 8/8 pass. |
| 6 Re-planning | Done. `src/simulation.py` steps the evacuation and re-plans from where each group stands after a block or unblock; every re-plan is VAL-checked. |
| 7 UI | Done, with a polish pass. `src/app.py` (Streamlit) over `Simulation`: theme and presenter mode, status banner, autoplay, timeline replay, before/after re-route view, whole-building overview, schematic north-up floor maps. Checked with AppTest and a real browser. |
| 8-9 | Not started. |

### Phase 0 details
- Python 3.14 via `py`; `python` on this machine is the Windows Store shortcut, so use `py` or `.venv\Scripts\python.exe`.
- Venv at `.venv/`; dependencies in `requirements.txt`.
- Fast Downward 26.6.0 comes from the `up-fast-downward` wheel (bundles `downward.exe` for Windows). Run it with `tools/run_fd.ps1`.
- Toy test: `pddl/toy_domain.pddl` + `pddl/problems/toy_problem.pddl` solve with A* in 4 steps. The plan is saved at `pddl/problems/toy_problem.plan`.
- **VAL:** KCL-Planning/VAL has no release binaries and is not on PyPI, so it is built from source. This needed the Visual Studio "Desktop development with C++" workload (installed by the user from the VS Installer; a scripted install attempt exited immediately).
  - Source is cloned to `third_party/VAL` (gitignored). Build with `tools\build_val.bat`, then copy `third_party\VAL\build\bin\Validate2.exe` to `tools\bin\validate.exe` (also gitignored).
  - Build workarounds for MSVC 2026 (no VAL source edits except one CMake line):
    - `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`, because VAL's CMake minimum is too old for current CMake.
    - `/FIfunctional /D_HAS_AUTO_PTR_ETC=1`, because VAL uses `std::unary_function` without including `<functional>`.
    - `/DYY_NO_UNISTD_H`, because the parser includes `unistd.h`.
    - `set (VERIFY_SYMBOLS True)` in VAL's `CMakeLists.txt`. This builds the standalone `Validate2` executable; the default DLL build fails to link the tools on Windows because symbols are not exported.
  - Only `Validate2` is built. The other VAL tools are not needed.
- **Verification:** `tools\check_toy.ps1` runs Fast Downward then VAL. The toy plan is reported valid (4 steps). A deliberately broken plan is reported as failed, so the validator does reject bad plans.

### Phase 1 details (`data/building.json`)
- 473 nodes, 512 edges across floors L0 (Lower) to L6. Node types: corridor, room, restroom, zone (L2 only), stair, elevator, exit, assembly.
- ID scheme: corridor/room/restroom/zone are `<floor>_<local>` (e.g. `L3_c_s_stair`, `L1_r109`); stairs, elevators and exits are `<kind>_<n>_<floor>` (e.g. `stair_5_L3`) so the same stair links across floors.
- Edge kinds: corridor, door, open, exit, outside, stairs, elevator.
- Floors L3-L5 use one 13-node ring-corridor template. L6 is the same ring, but room 606 replaces the north corridor. L2 uses coarse open-area zones. L0 and L1 are hand-modelled from the irregular corridors.
- Stair links: stair 2 and 5 L0-L6, stair 3 L0-L2, stair 1 L0-L2 (the unnumbered 2nd-floor stair is stair 1 by position; its L1-L2 link stays uncertain), stairs 4 and 6 Lower only (assumption A2). Elevators 1 and 2 L0-L6.
- **Orientation (resolved 2026-11-24):** the L0 and L1 posters have north at the top of the page. The L2-L6 posters have north pointing RIGHT (each poster's compass), so they are drawn rotated 90 degrees. They are not flipped: elevators and stair 2 sit in the compass south-west corner on every floor, and stairs 3 and 5 line up between L1 and L2. L1-L2 links for stairs 2, 3 and 5 are no longer flagged uncertain.
- **Naming (updated 2026-11-24):** node LABELS on every floor now use COMPASS directions (e.g. `L3_c_nw_lobby` is labelled "SW elevator lobby (stair 2)", `L3_c_n_e` is "West corridor, north end", `stair_5_L3` is "Stair 5 (east-center)"). Node IDS on L2-L6 keep the poster's PAGE directions (`nw`, `ne`, `n`, `e`, `s`, `w`) so scenarios and tests keep working. Page-to-compass on L2-L6: page top = west, page right = north, page bottom = east, page left = south, so a page-frame id suffix `nw` is compass SW, `ne` is NW, `se` is NE, `sw` is SE. For Phase 7: rotate each L2-L6 poster 90 degrees counter-clockwise to draw north-up; show labels, never ids, to users. `meta.conventions.poster_frame` and `meta.floor_frames` in `building.json` record this.
- Exit arrows on L2-L6 are stair entries, so real exits exist only on L0 and L1.
- Everything marked `uncertain: true` should be verified on site. Room-to-corridor attachments are inferred from proximity because the maps do not draw doors.
- Known uncertainties: see `meta.open_questions` in the JSON and item 5 of section 10.

### Phase 2 details (`pddl/domain.pddl`)
- **Actions:** `move`, `descend-stairs`, `use-elevator`, `exit-building`, `shelter-in-place`, `shelter-and-notify`.
- **Goal predicate:** `(safe ?g)`. It is set by `exit-building`, `shelter-in-place` and `shelter-and-notify`.
- **Gating rules in the domain:**
  - `descend-stairs` requires the group not be `mobility-impaired`.
  - `use-elevator` requires `directed-by-responders` (legal for impaired groups once true).
  - `shelter-in-place` requires `shelter-in-place-ok`. The rule layer (Phase 3) sets it only for emergencies that allow it, such as hazmat.
  - `shelter-and-notify` requires the location be a `refuge` (assumption A3: elevator lobbies).
  - All movement into a `blocked` location is illegal.
- **Static facts the generator must emit from `building.json`:** `connected` (both directions), `stairs-down` (upper stair node to the same stair one floor below), `elevator-link` (both directions between adjacent floors), `exit`, `refuge`.
- **Costs:** move 1, elevator 1, exit 1, stairs 2, wait-for-shaking 1, shelter-in-place 90, shelter-and-notify 100. (Phase 2 first used 150 for shelter-in-place; Phase 3 lowered it to 90 so a hazmat group stays put instead of walking to a refuge.) Shelter costs exceed any route in the building, so groups evacuate whenever a route exists and shelter only when they cannot. `py tools\check_costs.py` checks this on the real graph: worst evacuation cost is 19 (walking) and 15 (with elevators), all 333 rooms and restrooms reach an exit. Rerun it after changing `building.json` or the costs.
- **Tests:** `tests/test_phase2.py` runs four problems in `pddl/problems/` (written by `tools/gen_phase2_problems.py` on an abbreviated 4-floor mini-building): p1 = scenario 1, p2 = scenario 3, p3 = scenario 4, p4 = scenario 2. Each checks the plan's shape and that VAL accepts it. Run: `.venv\Scripts\python -m unittest tests.test_phase2 -v`.
- **Tooling:** `src/planner.py` (Fast Downward wrapper, `astar(lmcut())` by default) and `src/validate.py` (VAL wrapper).
- **Notes:**
  - Fast Downward lowercases all names in plans, so compare plans in lowercase.
  - Upward stairs are not modeled; groups only descend.
  - Phase 3 added `(shaking)` and `wait-for-shaking-to-stop` to the domain. While shaking, `move`, `descend-stairs`, `use-elevator` and `exit-building` are illegal; the shelter actions are not.
  - The mini-building problems use a 7-node ring on floor 4 and shortened floors 3, 2, 1; they do not read `building.json`.

### Phase 3 details (generator + rule layer)
- **One command:** `.venv\Scripts\python src\run.py tests\scenarios\<scenario>.json`. It writes `runs/<name>/problem.pddl` and `plan.txt` (gitignored), runs Fast Downward, validates with VAL and prints the plan with room names. Options: `--out DIR`, `--search "lama-first"`, `--no-validate`. About 4 seconds per single-group scenario with the default `astar(lmcut())`.
- **Code:** `src/graph.py` (loads `building.json`, derives the domain facts), `src/rules.py` (emergency type to blocked/elevator/shelter/shaking facts), `src/generate_problem.py` (PDDL text), `src/run.py` (CLI and `run_scenario()` for the UI and re-planner).
- **Scenario format** (JSON):
  - `name`, `emergency` (`fire` | `earthquake` | `hazmat`), `groups` (`id`, `location`, `mobility_impaired`, `size`).
  - Optional: `hazard_locations`, `hazard_radius` (same-floor steps), `block_stairwell` (block that stair on every floor), `blocked` (explicit, used for re-planning), `glass_nodes`, `outdoor_release`, `directed_by_responders`, `trust_uncertain_exits`, `refuges`.
- **Rules:**
  - **Fire:** blocks the hazard region; elevators banned unless `directed_by_responders`.
  - **Earthquake:** sets `shaking`, blocks glass nodes (any node with `"glass": true` in `building.json`, plus `glass_nodes`); elevators banned unless directed.
  - **Hazmat:** `shelter-in-place` allowed; an indoor release blocks the hazard region; an outdoor release blocks every exit, so groups shelter.
- **Decisions made:**
  - Exits flagged `uncertain` (the Lower-floor "east" arrow) are not treated as exits unless `trust_uncertain_exits` is true.
  - Refuges are derived as the elevator lobby on floors 2 and up (assumption A3): `L2_z_nw`, `L3`-`L6` `_c_nw_lobby`.
  - A group cannot start at an exit node.
- **Scenarios in `tests/scenarios/`:** s0 baseline, s1 (section 6 scenario 1), s2 (2), s3 (3), s4 (4), s7 (7), s8 hazmat outdoor release. Scenario 5 (crowding) needs Phase 4 and scenario 6 (mid-run block) needs Phase 6.
- **Tests:** `.venv\Scripts\python -m unittest tests.test_phase2 tests.test_phase3 -v` (18 tests, about 45 seconds). They check plan shape and VAL acceptance, the rule layer and input validation.
- **Known gaps:**
  - No real glass-corridor data exists; `L3_c_nw_lobby` in s7 is illustrative.
  - Hazmat is two coarse cases; real guidance (e.g. which exits are upwind) is not modeled.
  - Many groups at once use the same optimal search and will get slow; Phase 4 will need `lama-first` or a limit, to be decided with real timings.

### Phase 4 details (stair crowding)
- **Model (opt-in per scenario with `"crowding": {"stair_capacity": K, "waves": N}`):** time is a chain of waves `w0..wN-1`. Each stair segment (one stair, one floor to the next) has K slot objects per wave. `descend-stairs-crowded` needs a free slot in the group's current wave and moves the group to the next wave; `wait-a-wave` lets a wave pass (cost 2, same as one descent). Without the `crowding` key the plain `descend-stairs` is used and nothing changes from Phase 3. K defaults to 3 (placeholder, assumption A4); N defaults to tallest descent + ceil(groups / K) + 3.
- **Why waves:** classical PDDL has no time, so "at most K groups on the stair at once" cannot be said directly. With only a sequential plan and summed costs, the planner could send groups through one at a time for free. Waves make waiting cost something, so the planner weighs waiting a wave against using the other stair.
- **Scaling problem and fix:** searching all groups together did not scale. With 6 conflicting groups the optimal search timed out; at 9 groups even greedy search ran out of time (one earlier run used 5.6 GB). `lama-first` was also unsafe: it ignores action costs on its first pass, so it sheltered every group (cost 1222). Fix: `src/prioritized.py` plans one group at a time, marks the slots each plan used, plans the next group with the remaining slots, and joins the plans; VAL then checks the joined plan against the full problem. About 3 seconds per group (12 groups: about 38 seconds). The result is valid but not guaranteed globally optimal, and earlier groups in the scenario file get the best slots.
- **Checks:** `src/crowding.py` replays a plan by itself (it ignores slot names) and counts groups per (segment, wave); `run.py` prints the busiest segment and the wait count. Scenario 5 (`tests/scenarios/s5_crowding_floors3to6.json`: 12 groups on floors 3-6, limit 2): plan valid, busiest segment 2 groups, 12 waits, everyone exits, cost 178.
- **Tests:** `.venv\Scripts\python -m unittest tests.test_phase4 -v` (10 tests, about 2 minutes). One test plans the same groups with no limit and shows a stair would carry more than K, then shows the limit removes that. Others cover capacity 1, a generous capacity (no waits), earthquake plus crowding (a single wait-for-shaking), and slots never reused.
- **Planner wrapper:** `src/planner.py` now kills the whole process tree on timeout (default 120 s) and accepts alias searches. An earlier version killed only the launcher and left `downward.exe` running.
- **Limits of the model (be honest in the report):**
  - Walking does not advance the wave, so groups are assumed to reach the stairs together. Far groups are not delayed relative to near ones.
  - Capacity counts groups, not people. Group sizes (`size`) are ignored until real data exists (A4, A5).
  - Only stairs are limited. Elevators, corridors and exits have no capacity.
  - Mobility-impaired groups never use stairs, so they are unaffected.
  - Prioritized planning order is the scenario order; a different order can change which groups wait.

### Phase 5 details (validation + scenario suite)
- **Suite runner:** `.venv\Scripts\python src\suite.py` runs every file in `tests/scenarios/` (about 1 minute, mostly scenario 5), prints PASS/FAIL per scenario and writes `docs/RESULTS.md`. Exit code is 0 only if all pass. `suite.py s1 s5` runs a subset (and skips the report).
- **`expect` block in each scenario file:** `outcome` (`exit`, `shelter-and-notify`, `shelter-in-place` or `no-plan`: every group must end that way), plus optional `uses`, `avoids` (action names or node ids, case-insensitive), `first_action`, `max_cost`, `min_waits`. A scenario with no `expect` block fails.
- **Hard failure on VAL:** `run.run_scenario(..., strict=True)` raises `PlanInvalid` if VAL rejects a plan; the suite treats that as a failure. A missing `validate.exe` is an error, never a silent pass. The CLI (`run.py`) already exits 1 on an invalid plan.
- **What each scenario checks:** s0 walks out cheaply; s1 uses stair 2 and avoids stair 5 and elevators; s2 shelters and notifies (both stairs blocked); s3 shelters with no stairs or elevator; s4 uses the elevator once responders direct it; s5 respects the stair limit, waits, and everyone exits; s7 waits for the shaking first and avoids glass; s8 shelters in place with no exit.
- **Result:** 8 of 8 pass (see `docs/RESULTS.md`).
- **Tests:** `.venv\Scripts\python -m unittest tests.test_phase5 -v` (15 tests, about 20 s) cover the checker catching each kind of wrong plan, a rejected plan failing the suite, a wrong expectation being reported on a real run, and the report. All 43 tests across phases 2-5 pass (about 3 minutes).
- **Not covered yet:** scenario 6 (mid-run block) arrives with Phase 6. Expectations check plan shape, not that a route is the shortest possible; optimality comes from the planner.

### Phase 6 details (stepped simulation + re-planning)
- **Code:** `src/simulation.py`. `Simulation(scenario)` plans at once (VAL-checked), then `step()` advances, `block(nodes)` / `unblock(nodes)` / `update(block=, unblock=)` change the situation and re-plan whoever is affected, `snapshot()` gives the state for the UI, `run_script()` runs a scenario's scripted events, `violations(sim)` independently checks the action log. CLI: `.venv\Scripts\python src\simulation.py tests\scenarios\s6_midrun_block_lower.json`.
- **What a step is:**
  - Without crowding, one action per group (one move, one stair flight, the exit...), so groups walk node by node and a block can land mid-route.
  - With crowding, one leg (walking plus the stair flight or wait that ends it), because the crowding model counts stair waves, not walking time. Override with `unit="action"|"leg"`.
  - An earthquake adds a first step where everyone waits for the shaking to stop.
- **Group states:** `walking`, `out`, `sheltered` (with kind), `stuck` (no plan exists). A stair flight is one action, so a group is always at a node; a block takes effect before the next step. A group standing in a place that becomes blocked can leave it but nobody can enter it.
- **Who re-plans:**
  - Block, no crowding: only groups whose remaining route touches the newly blocked places, plus sheltering groups whose shelter just became blocked.
  - Block, crowding: every walking group together (they share stair slots); the wave clock restarts at the re-plan.
  - Unblock: every group that is not out, so sheltering and stuck groups can start walking and others can take a shorter way. A sheltering group stays put if staying is still the best plan.
  - The user can only unblock what the user blocked; places blocked by the emergency itself (fire region, glass, outdoor-release exits) stay blocked.
- **Safety nets:** each re-plan is validated by VAL on the joined plan (a rejection raises `PlanInvalid`); a group with no plan is marked stuck while the others carry on; the independent `violations()` check proves no action ever entered a place that was blocked at that moment.
- **Scenarios (in the suite, `script` key):** s6 (Lower floor: corridor to the north exit blocked after step 2, the group turns back for the south exit), s6b (both stairs blocked, the group shelters; stair 2 reopens and it walks out), s6c (4 groups, stair limit 2, stair 2 blocked on level 2 after the first wave: groups below it carry on, groups above it re-plan via stair 5; wave loads stay within the limit).
- **Planner fix found on the way:** Fast Downward exits 11 (not only 12) when a task is provably unsolvable; `src/planner.py` now treats both as "no plan". Before this, a stuck group would have crashed the run.
- **Tests:** `.venv\Scripts\python -m unittest tests.test_phase6 -v` (22 tests, about 3 minutes). All 65 tests across phases 2-6 pass (about 6 minutes); the suite is 11 of 11.
- **Limits (be honest in the report):**
  - A re-plan restarts the crowding wave clock, and legs stand in for waves, so crowded timing is approximate.
  - Re-planning has no memory: a group may walk back the way it came (as in s6) because nothing models the time already spent.
  - Fire does not spread on its own; blocks are what the user or script adds.
  - A crowded re-plan of many groups takes as long as the first plan (s5 size: about 40 seconds), so the UI needs a progress indicator.

### Phase 7 details (Streamlit UI)
- **Run it:** `.venv\Scripts\streamlit run src\app.py` from the project root. The sidebar picks a scenario (all of `tests/scenarios/` plus a blank one), the emergency, hazard places, responder-authorised elevators, a stair limit, and the groups (floor, room, wheelchair, people). Start plans the routes.
- **The screen (polish pass, 2026-11-24):**
  - **Status banner** across the top: "2 of 5 out of the building", the current step, chips for evacuating / sheltering / stuck / re-plans / "plans verified by VAL". It turns green when everyone is out and red if a group is stuck or a plan was rejected.
  - **Controls:** Next step, Play / Pause with a speed (0.5 to 4 steps per second), Run to end, Restart.
  - **Timeline:** drag back to any earlier step or any block / unblock moment; the banner, map and overview show that moment with a yellow "Replay" strip, and the controls lock until Back to live. New steps are followed automatically while watching live.
  - **Route change explained:** after Block or Unblock a card under the banner says who re-planned, how long it took, and the effect ("g1 is re-routed: 4 -> 6 actions left (2 actions longer)", "g2 can leave its shelter now", "g3 has no safe way down any more and will shelter"). On the map the old route stays as a grey dotted line under the new dashed one. The card clears at the next step.
  - **Whole-building overview** (right column): all seven levels stacked with the stair shafts and elevators, blocked stairs marked on their level, groups on their level or in the stair shaft they are in, finished groups in the "Outside" strip. Click a level to open its map.
  - **Floor map** (left): the schematic described below, with a floor selector that shows how many groups are on each floor.
  - **Presenter mode** (switch at the top right): hides the sidebar and enlarges text and the map for a projector; groups and log move into a collapsed panel.
  - **Theme:** `.streamlit/config.toml` (CSUF-style navy and orange accents) plus banner styling in `src/viewmodel.py`.
- **Changing the situation:** click a place on the map (or choose it by name) so it shows in the selection box, then Block or Unblock. Only the user's own blocks can be unblocked. Block / Unblock lock while replaying.
- **Code:** `src/app.py` (the page), `src/viewmodel.py` (banner numbers, sentences, CSS, no Streamlit needed), `src/mapview.py` (floor map and overview figures), `src/layout.py` (positions), `Simulation.frames` / `ghost` / `trail` / `route` / event `changes` (replay and before/after data), `simulation.describe` (plain English).
- **The floor map is a schematic drawn from the graph** (`src/layout.py`, `src/mapview.py`), north up on every floor:
  - Corridors, zones, stairs, elevators and exits have hand-placed positions read off the posters (L2-L6 posters are rotated, so their pixels are turned into compass coordinates). Rooms are seated automatically in rows along the corridor they attach to, nearest first, so no two rooms overlap and none covers a stair or exit.
  - Drawn: groups as coloured circles (diamond = out, square = sheltering, x = stuck), dashed planned route, faint trail of where the group has been, blocked places in red, picked places ringed. Hover shows the full name.
  - Not drawn: the assembly point (the exits simply lead outside). The layout is deterministic.
- **Checks:**
  - `tests/test_phase7.py` (37 tests, about 1 minute): layout (positions, no overlaps, compass directions on every floor, stairs line up between floors, rooms near their corridor), floor map drawing, overview drawing, frames and ghost routes, banner numbers and sentences, theme file, and the app driven with Streamlit's AppTest (start, step, run to end, Play to the end, timeline replay and Back to live, block and re-plan with the explanation, presenter mode, add / remove group, blank scenario).
  - `tools/e2e_check.py` drives the real app in Chrome with Playwright: Play and Pause, drag the timeline back and return, restart, click levels in the overview, click a corridor on the map, Block, check the re-route card, Run to end, switch to presenter mode. It found two real bugs that AppTest could not: the selection box being reset by the browser, and the timeline falling out of "live" while autoplay was running (fixed by letting only the user's own drag change that state).
  - `tools/preview_layout.py <floor>` renders a floor to `runs/layout_<floor>.png` for layout work.
- **Limits:**
  - Room positions are schematic, not the real room shapes; rooms may sit on the other side of the corridor from the real plan.
  - Picking by click replaces the browser selection each time; the selection box is the reliable way to remove a pick.
  - Re-planning blocks the page while it runs (a few seconds for one group, about 40 s for a dozen crowded groups); a spinner shows. Autoplay pauses itself when you block or unblock.
  - One session keeps its simulation in memory; refreshing the page restarts. The overview places groups by their position on their own level, not to scale.
  - Group size, stair capacity and the assembly area are still placeholders (A1, A4, A5).

### Log
- 2026-11-24: Saved the 7 evacuation map photos as one merged PDF, `docs/maps/FloorPlans.pdf`. The user's own FloorPlans.pdf showed the same seven posters, so it added no new building information.
- 2026-11-24: Read the plan and all 7 evacuation maps; cross-checked against section 2 (matches, except 6th floor center differs, upper floors appear flipped N-S, 2nd-floor arrows lead to stairs).
- 2026-11-24: Built and linked the graph for L0-L6; moved `docs/` and `data/` into the main project folder.
- 2026-11-24: Phase 0: created repo layout, venv, Fast Downward via wheel, toy problem solved. VAL was blocked (no binaries, no compiler).
- 2026-11-24: Installed VS C++ workload, built VAL (`Validate2`), validated the toy plan, confirmed a bad plan is rejected. Phase 0 complete.
- 2026-11-24: Phase 2: wrote the domain and 4 hand-written problems (scenarios 1-4 from section 6); all solve and validate. Fixed two test bugs found on the way (Fast Downward lowercases names; the substring "elev" matched the node `L1_c_elev`).
- 2026-11-24: Phase 3: added graph loader, rule layer, problem generator and `src/run.py`. Domain gained `shaking` / `wait-for-shaking-to-stop`; shelter-in-place cost lowered 150 to 90. 7 scenarios plan and validate on the real graph; `tools/check_costs.py` confirms evacuation costs stay far below the shelter costs. 18 tests pass.
- 2026-11-24: Phase 4: added the wave/slot crowding model, prioritized per-group planning, an independent crowding checker, and scenario 5. Found and fixed a planner-wrapper bug (timeout left `downward.exe` running) and avoided `lama-first` (ignores costs). 10 new tests pass; the 18 earlier tests still pass.
- 2026-11-24: Phase 5: added `src/suite.py`, `expect` blocks on all 8 scenarios, `PlanInvalid` hard failure in `run.py`, `docs/RESULTS.md`. 8/8 scenarios pass; 15 new tests, 43 total pass.
- 2026-11-24: Read the 2nd-floor poster against the 1st and 3rd. Resolved the "flipped N-S" worry: L2-L6 posters are rotated 90 degrees (north points right). Cleared the L1-L2 uncertain flags for stairs 2, 3, 5. The unnumbered L2 stair is stair 1 by position; renamed `stair_NE_L2` to `stair_1_L2` and linked it to L1 (uncertain). Recorded page-frame naming for the UI. Reachability still 100%, 8/8 scenarios pass.
- 2026-11-24: Relabelled 69 upper-floor nodes (L2-L6 corridors, lobbies, stairs, L2 zones, room 606 note) to compass directions; ids unchanged.
- 2026-11-24: Phase 6: added `src/simulation.py` (stepped simulation, block/unblock, re-planning with VAL on every re-plan), `solve_partial` in `prioritized.py`, scripted scenarios s6, s6b, s6c and suite support for them. Fixed the planner treating exit code 11 as a crash. 22 new tests; 65 total pass, suite 11/11.
- 2026-11-24: Phase 7: added `src/layout.py`, `src/mapview.py`, `src/app.py`, `Simulation.trail/route/start`, `simulation.describe`, tools `preview_layout.py` and `e2e_check.py`, 21 tests. Checked in a real browser; fixed the selection-box bug it exposed. requirements.txt now lists streamlit and plotly.
- 2026-11-24: UI polish pass (Phase 7): status banner, theme and presenter mode, autoplay, timeline replay, before/after re-route card and grey ghost route, whole-building overview. Added `src/viewmodel.py`, `Simulation.frames/ghost`, `mapview.building_figure`. 37 UI tests; browser check extended and passing.

## Next step
Phase 8 (LLM layer, last by agreement): announcements, then LLM-plan-versus-VAL comparison. To discuss first: which model, and what the LLM should do (text announcements for each group from the verified plan; or propose a plan and let VAL grade it). Phase 9: report, demo script, optional ENHSP. Before the demo: real assembly area (A1), stair capacities (A4), group sizes (A5), on-site check of the open map questions.
