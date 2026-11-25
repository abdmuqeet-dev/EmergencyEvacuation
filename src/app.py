"""EvacPlan-CSUF: interactive demo.  Run from the project root:

    .venv\\Scripts\\streamlit run src\\app.py

Pick a scenario (or build one), press Start, then step or play the evacuation. Click places on the
floor map (or choose them by name) and press Block / Unblock: the groups that are affected re-plan
from where they stand, and every new plan is checked by the VAL validator. Drag the timeline to
replay any earlier moment. The Presenter switch hides the sidebar for a projector.
"""
import copy
import json
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import graph  # noqa: E402
import mapview  # noqa: E402
import run  # noqa: E402
import simulation  # noqa: E402
import viewmodel  # noqa: E402

ROOT = graph.ROOT
SCENARIOS = ROOT / "tests" / "scenarios"
FLOORS = graph.FLOOR_ORDER
FLOOR_TAG = {"L0": "Lower", "L1": "1st", "L2": "2nd", "L3": "3rd", "L4": "4th", "L5": "5th", "L6": "6th"}
EMERGENCIES = ["fire", "earthquake", "hazmat"]
STATUS_TEXT = {"walking": "evacuating", "out": "out of the building", "sheltered": "sheltering", "stuck": "STUCK - no way out"}
SPEEDS = [0.5, 1, 2, 4]


@st.cache_resource
def building():
    return graph.Building()


def presets():
    out = {}
    for p in sorted(SCENARIOS.glob("*.json")):
        d = json.loads(p.read_text())
        out[d.get("name", p.stem)] = d
    return out


def node_choices(b, kinds):
    ids = [i for i in b.nodes if b.nodes[i]["type"] in kinds and b.nodes[i].get("floor")]
    ids.sort(key=lambda i: (graph.FLOOR_ORDER.index(b.nodes[i]["floor"]), b.nodes[i]["type"] != "room", i))
    return ids


def fmt(b):
    return lambda i: "%s | %s" % (FLOOR_TAG[b.nodes[i]["floor"]] if b.nodes[i].get("floor") else "-", b.label(i))


def blank_draft():
    return {"name": "my_scenario", "emergency": "fire", "groups": [], "description": ""}


def init_state():
    ss = st.session_state
    ss.setdefault("draft", copy.deepcopy({k: v for k, v in presets()["s1_fire_floor4_near_stair5"].items()
                                           if k not in ("expect", "script")}))
    ss.setdefault("sim", None)
    ss.setdefault("picked", [])
    ss.setdefault("last_sel", [])
    ss.setdefault("floor_radio", "L3")
    ss.setdefault("message", None)
    ss.setdefault("playing", False)
    ss.setdefault("speed", 1)
    ss.setdefault("tl", 0)
    ss.setdefault("follow", True)
    ss.setdefault("presenter", False)


def new_simulation(b, scn_name=None):
    ss = st.session_state
    scn = {k: v for k, v in ss.draft.items() if k != "description"}
    scn["name"] = scn_name or ss.draft.get("name", "scenario")
    with st.spinner("Planning routes..."):
        ss.sim = simulation.Simulation(scn, building=b, workdir=ROOT / "runs" / "app" / scn["name"])
    ss.picked, ss.last_sel, ss.message = [], [], None
    ss.playing, ss.tl, ss.follow = False, 0, True
    counts = {f: sum(1 for g in ss.sim.groups.values() if b.floor(g["location"]) == f) for f in FLOORS}
    ss.floor_radio = max(FLOORS, key=lambda f: counts[f])


