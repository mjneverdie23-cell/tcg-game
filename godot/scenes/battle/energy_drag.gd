class_name EnergyDrag
extends Node
## Dragging the turn's energy out of its well and onto a dinosaur.
##
## Hand-rolled rather than Godot's Control drag-and-drop, because that can
## only hand data between Controls and the drop targets here are 3D cards on
## a table. The well reports where the pointer went, a ray into the world
## says which card was under it, and this class turns that into "the player
## wants energy on that dinosaur" — which is all the battle screen is told.

## Dropped on one of your dinosaurs: -1 for the Active, 0.. for the bench.
signal attach_chosen(target: int)
## Let go on the well itself. That is a click, not a drag, so the battle
## screen falls back to asking which dinosaur.
signal pick_requested

## Reach of the pointer ray used to find the card under the well.
const RAY_LENGTH := 100.0
## Returned by target_of for a dinosaur that is not the local player's.
const INVALID_TARGET := -99
const GHOST_SIZE := Vector2(58, 58)

var _orb: EnergyOrb
var _hud: Control
var _camera: Camera3D
## DinoInPlay -> Card3D, held by reference: the battle screen keeps it up to
## date as the board changes and this always sees the current one.
var _card_nodes: Dictionary = {}
var _engine: BattleEngine = null
var _seat := 0
## Dome that follows the pointer while energy is being carried.
var _ghost: EnergyOrb = null


func setup(orb: EnergyOrb, hud: Control, camera: Camera3D, card_nodes: Dictionary) -> void:
	_orb = orb
	_hud = hud
	_camera = camera
	_card_nodes = card_nodes
	orb.drag_started.connect(_on_drag_started)
	orb.dragged.connect(_on_dragged)
	orb.dropped.connect(_on_dropped)


func attach(engine: BattleEngine, seat: int) -> void:
	_engine = engine
	_seat = seat


## Attach-action target for one of your dinosaurs: -1 for the Active, 0..
## for the bench, INVALID_TARGET when it is not yours.
func target_of(dino: DinoInPlay) -> int:
	var you := _engine.players[_seat]
	if dino == you.active:
		return -1
	for b in range(you.bench.size()):
		if you.bench[b] == dino:
			return b
	return INVALID_TARGET


func _on_drag_started() -> void:
	if _ghost != null:
		_ghost.queue_free()
	_ghost = EnergyOrb.new()
	_ghost.color = CardStyle.TYPE_COLORS[_engine.players[_seat].element]
	_ghost.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ghost.z_index = 20
	_hud.add_child(_ghost)
	_ghost.size = GHOST_SIZE


func _on_dragged(at: Vector2) -> void:
	if _ghost != null:
		_ghost.global_position = at - _ghost.size * 0.5
	# Light up whatever the energy is hovering, so the drop target reads.
	var target := _card_under(at)
	for dino: DinoInPlay in _card_nodes:
		var node := _card_nodes[dino] as Card3D
		node.set_selected(node == target and target_of(dino) != INVALID_TARGET)


func _on_dropped(at: Vector2) -> void:
	if _ghost != null:
		_ghost.queue_free()
		_ghost = null
	for dino: DinoInPlay in _card_nodes:
		(_card_nodes[dino] as Card3D).set_selected(false)

	var node := _card_under(at)
	if node == null:
		if _orb.get_global_rect().has_point(at):
			pick_requested.emit()
		return
	for dino: DinoInPlay in _card_nodes:
		if _card_nodes[dino] == node:
			attach_chosen.emit(target_of(dino))
			return


## The board card under a viewport position, via a ray against the pickable
## areas — the same ones that make cards clickable.
func _card_under(at: Vector2) -> Card3D:
	var origin := _camera.project_ray_origin(at)
	var query := PhysicsRayQueryParameters3D.create(
		origin, origin + _camera.project_ray_normal(at) * RAY_LENGTH)
	query.collide_with_areas = true
	query.collide_with_bodies = false
	var hit := _camera.get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return null
	return (hit["collider"] as Node).get_parent() as Card3D
