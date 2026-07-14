"""
Viking boat - FLAT BOTTOM + SKELETON design (bottom, keel spine, ribs only).

Parts
  P1  Flat bottom  - elongated hexagon: pointed bow & stern, straight
                     parallel sides amidships (12 mm plate, lies flat)
  P2  Keel spine   - one long vertical plate, bow-to-stern, with an
                     integrated 2D-extruded dragon head (bow) and spiral
                     tail volute (stern); 3 tabs drop into the bottom
  P3..P7 Ribs (x5) - separate frame parts (floor timbers), each cross-laps
                     over the spine (egg-crate half-lap) and stands on the
                     flat bottom.  Limber holes beside the keel, like the
                     Skuldelev construction drawing.

  X bow +, Y port +, Z up.  Bottom plate: z 0..12.  All stock 12 mm.
"""
import numpy as np
import trimesh
from trimesh.creation import extrude_polygon
from shapely.geometry import Polygon, Point, box as sbox
from shapely.ops import unary_union

T = 12.0                 # stock thickness
FIT = 0.4
SLOT_W = T + FIT

BOW_X, STERN_X = 280.0, -280.0
PAR_X, HALF_W = 90.0, 90.0        # parallel section |x|<=90, half width 90
RIB_X = [-180.0, -90.0, 0.0, 90.0, 180.0]
SPINE_TOP = 58.0
LAP_Z = 30.0             # egg-crate meeting plane
TAB_XS = [-140.0, 0.0, 140.0]


# ------------------------------------------------------------------ helpers
def bezier(p0, c0, c1, p1, n=26):
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


def spiral(cx, cy, r0, r1, a0, a1, n=110):
    t = np.linspace(0, 1, n)
    a = a0 + (a1 - a0) * t
    r = r0 + (r1 - r0) * t
    return np.column_stack([cx + r * np.cos(a), cy + r * np.sin(a)])


def poly(pts):
    p = Polygon(pts)
    return p if p.is_valid else p.buffer(0)


def biggest(p):
    """Largest polygon of a (Multi)Polygon - drops boolean slivers."""
    if p.geom_type == "MultiPolygon":
        return max(p.geoms, key=lambda g: g.area)
    return p


def subdiv(m, size=8.0):
    try:
        m = m.subdivide_to_size(max_edge=size, max_iter=10)
    except BaseException:
        pass
    m.fix_normals()
    return m


def place_xz(mesh, y_out):
    """Extruded XY mesh -> part drawn in (x,z), thickness towards -Y."""
    M = np.array([[1, 0, 0, 0], [0, 0, -1, y_out], [0, 1, 0, 0],
                  [0, 0, 0, 1]], float)
    mesh.apply_transform(M)
    return mesh


def place_yz(mesh, x0):
    """Extruded XY mesh -> part drawn in (y,z), thickness towards +X."""
    M = np.array([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0],
                  [0, 0, 0, 1]], float)
    mesh.apply_transform(M)
    return mesh


def bottom_half_width(x):
    """Half width of the hexagonal bottom at station x."""
    ax = abs(x)
    if ax <= PAR_X:
        return HALF_W
    return HALF_W * max(0.0, (BOW_X - ax)) / (BOW_X - PAR_X)


# =================================================== P1  FLAT BOTTOM PANEL
def bottom_outline():
    return poly([(BOW_X, 0), (PAR_X, HALF_W), (-PAR_X, HALF_W),
                 (STERN_X, 0), (-PAR_X, -HALF_W), (PAR_X, -HALF_W)])


def build_bottom():
    p = bottom_outline()
    slots = [sbox(x - 20, -SLOT_W / 2 - 0.1, x + 20, SLOT_W / 2 + 0.1)
             for x in TAB_XS]                       # spine tab slots
    p = p.difference(unary_union(slots))
    return subdiv(extrude_polygon(p, T, engine="earcut"), 6.0)   # z 0..12


