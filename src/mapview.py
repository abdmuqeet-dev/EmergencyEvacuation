"""Draw one floor of the building as a north-up schematic with Plotly.

floor_figure() takes plain data (blocked node ids, group markers, routes, picked nodes) so it can be
tested and reused without a running Streamlit app. The last trace is an invisible "pick" layer: one
point per node, so a click on the map selects a node (see picked_nodes).
"""
import math
import re

import plotly.graph_objects as go

import graph
import layout as layout_mod

PALETTE = ["#d62728", "#2ca02c", "#1f77b4", "#ff7f0e", "#9467bd", "#17becf", "#8c564b", "#e377c2",
           "#7f7f7f", "#bcbd22", "#0b3d91", "#b8860b"]
FLOOR_NAME = {"L0": "Lower floor", "L1": "1st floor", "L2": "2nd floor", "L3": "3rd floor", "L4": "4th floor",
              "L5": "5th floor", "L6": "6th floor"}
ZONE_RADIUS = {"L2_z_center": (150, 190), "L2_z_south": (130, 150), "L2_z_e": (120, 110)}
CORRIDOR = "#d5dae1"
DOOR = "#9aa3ad"
ROOM_FILL, ROOM_LINE = "#f6f3ec", "#b8b1a2"
BLOCK_FILL, BLOCK_LINE = "#f6c1c1", "#c0392b"

_cache = {}


def _lay(b=None):
    """(building, layout), computed once per Building object (the layout takes a couple of seconds)."""
    if b is None:
        if "default" not in _cache:
            _cache["default"] = graph.Building()
        b = _cache["default"]
    if id(b) not in _cache:
        _cache[id(b)] = (b, layout_mod.Layout(b))
    return _cache[id(b)]


def short(b, node):
    """Short on-map text: 'Room 444' -> '444', 'Stair 2 (SW)' -> 'S2', 'Elevator 1' -> 'E1'."""
    n = b.nodes[node]
    t = n["type"]
    label = n.get("label", node)
    if t == "room":
        m = re.match(r"Room (\S+)", label)
        if m:
            return m.group(1)
        if label.lower().startswith("unlabeled"):
            return "?"
        t_ = label.split("(")[0].strip()
        return t_ if len(t_) <= 8 else t_[:6] + ".."
    if t == "stair":
        m = re.search(r"Stair (\w+)", label)
        return "S" + m.group(1) if m else "S"
    if t == "elevator":
        m = re.search(r"Elevator (\d)", label)
        return "E" + m.group(1) if m else "E"
    if t == "exit":
        return "EXIT"
    if t == "restroom":
        return "WC"
    return ""


def group_color(index):
    return PALETTE[index % len(PALETTE)]


def pick_ids(floor, b=None):
    """The node ids of the invisible pick layer, in trace order."""
    b, lay = _lay(b)
    return [i for i in b.nodes if b.nodes[i].get("floor") == floor and i in lay.pos]


def picked_nodes(selection, floor, b=None):
    """Node ids selected by a Streamlit plotly selection event on this floor's figure."""
    ids = pick_ids(floor, b)
    out = []
    for p in (selection or {}).get("points", []) if isinstance(selection, dict) else getattr(selection, "points", []):
        cd = p.get("customdata")
        node = cd[0] if isinstance(cd, (list, tuple)) and cd else cd
        if node is None and p.get("point_index") is not None and 0 <= p["point_index"] < len(ids):
            node = ids[p["point_index"]]
        if node in ids and node not in out:
            out.append(node)
    return out


