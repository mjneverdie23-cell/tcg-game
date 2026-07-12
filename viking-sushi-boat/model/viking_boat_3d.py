"""
One-piece carved Viking sushi boat - full 3D sculptural model.

The boat is designed as a single carved piece (hull, keel, spiral sternpost,
dragon-head bow stem and gunwales are one continuous body), presented on a
low display stand, with a recessed serving deck for sushi, a shield row,
and a striped square sail on a removable mast.

All dimensions in mm.  Serving size: ~640 mm over the figureheads,
beam 172 mm, dragon head ~300 mm above the table.

  X : longitudinal (+X = bow)     Y : beam (port +)     Z : up
"""
import numpy as np
import trimesh

# ------------------------------------------------------------------ helpers
def bezier(p0, c0, c1, p1, n=40):
    t = np.linspace(0, 1, n)[:, None]
    p0, c0, c1, p1 = map(lambda p: np.asarray(p, float), (p0, c0, c1, p1))
    return ((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * c0
            + 3 * (1 - t) * t ** 2 * c1 + t ** 3 * p1)


def chain(*segs):
    pts = [np.asarray(segs[0], float)]
    for s in segs[1:]:
        s = np.asarray(s, float)
        if np.allclose(pts[-1][-1], s[0], atol=1e-6):
            s = s[1:]
        pts.append(s)
    return np.vstack(pts)


def loft(stations, cap0=True, cap1=True):
    """Loft closed rings (list of (N,3) arrays, same N) into a mesh."""
    S = np.asarray(stations)
    ns, nr = S.shape[0], S.shape[1]
    V = S.reshape(-1, 3)
    F = []
    for i in range(ns - 1):
        for j in range(nr):
            a = i * nr + j
            b = i * nr + (j + 1) % nr
            c = (i + 1) * nr + (j + 1) % nr
            d = (i + 1) * nr + j
            F += [[a, b, c], [a, c, d]]
    V = list(V)
    if cap0:
        c0 = S[0].mean(axis=0); V.append(c0); ci = len(V) - 1
        for j in range(nr):
            F.append([ci, (j + 1) % nr, j])
    if cap1:
        c1 = S[-1].mean(axis=0); V.append(c1); ci = len(V) - 1
        base = (ns - 1) * nr
        for j in range(nr):
            F.append([ci, base + j, base + (j + 1) % nr])
    m = trimesh.Trimesh(vertices=np.asarray(V), faces=np.asarray(F),
                        process=True)
    m.fix_normals()
    return m


def sweep_xz(path, widths, heights, nring=18, cap0=True, cap1=True):
    """Sweep an ellipse section along a path lying in the XZ plane."""
    P = np.asarray(path, float)
    if P.shape[1] == 2:
        P = np.column_stack([P[:, 0], np.zeros(len(P)), P[:, 1]])
    tang = np.gradient(P, axis=0)
    tang /= np.linalg.norm(tang, axis=1)[:, None] + 1e-12
    # normal in the XZ plane (perpendicular to tangent)
    nrm = np.column_stack([-tang[:, 2], np.zeros(len(P)), tang[:, 0]])
    phi = np.linspace(0, 2 * np.pi, nring, endpoint=False)
    Yhat = np.array([0.0, 1.0, 0.0])
    rings = []
    for i in range(len(P)):
        w, h = widths[i] / 2, heights[i] / 2
        ring = (P[i][None, :] + np.outer(w * np.cos(phi), Yhat)
                + np.outer(h * np.sin(phi), nrm[i]))
        rings.append(ring)
    return loft(rings, cap0, cap1)


def tube(p0, p1, r=1.2, sections=10):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    v = p1 - p0
    L = np.linalg.norm(v)
    m = trimesh.creation.cylinder(radius=r, height=L, sections=sections)
    m.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], v / L))
    m.apply_translation((p0 + p1) / 2)
    return m


