class_name BattleFx
extends Node
## The battle screen's presentation layer: camera moves, the HUD entrance,
## the turn banner, and the 2D card ghosts that fly between the deck, the
## hand and the used piles.
##
## Split out of battle.gd because none of it touches the rules — it only
## needs the camera, the HUD layer to draw into, and a banner to write on.
## Everything here is fire-and-forget and gated on reduced motion.

const CARD_FACE_SCENE := preload("res://scenes/cards/card_face.tscn")
## Size of the card ghosts that fly between the piles, the hand and the board.
const GHOST_SCALE := 0.3
## Flight time deck -> hand. A drawn card only appears in the hand once its
## ghost lands, so the two read as one movement.
const DRAW_FLIGHT := 0.38
## Flight time hand/board -> used pile.
const DISCARD_FLIGHT := 0.45

## How long the camera takes to push in on a row and to come back out.
const FOCUS_TIME := 0.4
## How long a notice stays up before it fades.
const NOTICE_SECONDS := 1.8

var _hud: Control
var _camera: Camera3D
var _banner: Label
var _notice: Label
## The notice's resting y, so it can rise into place from below it.
var _notice_home := 0.0
## Camera fov authored in the scene — the attack punch returns to exactly
## this value instead of a hardcoded one.
var _base_fov := 46.0
## Camera pose authored in the scene: the resting view of the whole table,
## and what release_focus() returns to.
var _home_view: Transform3D
## The focus move in flight, killed before another starts so a fast
## cancel-and-refocus cannot leave two tweens fighting over the camera.
var _focus_move: Tween = null


func setup(hud: Control, camera: Camera3D, banner: Label, notice_label: Label) -> void:
	_hud = hud
	_camera = camera
	_banner = banner
	_notice = notice_label
	_notice_home = notice_label.position.y
	_base_fov = camera.fov
	_home_view = camera.transform


## Small card ghost gliding across the HUD — the visual link between a zone
## and a pile. `card` renders the real face; null shows a card back.
func fly(card: CardData, from: Vector2, to: Vector2, duration: float,
		delay: float = 0.0, landed: Callable = Callable()) -> void:
	if Settings.reduced_motion:
		if landed.is_valid():
			landed.call()
		return
	var ghost := _make_ghost(card)
	_hud.add_child(ghost)
	ghost.global_position = from - ghost.size * 0.5
	ghost.scale = Vector2(0.7, 0.7)
	ghost.modulate.a = 0.0
	var tween := create_tween()
	if delay > 0.0:
		tween.tween_interval(delay)
	tween.tween_property(ghost, "global_position", to - ghost.size * 0.5, duration) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	tween.parallel().tween_property(ghost, "modulate:a", 1.0, duration * 0.3)
	tween.parallel().tween_property(ghost, "scale", Vector2.ONE, duration * 0.5)
	tween.tween_property(ghost, "scale", Vector2(0.55, 0.55), 0.12)
	tween.parallel().tween_property(ghost, "modulate:a", 0.0, 0.12)
	tween.tween_callback(ghost.queue_free)
	if landed.is_valid():
		tween.tween_callback(landed)


func _make_ghost(card: CardData) -> Control:
	var ghost := Control.new()
	ghost.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ghost.custom_minimum_size = CardStyle.BASE_SIZE * GHOST_SCALE
	ghost.size = CardStyle.BASE_SIZE * GHOST_SCALE
	ghost.pivot_offset = ghost.size * 0.5
	ghost.z_index = 10  # above the dock and the panels it flies over
	if card == null:
		var back := Panel.new()
		back.mouse_filter = Control.MOUSE_FILTER_IGNORE
		back.size = ghost.size
		back.add_theme_stylebox_override("panel", CardStyle.make_panel(
			Color("111a33"), 8, CardStyle.GOLD, 2))
		ghost.add_child(back)
		return ghost
	var face: CardFace = CARD_FACE_SCENE.instantiate()
	face.scale = Vector2(GHOST_SCALE, GHOST_SCALE)
	ghost.add_child(face)
	face.show_card(card)
	return ghost


## Small bump on a pile as a card lands on it.
func pile_thump(pile: Node3D) -> void:
	if Settings.reduced_motion or not is_instance_valid(pile):
		return
	var tween := pile.create_tween()
	tween.tween_property(pile, "scale", Vector3(1.0, 1.6, 1.0), 0.09)
	tween.tween_property(pile, "scale", Vector3.ONE, 0.18) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


# ── 3D board presentation ─────────────────────────────────────────────


