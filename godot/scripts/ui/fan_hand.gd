class_name FanHand
extends Control
## A hand of cards spread in an arc, the way you would actually hold them.
##
## Not a Container: the cards overlap, tilt, and lift out of the fan on
## hover, none of which a BoxContainer can express. Positions are recomputed
## from scratch on every refresh and on resize, so the fan reflows with the
## window instead of being pinned to pixels.
##
## The same control serves both players. The rival's hand is face-down and
## `inverted`, which flips the arc and the tilt so it hangs from the top of
## the screen rather than rising from the bottom.

signal card_pressed(index: int)

const CARD_SCALE := 0.36
const CARD_SIZE := Vector2(250, 350)
## Widest total tilt across the fan, in degrees. Beyond this a big hand
## starts to look like a peacock rather than a hand of cards.
const MAX_SPREAD := 26.0
## How far the outer cards drop below the middle one.
const ARC_DEPTH := 26.0
## Horizontal step between neighbours, capped so a big hand still fits.
const MAX_STEP := 78.0
const HOVER_LIFT := 52.0
const HOVER_SCALE := 1.16

## Face-down hands draw card backs and ignore the mouse entirely.
var face_down := false
## Hangs the fan from the top of the control instead of the bottom.
var inverted := false

var _slots: Array[Control] = []
## Index the mouse is currently over, or -1.
var _hovered := -1


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(_layout)


## Rebuilds the fan. `cards` may hold nulls for a face-down hand; `playable`
## maps hand index -> true for cards with a legal play right now.
func set_hand(cards: Array, playable: Dictionary, interactive: bool) -> void:
	for slot in _slots:
		slot.queue_free()
	_slots.clear()
	_hovered = -1
	for i in range(cards.size()):
		var slot := _make_slot(cards[i] as CardData, playable.has(i), interactive, i)
		add_child(slot)
		_slots.append(slot)
	_layout()


## The card widget at `index`, so the battle screen can fly a ghost to it or
## animate it in. Null when the index is out of range.
func slot_at(index: int) -> Control:
	if index < 0 or index >= _slots.size():
		return null
	return _slots[index]


func count() -> int:
	return _slots.size()


func _make_slot(card: CardData, is_playable: bool, interactive: bool, index: int) -> Control:
	var size_px := CARD_SIZE * CARD_SCALE
	var slot := Button.new()
	slot.flat = true
	slot.focus_mode = Control.FOCUS_NONE
	slot.size = size_px
	slot.pivot_offset = Vector2(size_px.x * 0.5, size_px.y)  # tilt around the base
	slot.mouse_filter = (
		Control.MOUSE_FILTER_STOP if interactive and not face_down
		else Control.MOUSE_FILTER_IGNORE)
	if interactive and not face_down:
		slot.pressed.connect(card_pressed.emit.bind(index))
		slot.mouse_entered.connect(_on_slot_hover.bind(index, true))
		slot.mouse_exited.connect(_on_slot_hover.bind(index, false))
		# Cards with no legal play stay in the fan but read as inert.
		slot.modulate = Color.WHITE if is_playable else Color(0.62, 0.66, 0.76, 0.85)

	if face_down or card == null:
		var back := Panel.new()
		back.size = size_px
		back.mouse_filter = Control.MOUSE_FILTER_IGNORE
		back.add_theme_stylebox_override("panel", CardStyle.make_panel(
			Color("111a33"), 10, CardStyle.GOLD, 2))
		slot.add_child(back)
		return slot

	slot.tooltip_text = card.display_name
	var face: CardFace = preload("res://scenes/cards/card_face.tscn").instantiate()
	face.scale = Vector2(CARD_SCALE, CARD_SCALE)
	slot.add_child(face)
	face.show_card(card)
	return slot


func _on_slot_hover(index: int, entered: bool) -> void:
	if entered:
		_hovered = index
		_slots[index].move_to_front()  # never peek out from under a neighbour
	elif _hovered == index:
		_hovered = -1
	_layout()


## Positions every card: linear horizontal spacing, an arc in y, and a tilt
## that grows toward the edges.
func _layout() -> void:
	var total := _slots.size()
	if total == 0:
		return
	var size_px := CARD_SIZE * CARD_SCALE
	var step := minf(MAX_STEP, maxf(28.0, (size.x - size_px.x) / maxf(1.0, total - 1.0)))
	var spread := minf(MAX_SPREAD, total * 4.5)
	var base_y := size.y - size_px.y if not inverted else 0.0

	for i in range(total):
		# -1 .. 1 across the fan; 0 for a single card.
		var t := 0.0 if total == 1 else (float(i) / float(total - 1)) * 2.0 - 1.0
		var angle := deg_to_rad(t * spread * 0.5)
		var arc := (1.0 - cos(angle)) / maxf(0.0001, 1.0 - cos(deg_to_rad(spread * 0.5)))
		var offset := Vector2(
			size.x * 0.5 - size_px.x * 0.5 + (float(i) - (total - 1) * 0.5) * step,
			base_y + arc * ARC_DEPTH * (-1.0 if inverted else 1.0))

		var slot := _slots[i]
		var lifted := i == _hovered
		if lifted:
			offset.y += HOVER_LIFT * (1.0 if inverted else -1.0)
		slot.position = offset
		slot.rotation = 0.0 if lifted else angle * (-1.0 if inverted else 1.0)
		slot.scale = Vector2.ONE * (HOVER_SCALE if lifted else 1.0)
