extends Control
## Shop & packs: coin balance, the free daily pack (24 h cooldown) and the
## premium pack, with a simple five-card reveal (fancy opening animations
## are post-demo polish by design).

const CARD_FACE_SCENE := preload("res://scenes/cards/card_face.tscn")
const REVEAL_SCALE := 0.55

## pack id -> its status Button, for the once-a-second state refresh.
var _pack_buttons: Dictionary = {}
var _tick_accumulator := 0.0

# Pack-opening sequence state (see the reveal section below).
var _reveal_cards: Array[CardData] = []
var _owned_before: Dictionary = {}
var _reveal_index := 0
var _reveal_phase := "idle"  # idle | pack | card | summary
var _drag_start_x := 0.0
var _dragging := false


func _ready() -> void:
	%BackButton.pressed.connect(SceneRouter.back)
	%DoneButton.pressed.connect(func() -> void: %RevealPanel.visible = false)
	PlayerData.coins_changed.connect(func(_amount: int) -> void: _refresh_buttons())
	_build_pack_panels()
	_refresh_coins()
	_refresh_buttons()


func _process(delta: float) -> void:
	_tick_accumulator += delta
	if _tick_accumulator >= 1.0:  # countdown only needs second resolution
		_tick_accumulator = 0.0
		_refresh_buttons()


func _build_pack_panels() -> void:
	for pack: Dictionary in PackRules.PACKS:
		var panel := PanelContainer.new()
		var column := VBoxContainer.new()
		column.add_theme_constant_override("separation", 10)
		column.custom_minimum_size = Vector2(300, 0)
		panel.add_child(column)

		var title := Label.new()
		title.text = pack["name"]
		title.add_theme_font_size_override("font_size", 22)
		title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		column.add_child(title)

		var description := Label.new()
		description.text = pack["description"]
		description.add_theme_font_size_override("font_size", 12)
		description.add_theme_color_override("font_color", CardStyle.TEXT_DIM)
		description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		description.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		column.add_child(description)

		var button := Button.new()
		button.pressed.connect(_open_pack.bind(pack))
		column.add_child(button)
		_pack_buttons[pack["id"]] = button
		%PackRow.add_child(panel)


func _refresh_coins() -> void:
	%CoinsLabel.text = "%d coins" % PlayerData.coins


func _refresh_buttons() -> void:
	_refresh_coins()
	var now := int(Time.get_unix_time_from_system())
	for pack: Dictionary in PackRules.PACKS:
		var button: Button = _pack_buttons[pack["id"]]
		if int(pack["price"]) == 0:
			if PlayerData.is_daily_pack_ready(now):
				button.text = "Open free pack"
				button.disabled = false
			else:
				var wait := PlayerData.last_daily_claim \
					+ PlayerData.DAILY_PACK_COOLDOWN_SECONDS - now
				button.text = "Next in %s" % _format_countdown(wait)
				button.disabled = true
		else:
			button.text = "Open — %d coins" % int(pack["price"])
			button.disabled = PlayerData.coins < int(pack["price"])


func _format_countdown(seconds: int) -> String:
	seconds = maxi(0, seconds)
	@warning_ignore("integer_division")
	return "%dh %02dm %02ds" % [seconds / 3600, (seconds % 3600) / 60, seconds % 60]


func _open_pack(pack: Dictionary) -> void:
	var now := int(Time.get_unix_time_from_system())
	if int(pack["price"]) == 0:
		if not PlayerData.is_daily_pack_ready(now):
			return
		PlayerData.claim_daily_pack(now)
	elif not PlayerData.spend_coins(int(pack["price"])):
		return

	var rng := RandomNumberGenerator.new()
	rng.randomize()
	var owned_before := PlayerData.owned_cards.duplicate()
	var cards := PackRules.open_pack(pack, owned_before, rng)
	for card: CardData in cards:
		PlayerData.add_card(card.id)
	_begin_reveal(pack, cards, owned_before)
	_refresh_buttons()