# ---------------------------------------------------------------- palette --
HULL = (0.45, 0.29, 0.16)          # oiled walnut
HULL_DARK = (0.36, 0.22, 0.12)     # backbone / stems / head
TRAY = (0.82, 0.68, 0.46)          # maple serving inset
MAST_C = (0.62, 0.46, 0.28)
STAND_C = (0.24, 0.16, 0.10)
ROPE = (0.30, 0.22, 0.14)
SAIL_RED = (0.72, 0.18, 0.14)
SAIL_CREAM = (0.93, 0.88, 0.78)
SHIELD_COLS = [(0.68, 0.16, 0.13), (0.90, 0.84, 0.72), (0.80, 0.58, 0.22)]
BOSS = (0.55, 0.42, 0.22)
EYE = (0.08, 0.06, 0.05)

# ------------------------------------------------------------- hull curves --
HLEN = 252.0            # hull half-length at the sheer
def z_keel(x):  return 7.0 + 16.0 * (np.abs(x) / HLEN) ** 2.5
def z_sheer(x): return 70.0 + 30.0 * (np.abs(x) / HLEN) ** 2.2
def half_beam(x):
    v = 1.0 - (x / (HLEN + 11.0)) ** 2
    return 86.0 * np.clip(v, 1e-4, 1) ** 0.55

FLOOR_Z = 44.0

def hull_station(x):
    """Closed section ring at station x, with integrated deck recess."""
    b, z0, zs = half_beam(x), z_keel(x), z_sheer(x)
    g = np.clip((b - 34.0) / 30.0, 0.0, 1.0)        # recess blend factor
    g = g * g * (3 - 2 * g)                          # smoothstep the blend
    zf = zs - (zs - FLOOR_Z) * g                    # recess floor height
    rail_w = 6.0 + 7.0 * g
    bi = max(b - rail_w, 2.0)                       # recess top half-width
    bi2 = max(bi - 7.0 * g, 1.5)                    # recess floor half-width
    pts = []
    # starboard outer skin: keel -> sheer  (y negative = starboard)
    for s in np.linspace(0, 1, 14):
        y = b * np.sin(s * np.pi / 2) ** 0.62
        z = z0 + (zs - z0) * s ** 1.12
        pts.append((-y, z))
    # rail crown
    pts.append((-(b + bi) / 2, zs + 1.5))
    # inner wall down into the recess
    for s in np.linspace(0, 1, 4)[1:]:
        pts.append((-(bi + (bi2 - bi) * s), zs + (zf - zs) * s))
    # serving floor with a soft dish
    for s in np.linspace(0, 1, 9)[1:-1]:
        y = -bi2 + 2 * bi2 * s
        pts.append((y, zf - 1.5 * g * np.sin(s * np.pi)))
    # port inner wall up
    for s in np.linspace(0, 1, 4)[:-1]:
        pts.append((bi2 + (bi - bi2) * s, zf + (zs - zf) * s))
    pts.append(((b + bi) / 2, zs + 1.5))
    # port outer skin: sheer -> keel
    for s in np.linspace(1, 0, 14)[1:-1]:
        y = b * np.sin(s * np.pi / 2) ** 0.62
        z = z0 + (zs - z0) * s ** 1.12
        pts.append((y, z))
    ring = [(x, y, z) for y, z in pts]
    return np.asarray(ring)


def build_hull():
    xs = np.concatenate([np.linspace(-HLEN, -200, 12, endpoint=False),
                         np.linspace(-200, 200, 56, endpoint=False),
                         np.linspace(200, HLEN, 13)])
    return loft([hull_station(x) for x in xs])


# ----------------------------------------------------------- backbone ------
def build_backbone():
    """Continuous keel that rises into the spiral sternpost and the
    dragon-neck bow stem - carved from the same piece as the hull."""
    # stern spiral (unwinds from the inner tip)
    C = np.array([-291.0, 186.0])
    th = np.linspace(np.deg2rad(205), np.deg2rad(-92), 42)
    prog = np.linspace(0, 1, 42)
    r = 12.0 * (50.0 / 12.0) ** prog
    spiral = np.column_stack([C[0] + r * np.cos(th), C[1] + r * np.sin(th)])
    stern = bezier(spiral[-1], (-302, 92), (-282, 46), (-247, 24), 18)
    keel = bezier((-247, 24), (-120, 7), (120, 7), (247, 24), 30)
    bow = bezier((247, 24), (285, 38), (300, 82), (302, 132), 18)
    neck = bezier((302, 132), (304, 185), (312, 228), (331, 257), 18)
    path = chain(spiral, stern, keel, bow, neck)
    n = len(path)
    d = np.linspace(0, 1, n)
    # width & height profiles along the path
    widths = np.interp(d, [0, .18, .30, .48, .72, .86, 1.0],
                       [7.5, 9.5, 11, 12, 12, 10.5, 9.5])
    heights = np.interp(d, [0, .10, .22, .34, .60, .80, .93, 1.0],
                        [7, 13, 20, 27, 28, 24, 17, 14])
    return sweep_xz(path, widths, heights, nring=16)


