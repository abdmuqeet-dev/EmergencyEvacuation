r"""Phase 7 done-check: schematic layout, map drawing, and the Streamlit app.

Run from the project root:  .venv\Scripts\python -m unittest tests.test_phase7 -v   (about 2 minutes)
Start the app:              .venv\Scripts\streamlit run src\app.py
"""
import itertools
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import graph  # noqa: E402
import layout  # noqa: E402
import mapview  # noqa: E402

B = graph.Building()
L = layout.Layout(B)


def floor_nodes(f):
    return [i for i, n in B.nodes.items() if n.get("floor") == f]


class LayoutTests(unittest.TestCase):
    def test_every_node_has_a_finite_position(self):
        for i in B.locations():
            self.assertIn(i, L.pos, i)
            self.assertTrue(all(math.isfinite(v) for v in L.pos[i]), i)

    def test_no_two_rooms_overlap(self):
        for f in graph.FLOOR_ORDER:
            rooms = [i for i in L.sizes if B.nodes[i].get("floor") == f]
            for a, c in itertools.combinations(rooms, 2):
                (x1, y1), (x2, y2) = L.pos[a], L.pos[c]
                self.assertFalse(abs(x1 - x2) < layout.ROOM_W - 1 and abs(y1 - y2) < layout.ROOM_H - 1, (f, a, c))

    def test_no_room_covers_a_stair_elevator_or_exit(self):
        for f in graph.FLOOR_ORDER:
            fixed = [i for i in floor_nodes(f) if B.nodes[i]["type"] in ("stair", "elevator", "exit")]
            for r in (i for i in L.sizes if B.nodes[i].get("floor") == f):
                for s in fixed:
                    dx, dy = abs(L.pos[r][0] - L.pos[s][0]), abs(L.pos[r][1] - L.pos[s][1])
                    self.assertFalse(dx < layout.ROOM_W / 2 and dy < layout.ROOM_H / 2, (r, s))

    def test_rooms_sit_close_to_their_corridor(self):
        far = []
        for e in B.edges:
            for r, p in ((e["from"], e["to"]), (e["to"], e["from"])):
                if r in L.sizes and p in L.pos and r != "L6_r606" and B.nodes[p].get("floor") == B.nodes[r].get("floor"):
                    if math.dist(L.pos[r], L.pos[p]) > 220:
                        far.append(r)
        self.assertEqual(far, [])

    def test_the_layout_is_deterministic(self):
        again = layout.Layout(B)
        self.assertEqual(L.pos, again.pos)

    def test_compass_directions_are_right_on_every_floor(self):
        """North up on all floors: stair 2 and the elevators are in the south-west corner."""
        for f in graph.FLOOR_ORDER:
            ids = [i for i in floor_nodes(f) if B.nodes[i]["type"] in ("corridor", "zone")]
            cx = sum(L.pos[i][0] for i in ids) / len(ids)
            cy = sum(L.pos[i][1] for i in ids) / len(ids)
            for node in ("stair_2_" + f, "elev_1_" + f, "elev_2_" + f):
                self.assertLess(L.pos[node][0], cx, node)   # west of centre
                self.assertLess(L.pos[node][1], cy, node)   # south of centre
        # the poster-labelled exits
        self.assertLess(L.pos["exit_L1_W"][0], L.pos["exit_L1_E"][0])
        self.assertGreater(L.pos["exit_L1_N"][1], L.pos["exit_L1_S"][1])
        self.assertGreater(L.pos["exit_L0_N"][1], L.pos["exit_L0_S4"][1])
        # the unnumbered 2nd-floor stair (stair 1) is north-west of stair 2
        self.assertGreater(L.pos["stair_1_L2"][1], L.pos["stair_2_L2"][1])
        # stair 5 is on the east side of the ring floors
        for n in range(3, 7):
            ring = [L.pos[i][0] for i in floor_nodes("L%d" % n) if i.startswith("L%d_c_" % n)]
            self.assertGreater(L.pos["stair_5_L%d" % n][0], max(ring))

    def test_stairs_line_up_between_floors(self):
        """The same stair sits in about the same place on the floors above each other (L3-L6 exactly)."""
        for n in range(3, 6):
            self.assertEqual(L.pos["stair_2_L%d" % n], L.pos["stair_2_L%d" % (n + 1)])
            self.assertEqual(L.pos["stair_5_L%d" % n], L.pos["stair_5_L%d" % (n + 1)])


