"""Generate all renders and 3D exports for the one-piece Viking sushi boat."""
import os
import time

from viking_boat_3d import boat_meshes, build_sushi, export
from render import render

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
R = os.path.join(ROOT, "renders")
CAD = os.path.join(ROOT, "cad")
os.makedirs(R, exist_ok=True)
os.makedirs(CAD, exist_ok=True)


def main():
    t0 = time.time()
    full = boat_meshes(sail=True)
    bare = boat_meshes(sail=False)
    sushi = build_sushi()

    views = [
        ("01_hero.png", full, dict(az=30, el=15, target=(0, 0, 150))),
        ("02_side.png", full, dict(az=90, el=6, target=(0, 0, 150))),
        ("03_bow_quarter.png", full, dict(az=-25, el=10,
                                          target=(140, 0, 170), dist=1150)),
        ("04_stern_quarter.png", full, dict(az=152, el=12,
                                            target=(-110, 0, 170), dist=1150)),
        ("05_top.png", bare + sushi, dict(az=90, el=78, target=(0, 0, 60))),
        ("06_dragon_detail.png", bare, dict(az=-32, el=8,
                                            target=(345, 0, 265), dist=560)),
        ("07_with_sushi.png", full + sushi, dict(az=-38, el=22,
                                                 target=(30, 0, 110),
                                                 dist=1250)),
        ("08_serving_closeup.png", bare + sushi, dict(az=-62, el=28,
                                                      target=(10, 0, 70),
                                                      dist=800)),
        ("09_carved_boat_no_sail.png", bare, dict(az=35, el=14,
                                                  target=(0, 0, 130))),
    ]
    for name, meshes, kw in views:
        render(meshes, os.path.join(R, name), **kw)
        print(f"  render {name}  ({time.time() - t0:.0f}s)")

    export(os.path.join(CAD, "viking_sushi_boat.glb"),
           os.path.join(CAD, "viking_sushi_boat.stl"), sail=True)
    export(os.path.join(CAD, "viking_sushi_boat_carved_only.glb"),
           os.path.join(CAD, "viking_sushi_boat_carved_only.stl"), sail=False)
    print(f"exports done  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