# =================================================== P2  KEEL SPINE (X-Z)
def dragon_head_path():
    """Outline run: up the bow stem, around the dragon head, down again
    to the bow point of the bottom plate."""
    up = chain(
        bezier((190, SPINE_TOP), (236, 62), (258, 88), (268, 120)),
        bezier((268, 120), (278, 152), (283, 172), (290, 192)),
        # crest spikes up the back of the neck
        [[301, 196]], [[295, 208]], [[309, 213]], [[303, 225]], [[318, 228]],
        # swept-back horn
        bezier((318, 228), (316, 246), (307, 259), (294, 269)),
        bezier((294, 269), (309, 265), (319, 254), (323, 241)),
        # skull and snout
        bezier((323, 241), (335, 243), (345, 239), (352, 232)),
        bezier((352, 232), (368, 228), (381, 223), (392, 214)),
        # curled nose tip and open mouth
        bezier((392, 214), (397, 206), (393, 199), (386, 199)),
        bezier((386, 199), (376, 202), (365, 204), (356, 204)),
        [[352, 197]],
        # lower jaw with chin barb
        bezier((352, 197), (363, 196), (373, 191), (381, 184)),
        bezier((381, 184), (368, 179), (356, 177), (346, 180)),
        [[340, 170]], [[334, 179]],
        # throat, then the leading edge of the stem down to the bow point
        bezier((334, 179), (320, 164), (309, 140) , (302, 118)),
        bezier((302, 118), (295, 78), (289, 38), (281, 13)),
        [[BOW_X, T]])
    return up


def stern_tail_parts():
    """Stern post band + spiral volute disc (unioned onto the outline)."""
    band = chain(
        bezier((-190, SPINE_TOP), (-218, 64), (-230, 84), (-236, 108)),
        bezier((-236, 108), (-244, 136), (-256, 168), (-263, 200)),
        [[-283, 194]],
        bezier((-283, 194), (-282, 176), (-279, 156), (-270, 124)),
        bezier((-270, 124), (-262, 92), (-263, 54), (-272, 24)),
        [[STERN_X, T]])
    disc = Point(-291, 228).buffer(45, 72)
    groove_pts = spiral(-291, 228, 56, 9, np.deg2rad(-70), np.deg2rad(485))
    from shapely.geometry import LineString
    groove = LineString(groove_pts).buffer(5.5, 16)
    return band, disc, groove


def build_spine():
    band, disc, groove = stern_tail_parts()
    # main silhouette: stern bottom -> bow bottom along z=12, up and around
    # the dragon, back along the top edge, down around the tail
    bow = dragon_head_path()
    outline_pts = chain(
        [[STERN_X, T]], [[BOW_X, T]],           # bottom edge (on the plate)
        bow[::-1],                              # up the bow (reverse: from tip)
        [[190, SPINE_TOP]], [[-190, SPINE_TOP]],  # top edge amidships
        band)                                   # down the stern
    main = poly(outline_pts)
    main = unary_union([main, disc])
    # tabs into the bottom plate (land flush with the underside after the
    # 0.6 mm seating offset applied in assembly())
    tabs = [sbox(x - 19.0, 1.0, x + 19.0, T + 1) for x in TAB_XS]
    main = unary_union([main] + tabs)
    # rib cross-slots, open from the top edge (down to the lap plane)
    cuts = [sbox(x - SLOT_W / 2, LAP_Z, x + SLOT_W / 2, SPINE_TOP + 4)
            for x in RIB_X]
    cuts.append(Point(348, 216).buffer(4.5, 24))          # dragon eye
    main = biggest(main.difference(unary_union(cuts)).difference(groove))
    mesh = subdiv(extrude_polygon(main, T, engine="earcut"))
    return place_xz(mesh, y_out=T / 2)