class MapTests(unittest.TestCase):
    def test_every_floor_draws(self):
        for f in graph.FLOOR_ORDER:
            fig = mapview.floor_figure(f, B)
            self.assertEqual(fig.data[-1].name, "pick")
            self.assertEqual(len(fig.data[-1].x), len(mapview.pick_ids(f, B)))

    def test_pick_layer_covers_every_node_on_the_floor(self):
        ids = set(mapview.pick_ids("L3", B))
        self.assertEqual(ids, {i for i in floor_nodes("L3")})

    def test_blocked_rooms_are_red_and_blocked_places_get_a_marker(self):
        calm = mapview.floor_figure("L3", B)
        fire = mapview.floor_figure("L3", B, blocked={"L3_r301", "stair_5_L3"})
        reds = lambda f: sum(1 for s in f.layout.shapes if s.fillcolor == mapview.BLOCK_FILL)  # noqa: E731
        self.assertEqual(reds(calm), 0)
        self.assertEqual(reds(fire), 1)
        self.assertTrue(any(t.name == "blocked" for t in fire.data))

    def test_routes_are_only_drawn_on_the_floor_they_are_on(self):
        g = {"id": "g1", "location": "stair_2_L3", "status": "walking", "color": "#d62728", "trail": [],
             "route": ["stair_2_L3", "stair_2_L2", "stair_2_L1"]}
        on3 = mapview.floor_figure("L3", B, groups=[g])
        on2 = mapview.floor_figure("L2", B, groups=[g])
        lines = lambda f: [t for t in f.data if t.mode == "lines" and t.line.dash == "dash"]  # noqa: E731
        self.assertEqual(lines(on3), [])     # stair nodes on other floors: nothing to draw here
        self.assertEqual(lines(on2), [])
        g["route"] = ["L3_c_nw_lobby", "stair_2_L3"]
        self.assertEqual(len(lines(mapview.floor_figure("L3", B, groups=[g]))), 1)

    def test_groups_are_drawn_only_on_their_floor(self):
        g = {"id": "g1", "location": "L3_r301", "status": "walking", "color": "#d62728", "trail": [], "route": []}
        has_group = lambda f: any(t.mode == "markers+text" and list(t.text) == ["g1"] for t in f.data)  # noqa: E731
        self.assertTrue(has_group(mapview.floor_figure("L3", B, groups=[g])))
        self.assertFalse(has_group(mapview.floor_figure("L4", B, groups=[g])))

    def test_selection_events_map_back_to_nodes(self):
        ids = mapview.pick_ids("L3", B)
        by_data = {"points": [{"customdata": ["L3_r301"]}, {"customdata": ["L3_r301"]}]}
        self.assertEqual(mapview.picked_nodes(by_data, "L3", B), ["L3_r301"])
        by_index = {"points": [{"point_index": ids.index("L3_c_nw_lobby")}]}
        self.assertEqual(mapview.picked_nodes(by_index, "L3", B), ["L3_c_nw_lobby"])
        self.assertEqual(mapview.picked_nodes({"points": [{"customdata": ["L4_r401"]}]}, "L3", B), [])  # other floor
        self.assertEqual(mapview.picked_nodes({}, "L3", B), [])
        self.assertEqual(mapview.picked_nodes(None, "L3", B), [])

    def test_short_labels(self):
        self.assertEqual(mapview.short(B, "L4_r444"), "444")
        self.assertEqual(mapview.short(B, "stair_5_L4"), "S5")
        self.assertEqual(mapview.short(B, "elev_2_L4"), "E2")
        self.assertEqual(mapview.short(B, "exit_L1_N"), "EXIT")
        self.assertEqual(mapview.short(B, "L0_c_c_n"), "")
        for i in B.nodes:   # nothing long enough to spill out of a room rectangle
            self.assertLessEqual(len(mapview.short(B, i)), 8, i)