def floor_figure(floor, b=None, blocked=(), groups=(), picked=(), ghosts=(), height=780):
    """groups: [{"id", "location", "status", "color", "trail": [node ids], "route": [node ids]}].
    ghosts: [{"route": [node ids]}] the routes groups had before their latest re-plan, drawn faded underneath."""
    b, lay = _lay(b)
    blocked, picked = set(blocked), set(picked)
    on = lambda i: b.nodes[i].get("floor") == floor and i in lay.pos  # noqa: E731
    fig = go.Figure()
    shapes, annotations = [], []

    # zones (2nd floor): soft areas instead of corridors
    for i in b.of_type("zone"):
        if on(i):
            x, y = lay.pos[i]
            rx, ry = ZONE_RADIUS.get(i, (95, 85))
            shapes.append(dict(type="circle", x0=x - rx, x1=x + rx, y0=y - ry, y1=y + ry, layer="below",
                               fillcolor="rgba(205,220,240,0.35)" if i not in blocked else "rgba(246,193,193,0.55)",
                               line=dict(color="rgba(120,150,190,0.5)", width=1, dash="dot")))

    # corridors, doors
    for kind, width, color in (("corridor", 15, CORRIDOR), ("open", 9, CORRIDOR), ("door", 1.5, DOOR),
                               ("exit", 3, "#7fb77e")):
        xs, ys = [], []
        for e in b.edges:
            if e["kind"] == kind and on(e["from"]) and on(e["to"]):
                (x1, y1), (x2, y2) = lay.pos[e["from"]], lay.pos[e["to"]]
                xs += [x1, x2, None]
                ys += [y1, y2, None]
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=width),
                                     hoverinfo="skip", showlegend=False))

    # rooms and restrooms as rectangles
    tx, ty, tt = [], [], []
    for i in b.nodes:
        if on(i) and b.nodes[i]["type"] in ("room", "restroom"):
            x, y = lay.pos[i]
            w, h = lay.sizes.get(i, (layout_mod.ROOM_W, layout_mod.ROOM_H))
            red = i in blocked
            shapes.append(dict(type="rect", x0=x - w / 2, x1=x + w / 2, y0=y - h / 2, y1=y + h / 2, layer="below",
                               fillcolor=BLOCK_FILL if red else ROOM_FILL, line=dict(color=BLOCK_LINE if red else ROOM_LINE, width=1.2)))
            tx.append(x)
            ty.append(y)
            tt.append(short(b, i))
    fig.add_trace(go.Scatter(x=tx, y=ty, mode="text", text=tt, textfont=dict(size=10, color="#4a4a4a"),
                             hoverinfo="skip", showlegend=False))

    # corridor / zone nodes
    ids = [i for i in b.nodes if on(i) and b.nodes[i]["type"] in ("corridor", "zone")]
    fig.add_trace(go.Scatter(x=[lay.pos[i][0] for i in ids], y=[lay.pos[i][1] for i in ids], mode="markers",
                             marker=dict(size=7, color=["#c0392b" if i in blocked else "#8b95a1" for i in ids]),
                             hoverinfo="skip", showlegend=False))

    # stairs, elevators, exits
    for typ, symbol, size, color in (("stair", "triangle-up", 20, "#4b5f8a"), ("elevator", "square", 17, "#b8923a"),
                                     ("exit", "diamond", 20, "#2e8b57")):
        ids = [i for i in b.nodes if on(i) and b.nodes[i]["type"] == typ]
        if ids:
            fig.add_trace(go.Scatter(
                x=[lay.pos[i][0] for i in ids], y=[lay.pos[i][1] for i in ids], mode="markers+text",
                marker=dict(symbol=symbol, size=size, color=["#c0392b" if i in blocked else color for i in ids],
                            line=dict(color="white", width=1.5)),
                text=[short(b, i) for i in ids], textposition="top center" if typ != "exit" else "bottom center",
                textfont=dict(size=11, color="#2b2b2b"), hoverinfo="skip", showlegend=False))

    # blocked markers
    bl = [i for i in blocked if on(i)]
    if bl:
        fig.add_trace(go.Scatter(x=[lay.pos[i][0] for i in bl], y=[lay.pos[i][1] for i in bl], mode="markers",
                                 marker=dict(symbol="x", size=22, color=BLOCK_LINE, line=dict(width=3, color=BLOCK_LINE)),
                                 hoverinfo="skip", showlegend=False, name="blocked"))

    # the route a group had before its latest re-plan, faded, under the new one
    for g in ghosts:
        seg_x, seg_y = [], []
        nodes = g.get("route") or []
        for a, c in zip(nodes, nodes[1:]):
            if a in lay.pos and c in lay.pos and on(a) and on(c):
                seg_x += [lay.pos[a][0], lay.pos[c][0], None]
                seg_y += [lay.pos[a][1], lay.pos[c][1], None]
        if seg_x:
            fig.add_trace(go.Scatter(x=seg_x, y=seg_y, mode="lines", opacity=0.75, hoverinfo="skip", showlegend=False,
                                     line=dict(color="#8a8f98", width=6, dash="dot"), name="old route"))

    # routes and trails per group
    for g in groups:
        for key, dash, width, opacity in (("trail", "solid", 3, 0.45), ("route", "dash", 4, 0.9)):
            seg_x, seg_y = [], []
            nodes = g.get(key) or []
            for a, c in zip(nodes, nodes[1:]):
                if a in lay.pos and c in lay.pos and on(a) and on(c):
                    seg_x += [lay.pos[a][0], lay.pos[c][0], None]
                    seg_y += [lay.pos[a][1], lay.pos[c][1], None]
            if seg_x:
                fig.add_trace(go.Scatter(x=seg_x, y=seg_y, mode="lines", opacity=opacity, hoverinfo="skip",
                                         line=dict(color=g["color"], width=width, dash=dash), showlegend=False))

    # groups
    at = {}
    for g in groups:
        if g["location"] in lay.pos and on(g["location"]):
            at.setdefault(g["location"], []).append(g)
    gx, gy, gt, gc, gs = [], [], [], [], []
    for node, gl in at.items():
        x, y = lay.pos[node]
        for k, g in enumerate(gl):
            ang = 2 * math.pi * k / max(len(gl), 1)
            r = 0 if len(gl) == 1 else 16
            gx.append(x + r * math.cos(ang))
            gy.append(y + r * math.sin(ang))
            gt.append(g["id"])
            gc.append(g["color"])
            gs.append({"out": "diamond", "sheltered": "square", "stuck": "x"}.get(g.get("status"), "circle"))
    if gx:
        fig.add_trace(go.Scatter(x=gx, y=gy, mode="markers+text", text=gt, textposition="middle center",
                                 marker=dict(size=26, color=gc, symbol=gs, line=dict(color="white", width=2)),
                                 textfont=dict(color="white", size=10), hoverinfo="skip", showlegend=False))

    # picked ring
    pk = [i for i in picked if on(i)]
    if pk:
        fig.add_trace(go.Scatter(x=[lay.pos[i][0] for i in pk], y=[lay.pos[i][1] for i in pk], mode="markers",
                                 marker=dict(symbol="circle-open", size=34, line=dict(color="#e6a700", width=4)),
                                 hoverinfo="skip", showlegend=False))

    # invisible pick layer, always last
    pids = pick_ids(floor, b)
    fig.add_trace(go.Scatter(
        x=[lay.pos[i][0] for i in pids], y=[lay.pos[i][1] for i in pids], mode="markers",
        marker=dict(size=22, opacity=0.001, color="#000000"), customdata=[[i] for i in pids],
        text=["%s%s" % (b.label(i), "  [BLOCKED]" if i in blocked else "") for i in pids],
        hovertemplate="%{text}<extra></extra>", showlegend=False, name="pick",
        unselected=dict(marker=dict(opacity=0.001)), selected=dict(marker=dict(opacity=0.001))))

    x0, x1, y0, y1 = lay.bounds(floor)
    annotations.append(dict(x=x1 - 40, y=y1 - 10, ax=x1 - 40, ay=y1 - 100, xref="x", yref="y", axref="x", ayref="y",
                            showarrow=True, arrowhead=2, arrowwidth=3, arrowcolor="#333", text="<b>N</b>",
                            font=dict(size=16), yshift=0))
    fig.update_layout(
        shapes=shapes, annotations=annotations, height=height, margin=dict(l=4, r=4, t=36, b=4),
        title=dict(text="%s (north is up)" % FLOOR_NAME.get(floor, floor), font=dict(size=16), x=0.01),
        plot_bgcolor="white", paper_bgcolor="white", dragmode="pan", clickmode="event+select", hovermode="closest",
        xaxis=dict(visible=False, range=[x0, x1], constrain="domain"),
        yaxis=dict(visible=False, range=[y0, y1], scaleanchor="x", scaleratio=1))
    return fig


