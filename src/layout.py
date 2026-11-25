"""Schematic floor layouts: an (x, y) position for every node of data/building.json, north up.

The graph has connections but no coordinates. Corridors, zones, stairs, elevators and exits are
placed by hand below (read off the evacuation posters, so the shape of each floor is recognisable);
rooms and restrooms are placed automatically beside the corridor they attach to, alternating sides,
then nudged apart so no two overlap and none sits on a corridor.

Frame: x grows east, y grows north, one unit is about one poster pixel. L0 and L1 posters have
north at the top of the page; the L2-L6 posters have north pointing right, so their poster pixels
are turned into compass coordinates (page down = east, page right = north). Node ids on L2-L6 keep
the poster's page directions (see docs/PROJECT_PLAN.md, Phase 1) but the coordinates here are
compass, so every floor is drawn north-up.

Nodes are placed only for floors that exist in the graph; the assembly node is not drawn (the
exits simply lead out of the building).
"""
import math

import graph

ROOM_W, ROOM_H = 52, 36
GAP = 6
ROWS = 3          # rooms sit in up to this many rows behind each other, each side of a corridor


def _l1(px, py):          # L0/L1 poster pixels: north is up the page
    return (px, -py)


def _l2(px, py):          # L2 poster pixels: north is the page's right, east is down the page
    return (py, px)


# id -> (x, y, axis) for corridor/zone nodes; axis is the direction the corridor runs ("h" or "v"),
# which decides where its rooms go. Stairs/elevators/exits: id -> (x, y).
def _l0():
    c = {"L0_c_nw": (400, 700, "h"), "L0_c_w_n": (470, 740, "v"), "L0_c_w_a": (470, 820, "v"),
         "L0_c_w_e": (470, 890, "v"), "L0_c_w_b": (470, 980, "v"), "L0_c_w_c": (470, 1060, "v"),
         "L0_c_w_d": (470, 1130, "v"), "L0_c_elev": (430, 1215, "h"), "L0_c_br_a": (580, 1140, "h"),
         "L0_c_c_n": (745, 925, "v"), "L0_c_c_j1": (745, 1030, "v"), "L0_c_c_s5": (745, 1090, "v"),
         "L0_c_c_j2": (745, 1140, "v"), "L0_c_c_s": (750, 1205, "v"), "L0_c_c_s4": (750, 1270, "v"),
         "L0_c_e_a": (880, 1030, "h"), "L0_c_e_b": (1000, 1030, "h"), "L0_c_e_c": (990, 1190, "v"),
         "L0_c_e_d": (990, 1270, "v")}
    f = {"stair_1_L0": (280, 640), "stair_2_L0": (395, 1290), "stair_3_L0": (535, 1305),
         "stair_4_L0": (735, 1300), "stair_5_L0": (700, 1090), "stair_6_L0": (990, 1300),
         "elev_1_L0": (380, 1197), "elev_2_L0": (380, 1232),
         "exit_L0_W": (335, 700), "exit_L0_E": (520, 885), "exit_L0_N": (745, 880),
         "exit_L0_SW": (470, 1250), "exit_L0_S4": (750, 1360), "exit_L0_S6": (995, 1360)}
    return {k: _l1(*v[:2]) + v[2:] for k, v in c.items()}, {k: _l1(*v) for k, v in f.items()}


def _l1_floor():
    c = {"L1_c_nw": (350, 560, "h"), "L1_c_n_mid": (580, 555, "h"), "L1_c_ne": (705, 555, "h"),
         "L1_c_w_upper": (470, 620, "v"), "L1_c_w_mid": (470, 780, "v"), "L1_c_w_cross": (470, 940, "v"),
         "L1_c_w_south": (470, 1070, "v"), "L1_c_elev": (420, 1150, "h"), "L1_c_s_west": (560, 1160, "h"),
         "L1_c_s_mid": (800, 1160, "h"), "L1_c_e_south": (1020, 1160, "v"), "L1_c_e_cross": (1020, 940, "v"),
         "L1_c_e_north": (1020, 800, "v"), "L1_c_cross_mid": (780, 940, "h"), "L1_c_spur": (790, 1050, "v")}
    f = {"stair_1_L1": (250, 520), "stair_2_L1": (390, 1260), "stair_3_L1": (595, 1270),
         "stair_5_L1": (740, 1000), "elev_1_L1": (370, 1130), "elev_2_L1": (370, 1175),
         "exit_L1_W": (320, 565), "exit_L1_E": (765, 560), "exit_L1_N": (1020, 740), "exit_L1_S": (445, 1235)}
    return {k: _l1(*v[:2]) + v[2:] for k, v in c.items()}, {k: _l1(*v) for k, v in f.items()}