class DescribeTests(unittest.TestCase):
    def test_every_action_reads_as_plain_english_without_ids(self):
        import simulation
        sim = simulation.Simulation({"name": "t", "emergency": "fire", "crowding": {"stair_capacity": 2},
                                     "groups": [{"id": "g1", "location": "L5_r510", "mobility_impaired": False, "size": 5}]},
                                    building=B, workdir=ROOT / "runs" / "t_describe")
        acts = list(sim.groups["g1"]["queue"]) + ["(shelter-and-notify g1 l5_c_nw_lobby)", "(shelter-in-place g1 l5_c_nw_lobby)",
                                                    "(use-elevator g1 elev_1_l5 elev_1_l4)", "(wait-for-shaking-to-stop)"]
        texts = [simulation.describe(sim, a) for a in acts]
        for t in texts:
            self.assertNotIn("[", t)
            self.assertNotIn("L5_", t)
            self.assertGreater(len(t), 8)
        self.assertTrue(any(t.startswith("takes the stairs down to") and t.endswith("floor") for t in texts))
        self.assertIn("leaves the building at", " ".join(texts))
        self.assertIn("waits for the shaking to stop", texts)


class ViewModelTests(unittest.TestCase):
    def frame(self, *statuses):
        return {"step": 3, "label": "Step 3", "groups": {"g%d" % i: {"status": s} for i, s in enumerate(statuses)}}

    def test_stats_and_state(self):
        import viewmodel
        s = viewmodel.stats(self.frame("out", "walking", "sheltered"), replans=2, valid=True)
        self.assertEqual((s["total"], s["out"], s["walking"], s["sheltered"], s["stuck"]), (3, 1, 1, 1, 0))
        self.assertEqual(s["state"], "live")
        self.assertEqual(viewmodel.stats(self.frame("out", "out"))["state"], "done")
        self.assertEqual(viewmodel.stats(self.frame("out", "sheltered"))["state"], "done")
        self.assertEqual(viewmodel.stats(self.frame("out", "stuck"))["state"], "stuck")
        self.assertEqual(viewmodel.stats(self.frame("walking", "stuck"))["state"], "live")

    def test_banner_text_and_colours(self):
        import viewmodel
        html = viewmodel.banner_html(viewmodel.stats(self.frame("out", "walking"), replans=1), "Fire emergency")
        self.assertIn("1 of 2 out of the building", html)
        self.assertIn("1 re-plan<", html.replace("</span>", "<"))
        self.assertIn("plans verified by VAL", html)
        self.assertIn("evac-banner live", html)
        done = viewmodel.banner_html(viewmodel.stats(self.frame("out", "out")))
        self.assertIn("Everyone is out: 2 of 2", done)
        self.assertIn("evac-banner ok", done)
        bad = viewmodel.banner_html(viewmodel.stats(self.frame("stuck"), valid=False))
        self.assertIn("evac-banner bad", bad)
        self.assertIn("A PLAN WAS REJECTED", bad)
        self.assertIn("Replay", viewmodel.banner_html(viewmodel.stats(self.frame("walking")), replay=True))

    def test_banner_escapes_text(self):
        import viewmodel
        html = viewmodel.banner_html(viewmodel.stats(self.frame("walking")), "<script>x</script>")
        self.assertNotIn("<script>", html)

    def test_change_sentences(self):
        import viewmodel
        ev = {"changes": {"g1": {"before": 4, "after": 6, "was": "walking", "now": "walking"},
                          "g2": {"before": 1, "after": 9, "was": "sheltered", "now": "walking"},
                          "g3": {"before": 5, "after": 1, "was": "walking", "now": "sheltered"},
                          "g4": {"before": 5, "after": 0, "was": "walking", "now": "stuck"},
                          "g5": {"before": 3, "after": 3, "was": "walking", "now": "walking"}}}
        text = viewmodel.change_sentences(ev)
        self.assertIn("g1 is re-routed: 4 -> 6 actions left (2 actions longer).", text)
        self.assertTrue(any("g2 can leave its shelter" in t for t in text))
        self.assertTrue(any("g3 has no safe way down" in t for t in text))
        self.assertTrue(any("g4 has no way out" in t for t in text))
        self.assertTrue(any("the same length" in t for t in text))
        self.assertEqual(viewmodel.change_sentences({}), [])