# ---------------------------------------------------------------------------------------------------
def sidebar(b):
    ss = st.session_state
    d = ss.draft
    st.sidebar.title("EvacPlan-CSUF")
    st.sidebar.caption("Education Classroom building, 7 levels. A planner (Fast Downward) chooses routes; "
                       "a validator (VAL) checks every plan.")
    names = list(presets())
    choice = st.sidebar.selectbox("Scenario", ["(start blank)"] + names, index=1 + names.index("s1_fire_floor4_near_stair5"))
    if choice != ss.get("loaded_choice"):
        ss.loaded_choice = choice
        ss.draft = (blank_draft() if choice == "(start blank)" else
                    copy.deepcopy({k: v for k, v in presets()[choice].items() if k not in ("expect", "script")}))
        ss.sim, ss.picked, ss.last_sel, ss.playing = None, [], [], False
        st.rerun()
    if d.get("description"):
        st.sidebar.caption(d["description"])

    d.setdefault("blocked", [])
    if d["blocked"]:
        st.sidebar.caption("Blocked from the start: " + ", ".join(b.label(i) for i in d["blocked"]))
    d["emergency"] = st.sidebar.selectbox("Emergency", EMERGENCIES, index=EMERGENCIES.index(d.get("emergency", "fire")))
    d["directed_by_responders"] = st.sidebar.checkbox("Responders authorise elevators", bool(d.get("directed_by_responders")))
    if d["emergency"] == "hazmat":
        d["outdoor_release"] = st.sidebar.checkbox("Release is outside (all exits blocked)", bool(d.get("outdoor_release")))
    haz = node_choices(b, ("corridor", "zone", "stair", "room", "elevator"))
    d["hazard_locations"] = st.sidebar.multiselect(
        "Hazard at (fire / smoke / indoor release)", haz, default=[h for h in d.get("hazard_locations", []) if h in haz],
        format_func=fmt(b))
    if d["hazard_locations"]:
        d["hazard_radius"] = st.sidebar.slider("Hazard spreads (steps along the corridor)", 0, 4, int(d.get("hazard_radius", 0)))
    crowd = st.sidebar.checkbox("Limit people on the stairs", bool(d.get("crowding")))
    if crowd:
        cap = st.sidebar.number_input("Groups per stair per wave (placeholder value)", 1, 10,
                                      int((d.get("crowding") or {}).get("stair_capacity", 2)))
        d["crowding"] = {"stair_capacity": int(cap)}
    else:
        d.pop("crowding", None)

    st.sidebar.subheader("Groups")
    for k, g in enumerate(list(d["groups"])):
        c1, c2 = st.sidebar.columns([5, 1])
        c1.write("**%s** %s%s" % (g["id"], b.label(g["location"]), " (wheelchair)" if g.get("mobility_impaired") else ""))
        if c2.button("x", key="rm%d" % k, help="remove this group"):
            d["groups"].pop(k)
            st.rerun()
    with st.sidebar.expander("Add a group", expanded=not d["groups"]):
        fl = st.selectbox("Floor", FLOORS, index=3, format_func=lambda f: FLOOR_TAG[f], key="addfloor")
        rooms = [i for i in node_choices(b, ("room", "restroom", "corridor", "zone")) if b.nodes[i]["floor"] == fl]
        loc = st.selectbox("Where", rooms, format_func=lambda i: b.label(i), key="addloc")
        mob = st.checkbox("Wheelchair / cannot use stairs", key="addmob")
        size = st.number_input("People", 1, 200, 20, key="addsize")
        if st.button("Add group", key="addbtn"):
            n = 1
            used = {g["id"] for g in d["groups"]}
            while "g%d" % n in used:
                n += 1
            d["groups"].append({"id": "g%d" % n, "location": loc, "mobility_impaired": bool(mob), "size": int(size)})
            st.rerun()
    if st.sidebar.button("Start", type="primary", disabled=not d["groups"], width="stretch"):
        try:
            new_simulation(b)
        except (ValueError, run.PlanInvalid) as e:
            ss.sim = None
            st.sidebar.error(str(e))
        st.rerun()


# ---------------------------------------------------------------------------------------------------
def markers(view):
    """Group markers for the drawings, from one simulation frame (live or replayed)."""
    return [{"id": gid, "location": g["location"], "status": g["status"], "color": mapview.group_color(k),
             "trail": g["trail"], "route": g["route"]} for k, (gid, g) in enumerate(view["groups"].items())]