def _l2_floor():
    c = {"L2_z_nw": (340, 540), "L2_z_n": (617, 530), "L2_z_ne": (900, 580), "L2_z_e": (1115, 680),
         "L2_z_center": (500, 800), "L2_z_stair5": (560, 940), "L2_z_south": (500, 1300), "L2_z_wpass": (290, 860)}
    f = {"stair_2_L2": (275, 520), "stair_3_L2": (260, 750), "stair_5_L2": (545, 880), "stair_1_L2": (1085, 380),
         "elev_1_L2": (415, 505), "elev_2_L2": (370, 505)}
    return {k: _l2(*v) + ("v",) for k, v in c.items()}, {k: _l2(*v) for k, v in f.items()}


def _ring(n):
    """L3-L6: one ring corridor, drawn north-up. Ids keep poster page directions: c_n_* is the WEST
    corridor, c_e_* the NORTH corridor, c_s_* the EAST corridor, c_w_* the SOUTH corridor."""
    p = "L%d_c_" % n
    c = {p + "nw_lobby": (60, 60, "h"), p + "n_mid": (60, 400, "v"), p + "n_e": (60, 740, "v"),
         p + "e_n": (230, 740, "h"), p + "e_mid": (470, 740, "h"), p + "e_s": (800, 740, "h"),
         p + "s_e": (800, 560, "v"), p + "s_stair": (800, 400, "v"), p + "s_mid": (800, 240, "v"),
         p + "s_w": (800, 60, "v"), p + "w_s": (640, 60, "h"), p + "w_mid": (440, 60, "h"),
         p + "w_n": (240, 60, "h")}
    f = {"stair_2_L%d" % n: (60, -70), "stair_5_L%d" % n: (890, 400),
         "elev_1_L%d" % n: (-60, 210), "elev_2_L%d" % n: (-60, 140)}
    return c, f


def skeleton(floor):
    if floor == "L0":
        return _l0()
    if floor == "L1":
        return _l1_floor()
    if floor == "L2":
        return _l2_floor()
    return _ring(int(floor[1:]))


