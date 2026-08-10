class_name Card3D
extends Node3D
## A card as a 3D tabletop object: the 2D CardFace is rendered into a
## SubViewport and textured onto a quad, so every future face improvement
## (holo shaders, animated art) automatically appears in 3D. Reusable
## anywhere cards live in world space (battle board, future 3D menus).
##
## The node owns polished micro-interactions: hover raise, selection lift,
## smooth homing to a slot transform, attack lunge and a pulse for energy
## attachments. All motion is tween-based and respects reduced motion.
##
## A dinosaur card may also carry a real 3D model that stands on the card
## face (DinoCardData.model — see assets/models/README.md); the card is a
## plain Node3D, so the model is simply another child that inherits every
## slot move, lunge and knockout animation for free.

signal clicked(card: Card3D)

## World size of a card (design ratio 250x350).
const WIDTH := 0.9
const HEIGHT := 1.26
const HOVER_RAISE := 0.14
const SELECT_RAISE := 0.3
const MOVE_TIME := 0.35
## Height a dinosaur model stands at above the card face.
const MODEL_LIFT := 0.06
## Travel of the model's idle bob.
const MODEL_BOB := 0.05

var card_data: CardData = null
## Slot transform this card returns to after hover/selection.
var home_transform: Transform3D
var selected := false

var _face: CardFace
var _viewport: SubViewport
var _front: MeshInstance3D
var _info: Label3D
## Instanced DinoCardData.model, standing on the card face; null when the
## card has no model configured.
var _model: Node3D = null
var _idle: Tween = null
var _hovered := false
var _motion: Tween = null
## Set once vanish() starts: the card is leaving play, so every other
## motion request (recoil, hover, homing, pulse) must be ignored or it
## fights the exit animation.
var _dying := false


func _ready() -> void:
	_build_viewport()
	_build_meshes()
	_build_pickable_area()
	home_transform = transform
	if card_data != null:
		_render_face()


func show_card(card: CardData) -> void:
	card_data = card
	if is_inside_tree():
		_render_face()


## Status line floating above the card ("45/90 E2").
func set_info(text: String, color: Color = Color.WHITE) -> void:
	_info.text = text
	_info.modulate = color


## Tweens the card to a new slot (or snaps when animate is false).
func move_home(target: Transform3D, animate: bool = true) -> void:
	if _dying:
		return
	home_transform = target
	if not animate or Settings.reduced_motion:
		transform = target
		return
	_restart_motion().tween_property(self, "transform", target, MOVE_TIME) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


func set_selected(on: bool) -> void:
	if _dying:
		return
	selected = on
	_settle()


## Quick lunge toward `target_position` and back — attack motion.
func lunge(target_position: Vector3) -> void:
	if _dying or Settings.reduced_motion:
		return
	var toward := home_transform.translated(
		(target_position - home_transform.origin) * 0.35 + Vector3(0, 0.2, 0))
	var tween := _restart_motion()
	tween.tween_property(self, "transform", toward, 0.14) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tween.tween_property(self, "transform", _rest_transform(), 0.22) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)


## Scale pop — energy attach / heal feedback.
func pulse() -> void:
	if _dying or Settings.reduced_motion:
		return
	var tween := create_tween()
	tween.tween_property(self, "scale", Vector3.ONE * 1.12, 0.1)
	tween.tween_property(self, "scale", Vector3.ONE, 0.15)


## Floating damage number that rises off the card and fades away.
func show_damage(amount: int) -> void:
	# Deliberately NOT gated on _dying — a knockout is exactly when the
	# player most needs to see the number.
	var popup := Label3D.new()
	popup.text = "-%d" % amount
	popup.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	popup.font_size = 78
	popup.pixel_size = 0.004
	popup.outline_size = 14
	popup.modulate = Color("ff6a58")
	popup.no_depth_test = true
	var host: Node = get_parent() if get_parent() != null else self
	host.add_child(popup)
	popup.global_position = global_position + Vector3(0, 0.42, 0)
	if Settings.reduced_motion:
		# Still readable without motion: hold briefly, then clear.
		var hold := create_tween()
		hold.tween_interval(0.8)
		hold.tween_callback(popup.queue_free)
		return
	popup.scale = Vector3.ONE * 0.4
	var tween := create_tween()
	tween.tween_property(popup, "scale", Vector3.ONE * 1.15, 0.16) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(popup, "position", popup.position + Vector3(0, 0.75, 0), 0.65) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tween.parallel().tween_property(popup, "modulate:a", 0.0, 0.65)
	tween.tween_callback(popup.queue_free)


## Tints the card briefly — impact feedback (red), heal (green), buff (gold).
func flash(color: Color) -> void:
	var material := _front.material_override as StandardMaterial3D
	if _dying or material == null or Settings.reduced_motion:
		return
	var tween := create_tween()
	tween.tween_property(material, "albedo_color", color, 0.08)
	tween.tween_property(material, "albedo_color", Color.WHITE, 0.3)


## Short recoil away from `source_position` — being hit.
func recoil(source_position: Vector3) -> void:
	if _dying or Settings.reduced_motion:
		return
	var away := (home_transform.origin - source_position).normalized() * 0.18
	var tween := _restart_motion()
	tween.tween_property(self, "transform", home_transform.translated(away), 0.09) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(self, "transform", _rest_transform(), 0.28) \
		.set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)