def banner(sim, view, live):
    s = viewmodel.stats(view, replans=sim.replans - 1, valid=sim.all_valid)
    where = "%s emergency" % sim.scn.get("emergency", "").capitalize()
    st.markdown(viewmodel.banner_html(s, where, replay=not live), unsafe_allow_html=True)


def _go_live():
    ss = st.session_state
    ss.tl = len(ss.sim.frames) - 1
    ss.follow = True


def controls(sim, b, live):
    ss = st.session_state
    c = st.columns([1.1, 1.1, 1.6, 1.1, 1, 1.3])
    if c[0].button("Next step", type="primary", disabled=sim.done or not live, width="stretch"):
        ss.playing, ss.message = False, None
        sim.step()
        st.rerun()
    if c[1].button("Pause" if ss.playing else "Play", disabled=sim.done or not live, width="stretch"):
        ss.playing = not ss.playing
        st.rerun()
    c[2].select_slider("Speed (steps per second)", options=SPEEDS, key="speed")
    if c[3].button("Run to end", disabled=sim.done or not live, width="stretch"):
        ss.playing = False
        with st.spinner("Running..."):
            while not sim.done and sim.step_no < simulation.MAX_STEPS:
                sim.step()
        st.rerun()
    if c[4].button("Restart", width="stretch"):
        new_simulation(b, ss.sim.scn.get("name"))
        st.rerun()
    if not live:
        c[5].button("Back to live", on_click=_go_live, type="primary", width="stretch")
    elif sim.done:
        if any(g["status"] == "stuck" for g in sim.groups.values()):
            c[5].error("Some groups are stuck.")
        else:
            c[5].success("Finished.")


def _on_timeline():
    """Only a drag by the user lands here (not the app's own updates), so it decides whether we follow live."""
    ss = st.session_state
    ss.follow = ss.tl >= len(ss.sim.frames) - 1


def timeline(sim):
    ss = st.session_state
    n = len(sim.frames)
    if n > 1:
        st.select_slider("Timeline (drag back to replay an earlier moment)", options=list(range(n)), key="tl",
                         format_func=lambda i: sim.frames[i]["label"], on_change=_on_timeline)


def block_panel(sim, b, live):
    ss = st.session_state
    st.markdown("**Change the situation**")
    options = node_choices(b, ("corridor", "zone", "stair", "elevator", "exit", "room", "restroom"))
    st.multiselect("Places to block / unblock (click the map or choose by name)", options, format_func=fmt(b), key="picked")
    blocked_now = sorted(sim.manual)
    c = st.columns([1, 1, 1])
    if c[0].button("Block", disabled=not ss.picked or not live, width="stretch"):
        _apply(sim, block=ss.picked)
    if c[1].button("Unblock", disabled=not live or not any(p in sim.manual for p in ss.picked), width="stretch"):
        _apply(sim, unblock=[p for p in ss.picked if p in sim.manual])
    if c[2].button("Clear selection", disabled=not ss.picked, width="stretch"):
        ss.clear_picks = True
        st.rerun()
    if blocked_now:
        st.caption("Blocked by you: " + ", ".join(b.label(i) for i in blocked_now))
    if sim.base_blocked:
        st.caption("Blocked by the emergency itself: %d place(s) (cannot be unblocked)" % len(sim.base_blocked))


def _apply(sim, block=(), unblock=()):
    ss = st.session_state
    ss.playing = False
    try:
        with st.spinner("Re-planning the affected groups..."):
            ev = sim.update(block=block, unblock=unblock)
    except (ValueError, run.PlanInvalid) as e:
        ss.message = "Could not apply: %s" % e
        st.rerun()
    sentences = viewmodel.change_sentences(ev)
    if ev["replanned"]:
        head = "<b>Re-planned in %.1f s, new plan verified.</b>" % ev["seconds"]
        ss.message = head + "<br>" + "<br>".join(sentences or ["Nobody's route actually changed."])
    else:
        ss.message = "Nobody's route was affected, so nobody re-planned."
    if ev["stuck"]:
        ss.message += "<br>No way out for: %s." % ", ".join(ev["stuck"])
    ss.clear_picks = True      # a widget's value can only be reset before it is drawn: do it at the next run
    st.rerun()


