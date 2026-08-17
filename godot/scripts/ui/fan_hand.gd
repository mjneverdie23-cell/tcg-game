class_name FanHand
extends Control
## A hand of cards spread in an arc, the way you would actually hold them.
##
## Not a Container: the cards overlap, tilt, and lift out of the fan on
## hover, none of which a BoxContainer can express. Positions are recomputed
## from scratch on every refresh and on resize, so the fan reflows with the
## window instead of being pinned to pixels.
##
## A card is never played by clicking it. A press opens a gesture that
## becomes one of three things: drag the card out and drop it on the table
## to play it, hold it still to inspect it, or let go where it started —
## which plays nothing and only points at where the card could have gone.
## The fan knows nothing about legal plays, or even whose turn it is; it
## reports the gesture and the battle screen decides what it meant. That is
## deliberate: reading your own cards is something you do while waiting for
## the other player, so the fan stays alive on their turn too and only what
## the gesture is allowed to *do* changes.
##
## The same control serves both players. The rival's hand is face-down and
## `inverted`, which flips the arc and the tilt so it hangs from the top of
## the screen rather than rising from the bottom.

## Released without ever leaving the fan: a look, not a play.
signal card_tapped(index: int)
## Held still long enough to mean "let me read this one".
signal card_held(index: int)
signal drag_started(index: int)
## Carried to a new pointer position, in viewport coordinates.
signal dragged(index: int, at: Vector2)
## Let go, in viewport coordinates. The card stays where it was dropped
## until the battle screen either plays it or calls return_card().
signal dropped(index: int, at: Vector2)

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
## Pointer travel that turns a press into a drag. Small enough that pulling
## a card out feels immediate, large enough that a shaky click is still a
## click.
const DRAG_THRESHOLD := 12.0
## Hold a card still this long to inspect it instead of playing it.
const HOLD_SECONDS := 0.9
## A carried card is slightly larger than one sitting in the fan.
const DRAG_SCALE := 1.05
## Draw order while dragging: over every other panel on the HUD.
const DRAG_Z := 30
const RETURN_TIME := 0.22
## Tint a card reaches at the end of a hold, so the gesture shows progress
## rather than leaving the player guessing how long the hold is.
const HOLD_TINT := Color(1.35, 1.25, 0.85)

## Face-down hands draw card backs and ignore the mouse entirely.
var face_down := false
## Hangs the fan from the top of the control instead of the bottom.
var inverted := false

var _slots: Array[Control] = []
## Resting modulate per slot, so the hold tint has something to return to.
var _tints: Array[Color] = []
## Which cards are on screen, in order — a change here needs a rebuild.
var _cards_shown := ""
## Which of them are playable — a change here is only a change of tint.
var _playable_shown := ""
## Index the mouse is currently over, or -1.
var _hovered := -1
## Index the pointer went down on, or -1 when no gesture is open.
var _pressed := -1
var _press_at := Vector2.ZERO
var _press_seconds := 0.0
var _dragging := false
## Set once a hold has fired: the release that ends it must not also count
## as a tap.
var _consumed := false


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_process(false)
	resized.connect(_layout)


## Rebuilds the fan. `cards` may hold nulls for a face-down hand; `playable`
## maps hand index -> true for cards with a legal play right now, which only
## dims the rest — every face-up card still answers the mouse.
##
## Only a change of cards rebuilds the fan. Which cards are playable changes
## every time the turn does, and rebuilding for that would throw away
## whatever gesture is in progress — a card being read must not be snatched
## out of the player's hand because the rival finished their turn.
func set_hand(cards: Array, playable: Dictionary) -> void:
	var layout := _layout_signature(cards)
	var lit := _playable_signature(cards.size(), playable)
	if layout == _cards_shown:
		if lit != _playable_shown:
			_playable_shown = lit
			_retint(playable)
		return
	_cards_shown = layout
	_playable_shown = lit
	_end_gesture()
	for slot in _slots:
		slot.queue_free()
	_slots.clear()
	_tints.clear()
	_hovered = -1
	for i in range(cards.size()):
		var slot := _make_slot(cards[i] as CardData, playable.has(i), i)
		add_child(slot)
		_slots.append(slot)
		_tints.append(slot.modulate)
	_layout()


## The card widget at `index`, so the battle screen can fly a ghost to it or
## animate it in. Null when the index is out of range.
func slot_at(index: int) -> Control:
	if index < 0 or index >= _slots.size():
		return null
	return _slots[index]


func count() -> int:
	return _slots.size()


## Sends a dropped card back to its place in the fan — the drop landed
## somewhere that plays nothing.
func return_card(index: int) -> void:
	if index < 0 or index >= _slots.size():
		return
	var slot := _slots[index]
	slot.z_index = 0
	var from_position := slot.position
	var from_scale := slot.scale
	var from_rotation := slot.rotation
	_layout()
	if Settings.reduced_motion:
		return
	var to_position := slot.position
	var to_scale := slot.scale
	var to_rotation := slot.rotation
	slot.position = from_position
	slot.scale = from_scale
	slot.rotation = from_rotation
	var tween := slot.create_tween().set_parallel()
	tween.tween_property(slot, "position", to_position, RETURN_TIME) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tween.tween_property(slot, "scale", to_scale, RETURN_TIME)
	tween.tween_property(slot, "rotation", to_rotation, RETURN_TIME)


func _layout_signature(cards: Array) -> String:
	var parts := PackedStringArray()
	for card: CardData in cards:
		parts.append("." if card == null else card.id)
	return "|".join(parts)