## Newly drawn cards fly out of the deck pile and pop into the hand,
## staggered by draw order. The card itself only animates scale and alpha —
## the fan owns its positions and would overwrite any `position` tween on the
## next layout pass — so the travel is carried by a ghost that hands over
## exactly when the card appears.
func deal_in(button: Control, order: int, from: Vector2) -> void:
	if Settings.reduced_motion:
		return
	var target_alpha := button.modulate.a  # dimmed-if-unplayable tint is set already
	button.modulate.a = 0.0
	button.scale = Vector2(0.72, 0.72)
	var delay := order * 0.09
	# Tweens bound to the button, not the scene: a refresh rebuilds the hand,
	# and a card that no longer exists must not keep animating.
	var settle := button.create_tween()
	settle.tween_interval(0.02)  # one frame, so the dock has placed the card
	settle.tween_callback(_launch_draw_ghost.bind(button, delay, from))
	var tween := button.create_tween().set_parallel()
	tween.tween_property(button, "scale", Vector2.ONE, 0.3) \
		.set_delay(delay + DRAW_FLIGHT).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(button, "modulate:a", target_alpha, 0.24) \
		.set_delay(delay + DRAW_FLIGHT)


func _launch_draw_ghost(button: Control, delay: float, from: Vector2) -> void:
	if not is_instance_valid(button):
		return
	fly(null, from, button.get_global_rect().get_center(), DRAW_FLIGHT, delay)


## Viewport position of a board card, so 3D cards can hand off to 2D piles.
func screen_of(node: Node3D) -> Vector2:
	if node == null or not is_instance_valid(node):
		return _hud.size * 0.5
	return _camera.unproject_position(node.global_position)


## Smooth descent from an overview to the play angle when a battle starts.
func intro_camera() -> void:
	if Settings.reduced_motion:
		return
	var play := _home_view
	var overview := play
	overview.origin += Vector3(0, 3.5, 4.0)
	_camera.transform = overview
	var tween := create_tween()
	tween.tween_property(_camera, "transform", play, 1.1) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


## Pushes the camera in until `target` fills the view from `distance` away,
## keeping the authored viewing angle — used when the player is asked to
## pick from a row, so the row they are picking from is what they see.
func focus_point(target: Vector3, distance: float) -> void:
	# basis.z is the camera's backward axis, so stepping along it from the
	# target puts the camera in front of it without changing the angle.
	_move_camera(Transform3D(_home_view.basis, target + _home_view.basis.z * distance))


func release_focus() -> void:
	_move_camera(_home_view)


func _move_camera(view: Transform3D) -> void:
	if _focus_move != null and _focus_move.is_valid():
		_focus_move.kill()
	if Settings.reduced_motion:
		_camera.transform = view
		return
	_focus_move = create_tween()
	_focus_move.tween_property(_camera, "transform", view, FOCUS_TIME) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


## Brief zoom pulse that sells an attack landing.
func camera_punch() -> void:
	if Settings.reduced_motion:
		return
	var tween := create_tween()
	tween.tween_property(_camera, "fov", _base_fov - 3.0, 0.12)
	tween.tween_property(_camera, "fov", _base_fov, 0.3)


## Slides the HUD panels in from their own edges when a battle begins.
## `panels` maps each Control to the offset it starts from, so this layer
## never has to know the battle scene's node names.
func hud_entrance(panels: Dictionary) -> void:
	if Settings.reduced_motion:
		return
	for panel: Control in panels:
		var offset: Vector2 = panels[panel]
		panel.position += offset
		panel.modulate.a = 0.0
		var tween := create_tween().set_parallel()
		tween.tween_property(panel, "position", panel.position - offset, 0.45) \
			.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		tween.tween_property(panel, "modulate:a", 1.0, 0.35)


## A line that speaks up when the game refuses something, or when something
## happened that the player did not ask for. Sits above the hand, holds long
## enough to read, and takes itself away.
func notice(text: String) -> void:
	var label: Label = _notice
	label.text = text
	if Settings.reduced_motion:
		label.modulate.a = 1.0
		var hold := label.create_tween()
		hold.tween_interval(NOTICE_SECONDS)
		hold.tween_callback(func() -> void: label.modulate.a = 0.0)
		return
	label.modulate.a = 0.0
	label.position.y = _notice_home + 12.0
	var tween := label.create_tween()
	tween.tween_property(label, "modulate:a", 1.0, 0.14)
	tween.parallel().tween_property(label, "position:y", _notice_home, 0.22) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tween.tween_interval(NOTICE_SECONDS)
	tween.tween_property(label, "modulate:a", 0.0, 0.3)


## Big centred announcement whenever the turn changes hands.
func turn_banner(your_turn: bool) -> void:
	var banner: Label = _banner
	banner.text = "Your Turn" if your_turn else "Rival's Turn"
	banner.add_theme_color_override(
		"font_color", CardStyle.GOLD if your_turn else Color("ff8a7a"))
	if Settings.reduced_motion:
		return
	banner.pivot_offset = banner.size * 0.5
	banner.scale = Vector2(0.85, 0.85)
	banner.modulate.a = 0.0
	var tween := create_tween()
	tween.tween_property(banner, "modulate:a", 1.0, 0.16)
	tween.parallel().tween_property(banner, "scale", Vector2.ONE, 0.28) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_interval(0.5)
	tween.tween_property(banner, "modulate:a", 0.0, 0.25)