class FramesAndOverviewTests(unittest.TestCase):
    def sim(self):
        import simulation
        return simulation.Simulation(json.loads((ROOT / "tests" / "scenarios" / "s6_midrun_block_lower.json").read_text()),
                                     building=B, workdir=ROOT / "runs" / "t_frames")

    def test_every_step_and_change_makes_a_frame(self):
        sim = self.sim()
        self.assertEqual([f["label"] for f in sim.frames], ["Start"])
        sim.step()
        sim.step()
        sim.block(["L0_c_c_n"])
        sim.step()
        self.assertEqual([f["label"] for f in sim.frames], ["Start", "Step 1", "Step 2", "Step 2, blocked", "Step 3"])
        self.assertEqual(sim.frames[1]["groups"]["g1"]["location"], "L0_c_e_b")      # frames keep the past
        self.assertEqual(sim.frames[0]["groups"]["g1"]["location"], "L0_r62")
        self.assertNotIn("L0_c_c_n", sim.frames[2]["blocked"])
        self.assertIn("L0_c_c_n", sim.frames[3]["blocked"])
        self.assertEqual(len(sim.frames[2]["groups"]["g1"]["trail"]), 3)
        self.assertEqual(len(sim.frames[4]["groups"]["g1"]["trail"]), 4)

    def test_a_replan_remembers_the_old_route(self):
        sim = self.sim()
        sim.step()
        sim.step()
        ev = sim.block(["L0_c_c_n"])
        self.assertEqual(sim.frames[2]["ghost"], {})
        ghost = sim.frames[-1]["ghost"]["g1"]
        self.assertIn("L0_c_c_n", ghost)                      # the route it used to have
        self.assertNotIn("L0_c_c_n", sim.frames[-1]["groups"]["g1"]["route"])
        ch = ev["changes"]["g1"]
        self.assertEqual((ch["before"], ch["after"]), (4, 6))

    def test_no_ghost_when_nobody_was_affected(self):
        sim = self.sim()
        sim.block(["L6_c_w_mid"])
        self.assertEqual(sim.frames[-1]["ghost"], {})
        self.assertEqual(sim.log[-1]["changes"], {})

    def test_ghost_routes_are_drawn_faded_and_only_on_their_floor(self):
        r = {"route": ["L3_c_nw_lobby", "L3_c_n_mid"]}
        fig = mapview.floor_figure("L3", B, ghosts=[r])
        faded = [t for t in fig.data if t.name == "old route"]
        self.assertEqual(len(faded), 1)
        self.assertEqual(faded[0].line.dash, "dot")
        self.assertEqual([t for t in mapview.floor_figure("L4", B, ghosts=[r]).data if t.name == "old route"], [])

    def test_overview_has_every_level_and_a_pick_layer(self):
        fig = mapview.building_figure(B, [], [], "L3")
        self.assertEqual(fig.data[-1].name, "pick")
        self.assertEqual([c[0] for c in fig.data[-1].customdata], graph.FLOOR_ORDER)
        labels = " ".join(a.text for a in fig.layout.annotations)
        for word in ("6th", "Lower", "Outside"):
            self.assertIn(word, labels)

    def test_overview_shows_groups_on_their_level_and_out_groups_outside(self):
        g = [{"id": "g1", "location": "L5_r510", "status": "walking", "color": "#d62728"},
             {"id": "g2", "location": "stair_2_L2", "status": "walking", "color": "#2ca02c"},
             {"id": "g3", "location": "exit_L1_S", "status": "out", "color": "#1f77b4"}]
        fig = mapview.building_figure(B, g, [], None)
        pts = {t: (x, y) for tr in fig.data if tr.mode == "markers+text" for t, x, y in zip(tr.text, tr.x, tr.y)}
        self.assertTrue(5.0 <= pts["g1"][1] <= 6.0)            # 5th floor band: y in [5, 6]
        self.assertTrue(2.0 <= pts["g2"][1] <= 3.0)            # 2nd floor
        self.assertAlmostEqual(pts["g2"][0], 2.5)              # standing in stair 2's shaft
        self.assertLess(pts["g3"][1], 0)                       # outside, below the Lower floor

    def test_overview_marks_blocked_stairs_on_their_level(self):
        fig = mapview.building_figure(B, [], {"stair_5_L4"}, None)
        xs = [tr for tr in fig.data if tr.mode == "markers" and tr.marker.symbol == "x"]
        self.assertEqual(len(xs), 1)
        self.assertEqual(list(xs[0].x), [5.0])
        self.assertEqual(list(xs[0].y), [4.5])

    def test_picked_floor_mapping(self):
        self.assertEqual(mapview.picked_floor({"points": [{"customdata": ["L4"]}]}), "L4")
        self.assertEqual(mapview.picked_floor({"points": [{"point_index": 2}]}), "L2")
        self.assertIsNone(mapview.picked_floor({}))
        self.assertIsNone(mapview.picked_floor(None))
        self.assertIsNone(mapview.picked_floor({"points": [{"customdata": ["nope"]}]}))


