class_name FieldSurface
extends Node3D
## The ground each player fights on, once their Environment is down.
##
## One plane per half of the table, lying just above it and invisible until
## an Environment is set. Placing one sends a wave out from the card that
## turns that half into the terrain it names — lava, turf, sea or open sky.
## Replacing an Environment sweeps the new terrain over the old one, so a
## change of ground reads as a change of ground rather than a swapped card.
##
## The look lives entirely in field_surface.gdshader; this owns the two
## planes, which theme belongs to which dinosaur type, and the timing of
## the sweep.

const SHADER := preload("res://scenes/battle/field_surface.gdshader")
## Covers one half of the 11 x 6.5 table.
const PLANE_SIZE := Vector2(11.0, 3.25)
## Just above the table, below the slot outlines so they stay readable.
const HEIGHT := 0.152
const SWEEP_TIME := 1.15

## Shader theme per dinosaur type. The order matches the shader's constants.
const THEME_LAVA := 0
const THEME_GRASS := 1
const THEME_WIND := 2
const THEME_OCEAN := 3
const THEMES: Dictionary = {
	CardCatalogTypes.DinoType.CARNIVORE: THEME_LAVA,
	CardCatalogTypes.DinoType.HERBIVORE: THEME_GRASS,
	CardCatalogTypes.DinoType.PTEROSAUR: THEME_WIND,
	CardCatalogTypes.DinoType.AMPHIBIAN: THEME_OCEAN,
}
## The colour of the wave front, per theme.
const RIM_COLORS: Dictionary = {
	THEME_LAVA: Color("ffb347"),
	THEME_GRASS: Color("b7f07a"),
	THEME_WIND: Color("ffffff"),
	THEME_OCEAN: Color("9fe8ff"),
}

## Table side -> the plane covering it.
var _planes: Array[MeshInstance3D] = []


func build() -> void:
	var mesh := PlaneMesh.new()
	mesh.size = PLANE_SIZE
	for side in range(2):
		var plane := MeshInstance3D.new()
		plane.mesh = mesh
		var material := ShaderMaterial.new()
		material.shader = SHADER
		material.set_shader_parameter("plane_size", PLANE_SIZE)
		material.set_shader_parameter("progress", 0.0)
		plane.material_override = material
		# Each half sits on its own side of the centre line.
		plane.position = Vector3(0.0, HEIGHT, PLANE_SIZE.y * 0.5 * (1.0 if side == 0 else -1.0))
		plane.visible = false
		add_child(plane)
		_planes.append(plane)


## Sweeps `dino_type`'s terrain across one half, starting from the table
## position the Environment card was laid at.
func sweep(side: int, dino_type: int, from_position: Vector3) -> void:
	if side < 0 or side >= _planes.size():
		return
	var plane := _planes[side]
	var material := plane.material_override as ShaderMaterial
	var theme: int = THEMES.get(dino_type, THEME_GRASS)
	material.set_shader_parameter("theme", theme)
	material.set_shader_parameter("rim_color", RIM_COLORS[theme])
	# The shader measures the wave in the plane's own space, so the card's
	# world position has to come back through the plane's transform.
	material.set_shader_parameter(
		"origin", Vector2(from_position.x - plane.position.x,
			from_position.z - plane.position.z))
	plane.visible = true
	if Settings.reduced_motion:
		material.set_shader_parameter("progress", 1.0)
		return
	material.set_shader_parameter("progress", 0.0)
	var tween := plane.create_tween()
	tween.tween_method(
		func(value: float) -> void:
			material.set_shader_parameter("progress", value),
		0.0, 1.0, SWEEP_TIME).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


## Takes a half back to bare table — a battle ending, or a fresh one
## starting on a screen that already ran one.
func clear(side: int) -> void:
	if side < 0 or side >= _planes.size():
		return
	_planes[side].visible = false
	(_planes[side].material_override as ShaderMaterial).set_shader_parameter("progress", 0.0)