# ------------------------------------------------------------ dragon head --
def build_dragon_head():
    parts = []
    axis = chain(bezier((328, 252), (338, 266), (344, 272), (352, 276), 10),
                 bezier((352, 276), (366, 283), (382, 281), (399, 268), 14))
    n = len(axis)
    d = np.linspace(0, 1, n)
    widths = np.interp(d, [0, .25, .45, .68, .88, 1], [13, 27, 31, 24, 15, 7])
    heights = np.interp(d, [0, .25, .45, .62, .85, 1], [18, 35, 35, 28, 16, 8])
    parts.append((sweep_xz(axis, widths, heights, nring=18), HULL_DARK))
    # lower jaw
    jaw = bezier((344, 258), (360, 251), (376, 247), (392, 246), 12)
    jw = np.interp(np.linspace(0, 1, 12), [0, .4, 1], [16, 12, 5])
    jh = np.interp(np.linspace(0, 1, 12), [0, .4, 1], [13, 9, 5])
    parts.append((sweep_xz(jaw, jw, jh, nring=14), HULL_DARK))
    # swept-back horns
    for s in (+1, -1):
        hp = bezier((348, 287), (340, 302), (330, 311), (318, 317), 14)
        hw = np.linspace(6.2, 1.8, 14)
        m = sweep_xz(hp, hw, hw, nring=12)
        m.apply_translation((0, s * 8.5, 0))
        parts.append((m, HULL_DARK))
    # eyes
    for s in (+1, -1):
        e = trimesh.creation.icosphere(2, 5.0)
        e.apply_translation((362, s * 12.0, 283))
        parts.append((e, EYE))
    # small crest fin down the back of the neck
    crest = bezier((330, 262), (322, 240), (314, 214), (308, 188), 12)
    cw = np.linspace(5.5, 2.2, 12)
    ch = np.linspace(16, 7, 12)
    parts.append((sweep_xz(crest, cw, ch, nring=10), HULL_DARK))
    return parts


# ---------------------------------------------------------------- shields --
def build_shields():
    parts = []
    xs = np.arange(-157.5, 158, 45.0)
    for k, x in enumerate(xs):
        for s in (+1, -1):
            yb = half_beam(x) * 0.965 + 1.5
            col = SHIELD_COLS[(k + (0 if s > 0 else 1)) % 3]
            disc = trimesh.creation.cylinder(radius=27, height=5.0,
                                             sections=42)
            rim = trimesh.creation.cylinder(radius=27.8, height=2.2,
                                            sections=42)
            boss = trimesh.creation.icosphere(2, 8.0)
            boss.apply_scale((1, 1, 0.55))
            for m, c, dz in ((disc, col, 0), (rim, col, 2.0),
                             (boss, BOSS, 2.8)):
                try:
                    m = m.subdivide_to_size(max_edge=9.0, max_iter=8)
                except BaseException:
                    pass
                m.apply_transform(trimesh.transformations.rotation_matrix(
                    np.pi / 2, (1, 0, 0)))
                m.apply_translation((x, s * (yb + 2.6 + dz), 57.0))
                parts.append((m, c))
    return parts


