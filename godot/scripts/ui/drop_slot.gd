class_name DropSlot
extends Control
## The hollow card frame in the middle of the table. Spells, Supports and
## Environments are not aimed at anything on the board, so they are played
## by dropping them here — the same gesture as fielding a dinosaur, with a
## place to aim it.
##
## Drawn rather than themed: a dashed outline says "put something here" in a
## way a filled panel cannot, and drawing it keeps the dash spacing correct
## at any size instead of stretching a nine-patch.

## Dash geometry along the outline.
const DASH := 13.0
const GAP := 9.0
const CORNER := 14.0
## Fill under the frame when a card is hovering over it.
const ACTIVE_FILL := 0.14

## True while a dragged card is over the slot: the frame lights up and grows
## a little, so the player can see the drop will land before they let go.
var active := false:
	set(value):
		if active == value:
			return
		active = value
		_label.modulate = Color.WHITE if active else Color(1, 1, 1, 0.75)
		queue_redraw()
		_pop()

var _label := Label.new()


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE  # never eats a drop
	pivot_offset = size * 0.5
	_label.text = "Play"
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_label.add_theme_color_override("font_color", CardStyle.GOLD)
	_label.add_theme_font_size_override("font_size", 20)
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_label)
	resized.connect(func() -> void:
		pivot_offset = size * 0.5
		queue_redraw())


## What the slot is asking for right now ("Play this Spell").
func set_prompt(text: String) -> void:
	_label.text = text


func _draw() -> void:
	var rect := Rect2(Vector2.ZERO, size)
	var color := Color(CardStyle.GOLD, 0.95 if active else 0.5)
	if active:
		draw_rect(rect, Color(CardStyle.GOLD, ACTIVE_FILL), true)
	_dashed_rect(rect, color, 3.0 if active else 2.0)


## The outline, as dashes running around a rectangle with clipped corners —
## close enough to a rounded frame at this stroke width, and exact about
## where the dashes fall.
func _dashed_rect(rect: Rect2, color: Color, width: float) -> void:
	var corners: Array[Vector2] = [
		rect.position + Vector2(CORNER, 0),
		rect.position + Vector2(rect.size.x - CORNER, 0),
		rect.position + Vector2(rect.size.x, CORNER),
		rect.position + Vector2(rect.size.x, rect.size.y - CORNER),
		rect.position + Vector2(rect.size.x - CORNER, rect.size.y),
		rect.position + Vector2(CORNER, rect.size.y),
		rect.position + Vector2(0, rect.size.y - CORNER),
		rect.position + Vector2(0, CORNER),
	]
	for i in range(corners.size()):
		_dashed_line(corners[i], corners[(i + 1) % corners.size()], color, width)


func _dashed_line(from: Vector2, to: Vector2, color: Color, width: float) -> void:
	var span := from.distance_to(to)
	if span <= 0.0:
		return
	var step := DASH + GAP
	var direction := (to - from) / span
	var travelled := 0.0
	while travelled < span:
		var end := minf(travelled + DASH, span)
		draw_line(from + direction * travelled, from + direction * end, color, width, true)
		travelled += step


func _pop() -> void:
	if Settings.reduced_motion:
		return
	var tween := create_tween()
	tween.tween_property(self, "scale", Vector2.ONE * (1.06 if active else 1.0), 0.12) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
