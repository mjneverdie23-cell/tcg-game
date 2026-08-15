class_name BattleZoom
extends Node
## The action zoom: one of your dinosaurs, blown up, with everything you can
## do with it laid directly on the card.
##
## Everything lives on the card itself. The energy attached to it sits in the
## bottom-left corner, and each attack row and the retreat cell carry an
## invisible hit target. Nothing is repeated around it — no panel frame and
## no title bar — because the card already prints its own name, HP, and what
## every attack costs and does.
##
## Split out of battle.gd because it is a self-contained view: give it a
## dinosaur, and it reports back the one thing the player picked.

signal attack_chosen(action: Dictionary)
## The player asked to retreat; the battle screen runs the swap choice.
signal retreat_requested

const CARD_FACE_SCENE := preload("res://scenes/cards/card_face.tscn")
## Card face scale inside the zoom.
const CARD_SCALE := 1.05
## Energy balls in the card's bottom-left corner: where they sit in the
## card's own 250x350 design space, and how big each one is.
const ENERGY_CORNER := Vector2(14, 300)
const ENERGY_SIZE := 11
## Slack around a row so its hit target is comfortable to click.
const HIT_PADDING := 3.0

var _root: Control
var _face_box: Control
var _engine: BattleEngine = null
var _dino: DinoInPlay = null


## `backdrop` dismisses the zoom when clicked — the card is the panel, so
## there is no close button to place.
func setup(root: Control, backdrop: Control, face_box: Control) -> void:
	_root = root
	_face_box = face_box
	backdrop.gui_input.connect(_on_backdrop_input)


func open(engine: BattleEngine, dino: DinoInPlay) -> void:
	_engine = engine
	_dino = dino
	_root.visible = true
	refresh()


func refresh() -> void:
	if _engine == null or _dino == null \
			or not _engine.players[0].dinos_in_play().has(_dino):
		close()
		return
	var is_active := _dino == _engine.players[0].active
	var your_turn := _engine.current == 0 and not _engine.is_over()

	for child in _face_box.get_children():
		child.queue_free()
	var holder := Control.new()
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.custom_minimum_size = CardStyle.BASE_SIZE * CARD_SCALE
	var face: CardFace = CARD_FACE_SCENE.instantiate()
	face.scale = Vector2(CARD_SCALE, CARD_SCALE)
	holder.add_child(face)
	face.show_card(_dino.card())
	face.make_input_transparent()  # the hit targets on top own the clicks
	_face_box.add_child(holder)

	# The card face and its rows are Containers: a child added to them gets
	# laid out, not positioned. So the overlays are parented to the plain
	# holder and placed over the rows' rects — which only exist after a
	# layout pass, hence the one-frame wait.
	var settle := holder.create_tween()
	settle.tween_interval(0.02)
	settle.tween_callback(_place_overlays.bind(holder, face, is_active, your_turn))


func close() -> void:
	_root.visible = false
	_dino = null


func is_open() -> bool:
	return _root.visible


## The dinosaur on display, or null — the battle screen needs it to know
## which retreat the player asked for.
func subject() -> DinoInPlay:
	return _dino


func _place_overlays(
		holder: Control, face: CardFace, is_active: bool, your_turn: bool) -> void:
	if not (is_instance_valid(holder) and is_instance_valid(face)) or _dino == null:
		return
	_add_energy(holder)

	var legal: Dictionary = {}
	if is_active and your_turn:
		for action: Dictionary in _engine.get_legal_actions():
			if action["type"] == "attack":
				legal[int(action["index"])] = action

	for index in range(_dino.card().attacks.size()):
		var row := face.attack_row(index)
		if row == null:
			continue
		var hit := _hit_target(holder, row, legal.has(index))
		if legal.has(index):
			hit.tooltip_text = "Attack for %d damage" % _engine.preview_damage(index)
			hit.pressed.connect(_on_attack.bind(legal[index]))
		else:
			hit.tooltip_text = _attack_block_reason(is_active, your_turn)

	var cell := face.retreat_cell()
	if cell == null:
		return
	var can_retreat := your_turn and is_active and _engine.get_legal_actions().any(
		func(action: Dictionary) -> bool: return action["type"] == "retreat")
	var retreat_hit := _hit_target(holder, cell, can_retreat)
	if can_retreat:
		retreat_hit.tooltip_text = "Retreat for %d energy" % _engine.retreat_cost(0)
		retreat_hit.pressed.connect(_on_retreat)
	else:
		retreat_hit.tooltip_text = (
			"Only your Active dinosaur can retreat" if not is_active
			else "Not enough energy to retreat")


## Energy attached to this dinosaur, as balls in the card's bottom-left
## corner — the same ball the player dragged off the well.
func _add_energy(holder: Control) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 3)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(row)
	row.position = ENERGY_CORNER * CARD_SCALE
	for i in range(_dino.energy):
		var ball := EnergyOrb.new()
		ball.color = CardStyle.TYPE_COLORS[_engine.players[0].element]
		ball.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ball.custom_minimum_size = Vector2.ONE * ENERGY_SIZE * CARD_SCALE
		row.add_child(ball)


## A transparent button covering `over`, added to `holder`. Never `flat`:
## a flat Button skips stylebox drawing altogether, which silently threw
## away the hover glow. Instead every state carries its own box — fully
## transparent when the action is unavailable, a faint gold outline when it
## is, and a thicker outline with a soft bloom under the cursor.
func _hit_target(holder: Control, over: Control, enabled: bool) -> Button:
	var hit := Button.new()
	hit.focus_mode = Control.FOCUS_NONE
	hit.disabled = not enabled
	hit.add_theme_stylebox_override("disabled", _hit_box(0.0, 0, false))
	if enabled:
		hit.add_theme_stylebox_override("normal", _hit_box(0.0, 2, false))
		hit.add_theme_stylebox_override("hover", _hit_box(0.16, 3, true))
		hit.add_theme_stylebox_override("pressed", _hit_box(0.26, 3, true))
	holder.add_child(hit)
	var rect := over.get_global_rect().grow(HIT_PADDING)
	hit.position = rect.position - holder.global_position
	hit.size = rect.size
	return hit


func _hit_box(fill_alpha: float, border: int, lit: bool) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = Color(CardStyle.GOLD, fill_alpha)
	box.set_corner_radius_all(6)
	box.set_border_width_all(border)
	box.border_color = Color(CardStyle.GOLD, 1.0 if lit else 0.5)
	if lit:
		box.shadow_color = Color(CardStyle.GOLD, 0.5)
		box.shadow_size = 8
	return box


func _attack_block_reason(is_active: bool, your_turn: bool) -> String:
	if not is_active:
		return "Only your Active dinosaur can attack"
	if not your_turn:
		return "Wait for your turn"
	if _engine.turn_number < 2:
		return "No attack on turn 1"
	if _engine.players[1].active == null:
		return "The rival has not fielded a dinosaur yet"
	return "Not enough energy attached"


func _on_backdrop_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed:
		close()


func _on_attack(action: Dictionary) -> void:
	close()
	attack_chosen.emit(action)


func _on_retreat() -> void:
	close()
	retreat_requested.emit()