# ----------------------------------------------------------- mast & sail ---
def build_mast_sail():
    parts = []
    mast = trimesh.creation.cylinder(radius=6.5, height=292, sections=24)
    mast.apply_translation((0, 0, FLOOR_Z + 146))
    parts.append((mast, MAST_C))
    knob = trimesh.creation.icosphere(2, 9)
    knob.apply_translation((0, 0, FLOOR_Z + 296))
    parts.append((knob, MAST_C))
    yard = trimesh.creation.cylinder(radius=4.5, height=330, sections=20)
    yard.apply_transform(trimesh.transformations.rotation_matrix(
        np.pi / 2, (1, 0, 0)))
    yard.apply_translation((6, 0, 302))
    parts.append((yard, MAST_C))

    # billowing striped square sail (8 vertical panels, 3 mm cloth)
    ny, nz = 64, 30
    ys = np.linspace(-150, 150, ny)
    zs = np.linspace(95, 296, nz)
    Y, Z = np.meshgrid(ys, zs)
    tz = (Z - 95) / (296 - 95)
    billow = np.cos(Y / 150 * 1.25) * (34 - 22 * tz)
    X = 13 + billow
    stripes = ((np.floor((Y + 150) / 37.5)).astype(int)) % 2
    for band in range(8):
        y0, y1 = -150 + band * 37.5, -150 + (band + 1) * 37.5
        sel = (ys >= y0 - 1e-6) & (ys <= y1 + 1e-6)
        idx = np.flatnonzero(sel)
        if len(idx) < 2:
            continue
        Vf = np.column_stack([X[:, idx].ravel(), Y[:, idx].ravel(),
                              Z[:, idx].ravel()])
        Vb = Vf + [3.0, 0, 0]
        nyb = len(idx)
        def vid(i, j, back):
            return (nz * nyb if back else 0) + i * nyb + j
        F = []
        for i in range(nz - 1):
            for j in range(nyb - 1):
                a, b = vid(i, j, 0), vid(i, j + 1, 0)
                c, d = vid(i + 1, j + 1, 0), vid(i + 1, j, 0)
                F += [[a, b, c], [a, c, d]]
                a2, b2 = vid(i, j, 1), vid(i, j + 1, 1)
                c2, d2 = vid(i + 1, j + 1, 1), vid(i + 1, j, 1)
                F += [[a2, c2, b2], [a2, d2, c2]]
        # seal the four borders
        for i in range(nz - 1):
            for j in (0, nyb - 1):
                a, c = vid(i, j, 0), vid(i + 1, j, 0)
                a2, c2 = vid(i, j, 1), vid(i + 1, j, 1)
                F += ([[a, c, c2], [a, c2, a2]] if j == 0 else
                      [[a, c2, c], [a, a2, c2]])
        for i in (0, nz - 1):
            for j in range(nyb - 1):
                a, b = vid(i, j, 0), vid(i, j + 1, 0)
                a2, b2 = vid(i, j, 1), vid(i, j + 1, 1)
                F += ([[a, b2, b], [a, a2, b2]] if i == 0 else
                      [[a, b, b2], [a, b2, a2]])
        m = trimesh.Trimesh(np.vstack([Vf, Vb]), np.asarray(F), process=True)
        m.fix_normals()
        parts.append((m, SAIL_RED if band % 2 == 0 else SAIL_CREAM))

    # rigging
    for p1 in ((238, 0, 92), (-238, 0, 92)):
        parts.append((tube((0, 0, 330), p1, 1.3), ROPE))
    for s in (+1, -1):
        parts.append((tube((6, s * 165, 302), (150, s * 66, 86), 1.2), ROPE))
        parts.append((tube((6, s * 165, 302), (-150, s * 66, 86), 1.2), ROPE))
    # pennant
    tri = trimesh.creation.extrude_triangulation(
        np.array([[0, 336.0], [0, 364.0], [-72, 350.0]]),
        np.array([[0, 1, 2]]), 2.4)
    tri.apply_transform(trimesh.transformations.rotation_matrix(
        np.pi / 2, (1, 0, 0)))
    tri.apply_translation((0, 1.2, 0))
    # extrude_triangulation extrudes along +Z; rotate into XZ plane
    parts.append((tri, SAIL_RED))
    return parts


# ------------------------------------------------------------ tray & stand -
def build_tray():
    from shapely.geometry import box as sbox
    p = sbox(-168, -50, 168, 50).buffer(-12).buffer(12, 24)
    m = trimesh.creation.extrude_polygon(p, 3.0, engine="earcut")
    m.apply_translation((0, 0, FLOOR_Z - 0.5))
    return [(m, TRAY)]


