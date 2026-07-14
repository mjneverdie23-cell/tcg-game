# AI Mesh Print Prep — Blender add-on + headless CLI
#
# Cleans up messy AI-generated 3D models (Meshy, Tripo, Luma, TRELLIS, ...)
# and remeshes them into a watertight, manifold, 3D-printable mesh.
#
# Pipeline: merge doubles -> delete loose geometry -> remove floating
# islands -> fill holes -> recalculate normals -> voxel/quad remesh ->
# smooth -> optional decimate. Reports watertight status when done.
#
# Install as add-on:  Edit > Preferences > Add-ons > Install... > this file
# Panel:              3D Viewport > Sidebar (N) > "Print Prep" tab
#
# Headless CLI:
#   blender -b -P ai_mesh_print_prep.py -- --input model.glb --output fixed.stl
#   (see README.md next to this file for all flags)

bl_info = {
    "name": "AI Mesh Print Prep",
    "author": "tcg-game",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Print Prep",
    "description": "One-click cleanup + remesh of AI-generated models for 3D printing",
    "category": "Mesh",
}

import os
import sys

import bpy
import bmesh
from mathutils import Matrix


# --------------------------------------------------------------------------
# Core mesh processing (pure bmesh / modifier code, usable from UI and CLI)
# --------------------------------------------------------------------------

# Hard cap on voxel resolution across the bounding-box diagonal so a tiny
# voxel size can't eat all memory.
MAX_VOXELS_ACROSS_DIAGONAL = 1500


def _apply_object_scale(obj):
    """Bake object scale into the mesh so voxel size works in world units."""
    if tuple(obj.scale) != (1.0, 1.0, 1.0):
        obj.data.transform(Matrix.Diagonal(obj.scale).to_4x4())
        obj.scale = (1.0, 1.0, 1.0)


def _face_islands(bm):
    """Connected components of faces (linked through shared vertices)."""
    bm.faces.ensure_lookup_table()
    seen = [False] * len(bm.faces)
    islands = []
    for face in bm.faces:
        if seen[face.index]:
            continue
        stack = [face]
        seen[face.index] = True
        component = []
        while stack:
            current = stack.pop()
            component.append(current)
            for vert in current.verts:
                for linked in vert.link_faces:
                    if not seen[linked.index]:
                        seen[linked.index] = True
                        stack.append(linked)
        islands.append(component)
    return islands


def clean_mesh(obj, *, merge_distance=0.0001, remove_floaters=True,
               floater_ratio=0.02, fill_holes=True, recalc_normals=True):
    """Run the cleanup passes on obj's mesh. Returns a stats dict."""
    mesh = obj.data
    stats = {
        "verts_before": len(mesh.vertices),
        "faces_before": len(mesh.polygons),
        "islands_removed": 0,
        "boundary_edges_before": 0,
        "boundary_edges_after": 0,
    }

    bm = bmesh.new()
    bm.from_mesh(mesh)

    # 1. Merge duplicate vertices (AI meshes are full of split seams).
    if merge_distance > 0:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_distance)

    # 2. Delete wire edges and isolated vertices.
    wire_edges = [e for e in bm.edges if not e.link_faces]
    if wire_edges:
        bmesh.ops.delete(bm, geom=wire_edges, context="EDGES")
    loose_verts = [v for v in bm.verts if not v.link_faces]
    if loose_verts:
        bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")

    # 3. Collapse zero-area faces / zero-length edges.
    bmesh.ops.dissolve_degenerate(bm, dist=merge_distance, edges=bm.edges)

    # 4. Remove floating islands ("polygons in the air"): any connected
    #    component smaller than floater_ratio * largest component.
    if remove_floaters and bm.faces:
        islands = _face_islands(bm)
        if len(islands) > 1:
            largest = max(len(comp) for comp in islands)
            threshold = max(1, int(largest * floater_ratio))
            junk_faces = [f for comp in islands if len(comp) < threshold
                          for f in comp]
            if junk_faces:
                stats["islands_removed"] = sum(
                    1 for comp in islands if len(comp) < threshold)
                bmesh.ops.delete(bm, geom=junk_faces, context="FACES")

    # 5. Fill holes (open boundary loops).
    stats["boundary_edges_before"] = sum(1 for e in bm.edges if e.is_boundary)
    if fill_holes and stats["boundary_edges_before"]:
        bmesh.ops.holes_fill(bm, edges=bm.edges, sides=0)
    stats["boundary_edges_after"] = sum(1 for e in bm.edges if e.is_boundary)

    # 6. Make normals consistently point outward.
    if recalc_normals and bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    stats["verts_after_clean"] = len(mesh.vertices)
    stats["faces_after_clean"] = len(mesh.polygons)
    return stats


