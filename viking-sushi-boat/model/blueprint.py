"""
Viking boat skeleton - CNC BLUEPRINT (v2 geometry).

Corrections over the first skeleton design:
  1. Flat bottom: side edges are smooth rounded curves (pointed lens),
     not a hard-cornered hexagon.
  2. Ribs graded: the centre rib is the longest, widths follow the
     bottom outline toward bow and stern.
  3. Dragon head redrawn in the Urnes style of the reference image:
     flame crest, long swept horn, hooked snout, fang, curled jaw barb,
     almond eye cutout.
  4. Tail volute is a continuous tapering spiral band (koru) - smooth
     negative space between windings, no rim gap.

Outputs (run this file):
  blueprints/sheet1_bottom.png     dimensioned plan of the bottom plate
  blueprints/sheet2_spine.png      dimensioned keel-spine profile
  blueprints/sheet3_ribs.png       dimensioned rib family (3 unique)
  blueprints/sheet4_assembly.png   assembly views, joints and notes
  cnc/*.dxf                        cut-ready profiles (mm, dogboned)

All dimensions in millimetres.  Stock: 12 mm plate.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, Point, box as sbox
from shapely.ops import unary_union

# ----------------------------------------------------------------- params --
T = 12.0
FIT = 0.4
SLOT_W = T + FIT              # 12.4
TOOL_D = 6.0
DOG_R = TOOL_D / 2 + 0.1      # dogbone relief radius

BOW_X, STERN_X = 280.0, -280.0
HALF_W = 90.0
RIB_X = [-180.0, -90.0, 0.0, 90.0, 180.0]
SPINE_TOP = 58.0
LAP_Z = 30.0                  # egg-crate meeting plane
TAB_XS = [-140.0, 0.0, 140.0]
TAB_L = 38.0
PLATE_TOP = T                 # spine & ribs stand on the plate (z = 12)

NAVY = "#16386e"
DIMC = "#a03028"

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BP = os.path.join(ROOT, "blueprints")
CNC = os.path.join(ROOT, "cnc")


# ---------------------------------------------------------------- helpers --
def bezier(p0, c0, c1, p1, n=32):
    t = np.linspace(0, 1, n)[:, None]
    p0, c0, c1, p1 = map(lambda p: np.asarray(p, float), (p0, c0, c1, p1))
    return ((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * c0
            + 3 * (1 - t) * t ** 2 * c1 + t ** 3 * p1)


def chain(*segs):
    pts = [np.asarray(segs[0], float)]
    for s in segs[1:]:
        s = np.asarray(s, float)
        if len(s) and np.allclose(pts[-1][-1], s[0], atol=1e-6):
            s = s[1:]
        if len(s):
            pts.append(s)
    return np.vstack(pts)


def poly(pts):
    p = Polygon(pts)
    return p if p.is_valid else p.buffer(0)


def dogbone_rect(x0, y0, x1, y1, corners):
    """Rect cutout with dogbone reliefs at the named corners."""
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    base = sbox(x0, y0, x1, y1)
    tags = {"ll": (x0, y0, 1, 1), "lr": (x1, y0, -1, 1),
            "ul": (x0, y1, 1, -1), "ur": (x1, y1, -1, -1)}
    if corners == "all":
        corners = tuple(tags)
    d = DOG_R / np.sqrt(2)
    discs = [Point(tags[c][0] - tags[c][2] * d,
                   tags[c][1] - tags[c][3] * d).buffer(DOG_R, 24)
             for c in corners]
    return unary_union([base] + discs)


# ======================================================= P1  BOTTOM PLATE ==
def bottom_boundary():
    """Rounded lens: pointed bow/stern, smoothly curved sides."""
    up = chain(bezier((BOW_X, 0), (180, 55), (90, HALF_W), (0, HALF_W)),
               bezier((0, HALF_W), (-90, HALF_W), (-180, 55), (STERN_X, 0)))
    dn = up[::-1].copy()
    dn[:, 1] *= -1
    return chain(up, dn)


def bottom_half_width(x):
    b = bottom_boundary()
    up = b[: len(b) // 2 + 1]
    order = np.argsort(up[:, 0])
    return float(np.interp(x, up[order, 0], up[order, 1]))


def bottom_part():
    p = poly(bottom_boundary())
    slots = [dogbone_rect(x - TAB_L / 2 - 0.2, -SLOT_W / 2,
                          x + TAB_L / 2 + 0.2, SLOT_W / 2, "all")
             for x in TAB_XS]
    return p.difference(unary_union(slots))


# ========================================================= P2  KEEL SPINE ==
def _spike(base_f, tip, base_a, pull=0.55):
    """Flame spike: both edges curved aft (Urnes style)."""
    bf, tp, ba = map(np.asarray, (base_f, tip, base_a))
    c1 = bf + (tp - bf) * pull + np.array([6, 0])
    c2 = tp + (bf - tp) * 0.2 + np.array([8, -4])
    up = bezier(bf, c1, c2, tp, 14)
    c3 = tp + (ba - tp) * 0.35 + np.array([6, 0])
    c4 = ba + (tp - ba) * 0.35 + np.array([2, 4])
    dn = bezier(tp, c3, c4, ba, 14)
    return chain(up, dn)


def dragon_path():
    """Bow: up the back of the neck, crest, horn, head, jaw, throat, down
    the leading edge to the bow point.  Head faces forward (+X)."""
    return chain(
        # back of the neck, long smooth sweep
        bezier((195, SPINE_TOP), (248, 66), (270, 92), (276, 130)),
        # three crest flames descending the neck (drawn going up)
        _spike((277, 142), (258, 163), (281, 165)),
        _spike((283, 178), (263, 202), (286, 202)),
        _spike((288, 214), (268, 240), (292, 237)),
        # long swept-back horn
        _spike((295, 249), (281, 292), (311, 270), pull=0.6),
        # brow spike
        _spike((315, 279), (311, 304), (328, 288), pull=0.5),
        # forehead and snout, dipping nose line
        bezier((328, 288), (344, 287), (356, 281), (366, 271)),
        bezier((366, 271), (384, 261), (396, 251), (402, 240)),
        # hooked, curled nose tip
        bezier((402, 240), (408, 230), (401, 221), (392, 223)),
        # upper lip back to the fang
        bezier((392, 223), (382, 226), (372, 228), (364, 229)),
        [[359, 219]], [[353, 229]],                    # fang
        [[344, 234]],                                  # gape corner
        # lower jaw sweeping out, hooked tip and barb
        bezier((344, 234), (360, 224), (374, 212), (384, 200)),
        bezier((384, 200), (391, 191), (385, 181), (374, 185)),
        [[365, 175]], [[361, 186]],                    # jaw barb
        # chin, then the big inner throat curve of the reference image
        bezier((361, 186), (348, 190), (339, 192), (333, 193)),
        bezier((333, 193), (315, 176), (302, 156), (297, 128)),
        bezier((297, 128), (288, 72), (280, 38), (279, 16)),
        [[BOW_X, T]])


def eye_cutout():
    """Almond eye slit, tilted along the snout line."""
    a, b, rot = 11.0, 4.2, np.deg2rad(28)
    t = np.linspace(0, 2 * np.pi, 40)
    x = a * np.cos(t)
    y = b * np.sin(t) * (1 + 0.35 * np.cos(t))       # pointed almond
    R = np.array([[np.cos(rot), -np.sin(rot)], [np.sin(rot), np.cos(rot)]])
    pts = (R @ np.vstack([x, y])).T + [351, 261]
    return poly(pts)


# tail volute: continuous tapering spiral band (koru)
VC = np.array([-296.0, 212.0])   # spiral centre
V_R0, V_R1 = 52.0, 11.0          # centreline radius, start -> tip
V_W0, V_W1 = 14.0, 4.0           # band half-width, start -> tip
V_SWEEP = np.deg2rad(438.0)      # total sweep
V_A0 = np.deg2rad(-90.0)         # attachment angle (bottom of the curl)

def _volute_edges(n=160):
    t = np.linspace(0, 1, n)
    ang = V_A0 + V_SWEEP * t
    r = V_R0 * (V_R1 / V_R0) ** t
    w = V_W0 + (V_W1 - V_W0) * t ** 0.8
    cx = VC[0] + r * np.cos(ang)
    cz = VC[1] + r * np.sin(ang)
    nx, nz = np.cos(ang), np.sin(ang)
    outer = np.column_stack([cx + w * nx, cz + w * nz])
    inner = np.column_stack([cx - w * nx, cz - w * nz])
    # rounded tip cap
    tipc = np.array([cx[-1], cz[-1]])
    a_end = ang[-1]
    cap_a = np.linspace(a_end - np.pi, a_end, 18)
    cap = np.column_stack([tipc[0] + w[-1] * np.cos(cap_a),
                           tipc[1] + w[-1] * np.sin(cap_a)])
    return inner, cap, outer


def volute_band():
    """The koru spiral as a standalone simple polygon (unioned onto the
    stem so winding direction can never break the outline)."""
    inner, cap, outer = _volute_edges()
    strip = chain(inner, cap, outer[::-1],
                  [[VC[0], VC[1] - (V_R0 - V_W0)]])
    return poly(strip)


def stern_path():
    """Stem only: up the leading edge into the band region, across, and
    back down the trailing edge to the stern point."""
    front = chain(
        bezier((-190, SPINE_TOP), (-230, 70), (-262, 112), (-279, 150)),
        bezier((-279, 150), (-285, 156), (-289, 158), (-293, 159)))
    back = chain(
        [[-301, 151]],
        bezier((-301, 151), (-306, 141), (-308, 134), (-308, 126)),
        bezier((-308, 126), (-306, 94), (-291, 52), (-272, 16)),
        [[STERN_X, T]])
    return chain(front, back)


def spine_part():
    outline = chain(
        [[STERN_X, T]], [[BOW_X, T]],
        dragon_path()[::-1],
        [[195, SPINE_TOP]], [[-190, SPINE_TOP]],
        stern_path())
    main = poly(outline)
    tabs = [sbox(x - TAB_L / 2, 0.0, x + TAB_L / 2, T + 1) for x in TAB_XS]
    main = unary_union([main, volute_band()] + tabs)
    slots = [dogbone_rect(x - SLOT_W / 2, LAP_Z, x + SLOT_W / 2,
                          SPINE_TOP + 4, ("ll", "lr")) for x in RIB_X]
    out = main.difference(unary_union(slots)).difference(eye_cutout())
    if out.geom_type == "MultiPolygon":       # drop boolean slivers only
        keep = max(out.geoms, key=lambda g: g.area)
        dropped = out.area - keep.area
        assert dropped < 50, f"spine lost a real piece ({dropped:.0f} mm2)"
        out = keep
    return out


# ================================================================ P3 RIBS ==
def rib_widths():
    """(station, foot half-width) - centre rib longest, graded outward."""
    return {x: bottom_half_width(x) - 8.0 for x in RIB_X}


def rib_part(wb):
    tipy, tipz = wb + 10, 62.0 + 0.32 * wb           # taller when wider
    right = chain(
        [[-wb, PLATE_TOP]], [[wb, PLATE_TOP]],
        bezier((wb, PLATE_TOP), (wb + 12, 32), (wb + 11, tipz - 26),
               (tipy - 4, tipz)),
        bezier((tipy - 4, tipz), (tipy + 2, tipz + 6), (wb - 8, tipz + 5),
               (wb - 15, tipz - 4)),
        bezier((wb - 15, tipz - 4), (wb - 11, tipz - 26), (wb - 13, 42),
               (wb - 22, 34)),
        bezier((wb - 22, 34), (wb * 0.4, 46), (-wb * 0.4, 46), (-wb + 22, 34)),
        bezier((-wb + 22, 34), (-wb + 13, 42), (-wb + 11, tipz - 26),
               (-wb + 15, tipz - 4)),
        bezier((-wb + 15, tipz - 4), (-wb + 8, tipz + 5), (-tipy - 2, tipz + 6),
               (-tipy + 4, tipz)),
        bezier((-tipy + 4, tipz), (-wb - 11, tipz - 26), (-wb - 12, 32),
               (-wb, PLATE_TOP)))
    p = poly(right)
    cuts = [dogbone_rect(-SLOT_W / 2, PLATE_TOP - 2, SLOT_W / 2, LAP_Z,
                         ("ul", "ur")),
            Point(16, PLATE_TOP).buffer(5, 20),
            Point(-16, PLATE_TOP).buffer(5, 20)]
    return p.difference(unary_union(cuts))


if __name__ == "__main__":
    ws = rib_widths()
    print("rib foot half-widths:", {k: round(v, 1) for k, v in ws.items()})
    for name, p in [("bottom", bottom_part()), ("spine", spine_part())] + \
                   [(f"rib@{x:+.0f}", rib_part(w)) for x, w in ws.items()]:
        print(f"{name:10s} {p.geom_type:12s} area={p.area:8.0f} "
              f"bounds={np.round(p.bounds, 1)}")