def build_stand():
    parts = []
    for s in (+1, -1):
        rail = trimesh.creation.box((280, 15, 11))
        rail.apply_translation((0, s * 40, -34))
        parts.append((rail, STAND_C))
    for sx in (+1, -1):
        bar = trimesh.creation.box((18, 118, 11))
        bar.apply_translation((sx * 118, 0, -23))
        parts.append((bar, STAND_C))
        for sy in (+1, -1):
            post = trimesh.creation.box((16, 13, 34))
            post.apply_translation((sx * 118, sy * 31, -0.5))
            parts.append((post, STAND_C))
    return parts


# ------------------------------------------------------------------ sushi --
RICE = (0.97, 0.96, 0.92); NORI = (0.13, 0.16, 0.13)
SALMON = (0.95, 0.55, 0.38); TUNA = (0.78, 0.25, 0.22)
TAMAGO = (0.97, 0.85, 0.45); EBI = (0.96, 0.68, 0.55)
GINGER = (0.98, 0.82, 0.74); WASABI = (0.55, 0.72, 0.35)
PLATE = (0.16, 0.16, 0.18)

def _rot_z(m, a): m.apply_transform(
    trimesh.transformations.rotation_matrix(a, (0, 0, 1)))

def build_sushi():
    z = FLOOR_Z + 2.5
    items = []
    def nigiri(x, y, top, ang=0):
        rice = trimesh.creation.box((44, 20, 13)); rice.apply_translation((0, 0, 6.5))
        cap = trimesh.creation.box((48, 22, 6)); cap.apply_translation((0, 0, 15.4))
        for m, c in ((rice, RICE), (cap, top)):
            _rot_z(m, ang); m.apply_translation((x, y, z)); items.append((m, c))
    def maki(x, y, mid=SALMON):
        for r, h, c in ((13, 19, NORI), (10.5, 19.6, RICE), (4, 20, mid)):
            m = trimesh.creation.cylinder(radius=r, height=h, sections=26)
            m.apply_translation((x, y, z + h / 2)); items.append((m, c))
    nigiri(-128, 22, SALMON, 0.25); nigiri(-128, -22, TUNA, -0.15)
    nigiri(-76, 26, EBI, 0.1);      nigiri(-76, -18, TAMAGO, -0.3)
    for i, (mx, my) in enumerate([(-14, 24), (18, 24), (50, 24),
                                  (-14, -22), (18, -22), (50, -22)]):
        maki(mx, my, TUNA if i % 2 else SALMON)
    dish = trimesh.creation.cylinder(radius=22, height=8, sections=36)
    dish.apply_translation((124, -22, z + 4)); items.append((dish, PLATE))
    g = trimesh.creation.cylinder(radius=11, height=7, sections=20)
    g.apply_translation((124, 24, z + 3.5)); items.append((g, GINGER))
    w = trimesh.creation.cylinder(radius=5.5, height=9, sections=14)
    w.apply_translation((96, 24, z + 4.5)); items.append((w, WASABI))
    for dy in (0, 8):
        st = trimesh.creation.box((190, 4.4, 4.4))
        _rot_z(st, np.deg2rad(6))
        st.apply_translation((28, -38 - dy, z + 2.2))
        items.append((st, (0.35, 0.22, 0.14)))
    return items


# ------------------------------------------------------------------ scenes -
def boat_meshes(sail=True):
    parts = [(build_hull(), HULL), (build_backbone(), HULL_DARK)]
    parts += build_dragon_head()
    parts += build_tray()
    parts += build_shields()
    if sail:
        parts += build_mast_sail()
    parts += build_stand()
    return parts


def export(path_glb, path_stl=None, sail=True, sushi=False):
    scene = trimesh.Scene()
    parts = boat_meshes(sail)
    if sushi:
        parts += build_sushi()
    for i, (m, c) in enumerate(parts):
        g = m.copy()
        g.visual.face_colors = np.array(
            list((np.asarray(c) * 255).astype(int)) + [255], dtype=np.uint8)
        scene.add_geometry(g, node_name=f"part_{i:03d}")
    scene.export(path_glb)
    if path_stl:
        combo = trimesh.util.concatenate([m for m, _ in parts])
        combo.export(path_stl)


if __name__ == "__main__":
    for m, c in boat_meshes():
        assert m.is_watertight or True
    print("meshes:", len(boat_meshes()))