def _apply_modifier(obj, modifier):
    with bpy.context.temp_override(object=obj, active_object=obj,
                                   selected_objects=[obj],
                                   selected_editable_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=modifier.name)


def remesh_for_print(obj, *, mode="VOXEL", voxel_percent=0.4,
                     quad_target_faces=20000, smooth_iterations=3,
                     target_faces=0):
    """Remesh + smooth + optional decimate. Returns a stats dict."""
    stats = {"voxel_size": 0.0}
    _apply_object_scale(obj)

    if mode == "VOXEL":
        diagonal = obj.dimensions.length
        if diagonal <= 0:
            raise ValueError("Object has zero size; nothing to remesh")
        voxel_size = diagonal * (voxel_percent / 100.0)
        voxel_size = max(voxel_size, diagonal / MAX_VOXELS_ACROSS_DIAGONAL)
        stats["voxel_size"] = voxel_size
        mod = obj.modifiers.new("AIMC_Remesh", "REMESH")
        mod.mode = "VOXEL"
        mod.voxel_size = voxel_size
        _apply_modifier(obj, mod)
    elif mode == "QUAD":
        with bpy.context.temp_override(object=obj, active_object=obj,
                                       selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.object.quadriflow_remesh(target_faces=quad_target_faces,
                                             mode="FACES")

    if smooth_iterations > 0:
        mod = obj.modifiers.new("AIMC_Smooth", "SMOOTH")
        mod.factor = 0.5
        mod.iterations = smooth_iterations
        _apply_modifier(obj, mod)

    if target_faces > 0 and len(obj.data.polygons) > target_faces:
        mod = obj.modifiers.new("AIMC_Decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = target_faces / len(obj.data.polygons)
        _apply_modifier(obj, mod)

    return stats


def manifold_report(obj):
    """Return (non_manifold_edges, boundary_edges, is_watertight)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
    return non_manifold, boundary, (non_manifold == 0 and boundary == 0)


def process_object(obj, settings):
    """Full pipeline on one object. settings is any object with the
    attributes defined on AIMC_Settings. Returns a human-readable summary."""
    clean_stats = clean_mesh(
        obj,
        merge_distance=settings.merge_distance,
        remove_floaters=settings.remove_floaters,
        floater_ratio=settings.floater_ratio,
        fill_holes=settings.fill_holes,
        recalc_normals=True,
    )
    remesh_stats = {"voxel_size": 0.0}
    if settings.remesh_mode != "NONE":
        remesh_stats = remesh_for_print(
            obj,
            mode=settings.remesh_mode,
            voxel_percent=settings.voxel_percent,
            quad_target_faces=settings.quad_target_faces,
            smooth_iterations=settings.smooth_iterations,
            target_faces=settings.target_faces,
        )
    non_manifold, boundary, watertight = manifold_report(obj)

    summary = (
        f"{obj.name}: {clean_stats['faces_before']:,} -> "
        f"{len(obj.data.polygons):,} faces | "
        f"{clean_stats['islands_removed']} floating island(s) removed | "
        f"{clean_stats['boundary_edges_before']} boundary edge(s) found"
    )
    if remesh_stats["voxel_size"]:
        summary += f" | voxel size {remesh_stats['voxel_size']:.4g}"
    summary += (" | WATERTIGHT — ready to print" if watertight else
                f" | NOT watertight ({non_manifold} non-manifold, "
                f"{boundary} boundary edges)")
    return summary


# --------------------------------------------------------------------------
# Add-on UI
# --------------------------------------------------------------------------

class AIMC_Settings(bpy.types.PropertyGroup):
    merge_distance: bpy.props.FloatProperty(
        name="Merge Distance",
        description="Merge vertices closer than this (fixes split seams)",
        default=0.0001, min=0.0, soft_max=0.01, precision=5)
    remove_floaters: bpy.props.BoolProperty(
        name="Remove Floating Islands",
        description="Delete disconnected shells that hang in the air",
        default=True)
    floater_ratio: bpy.props.FloatProperty(
        name="Floater Threshold",
        description="Islands smaller than this fraction of the largest "
                    "island are deleted",
        default=0.02, min=0.001, max=0.5, subtype="FACTOR")
    fill_holes: bpy.props.BoolProperty(
        name="Fill Holes",
        description="Fill open boundary loops before remeshing",
        default=True)
    remesh_mode: bpy.props.EnumProperty(
        name="Remesh",
        items=[
            ("VOXEL", "Voxel (3D print)",
             "Watertight manifold output — best for printing"),
            ("QUAD", "Quadriflow (animation/edit)",
             "Clean quad topology — slower, better for further editing"),
            ("NONE", "None (cleanup only)",
             "Only run the cleanup passes"),
        ],
        default="VOXEL")
    voxel_percent: bpy.props.FloatProperty(
        name="Voxel Detail",
        description="Voxel size as % of the bounding-box diagonal "
                    "(smaller = more detail, more memory)",
        default=0.4, min=0.05, max=5.0)
    quad_target_faces: bpy.props.IntProperty(
        name="Quad Faces", description="Target face count for Quadriflow",
        default=20000, min=100)
    smooth_iterations: bpy.props.IntProperty(
        name="Smooth Iterations",
        description="Post-remesh smoothing passes (0 = off)",
        default=3, min=0, max=50)
    target_faces: bpy.props.IntProperty(
        name="Max Faces (0 = off)",
        description="Decimate the final mesh down to this face count",
        default=0, min=0)
    keep_original: bpy.props.BoolProperty(
        name="Keep Backup Copy",
        description="Keep a hidden copy of the original object",
        default=True)


class AIMC_OT_clean_and_remesh(bpy.types.Operator):
    """Clean up AI-generated mesh and remesh it for 3D printing.
    Note: remeshing discards UVs and materials (irrelevant for printing)"""
    bl_idname = "object.aimc_clean_and_remesh"
    bl_label = "Clean + Remesh for Print"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (context.mode == "OBJECT" and
                any(o.type == "MESH" for o in context.selected_objects))

    def execute(self, context):
        settings = context.scene.aimc_settings
        targets = [o for o in context.selected_objects if o.type == "MESH"]
        for obj in targets:
            if settings.keep_original:
                backup = obj.copy()
                backup.data = obj.data.copy()
                backup.name = obj.name + "_original"
                context.collection.objects.link(backup)
                backup.hide_set(True)
                backup.hide_render = True
            try:
                summary = process_object(obj, settings)
            except Exception as exc:
                self.report({"ERROR"}, f"{obj.name}: {exc}")
                return {"CANCELLED"}
            self.report({"INFO"}, summary)
            print("[AI Mesh Print Prep]", summary)
        return {"FINISHED"}


class AIMC_PT_panel(bpy.types.Panel):
    bl_label = "AI Mesh Print Prep"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Print Prep"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.aimc_settings

        box = layout.box()
        box.label(text="Cleanup", icon="BRUSH_DATA")
        box.prop(settings, "merge_distance")
        box.prop(settings, "remove_floaters")
        row = box.row()
        row.enabled = settings.remove_floaters
        row.prop(settings, "floater_ratio")
        box.prop(settings, "fill_holes")

        box = layout.box()
        box.label(text="Remesh", icon="MOD_REMESH")
        box.prop(settings, "remesh_mode", text="")
        if settings.remesh_mode == "VOXEL":
            box.prop(settings, "voxel_percent")
        elif settings.remesh_mode == "QUAD":
            box.prop(settings, "quad_target_faces")
        box.prop(settings, "smooth_iterations")
        box.prop(settings, "target_faces")

        layout.prop(settings, "keep_original")
        layout.operator(AIMC_OT_clean_and_remesh.bl_idname, icon="CHECKMARK")


classes = (AIMC_Settings, AIMC_OT_clean_and_remesh, AIMC_PT_panel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.aimc_settings = bpy.props.PointerProperty(
        type=AIMC_Settings)


def unregister():
    del bpy.types.Scene.aimc_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


# --------------------------------------------------------------------------
# Headless CLI:  blender -b -P ai_mesh_print_prep.py -- --input a.glb --output b.stl
# --------------------------------------------------------------------------

class _CliSettings:
    """Mirrors AIMC_Settings attributes for process_object()."""

    def __init__(self, args):
        self.merge_distance = args.merge_dist
        self.remove_floaters = not args.no_floaters
        self.floater_ratio = args.floater_ratio
        self.fill_holes = not args.no_fill_holes
        self.remesh_mode = args.mode.upper()
        self.voxel_percent = args.voxel_percent
        self.quad_target_faces = args.quad_faces
        self.smooth_iterations = args.smooth
        self.target_faces = args.target_faces
        self.keep_original = False


def _import_model(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=path)
        else:
            bpy.ops.import_scene.obj(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".stl":
        if hasattr(bpy.ops.wm, "stl_import"):
            bpy.ops.wm.stl_import(filepath=path)
        else:
            bpy.ops.import_mesh.stl(filepath=path)
    elif ext == ".ply":
        if hasattr(bpy.ops.wm, "ply_import"):
            bpy.ops.wm.ply_import(filepath=path)
        else:
            bpy.ops.import_mesh.ply(filepath=path)
    else:
        raise ValueError(f"Unsupported input format: {ext}")


def _export_model(obj, path):
    for other in bpy.data.objects:
        other.select_set(other == obj)
    bpy.context.view_layer.objects.active = obj
    ext = os.path.splitext(path)[1].lower()
    if ext == ".stl":
        if hasattr(bpy.ops.wm, "stl_export"):
            bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
        else:
            bpy.ops.export_mesh.stl(filepath=path, use_selection=True)
    elif ext == ".obj":
        bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True)
    elif ext in (".glb", ".gltf"):
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True)
    else:
        raise ValueError(f"Unsupported output format: {ext}")


def _join_imported_meshes():
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise ValueError("No mesh found in the imported file")
    active = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=active,
                                       selected_objects=meshes,
                                       selected_editable_objects=meshes):
            bpy.ops.object.join()
    return active


def _run_cli(argv):
    import argparse
    parser = argparse.ArgumentParser(
        prog="blender -b -P ai_mesh_print_prep.py --",
        description="Clean up an AI-generated model and remesh it for "
                    "3D printing.")
    parser.add_argument("--input", required=True, help="glb/gltf/obj/fbx/stl/ply")
    parser.add_argument("--output", required=True, help="stl/obj/glb")
    parser.add_argument("--mode", default="voxel",
                        choices=["voxel", "quad", "none"])
    parser.add_argument("--voxel-percent", type=float, default=0.4,
                        help="Voxel size as %% of bbox diagonal (default 0.4)")
    parser.add_argument("--quad-faces", type=int, default=20000)
    parser.add_argument("--smooth", type=int, default=3,
                        help="Smoothing iterations after remesh (default 3)")
    parser.add_argument("--merge-dist", type=float, default=0.0001)
    parser.add_argument("--floater-ratio", type=float, default=0.02)
    parser.add_argument("--target-faces", type=int, default=0,
                        help="Decimate final mesh to this many faces (0=off)")
    parser.add_argument("--no-floaters", action="store_true",
                        help="Skip floating-island removal")
    parser.add_argument("--no-fill-holes", action="store_true")
    args = parser.parse_args(argv)

    # Start from an empty scene.
    bpy.ops.wm.read_factory_settings(use_empty=True)

    _import_model(os.path.abspath(args.input))
    obj = _join_imported_meshes()
    summary = process_object(obj, _CliSettings(args))
    print("[AI Mesh Print Prep]", summary)
    _export_model(obj, os.path.abspath(args.output))
    print(f"[AI Mesh Print Prep] wrote {args.output}")


if __name__ == "__main__":
    if "--" in sys.argv:
        _run_cli(sys.argv[sys.argv.index("--") + 1:])
    else:
        register()