# =================================================== P3..P7  RIBS (Y-Z)
def rib_outline(wb):
    """Floor-timber style frame: flat foot, arched top, up-swept arms."""
    tipy, tipz = wb + 10, 88.0
    right = chain(
        [[-wb, T]], [[wb, T]],
        bezier((wb, T), (wb + 12, 32), (wb + 11, 62), (tipy - 4, tipz)),
        bezier((tipy - 4, tipz), (tipy + 2, 94), (wb - 8, 93), (wb - 15, 84)),
        bezier((wb - 15, 84), (wb - 11, 60), (wb - 13, 42), (wb - 22, 34)),
        bezier((wb - 22, 34), (wb * 0.4, 46), (-wb * 0.4, 46), (-wb + 22, 34)),
        bezier((-wb + 22, 34), (-wb + 13, 42), (-wb + 11, 60), (-wb + 15, 84)),
        bezier((-wb + 15, 84), (-wb + 8, 93), (-tipy - 2, 94), (-tipy + 4, tipz)),
        bezier((-tipy + 4, tipz), (-wb - 11, 62), (-wb - 12, 32), (-wb, T)))
    p = poly(right)
    cuts = [sbox(-SLOT_W / 2, T - 2, SLOT_W / 2, LAP_Z),   # keel half-lap
            Point(16, T).buffer(5, 20),                    # limber holes
            Point(-16, T).buffer(5, 20)]
    return p.difference(unary_union(cuts))


def build_ribs():
    out = []
    for x in RIB_X:
        wb = bottom_half_width(x) - 8.0
        mesh = subdiv(extrude_polygon(rib_outline(wb), T, engine="earcut"))
        out.append(place_yz(mesh, x0=x - T / 2))
    return out


# ------------------------------------------------------------------ colors
BOTTOM_C = (0.80, 0.66, 0.44)     # maple plate
SPINE_C = (0.38, 0.24, 0.13)      # dark walnut spine
RIB_C = (0.58, 0.42, 0.24)        # oak ribs


def assembly(explode=0.0):
    """explode: 0 = assembled; >0 lifts spine by e, ribs by 2.2e."""
    parts = [(build_bottom(), BOTTOM_C)]
    seat = -1.0                      # sink parts slightly into the plate to
    sp = build_spine()               # avoid coplanar-face render artifacts
    sp.apply_translation((0, 0, seat + explode))
    parts.append((sp, SPINE_C))
    for r in build_ribs():
        r.apply_translation((0, 0, seat + 2.2 * explode))
        parts.append((r, RIB_C))
    return parts


def parts_flat():
    """Every part laid flat, as cut from the sheet."""
    out = [(build_bottom(), BOTTOM_C)]                     # already flat
    band, disc, groove = stern_tail_parts()
    # spine flat: rebuild the 2D silhouette and extrude in place
    bow = dragon_head_path()
    main = poly(chain([[STERN_X, T]], [[BOW_X, T]], bow[::-1],
                      [[190, SPINE_TOP]], [[-190, SPINE_TOP]], band))
    main = unary_union([main, disc]
                       + [sbox(x - 19.8, -1.0, x + 19.8, T + 1) for x in TAB_XS])
    main = biggest(main.difference(unary_union(
        [sbox(x - SLOT_W / 2, LAP_Z, x + SLOT_W / 2, SPINE_TOP + 4)
         for x in RIB_X] + [Point(348, 216).buffer(4.5, 24)])).difference(groove))
    sp = subdiv(extrude_polygon(main, T, engine="earcut"))
    sp.apply_translation((0, 160, 0))                      # park above bottom
    out.append((sp, SPINE_C))
    u = -150.0
    for x in RIB_X:
        wb = bottom_half_width(x) - 8.0
        m = subdiv(extrude_polygon(rib_outline(wb), T, engine="earcut"))
        m.apply_translation((u + wb + 10, -170, 0))
        u += 2 * (wb + 10) + 26
        out.append((m, RIB_C))
    return out


if __name__ == "__main__":
    for m, _ in assembly():
        pass
    print("skeleton parts:", len(assembly()), "(1 bottom, 1 spine, 5 ribs)")