class ThemeTests(unittest.TestCase):
    def test_theme_file_is_valid(self):
        import tomllib
        cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
        self.assertEqual(cfg["theme"]["base"], "light")
        for k in ("primaryColor", "backgroundColor", "textColor"):
            self.assertRegex(cfg["theme"][k], r"^#[0-9A-Fa-f]{6}$")


class AppTests(unittest.TestCase):
    def new_app(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "src" / "app.py"), default_timeout=180)
        at.run()
        self.assertEqual([e.value for e in at.exception], [])
        return at

    def press(self, at, label, sidebar=False):
        pool = at.sidebar.button if sidebar else at.button
        pool[[b.label for b in pool].index(label)].click().run()
        self.assertEqual([e.value for e in at.exception], [])

    def banner(self, at):
        found = [m.value for m in at.markdown if "evac-banner" in m.value and "<div class='evac-banner" in m.value]
        self.assertEqual(len(found), 1, "expected exactly one banner")
        return found[0]

    def card(self, at):
        return " ".join(m.value for m in at.markdown if "evac-card" in m.value and "<div class='evac-card'" in m.value)

    def button(self, at, label):
        return at.button[[b.label for b in at.button].index(label)]

    def test_start_step_and_run_to_the_end(self):
        at = self.new_app()
        self.assertEqual([m for m in at.markdown if "<div class='evac-banner" in m.value], [])   # nothing before Start
        self.press(at, "Start", sidebar=True)
        self.assertIn("0 of 1 out of the building", self.banner(at))
        self.assertIn("plans verified by VAL", self.banner(at))
        self.assertIn("Start", self.banner(at))
        self.press(at, "Next step")
        self.assertIn("Step 1", self.banner(at))
        self.press(at, "Run to end")
        self.assertIn("Everyone is out: 1 of 1", self.banner(at))
        self.assertIn("evac-banner ok", self.banner(at))
        self.assertTrue(self.button(at, "Next step").disabled)

    def test_play_runs_by_itself_until_everyone_is_out(self):
        at = self.new_app()
        at.sidebar.selectbox[0].select("s0_fire_ground_floor_baseline").run()
        self.press(at, "Start", sidebar=True)
        at.select_slider(key="speed").set_value(4).run()
        self.press(at, "Play")                                    # the script keeps stepping and re-running itself
        self.assertIn("Everyone is out", self.banner(at))
        self.assertFalse(at.session_state["playing"])

    def test_timeline_replays_an_earlier_moment(self):
        at = self.new_app()
        self.press(at, "Start", sidebar=True)
        for _ in range(3):
            self.press(at, "Next step")
        at.select_slider(key="tl").set_value(1).run()
        self.assertEqual([e.value for e in at.exception], [])
        self.assertIn("Replay: Step 1", self.banner(at))
        self.assertTrue(self.button(at, "Next step").disabled)
        self.assertTrue(self.button(at, "Play").disabled)
        self.assertTrue(self.button(at, "Run to end").disabled)
        self.press(at, "Back to live")
        self.assertNotIn("Replay", self.banner(at))
        self.assertIn("Step 3", self.banner(at))
        self.assertFalse(self.button(at, "Next step").disabled)

    def test_blocking_a_place_on_the_route_replans_and_explains_the_change(self):
        at = self.new_app()
        at.sidebar.selectbox[0].select("s6_midrun_block_lower").run()
        self.press(at, "Start", sidebar=True)
        self.press(at, "Next step")
        self.press(at, "Next step")
        at.multiselect(key="picked").set_value(["L0_c_c_n"]).run()
        self.press(at, "Block")
        self.assertIn("1 re-plan", self.banner(at))
        self.assertIn("new plan verified", self.card(at))
        self.assertIn("g1 is re-routed: 4 -> 6 actions left", self.card(at))
        self.assertIn("plans verified by VAL", self.banner(at))
        timeline = at.select_slider(key="tl")
        self.assertEqual(timeline.format_func(timeline.value), "Step 2, blocked")
        self.press(at, "Run to end")
        self.assertIn("Everyone is out: 1 of 1", self.banner(at))

    def test_blocking_something_nobody_needs_says_so(self):
        at = self.new_app()
        self.press(at, "Start", sidebar=True)
        at.multiselect(key="picked").set_value(["L6_c_w_mid"]).run()
        self.press(at, "Block")
        self.assertIn("0 re-plans", self.banner(at))
        self.assertIn("nobody re-planned", self.card(at))

    def test_presenter_mode_hides_the_sidebar(self):
        at = self.new_app()
        css = lambda: " ".join(m.value for m in at.markdown)  # noqa: E731
        self.assertNotIn("stSidebar", css())
        at.toggle(key="presenter").set_value(True).run()
        self.assertEqual([e.value for e in at.exception], [])
        self.assertIn("stSidebar", css())

    def test_the_log_and_group_panel_use_plain_words(self):
        at = self.new_app()
        self.press(at, "Start", sidebar=True)
        self.press(at, "Next step")
        text = " ".join(t.value for t in at.text) + " ".join(m.value for m in at.markdown)
        self.assertIn("walks to", text)
        self.assertNotIn("[L4_", text)

    def test_add_and_remove_a_group(self):
        at = self.new_app()
        at.sidebar.selectbox(key="addfloor").select("L5").run()
        at.sidebar.selectbox(key="addloc").select("L5_r510").run()
        self.press(at, "Add group", sidebar=True)
        labels = [b.label for b in at.sidebar.button]
        self.assertEqual(labels.count("x"), 2)                     # g1 from the preset plus the new one
        at.sidebar.button[labels.index("x")].click().run()         # remove the first
        self.assertEqual([b.label for b in at.sidebar.button].count("x"), 1)

    def test_a_blank_scenario_cannot_start_without_groups(self):
        at = self.new_app()
        at.sidebar.selectbox[0].select("(start blank)").run()
        start = at.sidebar.button[[b.label for b in at.sidebar.button].index("Start")]
        self.assertTrue(start.disabled)


if __name__ == "__main__":
    unittest.main()