def overview_panel(sim, view, b):
    ss = st.session_state
    st.markdown("**The whole building** (click a level to open it)")
    fig = mapview.building_figure(b, markers(view), view["blocked"], floor=ss.floor_radio,
                                  height=520 if ss.presenter else 440)
    event = st.plotly_chart(fig, key="overview", on_select="rerun", selection_mode="points", width="stretch",
                            config={"displayModeBar": False})
    f = mapview.picked_floor(getattr(event, "selection", None) or {})
    if f and f != ss.get("ov_last"):
        ss.ov_last = f
        if f != ss.floor_radio:
            ss.floor_radio = f
            st.rerun()
    elif not f:
        ss.ov_last = None


def map_panel(sim, view, b):
    ss = st.session_state
    gm = markers(view)
    per_floor = {f: sum(1 for g in view["groups"].values() if b.floor(g["location"]) == f and g["status"] != "out") for f in FLOORS}
    floor = st.radio("Floor", FLOORS, horizontal=True, key="floor_radio",
                     format_func=lambda f: "%s%s" % (FLOOR_TAG[f], " (%d)" % per_floor[f] if per_floor[f] else ""))
    ghosts = [{"route": r} for r in view["ghost"].values()]
    fig = mapview.floor_figure(floor, b, blocked=view["blocked"], groups=gm, picked=ss.picked, ghosts=ghosts,
                               height=860 if ss.presenter else 760)
    event = st.plotly_chart(fig, key="map_%s" % floor, on_select="rerun", selection_mode="points",
                            width="stretch", config={"displaylogo": False, "scrollZoom": True})
    sel = mapview.picked_nodes(getattr(event, "selection", None) or {}, floor, b)
    fresh = [n for n in sel if n not in ss.last_sel]
    ss.last_sel = sel
    if fresh:
        ss.picked = ss.picked + [n for n in fresh if n not in ss.picked]
        st.rerun()
    st.caption("Circles are groups (diamond = out, square = sheltering, x = stuck). Dashed line = planned route, faint solid "
               "line = where the group has been, grey dotted line = the route before the last re-plan. Red = blocked. "
               "Triangles are stairs, E = elevators, green diamonds = exits to outside.")


SETUP_TOOLS = ["Add a group", "Set hazard (fire / smoke / release)", "Block a place", "Remove"]
GROUP_KINDS = ("room", "restroom", "corridor", "zone")
HAZARD_KINDS = ("corridor", "zone", "stair", "room", "elevator")
BLOCK_KINDS = ("corridor", "zone", "stair", "elevator", "exit", "room", "restroom")


def _toggle(lst, node):
    if node in lst:
        lst.remove(node)
        return False
    lst.append(node)
    return True