class Layout:
    def __init__(self, building=None):
        self.b = building or graph.Building()
        self.pos = {}
        self.axis = {}
        self.sizes = {}          # node id -> (w, h) of the rectangle drawn for it
        self.floors = [f for f in graph.FLOOR_ORDER]
        for f in self.floors:
            self._place_floor(f)

    def _nodes_of(self, floor):
        return [i for i, n in self.b.nodes.items() if n.get("floor") == floor]

    def _place_floor(self, floor):
        corr, fixed = skeleton(floor)
        ids = set(self._nodes_of(floor))
        for i, v in corr.items():
            if i in ids:
                self.pos[i] = (v[0], v[1])
                self.axis[i] = v[2]
        for i, v in fixed.items():
            if i in ids:
                self.pos[i] = v
        # rooms and restrooms: fan out beside the corridor they attach to
        parents = {}
        for a, c, kind in _edges(self.b):
            for r, p in ((a, c), (c, a)):
                if r in ids and self.b.nodes[r]["type"] in ("room", "restroom") and p in self.pos:
                    parents.setdefault(r, []).append(p)
        placed = self._slot_assign(floor, parents)
        parents = {r: ps for r, ps in parents.items() if r not in placed}
        by_parent = {}
        multi = []
        for r, ps in parents.items():
            if len(set(ps)) > 1:
                multi.append((r, sorted(set(ps))))
            else:
                by_parent.setdefault(ps[0], []).append(r)
        anchors = [self.pos[i] for i in corr if i in self.pos]
        if not anchors:
            anchors = [(0, 0)]
        cx = sum(a[0] for a in anchors) / len(anchors)
        cy = sum(a[1] for a in anchors) / len(anchors)
        rects = {}
        for p, rooms in by_parent.items():
            rooms.sort(key=_natural)
            px, py = self.pos[p]
            axis = self.axis.get(p, "v")
            if axis == "v":     # corridor runs north-south, rooms stack east/west of it
                outer = 1 if px >= cx else -1
                off, pitch = ROOM_W / 2 + 14, ROOM_H + GAP
            else:               # corridor runs east-west, rooms line up north/south of it
                outer = 1 if py >= cy else -1
                off, pitch = ROOM_H / 2 + 14, ROOM_W + GAP
            sides = {0: [], 1: []}
            for k, r in enumerate(rooms):
                sides[k % 2].append(r)
            shift = self._dead_end_shift(p, axis, max(len(g) for g in sides.values()) * pitch)
            for s, group in sides.items():
                sign = outer if s == 0 else -outer
                for j, r in enumerate(group):
                    t = (j - (len(group) - 1) / 2) * pitch + shift
                    rects[r] = (px + sign * off, py + t) if axis == "v" else (px + t, py + sign * off)
        for r, ps in multi:     # a room that spans several corridor nodes sits between them
            rects[r] = (sum(self.pos[p][0] for p in ps) / len(ps) - ROOM_W, sum(self.pos[p][1] for p in ps) / len(ps))
        if rects:
            self._relax(rects, floor, list(placed.values()))
        rects.update(placed)
        self.pos.update(rects)
        for r in rects:
            self.sizes[r] = (ROOM_W, ROOM_H)

    def _slot_assign(self, floor, parents):
        """Seat rooms in slots along the corridors, on both sides, nearest slot to the room's corridor first."""
        ids = set(self._nodes_of(floor))
        segs = []
        deg = {}
        for a, c, kind in _edges(self.b):
            if kind in ("corridor", "open") and a in self.pos and c in self.pos and a in ids and c in ids:
                segs.append((a, c))
                deg[a] = deg.get(a, 0) + 1
                deg[c] = deg.get(c, 0) + 1
        lines = [(self.pos[a], self.pos[c]) for a, c in segs]
        points = [self.pos[i] for i in ids if i in self.pos and self.b.nodes[i]["type"] in ("stair", "elevator", "exit")]

        def support(nx, ny):
            return abs(nx) * ROOM_W / 2 + abs(ny) * ROOM_H / 2

        def clear(cx, cy, own):
            for k, ((x1, y1), (x2, y2)) in enumerate(lines):
                if k == own:
                    continue
                dx, dy = x2 - x1, y2 - y1
                L2 = dx * dx + dy * dy
                t = max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / L2)) if L2 else 0
                vx, vy = cx - (x1 + t * dx), cy - (y1 + t * dy)
                d = math.hypot(vx, vy) or 1e-6
                if d < support(vx / d, vy / d) + 12:
                    return False
            for px, py in points:
                vx, vy = cx - px, cy - py
                d = math.hypot(vx, vy) or 1e-6
                if d < support(vx / d, vy / d) + 14:
                    return False
            return True

        slots = []
        for k, ((x1, y1), (x2, y2)) in enumerate(lines):
            L = math.hypot(x2 - x1, y2 - y1)
            if L < 1:
                continue
            ux, uy = (x2 - x1) / L, (y2 - y1) / L
            pitch = abs(ux) * (ROOM_W + GAP) + abs(uy) * (ROOM_H + GAP)
            count = max(1, int(L // pitch))
            for sgn in (1, -1):
                nx, ny = -uy * sgn, ux * sgn
                for row in range(ROWS):
                    off = support(nx, ny) + 14 + row * (2 * support(nx, ny) + GAP)
                    for j in range(count):
                        t = L / 2 + (j - (count - 1) / 2) * pitch
                        sx, sy = x1 + ux * t + nx * off, y1 + uy * t + ny * off
                        if clear(sx, sy, k):
                            slots.append((sx, sy, row))
            for node, (ex, ey), out in ((segs[k][0], (x1, y1), (-ux, -uy)), (segs[k][1], (x2, y2), (ux, uy))):
                if deg[node] == 1:      # dead end: one seat at the end of the corridor
                    along = support(out[0], out[1]) + 14
                    sx, sy = ex + out[0] * along, ey + out[1] * along
                    if clear(sx, sy, k):
                        slots.append((sx, sy, 0))
        want = {}
        for r, ps in parents.items():
            ps = sorted(set(ps))
            want[r] = (sum(self.pos[p][0] for p in ps) / len(ps), sum(self.pos[p][1] for p in ps) / len(ps), tuple(ps))
        pairs = sorted((math.hypot(sx - want[r][0], sy - want[r][1]) + 25 * row, _natural(r), si)
                       for r in want for si, (sx, sy, row) in enumerate(slots))
        taken, got = [], {}
        hw, hh = ROOM_W / 2 + 2, ROOM_H / 2 + 2
        for _, nat, si in pairs:
            r = next(rr for rr in want if _natural(rr) == nat)
            if r in got:
                continue
            sx, sy, _row = slots[si]
            if any(abs(sx - tx) < 2 * hw and abs(sy - ty) < 2 * hh for tx, ty in taken):
                continue
            got[r] = (sx, sy)
            taken.append((sx, sy))
        # rooms of one corridor node: keep room numbers in order along the corridor
        groups = {}
        for r, pos in got.items():
            groups.setdefault(want[r][2], []).append(r)
        for ps, rs in groups.items():
            axis = self.axis.get(ps[0], "v")
            seats = sorted((got[r] for r in rs), key=(lambda q: (-q[1], q[0])) if axis == "v" else (lambda q: (q[0], -q[1])))
            for r, q in zip(sorted(rs, key=_natural), seats):
                got[r] = q
        return got

    def _dead_end_shift(self, node, axis, run):
        """A corridor that ends at this node has nothing beyond it: slide the run of rooms back along it."""
        x, y = self.pos[node]
        ahead = behind = False
        for a, c, kind in _edges(self.b):
            if kind in ("corridor", "open") and node in (a, c):
                o = c if a == node else a
                if o in self.pos:
                    d = (self.pos[o][1] - y) if axis == "v" else (self.pos[o][0] - x)
                    if d > 10:
                        ahead = True
                    elif d < -10:
                        behind = True
        slack = max(run / 2 - layout_pitch(axis) / 2, 0)
        if ahead and not behind:
            return slack
        if behind and not ahead:
            return -slack
        return 0

    def _relax(self, rects, floor, fixed_rects=()):
        """Push rooms apart from each other and off corridors and fixed nodes, keeping them near home."""
        home = dict(rects)
        ids = [i for i in self._nodes_of(floor) if i in self.pos and i not in rects]
        # obstacles: corridor segments, and fixed nodes as zero-length segments
        segs = [(self.pos[i], self.pos[i]) for i in ids]
        for a, c, kind in _edges(self.b):
            if a in self.pos and c in self.pos and a not in rects and c not in rects                     and self.b.nodes[a].get("floor") == floor and self.b.nodes[c].get("floor") == floor                     and kind in ("corridor", "open"):
                segs.append((self.pos[a], self.pos[c]))
        order = sorted(rects, key=_natural)
        hw, hh = ROOM_W / 2 + 4, ROOM_H / 2 + 4
        for _ in range(150):
            moved = False
            for i, a in enumerate(order):
                ax, ay = rects[a]
                for b_ in order[i + 1:]:
                    bx, by = rects[b_]
                    ox, oy = 2 * hw - abs(ax - bx), 2 * hh - abs(ay - by)
                    if ox > 0 and oy > 0:
                        if ox < oy:
                            sgn = 1 if ax >= bx else -1
                            rects[a] = (ax + sgn * ox / 2, ay)
                            rects[b_] = (bx - sgn * ox / 2, by)
                        else:
                            sgn = 1 if ay >= by else -1
                            rects[a] = (ax, ay + sgn * oy / 2)
                            rects[b_] = (bx, by - sgn * oy / 2)
                        ax, ay = rects[a]
                        moved = True
            for a in order:
                ax, ay = rects[a]
                for fx, fy in fixed_rects:
                    ox, oy = 2 * hw - abs(ax - fx), 2 * hh - abs(ay - fy)
                    if ox > 0 and oy > 0:
                        if ox < oy:
                            ax += (1 if ax >= fx else -1) * ox
                        else:
                            ay += (1 if ay >= fy else -1) * oy
                        moved = True
                rects[a] = (ax, ay)
            for a in order:
                x, y = rects[a]
                for (x1, y1), (x2, y2) in segs:
                    dx, dy = x2 - x1, y2 - y1
                    L2 = dx * dx + dy * dy
                    t = 0 if L2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
                    qx, qy = x1 + t * dx, y1 + t * dy
                    vx, vy = x - qx, y - qy
                    dist = math.hypot(vx, vy)
                    if dist < 1e-6:     # centre exactly on the line: step off sideways
                        n = math.hypot(dx, dy) or 1
                        vx, vy, dist = -dy / n, dx / n, 1.0
                    nx, ny = vx / dist, vy / dist
                    need = abs(nx) * ROOM_W / 2 + abs(ny) * ROOM_H / 2 + (14 if L2 else 18)
                    if dist < need:
                        x += nx * (need - dist)
                        y += ny * (need - dist)
                        moved = True
                rects[a] = (x, y)
            if not moved:
                break
            for a in order:      # weak pull back to the starting spot
                hx, hy = home[a]
                x, y = rects[a]
                rects[a] = (x + (hx - x) * 0.02, y + (hy - y) * 0.02)

    def bounds(self, floor, pad=None):
        pad = pad if pad is not None else (190 if floor == "L2" else 90)
        pts = [self.pos[i] for i in self._nodes_of(floor) if i in self.pos]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad


def layout_pitch(axis):
    return ROOM_H + GAP if axis == "v" else ROOM_W + GAP


def _natural(s):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def _edges(b):
    """(a, b, kind) for every edge in the building, assembly edges included (callers filter by floor)."""
    return [(e["from"], e["to"], e["kind"]) for e in b.edges]
