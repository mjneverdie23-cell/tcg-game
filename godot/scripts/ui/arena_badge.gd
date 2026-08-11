class_name ArenaBadge
extends Control
## The hexagonal arena plaque under the home-screen hero: a filled hex with
## a gold rim, the arena number and its name. Drawn rather than imported so
## the plate always matches the label it wraps.

const NAME_GAP := 6

var arena_number: int = 1:
	set(value):
		arena_number = value
		_sync()

var arena_name: String = "":
	set(value):
		arena_name = value
		_sync()

var _label: Label = null


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(260, 96)
	_label = Label.new()
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_label)
	resized.connect(queue_redraw)
	_sync()


func _sync() -> void:
	if _label == null:
		return
	_label.text = ("Arena %d" % arena_number if arena_name == ""
		else "Arena %d\n%s" % [arena_number, arena_name])
	queue_redraw()


func _draw() -> void:
	var points := _hexagon()
	draw_colored_polygon(points, MenuStyle.PANEL_SOFT)
	# Closed outline: repeat the first point so the rim has no gap.
	var outline := points.duplicate()
	outline.append(points[0])
	draw_polyline(outline, MenuStyle.ACCENT, 3.0, true)


## Flat-topped hexagon inscribed in the control, with the points pulled in
## horizontally so it reads as a plaque rather than a regular hex.
func _hexagon() -> PackedVector2Array:
	var inset := size.x * 0.16
	return PackedVector2Array([
		Vector2(inset, 0.0),
		Vector2(size.x - inset, 0.0),
		Vector2(size.x, size.y * 0.5),
		Vector2(size.x - inset, size.y),
		Vector2(inset, size.y),
		Vector2(0.0, size.y * 0.5),
	])
