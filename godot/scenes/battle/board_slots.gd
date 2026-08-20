class_name BoardSlots
extends Node3D
## The outlines that mark every Active and bench place on the table, and the
## geometry the drag-and-drop needs to aim at them.
##
## Faint by default, so an empty board still reads as a board. A slot the
## dragged card can legally land in lights up and breathes, which is the
## whole of the "where does this go?" question answered without a word of
## instruction.
##
## Also the one place that knows where a slot physically is: both the board
## rendering and the drop tests ask this class, so a card and the outline
## under it can never disagree.

## How brightly a slot is lit. OFF is the resting outline that keeps an
## empty board legible; LEGAL means the card being carried may be dropped
## here; ARMED means the pointer is on it and letting go plays it here.
enum { OFF, LEGAL, ARMED }

## The shader's `lit` value per level, and how long a LEGAL slot takes to
## breathe once. ARMED does not pulse — a target under the pointer should
## sit still.
const LIT: Array = [0.0, 0.8, 1.0]
## How far a breathing slot dips before coming back.
const PULSE_LOW := 0.3
const PULSE_TIME := 0.6
## Outlines are drawn slightly proud of the card they mark.
const MARKER_SCALE := 1.06
## Just above the table surface, under the cards themselves.
const MARKER_HEIGHT := 0.155

## The Environment's place on each half, addressed as a slot beyond the
## bench so the drag-and-drop can aim at it like any other. It sits off to
## the left of the rows, where the Environment card stands.
const ENV_PLACE := 1 + BattleEngine.BENCH_SIZE
const ENV_POSITION := Vector3(-3.6, 0.18, 0.7)

## "side:index" -> MeshInstance3D.
var _markers: Dictionary = {}
## "side:index" -> the looping Tween lighting it, so it can be stopped.
var _pulses: Dictionary = {}


## Slot layout: active front-centre, bench of 3 behind; both sides mirrored
## across the centre line. play_index 0 = active, 1.. = bench.
static func transform_for(side: int, play_index: int) -> Transform3D:
	var forward := 1.0 if side == 0 else -1.0
	var position: Vector3
	if play_index == ENV_PLACE:
		position = Vector3(ENV_POSITION.x, ENV_POSITION.y, ENV_POSITION.z * forward)
	elif play_index == 0:
		position = Vector3(0, 0.18, 0.7 * forward)
	else:
		position = Vector3(-1.25 + (play_index - 1) * 1.25, 0.18, 2.15 * forward)
	# Both sides face the camera: an opponent's card the player cannot read
	# is worse than the tabletop realism of rotating it.
	return Transform3D(Basis.IDENTITY, position)


func build() -> void:
	var mesh := QuadMesh.new()
	mesh.size = Vector2(Card3D.WIDTH * MARKER_SCALE, Card3D.HEIGHT * MARKER_SCALE)
	for side in range(2):
		for slot in range(ENV_PLACE + 1):
			var marker := MeshInstance3D.new()
			marker.mesh = mesh
			marker.material_override = SlotFrame.material(mesh.size)
			var placement := transform_for(side, slot)
			placement.origin.y = MARKER_HEIGHT
			marker.transform = placement
			marker.rotate_object_local(Vector3.RIGHT, -PI / 2)
			add_child(marker)
			_markers[_key(side, slot)] = marker


## Lights a slot at one of the levels above.
func highlight(side: int, index: int, level: int) -> void:
	var key := _key(side, index)
	var marker: MeshInstance3D = _markers.get(key)
	if marker == null:
		return
	_stop_pulse(key)
	var material := marker.material_override as ShaderMaterial
	var lit := float(LIT[level])
	material.set_shader_parameter("lit", lit)
	if level != LEGAL or Settings.reduced_motion:
		return
	var breathe := func(value: float) -> void: material.set_shader_parameter("lit", value)
	var pulse := marker.create_tween().set_loops()
	pulse.tween_method(breathe, lit, PULSE_LOW, PULSE_TIME).set_trans(Tween.TRANS_SINE)
	pulse.tween_method(breathe, PULSE_LOW, lit, PULSE_TIME).set_trans(Tween.TRANS_SINE)
	_pulses[key] = pulse


func clear_highlights() -> void:
	for side in range(2):
		for slot in range(ENV_PLACE + 1):
			highlight(side, slot, OFF)


## Screen rectangle a slot covers, for hit-testing a drop against it. Empty
## when the slot is behind the camera, which cannot be hit anyway.
func screen_rect(camera: Camera3D, side: int, index: int) -> Rect2:
	var origin := transform_for(side, index).origin
	var half := Vector3(Card3D.WIDTH * 0.5, 0, Card3D.HEIGHT * 0.5)
	var rect := Rect2()
	for i in range(4):
		var corner := origin + Vector3(
			half.x if i < 2 else -half.x, 0, half.z if i % 2 == 0 else -half.z)
		if camera.is_position_behind(corner):
			return Rect2()
		var point := camera.unproject_position(corner)
		rect = Rect2(point, Vector2.ZERO) if i == 0 else rect.expand(point)
	return rect


func _stop_pulse(key: String) -> void:
	var pulse: Tween = _pulses.get(key)
	if pulse != null and pulse.is_valid():
		pulse.kill()
	_pulses.erase(key)


func _key(side: int, index: int) -> String:
	return "%d:%d" % [side, index]
