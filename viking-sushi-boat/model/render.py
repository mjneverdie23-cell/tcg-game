"""Soft-shaded renders of the assembly via a simple painter renderer."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection


def camera(az_deg, el_deg, dist, target=(0, 0, 90)):
    az, el = np.deg2rad(az_deg), np.deg2rad(el_deg)
    fwd = -np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az),
                     np.sin(el)])
    eye = np.asarray(target, float) - fwd * dist
    right = np.cross(fwd, (0, 0, 1.0)); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return eye, right, up, fwd


def render(meshes, path, az=35, el=18, dist=1600, target=(0, 0, 90),
           fov=28.0, figsize=(12.8, 9.0), light=None, floor=True,
           labels=None, dpi=150, bg="#f5f1e8", pad=1.06):
    """meshes: list of (trimesh, rgb) or Instance-like with .mesh/.color."""
    eye, right, up, fwd = camera(az, el, dist, target)
    lt = light if light is not None else (right * 0.35 + up * 0.8 - fwd * 0.95)
    lt = np.asarray(lt, float); lt /= np.linalg.norm(lt)
    f = 1.0 / np.tan(np.deg2rad(fov) / 2)

    tris, cols, depths = [], [], []
    norm = lambda c: np.asarray(c, float)

    def add_mesh(m, c):
        v = m.vertices
        rel = v - eye
        xc = rel @ right; yc = rel @ up; zc = rel @ fwd
        px = f * xc / zc; py = f * yc / zc
        F = m.faces
        n = m.face_normals
        # shading
        lam = np.clip(n @ lt, 0, 1)
        shade = 0.52 + 0.48 * lam
        base = norm(c)
        fc = np.clip(base * shade[:, None], 0, 1)
        zf = zc[F].mean(axis=1)
        # backface culling (all meshes are closed solids)
        cent = v[F].mean(axis=1)
        keep = np.einsum("ij,ij->i", n, cent - eye) < 0
        for i in np.flatnonzero(keep):
            tris.append(np.column_stack([px[F[i]], py[F[i]]]))
            depths.append(zf[i])
        cols.append(fc[keep])

    items = []
    for it in meshes:
        if hasattr(it, "mesh"):
            items.append((it.mesh, it.color))
        else:
            items.append(it)

    if floor:
        import trimesh
        from shapely.geometry import Point as _Pt
        from trimesh.creation import extrude_polygon as _ep
        allb = np.vstack([m.bounds for m, _ in items])
        lo, hi = allb.min(0), allb.max(0)
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        ell = _Pt(0, 0).buffer(1.0, 48)
        from shapely import affinity as _aff
        ell = _aff.scale(ell, (hi[0] - lo[0]) * 0.58, (hi[1] - lo[1]) * 0.75)
        sh = _ep(ell, 0.5)
        sh.apply_translation((cx, cy, lo[2] - 0.8))
        items = [(sh, (0.855, 0.825, 0.765))] + items

    for m, c in items:
        add_mesh(m, c)

    cols = np.vstack(cols)
    order = np.argsort(-np.asarray(depths))
    tris = [tris[i] for i in order]
    cols = cols[order]
    edge = np.clip(cols * 0.93, 0, 1)

    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    pc = PolyCollection(tris, facecolors=cols, edgecolors=edge,
                        linewidths=0.12)
    ax.add_collection(pc)
    allpts = np.vstack(tris)
    x0, x1 = allpts[:, 0].min(), allpts[:, 0].max()
    y0, y1 = allpts[:, 1].min(), allpts[:, 1].max()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hw = max(x1 - x0, (y1 - y0) * figsize[0] / figsize[1]) / 2 * pad
    ax.set_xlim(cx - hw, cx + hw)
    ax.set_ylim(cy - hw * figsize[1] / figsize[0],
                cy + hw * figsize[1] / figsize[0])
    ax.set_aspect("equal"); ax.axis("off")

    if labels:
        for text, wpos, dxy in labels:
            rel = np.asarray(wpos, float) - eye
            px = f * (rel @ right) / (rel @ fwd)
            py = f * (rel @ up) / (rel @ fwd)
            ax.annotate(text, (px, py), xytext=(px + dxy[0], py + dxy[1]),
                        fontsize=9, fontweight="bold", color="#3a3226",
                        ha="center",
                        arrowprops=dict(arrowstyle="-", lw=0.8,
                                        color="#3a3226", alpha=0.7))
    plt.tight_layout(pad=0.3)
    plt.savefig(path, dpi=dpi, facecolor=bg)
    plt.close(fig)
