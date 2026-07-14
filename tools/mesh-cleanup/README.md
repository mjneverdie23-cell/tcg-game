# AI Mesh Print Prep

AI 3D generators (Meshy, Tripo, Luma, TRELLIS, …) produce models that look
fine from a distance but fall apart up close: 40k–80k unorganized triangles,
floating polygons disconnected from the body, duplicate/split vertices, open
holes, flipped normals, and non-manifold edges. None of that slices cleanly
for 3D printing.

This folder contains **`ai_mesh_print_prep.py`** — a single-file Blender
add-on *and* headless command-line tool that fixes all of the above in one
pass and outputs a watertight, printable mesh.

## What it does (in order)

1. **Merge by distance** — welds duplicate/split vertices along seams.
2. **Delete loose geometry** — wire edges and isolated vertices.
3. **Dissolve degenerate faces** — zero-area triangles that break slicers.
4. **Remove floating islands** — any disconnected shell smaller than a
   configurable fraction (default 2%) of the largest shell is deleted.
   This is the fix for "polygons hanging in the air".
5. **Fill holes** — closes open boundary loops.
6. **Recalculate normals** — all faces point outward.
7. **Voxel remesh** — rebuilds the surface as a single guaranteed
   watertight, manifold shell (voxel size auto-scaled to the model's
   bounding box; Quadriflow quad remesh also available if you want to keep
   editing/animating the model instead of printing it).
8. **Smooth** — a few smoothing passes to remove voxel stair-stepping and
   the lumpy AI surface.
9. **Optional decimate** — cap the final triangle count.
10. **Watertight check** — reports non-manifold/boundary edge counts and
    whether the result is print-ready.

> Note: remeshing discards UVs and materials. That's irrelevant for resin/FDM
> printing, but use the "Keep Backup Copy" option (on by default) if you also
> need the textured original.

## Install as a Blender add-on

1. Blender ≥ 3.6 (tested API paths for 4.x too).
2. `Edit > Preferences > Add-ons > Install…` and pick `ai_mesh_print_prep.py`.
3. Enable **AI Mesh Print Prep**.
4. Select your imported AI model in the viewport, open the sidebar (`N`),
   go to the **Print Prep** tab, tweak if needed, hit
   **Clean + Remesh for Print**.

Defaults are tuned for AI-generated character/prop models:
- **Voxel Detail 0.4** = voxel size is 0.4% of the bounding-box diagonal
  (~250 voxels across the model). Lower = more detail, more RAM.
- **Floater Threshold 0.02** = islands with fewer than 2% of the largest
  island's faces get deleted.

## Run headless (batch / pipeline use)

```bash
blender -b -P ai_mesh_print_prep.py -- --input model.glb --output fixed.stl
```

Useful flags:

```
--mode voxel|quad|none    remesh mode (default voxel)
--voxel-percent 0.4       voxel size as % of bbox diagonal
--smooth 3                smoothing iterations (0 = off)
--floater-ratio 0.02      island-size threshold for floater removal
--target-faces 0          decimate final mesh to N faces (0 = off)
--no-floaters             keep disconnected islands
--no-fill-holes           skip hole filling
```

Input: `.glb .gltf .obj .fbx .stl .ply` — Output: `.stl .obj .glb`.
Multiple meshes in one file are joined before processing, which the voxel
remesh then fuses into a single printable shell.

## Research: existing software and add-ons

What's already out there for fixing messy AI meshes, if you'd rather not
script it:

### Inside Blender (free, built-in)

- **Manual cleanup tools** — `Mesh > Clean Up > Merge by Distance`,
  `Select > All by Trait > Loose Geometry`, `Shift+N` recalc normals. The
  standard hand workflow ([Tripo's step-by-step guide](https://www.tripo3d.ai/blog/how-to-clean-up-ai-generated-3d-models-in-blender)).
- **3D-Print Toolbox** (bundled add-on) — checks solidity/intersections and
  has a *Make Manifold* button.
- **Voxel Remesh / Quadriflow** — built-in remeshers
  ([Blender manual](https://docs.blender.org/manual/en/latest/modeling/meshes/retopology.html)).
  Voxel is the right one for printing: guaranteed watertight and fuses
  overlapping shells; Quadriflow gives clean quads for animation.

### Blender add-ons

- **[Instant Clean](https://superhivemarket.com/products/instantclean)**
  (paid, Superhive/Blender Market) — one-click geometry cleanup, normal
  fixing and a Make Manifold mode for printing. Closest commercial
  equivalent to the cleanup half of our tool.
- **[Mesh Cleaner 2](https://www.cgchannel.com/2025/05/free-tool-mesh-cleaner-for-blender/)**
  (free) — groups Blender's cleanup operators in one panel: doubles, loose
  geometry, hole filling, tris-to-quads.
- **[Quad Remesher](https://superrendersfarm.com/article/quad-remesher-blender-retopology)**
  (paid, by the ZRemesher author) — best-in-class auto-retopology; overkill
  for printing but great if the model must be rigged/animated.

### Standalone / outside Blender

- **Autodesk Meshmixer** (free, discontinued but still downloadable) — the
  classic *Inspector* auto-repair for holes/floaters
  ([mesh repair tool roundup](https://triverse.ai/blog/how-to-repair-mesh-for-3d-printing)).
- **Autodesk Netfabb / Materialise Magics** — industrial print-prep repair
  ([best 3D model fixer tools](https://www.tripo3d.ai/content/en/use-case/the-best-3d-model-fixer)).
- **Slicer built-ins** — PrusaSlicer/Windows repair, Cura mesh fixes:
  fine for small errors, not for floating-island cleanup.
- **Vendor cleanup** — [Meshy's own Blender plugin has a Clean Up panel](https://docs.meshy.ai/en/blender-plugin/model-cleanup);
  Meshy also documents [fixing hollow models for printing](https://help.meshy.ai/en/articles/13835793-how-do-i-fix-a-hollow-meshy-model-for-3d-printing).
  Rule of thumb from practitioners: if a model needs an hour of repair,
  regenerating it is usually faster
  ([Neural4D cleanup guide](https://blog.neural4d.com/user-guide/ai-3d-model-blender-cleanup-complete-mesh-fix-guide-2026/)).

### Python libraries (for a no-Blender pipeline)

- **[PyMeshFix](https://github.com/pyvista/pymeshfix)** — wraps MeshFix:
  outputs a single watertight mesh, removing self-intersections and
  degenerate elements.
- **[trimesh](https://trimesh.org/trimesh.repair.html)** — load/repair/export
  in pure Python; good for CI pipelines.
- **[ManifoldPlus](https://arxiv.org/pdf/2005.11621)** — research-grade
  watertight manifold generation from triangle soup.

Our tool exists because none of the above does **both halves in one step**:
the cleanup add-ons don't remesh, and the remeshers assume a pre-cleaned
mesh (voxel remesh alone happily keeps floating islands as separate printed
blobs). `ai_mesh_print_prep.py` chains cleanup → remesh → verify in a single
click or a single shell command.