## Rise, fade and free — knockout exit.
func vanish() -> void:
	_dying = true
	if _motion != null and _motion.is_valid():
		_motion.kill()
	if Settings.reduced_motion:
		queue_free()
		return
	var tween := create_tween()
	tween.tween_property(self, "position", position + Vector3(0, 1.4, 0), 0.45) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tween.parallel().tween_property(self, "rotation:z", PI * 0.6, 0.45)
	tween.parallel().tween_property(self, "scale", Vector3.ONE * 0.01, 0.45)
	tween.tween_callback(queue_free)


# ── construction ──────────────────────────────────────────────────────


func _build_viewport() -> void:
	_viewport = SubViewport.new()
	_viewport.size = Vector2i(250, 350)
	_viewport.transparent_bg = true
	# The viewport renders only a 2D CardFace. Give it its own (empty) 3D
	# world so it never shares — or interferes with — the battle's World3D.
	_viewport.own_world_3d = true
	_viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(_viewport)
	_face = preload("res://scenes/cards/card_face.tscn").instantiate()
	_viewport.add_child(_face)


func _build_meshes() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2(WIDTH, HEIGHT)

	_front = MeshInstance3D.new()
	_front.mesh = quad
	var front_material := StandardMaterial3D.new()
	front_material.albedo_texture = _viewport.get_texture()
	front_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	front_material.roughness = 0.4
	_front.material_override = front_material
	# Lie flat on the table, face up (+Y).
	_front.rotation_degrees = Vector3(-90, 0, 0)
	add_child(_front)

	var back := MeshInstance3D.new()
	back.mesh = quad
	var back_material := StandardMaterial3D.new()
	back_material.albedo_color = Color("111a33")
	back_material.roughness = 0.6
	back.material_override = back_material
	back.rotation_degrees = Vector3(90, 0, 0)
	back.position.y = -0.005
	add_child(back)

	_info = Label3D.new()
	_info.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_info.font_size = 40
	_info.pixel_size = 0.004
	_info.outline_size = 10
	_info.no_depth_test = true  # always legible, never behind a nearer card
	_info.position = Vector3(0, 0.34, 0)
	add_child(_info)


func _build_pickable_area() -> void:
	var area := Area3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(WIDTH, 0.06, HEIGHT)
	shape.shape = box
	area.add_child(shape)
	add_child(area)
	area.mouse_entered.connect(func() -> void: _set_hovered(true))
	area.mouse_exited.connect(func() -> void: _set_hovered(false))
	area.input_event.connect(_on_area_input)


func _on_area_input(
		_cam: Node, event: InputEvent, _pos: Vector3, _normal: Vector3, _shape: int) -> void:
	if event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		clicked.emit(self)


func _render_face() -> void:
	_face.show_card(card_data)
	# Render for a couple of frames so queued rebuild children get drawn,
	# then stop — the texture is static until the card changes.
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	var tween := create_tween()
	tween.tween_interval(0.2)
	tween.tween_callback(func() -> void:
		_viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED)
	_sync_model()


## Rebuilds the optional 3D model standing on the card. Nothing in the
## shipped catalog sets DinoCardData.model, so this is a no-op today; give a
## dinosaur a model path in cards.json and it appears here — the card face
## keeps rendering underneath it, unchanged.
func _sync_model() -> void:
	if _idle != null and _idle.is_valid():
		_idle.kill()
		_idle = null
	if _model != null:
		_model.queue_free()
		_model = null
	if not (card_data is DinoCardData):
		return
	var dino := card_data as DinoCardData
	if dino.model == "" or not ResourceLoader.exists(dino.model):
		return
	var packed := load(dino.model) as PackedScene
	if packed == null:
		push_error("Card3D: %s is not a PackedScene" % dino.model)
		return
	_model = packed.instantiate() as Node3D
	if _model == null:
		push_error("Card3D: %s does not instantiate a Node3D" % dino.model)
		return
	add_child(_model)
	_model.scale = Vector3.ONE * dino.model_scale
	_model.position = Vector3(0, MODEL_LIFT, 0)
	if Settings.reduced_motion:
		return
	# Slow idle bob so a model reads as alive rather than as scenery.
	_idle = create_tween().set_loops()
	_idle.tween_property(_model, "position:y", MODEL_LIFT + MODEL_BOB, 1.4) \
		.set_trans(Tween.TRANS_SINE)
	_idle.tween_property(_model, "position:y", MODEL_LIFT, 1.4) \
		.set_trans(Tween.TRANS_SINE)


# ── hover / selection ─────────────────────────────────────────────────


func _set_hovered(on: bool) -> void:
	if _dying:
		return
	_hovered = on
	_settle()


## Moves to the transform implied by current hover/selection state.
func _settle() -> void:
	if Settings.reduced_motion:
		transform = _rest_transform()
		return
	_restart_motion().tween_property(self, "transform", _rest_transform(), 0.18) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


func _rest_transform() -> Transform3D:
	var raise := 0.0
	if selected:
		raise = SELECT_RAISE
	elif _hovered:
		raise = HOVER_RAISE
	var rest := home_transform.translated(Vector3(0, raise, 0))
	if _hovered and not selected:
		rest.basis = rest.basis.rotated(Vector3.RIGHT, -0.06)  # tilt to camera
	return rest


func _restart_motion() -> Tween:
	if _motion != null and _motion.is_valid():
		_motion.kill()
	_motion = create_tween()
	return _motion