func _playable_signature(count: int, playable: Dictionary) -> String:
	var parts := PackedStringArray()
	for i in range(count):
		parts.append("1" if playable.has(i) else "0")
	return "".join(parts)


## Same cards, different dimming. The card in the middle of a gesture keeps
## whatever tint that gesture is painting on it; _process reads the new
## resting tint from _tints and carries on from there.
func _retint(playable: Dictionary) -> void:
	for i in range(_slots.size()):
		_tints[i] = Color.WHITE if playable.has(i) else Color(0.62, 0.66, 0.76, 0.85)
		if i != _pressed:
			_slots[i].modulate = _tints[i]


func _make_slot(card: CardData, is_playable: bool, index: int) -> Control:
	var size_px := CARD_SIZE * CARD_SCALE
	# A plain Control, not a Button: every gesture here is hand-rolled, and a
	# Button would fire `pressed` on release no matter how the card moved in
	# between.
	var slot := Control.new()
	slot.size = size_px
	slot.custom_minimum_size = size_px
	slot.pivot_offset = Vector2(size_px.x * 0.5, size_px.y)  # tilt around the base
	slot.mouse_filter = (
		Control.MOUSE_FILTER_IGNORE if face_down else Control.MOUSE_FILTER_STOP)
	if not face_down:
		slot.gui_input.connect(_on_slot_input.bind(index))
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

	slot.tooltip_text = "%s\nDrag onto the table to play  ·  hold to read" % card.display_name
	var face: CardFace = preload("res://scenes/cards/card_face.tscn").instantiate()
	face.scale = Vector2(CARD_SCALE, CARD_SCALE)
	slot.add_child(face)
	face.show_card(card)
	face.make_input_transparent()  # the slot underneath owns the gesture
	return slot


# ── the press gesture ─────────────────────────────────────────────────
# Only the press itself arrives through the card's own gui_input; the rest
# of the gesture happens with the pointer out over the table, so motion and
# release are read from _input like the energy well does.


func _on_slot_input(event: InputEvent, index: int) -> void:
	if not (event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT):
		return
	if not (event as InputEventMouseButton).pressed:
		return
	_pressed = index
	# A GUI event arrives already transformed into the card's own space, so
	# it is put back through the card's transform rather than read off the
	# pointer: every later position in this gesture comes from an event too,
	# and the two have to be measured in the same space.
	_press_at = _slots[index].get_global_transform() * (
		event as InputEventMouseButton).position
	_press_seconds = 0.0
	_dragging = false
	_consumed = false
	set_process(true)
	accept_event()


func _input(event: InputEvent) -> void:
	if _pressed == -1:
		return
	if event is InputEventMouseMotion:
		var at := (event as InputEventMouseMotion).position
		if not _dragging and not _consumed and at.distance_to(_press_at) > DRAG_THRESHOLD:
			_begin_drag()
		if _dragging:
			_carry(at)
			dragged.emit(_pressed, at)
	elif event is InputEventMouseButton and not (event as InputEventMouseButton).pressed \
			and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		_release((event as InputEventMouseButton).position)


## Runs only while a press is open, and only to time a hold.
func _process(delta: float) -> void:
	if _pressed == -1 or _dragging or _consumed:
		return
	_press_seconds += delta
	var slot := _slots[_pressed]
	slot.modulate = _tints[_pressed].lerp(HOLD_TINT, minf(1.0, _press_seconds / HOLD_SECONDS))
	if _press_seconds < HOLD_SECONDS:
		return
	_consumed = true
	slot.modulate = _tints[_pressed]
	card_held.emit(_pressed)


func _begin_drag() -> void:
	var slot := _slots[_pressed]
	_dragging = true
	slot.modulate = _tints[_pressed]
	slot.z_index = DRAG_Z
	slot.rotation = 0.0
	slot.scale = Vector2.ONE * DRAG_SCALE
	slot.move_to_front()
	drag_started.emit(_pressed)


## Carries the card under the pointer. The scale pivots on the card's base,
## not its middle, so the visual centre is not simply size * 0.5.
func _carry(at: Vector2) -> void:
	var slot := _slots[_pressed]
	var local: Vector2 = get_global_transform().affine_inverse() * at
	slot.position = local - Vector2(
		slot.size.x * 0.5, slot.size.y * (1.0 - DRAG_SCALE * 0.5))


func _release(at: Vector2) -> void:
	var index := _pressed
	var was_dragging := _dragging
	var was_consumed := _consumed
	_end_gesture()
	if index < 0 or index >= _slots.size():
		return
	_slots[index].modulate = _tints[index]
	if was_dragging:
		dropped.emit(index, at)
	elif not was_consumed:
		card_tapped.emit(index)


func _end_gesture() -> void:
	_pressed = -1
	_dragging = false
	_consumed = false
	_press_seconds = 0.0
	set_process(false)


func _on_slot_hover(index: int, entered: bool) -> void:
	if _dragging:
		return
	if entered:
		_hovered = index
		_slots[index].move_to_front()  # never peek out from under a neighbour
	elif _hovered == index:
		_hovered = -1
	_layout()


## Positions every card: linear horizontal spacing, an arc in y, and a tilt
## that grows toward the edges. The card being carried is left alone — the
## pointer owns it until it is dropped.
func _layout() -> void:
	var total := _slots.size()
	if total == 0:
		return
	var size_px := CARD_SIZE * CARD_SCALE
	var step := minf(MAX_STEP, maxf(28.0, (size.x - size_px.x) / maxf(1.0, total - 1.0)))
	var spread := minf(MAX_SPREAD, total * 4.5)
	var base_y := size.y - size_px.y if not inverted else 0.0

	for i in range(total):
		if _dragging and i == _pressed:
			continue
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