# ----------------------------------------------------------------------------------------------------
# Whole-building overview: all seven levels stacked, stair shafts between them, groups in their level.
SHAFTS = [("stair_1", "S1", 1.3), ("stair_2", "S2", 2.5), ("stair_3", "S3", 3.7), ("stair_5", "S5", 5.0),
          ("stair_4", "S4", 6.3), ("stair_6", "S6", 7.5), ("elev_1", "E", 8.8)]
OVERVIEW_PICK_X = -1.1


def _floor_x(lay, floor, node):
    x0, x1, _y0, _y1 = lay.bounds(floor)
    return 0.4 + 9.4 * (lay.pos[node][0] - x0) / (x1 - x0)


def building_figure(b=None, groups=(), blocked=(), floor=None, height=640):
    """Side view of the whole building. groups: [{"id", "location", "status", "color"}].
    The last trace is an invisible pick layer with one point per level (customdata = level id)."""
    b, lay = _lay(b)
    blocked = set(blocked)
    floors = graph.FLOOR_ORDER
    fig = go.Figure()
    shapes, annotations = [], []
    shapes.append(dict(type="rect", x0=-1.9, x1=10.4, y0=-1.0, y1=0, fillcolor="#e6f2e8", line=dict(width=0), layer="below"))
    annotations.append(dict(x=4.2, y=-0.5, text="Outside - assembly area", showarrow=False, font=dict(size=12, color="#2e6b3a")))
    for i, f in enumerate(floors):
        on_floor = f == floor
        shapes.append(dict(type="rect", x0=-1.9, x1=10.4, y0=i, y1=i + 1, layer="below",
                           fillcolor="#fff6e5" if on_floor else ("#f4f6fa" if i % 2 else "#eaeef5"),
                           line=dict(color="#e08a00" if on_floor else "#c5ccd8", width=3 if on_floor else 1)))
        annotations.append(dict(x=-1.8, y=i + 0.5, text="<b>%s</b>" % FLOOR_NAME[f].replace(" floor", ""), showarrow=False,
                                xanchor="left", font=dict(size=13, color="#1b2430")))
    # shafts: stairs and the elevators run through the levels where they exist
    for key, label, x in SHAFTS:
        present = [i for i, f in enumerate(floors) if (key + "_" + f) in b.nodes]
        if not present:
            continue
        fig.add_trace(go.Scatter(x=[x, x], y=[present[0] + 0.5, present[-1] + 0.5], mode="lines", hoverinfo="skip",
                                 line=dict(color="#aab4c4", width=9), showlegend=False))
        ys = [i + 0.5 for i in present]
        bad = [(key + "_" + floors[i]) in blocked for i in present]
        fig.add_trace(go.Scatter(x=[x] * len(ys), y=ys, mode="markers", hoverinfo="skip", showlegend=False,
                                 marker=dict(symbol="circle", size=11, color=["#c0392b" if q else "#4b5f8a" for q in bad],
                                             line=dict(color="white", width=1.5))))
        annotations.append(dict(x=x, y=present[-1] + 0.93, text=label, showarrow=False, font=dict(size=11, color="#4b5f8a")))
        blocked_y = [y for y, q in zip(ys, bad) if q]
        if blocked_y:
            fig.add_trace(go.Scatter(x=[x] * len(blocked_y), y=blocked_y, mode="markers", hoverinfo="skip", showlegend=False,
                                     marker=dict(symbol="x", size=20, color="#c0392b", line=dict(width=3, color="#c0392b"))))
    # groups
    n_out = 0
    per_floor = {}
    gx, gy, gt, gc, gs, gh = [], [], [], [], [], []
    for g in groups:
        loc = g["location"]
        if g["status"] == "out":
            x, y = 0.8 + 0.7 * n_out, -0.5
            n_out += 1
        else:
            f = b.floor(loc)
            i = floors.index(f)
            k = per_floor.get(f, 0)
            per_floor[f] = k + 1
            nt = b.nodes[loc]["type"]
            x = None
            for key, _label, sx in SHAFTS:
                if nt in ("stair", "elevator") and loc.startswith(key + "_"):
                    x = sx
            if x is None:
                x = _floor_x(lay, f, loc) if loc in lay.pos else 5
            y = i + 0.5 + 0.23 * ((k % 3) - 1)
        gx.append(x)
        gy.append(y)
        gt.append(g["id"])
        gc.append(g["color"])
        gs.append({"out": "diamond", "sheltered": "square", "stuck": "x"}.get(g["status"], "circle"))
        gh.append("%s - %s" % (g["id"], b.label(loc)))
    if gx:
        fig.add_trace(go.Scatter(x=gx, y=gy, mode="markers+text", text=gt, textposition="middle center", hovertext=gh,
                                 hoverinfo="text", showlegend=False, textfont=dict(color="white", size=10),
                                 marker=dict(size=24, color=gc, symbol=gs, line=dict(color="white", width=2))))
    # pick layer: click a level to open its map
    fig.add_trace(go.Scatter(x=[OVERVIEW_PICK_X] * len(floors), y=[i + 0.5 for i in range(len(floors))], mode="markers",
                             marker=dict(size=34, opacity=0.001, color="#000"), customdata=[[f] for f in floors],
                             text=["Click to open the %s" % FLOOR_NAME[f].lower() for f in floors],
                             hovertemplate="%{text}<extra></extra>", showlegend=False, name="pick",
                             unselected=dict(marker=dict(opacity=0.001)), selected=dict(marker=dict(opacity=0.001))))
    fig.update_layout(
        shapes=shapes, annotations=annotations, height=height, margin=dict(l=2, r=2, t=6, b=2), plot_bgcolor="white",
        paper_bgcolor="white", dragmode=False, clickmode="event+select", hovermode="closest",
        xaxis=dict(visible=False, range=[-1.9, 10.4], fixedrange=True),
        yaxis=dict(visible=False, range=[-1.05, 7.1], fixedrange=True))
    return fig


def picked_floor(selection):
    """The level chosen by a click on the overview figure, or None."""
    pts = selection.get("points", []) if isinstance(selection, dict) else getattr(selection, "points", [])
    for p in pts or []:
        cd = p.get("customdata")
        f = cd[0] if isinstance(cd, (list, tuple)) and cd else cd
        if f in graph.FLOOR_ORDER:
            return f
        idx = p.get("point_index")
        if idx is not None and 0 <= idx < len(graph.FLOOR_ORDER):
            return graph.FLOOR_ORDER[idx]
    return None
