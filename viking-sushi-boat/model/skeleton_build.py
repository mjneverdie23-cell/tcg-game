"""Renders + 3D exports for the flat-bottom + skeleton design."""
import os
import numpy as np
import trimesh

import skeleton_boat as sk
from render import render

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
R = os.path.join(ROOT, "renders")
CAD = os.path.join(ROOT, "cad")
os.makedirs(R, exist_ok=True)
os.makedirs(CAD, exist_ok=True)


def export(parts, path_glb, path_stl):
    scene = trimesh.Scene()
    for i, (m, c) in enumerate(parts):
        g = m.copy()
        g.visual.face_colors = np.array(
            list((np.asarray(c) * 255).astype(int)) + [255], dtype=np.uint8)
        scene.add_geometry(g, node_name=f"part_{i:02d}")
    scene.export(path_glb)
    trimesh.util.concatenate([m for m, _ in parts]).export(path_stl)


def main():
    a = sk.assembly()
    ex = sk.assembly(explode=105.0)
    flat = sk.parts_flat()

    views = [
        ("skeleton_01_hero.png", a, dict(az=28, el=30, target=(0, 0, 70))),
        ("skeleton_02_side.png", a, dict(az=90, el=5, target=(0, 0, 110))),
        ("skeleton_03_top.png", a, dict(az=90, el=80, target=(0, 0, 30))),
        ("skeleton_04_bow.png", a, dict(az=-30, el=14,
                                        target=(240, 0, 140), dist=800)),
        ("skeleton_05_stern.png", a, dict(az=150, el=14,
                                          target=(-240, 0, 150), dist=800)),
        ("skeleton_06_exploded.png", ex, dict(az=32, el=18, floor=False,
                                              target=(0, 0, 190), dist=1600)),
        ("skeleton_07_parts_flat.png", flat, dict(az=75, el=55, floor=False,
                                                  target=(0, 0, 0),
                                                  dist=1400)),
    ]
    for name, meshes, kw in views:
        render(meshes, os.path.join(R, name), **kw)
        print("  render", name)

    export(a, os.path.join(CAD, "skeleton_boat.glb"),
           os.path.join(CAD, "skeleton_boat.stl"))
    export(flat, os.path.join(CAD, "skeleton_boat_parts_flat.glb"),
           os.path.join(CAD, "skeleton_boat_parts_flat.stl"))
    print("exports done")


if __name__ == "__main__":
    main()