def apply_setup_click(b, d, tool, node):
    """Change the scenario draft for one click on the setup map. Returns a message for the user."""
    kind, name = b.nodes[node]["type"], b.label(node)
    if tool == SETUP_TOOLS[0]:
        if kind not in GROUP_KINDS:
            return "Groups start in a room or corridor, not at %s." % name
        used = {g["id"] for g in d["groups"]}
        n = 1
        while "g%d" % n in used:
            n += 1
        ss = st.session_state
        d["groups"].append({"id": "g%d" % n, "location": node, "mobility_impaired": bool(ss.get("setup_mob")),
                            "size": int(ss.get("setup_size", 20))})
        return "Added group g%d at %s." % (n, name)
    if tool == SETUP_TOOLS[1]:
        if kind not in HAZARD_KINDS:
            return "The hazard can't be placed at %s." % name
        hz = d.setdefault("hazard_locations", [])
        on = _toggle(hz, node)
        return "%s the hazard at %s." % ("Set" if on else "Cleared", name)
    if tool == SETUP_TOOLS[2]:
        if kind not in BLOCK_KINDS:
            return "%s can't be blocked." % name
        on = _toggle(d.setdefault("blocked", []), node)
        return "%s %s." % ("Blocked" if on else "Unblocked", name)
    here = [g for g in d["groups"] if g["location"] == node]
    out = []
    if here:
        d["groups"].remove(here[-1])
        out.append("group %s" % here[-1]["id"])
    for key, what in (("hazard_locations", "hazard"), ("blocked", "block")):
        if node in d.get(key, []):
            d[key].remove(node)
            out.append(what)
    return ("Removed %s at %s." % (" and ".join(out), name)) if out else "Nothing to remove at %s." % name


def setup_panel(b):
    """Scenario setup on the map: pick a tool, click places. Runs while no simulation exists."""
    ss = st.session_state
    d = ss.draft
    ss.setdefault("setup_floor", "L3")
    ss.setdefault("setup_nonce", 0)
    ss.setdefault("setup_msg", "")
    ss.setdefault("setup_tool", SETUP_TOOLS[0])
    st.markdown("**Set up the scenario on the map**")
    c = st.columns([3.2, 1.1, 1.1])
    c[0].radio("Click does", SETUP_TOOLS, horizontal=True, key="setup_tool")
    c[1].checkbox("Wheelchair", key="setup_mob", help="New groups cannot use stairs")
    c[2].number_input("People", 1, 200, 20, key="setup_size")
    counts = {f: sum(1 for g in d["groups"] if b.floor(g["location"]) == f) for f in FLOORS}
    st.radio("Floor", FLOORS, horizontal=True, key="setup_floor",
             format_func=lambda f: "%s%s" % (FLOOR_TAG[f], " (%d)" % counts[f] if counts[f] else ""))
    floor = ss.setup_floor
    gm = [{"id": g["id"], "location": g["location"], "status": "walking", "color": mapview.group_color(k),
           "trail": [], "route": []} for k, g in enumerate(d["groups"])]
    shown_blocked = set(d.get("blocked", [])) | set(d.get("hazard_locations", []))
    fig = mapview.floor_figure(floor, b, blocked=shown_blocked, groups=gm, height=800 if ss.presenter else 720)
    event = st.plotly_chart(fig, key="setup_%s_%d" % (floor, ss.setup_nonce), on_select="rerun",
                            selection_mode="points", width="stretch", config={"displaylogo": False, "scrollZoom": True})
    sel = mapview.picked_nodes(getattr(event, "selection", None) or {}, floor, b)
    if sel:
        ss.setup_msg = " ".join(apply_setup_click(b, d, ss.setup_tool, n) for n in sel)
        ss.setup_nonce += 1            # a fresh chart has no selection, so the same place can be clicked again
        st.rerun()
    if ss.setup_msg:
        st.info(ss.setup_msg)
    st.caption("Circles are groups, red crosses are blocked places or the hazard, triangles are stairs, E = elevators, "
               "green diamonds = exits. Scroll to zoom, drag to pan. Press Start in the sidebar when it looks right.")


def groups_panel(sim, view, b, live):
    st.markdown("**Groups**")
    for k, (gid, g) in enumerate(view["groups"].items()):
        color = mapview.group_color(k)
        nxt = ""
        live_g = sim.groups[gid]
        if live and g["status"] == "walking" and live_g["queue"]:
            nxt = " | next: " + simulation.describe(sim, live_g["queue"][0])
        st.markdown("<span style='color:%s;font-weight:700'>%s</span> &nbsp; %s &nbsp;|&nbsp; at %s%s" % (
            color, gid, STATUS_TEXT[g["status"]] + (" (%s)" % g["kind"] if g["kind"] else ""),
            b.label(g["location"]) + (" on " + FLOOR_TAG[b.floor(g["location"])] if b.floor(g["location"]) else ""), nxt),
            unsafe_allow_html=True)
        if live and g["status"] == "walking" and live_g["queue"]:
            with st.expander("Remaining plan for %s (%d actions)" % (gid, len(live_g["queue"]))):
                for i, a in enumerate(live_g["queue"], 1):
                    st.text("%2d. %s" % (i, simulation.describe(sim, a)))


