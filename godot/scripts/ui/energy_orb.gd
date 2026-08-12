class_name EnergyOrb
extends Control
## The turn's energy, drawn as a lit dome and dragged onto a dinosaur.
##
## Drag-and-drop is hand-rolled rather than Godot's Control drag: the drop
## targets are 3D cards on the table, and the built-in system only ever hands
## data between Controls. The orb reports where the pointer went up and lets
## the battle screen decide what was under it.

## Pressed and picked up.
signal drag_started
## Pointer moved while carrying it, in viewport coordinates.
signal dragged(at: Vector2)
## Released, in viewport coordinates. A release still inside the orb is a
## plain click and the battle screen falls back to a target menu.
signal dropped(at: Vector2)

const HIGHLIGHT := Color(1, 1, 1, 0.35)

## Element colour of the dome.
var color := Color("b18aff"):
	set(value):
		color = value
		queue_redraw()

## No energy left to attach this turn: the dome dims and stops responding.
var spent := false:
	set(value):
		spent = value
		queue_redraw()

var _dragging := false


func _ready() -> void:
	custom_minimum_size = Vector2(96, 62)
	mouse_filter = Control.MOUSE_FILTER_STOP
	resized.connect(queue_redraw)


func _gui_input(event: InputEvent) -> void:
	if spent:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT \
			and event.pressed:
		_dragging = true
		drag_started.emit()
		accept_event()


## Tracked here rather than in _gui_input because the pointer leaves the orb
## almost immediately — the rest of the gesture happens over the table.
func _input(event: InputEvent) -> void:
	if not _dragging:
		return
	if event is InputEventMouseMotion:
		dragged.emit(get_global_mouse_position())
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT \
			and not event.pressed:
		_dragging = false
		dropped.emit(get_global_mouse_position())


func _draw() -> void:
	var base := Vector2(size.x * 0.5, size.y - 6.0)
	var radius := minf(size.x * 0.5, size.y - 10.0)
	var fill := color if not spent else color.darkened(0.55)
	draw_colored_polygon(_dome(base, radius), fill.darkened(0.25))
	draw_colored_polygon(_dome(base, radius * 0.86), fill)
	# Specular cap, offset up-left, so the dome reads as a lit sphere.
	draw_colored_polygon(
		_dome(base - Vector2(radius * 0.22, radius * 0.34), radius * 0.34),
		HIGHLIGHT if not spent else Color(1, 1, 1, 0.12))
	var rim := _dome(base, radius)
	rim.append(rim[0])
	draw_polyline(rim, fill.lightened(0.35), 2.0, true)


## Closed polygon for the top half of a circle, flat side down.
func _dome(center: Vector2, radius: float) -> PackedVector2Array:
	var points := PackedVector2Array()
	for i in range(25):
		var angle := PI + PI * float(i) / 24.0
		points.append(center + Vector2(cos(angle), sin(angle)) * radius)
	return points