# ── pack opening sequence ─────────────────────────────────────────────
# Pack appears center screen; drag it sideways (mouse or touch — Godot
# emulates mouse from touch by default) or tap to tear it open, then cards
# reveal one at a time with slide transitions, ending on a summary row.
# The phases are plain state + tweens, so premium animations can replace
# each stage later without touching the flow.

func _begin_reveal(pack: Dictionary, cards: Array[CardData], owned_before: Dictionary) -> void:
	_reveal_cards = cards
	_owned_before = owned_before
	_reveal_index = 0
	_reveal_phase = "pack"
	%RevealTitle.text = pack["name"]
	%DoneButton.visible = false
	_clear_reveal_row()
	%RevealRow.add_child(_make_pack_visual())
	%RevealPanel.visible = true


func _clear_reveal_row() -> void:
	for child in %RevealRow.get_children():
		child.queue_free()


func _make_pack_visual() -> Control:
	var pack := PanelContainer.new()
	pack.custom_minimum_size = Vector2(170, 240)
	pack.add_theme_stylebox_override("panel", CardStyle.make_panel(
		CardStyle.SURFACE_LIGHT, 14, CardStyle.GOLD, 2))
	var label := Label.new()
	label.text = "PRIMORDIA\n\nswipe or tap\nto open"
	label.add_theme_font_size_override("font_size", 14)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	pack.add_child(label)
	pack.gui_input.connect(_on_pack_input.bind(pack))
	return pack


func _on_pack_input(event: InputEvent, pack: Control) -> void:
	if event is InputEventMouseButton:
		if event.pressed:
			_dragging = true
			_drag_start_x = pack.get_global_mouse_position().x
		else:
			if not _dragging:
				return
			_dragging = false
			var travelled: float = pack.get_global_mouse_position().x - _drag_start_x
			if absf(travelled) > 70.0 or absf(travelled) < 8.0:
				_tear_open(pack)  # decisive swipe, or a plain tap
			else:
				var back := create_tween()
				back.tween_property(pack, "position:x", 0.0, 0.2)
	elif event is InputEventMouseMotion and _dragging:
		pack.position.x += event.relative.x


func _tear_open(pack: Control) -> void:
	_dragging = false
	var tween := create_tween()
	tween.tween_property(pack, "scale", Vector2(1.15, 0.02), 0.18) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tween.tween_callback(_show_next_card)


func _show_next_card() -> void:
	_clear_reveal_row()
	if _reveal_index >= _reveal_cards.size():
		_show_summary()
		return
	_reveal_phase = "card"
	var card := _reveal_cards[_reveal_index]
	_reveal_index += 1
	var holder := _make_reveal_card(card, 0.8)
	%RevealRow.add_child(holder)
	holder.modulate.a = 0.0
	holder.position.x += 60.0
	var tween := create_tween()
	tween.tween_property(holder, "modulate:a", 1.0, 0.2)
	tween.parallel().tween_property(holder, "position:x", holder.position.x - 60.0, 0.25) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


func _show_summary() -> void:
	_reveal_phase = "summary"
	_clear_reveal_row()
	for card: CardData in _reveal_cards:
		%RevealRow.add_child(_make_reveal_card(card, REVEAL_SCALE))
	%RevealTitle.text += "  —  all cards"
	%DoneButton.visible = true


func _make_reveal_card(card: CardData, card_scale: float) -> Control:
	var holder := Control.new()
	holder.custom_minimum_size = CardStyle.BASE_SIZE * card_scale
	var face: CardFace = CARD_FACE_SCENE.instantiate()
	face.scale = Vector2(card_scale, card_scale)
	holder.add_child(face)
	face.show_card(card)
	if not _owned_before.has(card.id):
		var badge := Label.new()
		badge.text = "NEW"
		badge.add_theme_font_size_override("font_size", 12)
		badge.add_theme_color_override("font_color", CardStyle.GOLD)
		badge.z_index = 1
		holder.add_child(badge)
		badge.position = Vector2(6, -18)
	return holder


func _unhandled_input(event: InputEvent) -> void:
	# During single-card reveals, any click/tap advances to the next card.
	if _reveal_phase != "card":
		return
	if event is InputEventMouseButton and event.pressed:
		get_viewport().set_input_as_handled()
		_show_next_card()