def log_panel(sim, b):
    st.markdown("**What has happened**")
    lines = []
    for rec in sim.log:
        if rec["type"] == "step":
            if rec["shaking"]:
                lines.append("Step %d: everyone drops, covers and waits for the shaking to stop" % rec["n"])
            for gid, acts in rec["actions"].items():
                lines.append("Step %d: %s %s" % (rec["n"], gid, "; ".join(simulation.describe(sim, a) for a in acts)))
        else:
            what = []
            if rec["block"]:
                what.append("you blocked " + ", ".join(b.label(i) for i in rec["block"]))
            if rec["unblock"]:
                what.append("you unblocked " + ", ".join(b.label(i) for i in rec["unblock"]))
            if what:
                lines.append("After step %d: %s - %s" % (rec["after_step"], "; ".join(what),
                             "re-planned " + ", ".join(rec["replanned"]) if rec["replanned"] else "nobody was affected"))
    for ln in reversed(lines[-60:]):
        st.text(ln)
    if not lines:
        st.caption("Nothing yet. Press Next step or Play.")


def main():
    st.set_page_config(page_title="EvacPlan-CSUF", layout="wide")
    b = building()
    init_state()
    ss = st.session_state
    if ss.pop("clear_picks", False):
        ss.picked = []
        ss.last_sel = []
    sidebar(b)
    st.markdown(viewmodel.CSS + (viewmodel.PRESENTER_CSS if ss.presenter else ""), unsafe_allow_html=True)
    head = st.columns([5, 1.4])
    head[0].markdown("### Emergency evacuation planner")
    head[1].toggle("Presenter mode", key="presenter", help="Hide the sidebar and enlarge everything for a projector")
    sim = ss.sim
    if sim is None:
        st.write("Choose a scenario in the sidebar, or build one by clicking the map below, then press **Start**. "
                 "Routes come from an automated planner, and every plan is verified by an independent validator.")
        setup_panel(b)
        st.caption("Tip: after starting, press Play to watch groups walk, then block a stair or corridor on the route "
                   "and watch the plan change. Drag the timeline to replay.")
        return
    n = len(sim.frames)
    if ss.follow or ss.tl > n - 1:               # watching live: always show the newest frame
        ss.tl = n - 1
    view = sim.frames[ss.tl]
    live = ss.tl == n - 1
    banner(sim, view, live)
    if ss.message:                         # what the last Block / Unblock did, right under the banner where it is seen
        st.markdown("<div class='evac-card'>%s</div>" % ss.message, unsafe_allow_html=True)
    controls(sim, b, live)
    timeline(sim)
    left, right = st.columns([3, 1.25] if ss.presenter else [3, 1.6])
    with right:
        overview_panel(sim, view, b)       # a click here changes the floor, so it runs before the floor radio
    with left:
        map_panel(sim, view, b)            # a click here picks places, so it runs before the selection box
    with right:
        block_panel(sim, b, live)
        if ss.presenter:
            with st.expander("Groups and log"):
                groups_panel(sim, view, b, live)
                log_panel(sim, b)
        else:
            st.divider()
            groups_panel(sim, view, b, live)
            st.divider()
            log_panel(sim, b)
    if ss.playing:                         # autoplay: one step per refresh
        if sim.done or not live:
            ss.playing = False
        else:
            time.sleep(1.0 / float(ss.speed))
            ss.message = None
            sim.step()
            st.rerun()


main()
