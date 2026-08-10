extends Node3D
## Battle screen. The 3D table is the presentation stage; all interaction
## runs through the 2D HUD. The human plays via buttons that map 1:1 onto
## BattleEngine legal actions; the rival is driven by BattleAI with a short
## delay per action so its turn is readable.

const CARD_FACE_SCENE := preload("res://scenes/cards/card_face.tscn")
const HAND_SCALE := 0.36
const AI_ACTION_DELAY := 0.45
## Extra pause after an attack so impact feedback reads clearly.
const ATTACK_SETTLE_DELAY := 0.55
const AI_ACTION_CAP := 40
const WIN_COINS := 50
const LOSS_COINS := 10

var _engine: BattleEngine = null
var _ai := BattleAI.new()
var _log_lines: PackedStringArray = []
## Indices into PlayerData.decks that pass validation, aligned with dropdown.
var _valid_decks: Array[int] = []
var _reward_granted := false
## Last player index seen as current — drives the turn-change banner.
var _last_turn_owner := -1
## Card ids in the hand at the previous refresh, for deal-in animation.
var _previous_hand: Array = []
## Camera fov authored in the scene — the attack punch returns to exactly
## this value instead of a hardcoded one.
var _base_fov := 46.0
## DinoInPlay -> Card3D on the board (identity-keyed; survives promotion).
var _card_nodes: Dictionary = {}
var _env_nodes: Array = [null, null]  # per-player environment Card3D
@onready var _board: Node3D = $Board
@onready var _camera: Camera3D = $Camera3D


func _ready() -> void:
	# Area3D hover/click on board cards only fires when the viewport does
	# physics picking — off by default, which silently killed 3D input.
	get_viewport().physics_object_picking = true
	_base_fov = $Camera3D.fov
	_build_slot_markers()
	%BackButton.pressed.connect(SceneRouter.back)
	%SetupBackButton.pressed.connect(SceneRouter.back)
	%StartButton.pressed.connect(_on_start_pressed)
	%EndTurnButton.pressed.connect(func() -> void: _apply_player_action({"type": "end_turn"}))
	%RetreatButton.pressed.connect(_on_retreat_pressed)
	%EnergyButton.pressed.connect(_on_energy_pressed)
	%TargetCancel.pressed.connect(func() -> void: %TargetPopup.visible = false)
	%CoinButton.pressed.connect(_on_coin_dismissed)
	%ReturnButton.pressed.connect(SceneRouter.back)
	_populate_deck_choices()


# ── setup ─────────────────────────────────────────────────────────────


func _populate_deck_choices() -> void:
	%DeckDropdown.clear()
	_valid_decks.clear()
	for index in range(PlayerData.decks.size()):
		var deck: Dictionary = PlayerData.decks[index]
		if DeckRules.validate(deck["card_ids"]).is_empty():
			%DeckDropdown.add_item(deck["name"])
			_valid_decks.append(index)
	var none := _valid_decks.is_empty()
	%StartButton.disabled = none
	%NoDeckLabel.visible = none


func _on_start_pressed() -> void:
	var chosen: Dictionary = PlayerData.decks[_valid_decks[%DeckDropdown.selected]]
	var player_deck: Array = (chosen["card_ids"] as Array).duplicate()

	# The rival drafts a legal deck of a random type from full card access.
	var rival_owned: Dictionary = {}
	for card: CardData in GameData.all_cards():
		rival_owned[card.id] = 2
	var rival_deck := DeckRules.auto_build(rival_owned, randi_range(0, 3))

	_engine = BattleEngine.new(player_deck, rival_deck, randi())
	_log_lines = _engine.log_history.duplicate()  # setup events (coin flip…)
	_engine.log_line.connect(_on_log_line)
	_reward_granted = false
	%SetupPanel.visible = false
	%HUD.visible = true
	_last_turn_owner = _engine.current  # banner waits until after the toss
	_previous_hand = []
	_intro_camera()
	_animate_hud_entrance()
	_refresh()
	_show_coin_toss()


## The toss decides who acts first, so the player sees it before any card
## moves. Play only begins once it is dismissed.
func _show_coin_toss() -> void:
	var player_called_heads := _engine.heads_player == 0
	%CoinResult.text = "HEADS" if player_called_heads else "TAILS"
	%CoinResult.add_theme_color_override(
		"font_color", CardStyle.GOLD if _engine.first_player == 0 else Color("ff8a7a"))
	%CoinDetail.text = (
		"You called %s and go first." if _engine.first_player == 0
		else "Rival called %s and goes first.") % ("Heads" if player_called_heads else "Tails")
	%CoinPanel.visible = true


func _on_coin_dismissed() -> void:
	%CoinPanel.visible = false
	_last_turn_owner = -1  # let the turn banner announce the opening turn
	_refresh()
	if _engine.current == 1:
		_run_ai_turn()


func _on_log_line(text: String) -> void:
	_log_lines.append(text)
	if _log_lines.size() > 40:
		_log_lines.remove_at(0)


# ── acting ────────────────────────────────────────────────────────────


func _apply_player_action(action: Dictionary) -> void:
	if _engine == null or _engine.is_over() or _engine.current != 0:
		return
	%TargetPopup.visible = false
	_animate_action(action, 0)
	_engine.apply(action)
	_refresh()
	if not _engine.is_over() and _engine.current == 1:
		_run_ai_turn()


func _run_ai_turn() -> void:
	var steps := 0
	while _engine.current == 1 and not _engine.is_over() and steps < AI_ACTION_CAP:
		# Node-bound tween: if the player leaves the battle, the tween dies
		# with the scene and this coroutine simply never resumes.
		var delay := create_tween()
		delay.tween_interval(AI_ACTION_DELAY)
		await delay.finished
		var action := _ai.choose_action(_engine)
		_animate_action(action, 1)
		_engine.apply(action)
		_refresh()
		# Let attack impact + damage numbers land before the next action.
		if action["type"] == "attack" and not Settings.reduced_motion:
			var settle := create_tween()
			settle.tween_interval(ATTACK_SETTLE_DELAY)
			await settle.finished
		steps += 1


func _on_hand_card_pressed(hand_index: int) -> void:
	var options: Array[Dictionary] = []
	for action: Dictionary in _engine.get_legal_actions():
		if int(action.get("hand", -99)) == hand_index:
			options.append(action)
	if options.is_empty():
		_on_log_line("That card can't be played right now.")
		_refresh()
		return
	if options.size() == 1 and not options[0].has("target"):
		_apply_player_action(options[0])
		return
	_open_target_popup("Choose a target", options)


func _on_energy_pressed() -> void:
	var options: Array[Dictionary] = []
	for action: Dictionary in _engine.get_legal_actions():
		if action["type"] == "attach":
			options.append(action)
	if options.size() == 1:
		_apply_player_action(options[0])
	elif options.size() > 1:
		_open_target_popup("Attach energy to…", options)


func _on_retreat_pressed() -> void:
	var options: Array[Dictionary] = []
	for action: Dictionary in _engine.get_legal_actions():
		if action["type"] == "retreat":
			options.append(action)
	if options.size() == 1:
		_apply_player_action(options[0])
	elif options.size() > 1:
		_open_target_popup("Retreat into…", options)


func _open_target_popup(title: String, options: Array[Dictionary]) -> void:
	%TargetTitle.text = title
	for child in %TargetButtons.get_children():
		child.queue_free()
	for action: Dictionary in options:
		var button := Button.new()
		button.text = _describe_option(action)
		button.pressed.connect(_apply_player_action.bind(action))
		%TargetButtons.add_child(button)
	%TargetPopup.visible = true


func _describe_option(action: Dictionary) -> String:
	var player := _engine.players[0]
	match action["type"]:
		"retreat":
			return "Swap with %s" % player.bench[action["bench"]].card().display_name
		"place_basic":
			return "Place on bench"
		"environment":
			return "Set as your Environment"
		_:
			var target := int(action.get("target", -1))
			if action["type"] == "trainer":  # switch targets name the bench dino
				return "Switch with %s" % player.bench[target].card().display_name
			if target == -1:
				return "Active — %s" % player.active.card().display_name
			return "Bench — %s" % player.bench[target].card().display_name


# ── rendering ─────────────────────────────────────────────────────────


func _refresh() -> void:
	if _engine == null:
		return
	var you := _engine.players[0]
	var rival := _engine.players[1]
	var your_turn := _engine.current == 0 and not _engine.is_over()

	%TurnLabel.text = "%s  ·  Turn %d" % [
		"Your turn" if your_turn else "Rival's turn", _engine.turn_number]
	%PointsLabel.text = "You %d — %d Rival  (first to %d)" % [
		you.points, rival.points, BattleEngine.POINTS_TO_WIN]
	%RivalStatsLabel.text = "Rival · hand %d · deck %d" % [rival.hand.size(), rival.deck.size()]
	%FieldLabel.text = "Env — You: %s  ·  Rival: %s" % [
		_env_name(you), _env_name(rival)]

	_sync_board()
	_fill_hand(your_turn)
	_fill_attacks(your_turn)
	%EndTurnButton.disabled = not your_turn
	var can_attach := your_turn and _engine.players[0].energy_budget > 0
	%EnergyButton.text = "Attach %s energy" % CardStyle.type_display_name(
		_engine.players[0].element)
	%EnergyButton.disabled = not can_attach
	%RetreatButton.disabled = not (your_turn and _engine.get_legal_actions().any(
		func(action: Dictionary) -> bool: return action["type"] == "retreat"))

	var tail := mini(4, _log_lines.size())
	%LogLabel.text = "\n".join(_log_lines.slice(_log_lines.size() - tail))

	if _engine.current != _last_turn_owner and not _engine.is_over():
		_last_turn_owner = _engine.current
		_show_turn_banner(your_turn)

	if _engine.is_over():
		_show_result()


func _fill_hand(your_turn: bool) -> void:
	for child in %Hand.get_children():
		child.queue_free()
	var you := _engine.players[0]

	# Cards that arrived since the last refresh get a deal-in animation.
	var new_cards: Dictionary = {}
	for id: String in you.hand:
		new_cards[id] = int(new_cards.get(id, 0)) + 1
	for id: String in _previous_hand:
		if new_cards.has(id):
			new_cards[id] = int(new_cards[id]) - 1
	var dealt := 0

	# Which hand slots have a legal play right now — used to highlight them.
	var playable: Dictionary = {}
	if your_turn:
		for action: Dictionary in _engine.get_legal_actions():
			if action.has("hand"):
				playable[int(action["hand"])] = true

	for i in range(you.hand.size()):
		var card := GameData.get_card(you.hand[i])
		var button := Button.new()
		button.custom_minimum_size = CardStyle.BASE_SIZE * HAND_SCALE
		button.flat = true
		button.disabled = not your_turn
		button.tooltip_text = "%s\n%s" % [card.display_name, _card_hint(card)]
		button.pressed.connect(_on_hand_card_pressed.bind(i))
		button.mouse_entered.connect(_on_hand_hover.bind(button, true))
		button.mouse_exited.connect(_on_hand_hover.bind(button, false))
		button.pivot_offset = CardStyle.BASE_SIZE * HAND_SCALE * 0.5
		# Unplayable cards read as dimmed; playable ones stay bright.
		button.modulate = (
			Color.WHITE if playable.has(i) else Color(0.62, 0.66, 0.76, 0.85))

		var face: CardFace = CARD_FACE_SCENE.instantiate()
		face.scale = Vector2(HAND_SCALE, HAND_SCALE)
		button.add_child(face)
		face.show_card(card)
		%Hand.add_child(button)
		if new_cards.has(you.hand[i]) and int(new_cards[you.hand[i]]) > 0:
			new_cards[you.hand[i]] = int(new_cards[you.hand[i]]) - 1
			_deal_in(button, dealt)
			dealt += 1

	_previous_hand = you.hand.duplicate()


## Short "what is this" line for hand tooltips.
func _card_hint(card: CardData) -> String:
	if card is DinoCardData:
		var dino := card as DinoCardData
		return "Dinosaur · %s · %d HP" % [
			CardStyle.type_display_name(dino.dino_type), dino.hp]
	if card is FieldCardData:
		return "Environment · %s" % (card as FieldCardData).text
	if card is TrainerCardData:
		var trainer := card as TrainerCardData
		return "%s · %s" % [trainer.trainer_kind.capitalize(), trainer.text]
	return ""


## Lift and scale a hand card while the cursor is over it.
func _on_hand_hover(button: Button, entered: bool) -> void:
	if button.disabled or Settings.reduced_motion:
		return
	var tween := create_tween()
	tween.tween_property(button, "scale", Vector2.ONE * (1.12 if entered else 1.0), 0.12) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


func _fill_attacks(your_turn: bool) -> void:
	for child in %AttackList.get_children():
		child.queue_free()
	if not your_turn:
		return
	var has_attack := false
	for action: Dictionary in _engine.get_legal_actions():
		if action["type"] == "attack":
			has_attack = true
			break
	if not has_attack:
		var hint := Label.new()
		hint.text = (
			"No attack on turn 1." if _engine.turn_number < 2
			else "Not enough energy attached.")
		hint.add_theme_font_size_override("font_size", 12)
		hint.add_theme_color_override("font_color", CardStyle.TEXT_DIM)
		hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		%AttackList.add_child(hint)
		return
	for action: Dictionary in _engine.get_legal_actions():
		if action["type"] != "attack":
			continue
		var attack := _engine.players[0].active.card().attacks[action["index"]]
		var button := Button.new()
		button.text = "%s\n%d damage  ·  %d energy" % [
			attack.attack_name, _engine.preview_damage(action["index"]), attack.cost.size()]
		button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		button.custom_minimum_size = Vector2(0, 46)
		button.pressed.connect(_apply_player_action.bind(action))
		%AttackList.add_child(button)


func _show_result() -> void:
	var won := _engine.winner == 0
	%ResultLabel.text = "Victory!" if won else "Defeat"
	if not _reward_granted:
		_reward_granted = true
		PlayerData.earn_coins(WIN_COINS if won else LOSS_COINS)
	%RewardLabel.text = "+%d coins" % (WIN_COINS if won else LOSS_COINS)
	if %ResultPanel.visible:
		return  # already shown; don't replay the entrance
	%ResultPanel.visible = true
	if Settings.reduced_motion:
		return
	%ResultPanel.modulate.a = 0.0
	%ResultPanel.scale = Vector2(0.85, 0.85)
	%ResultPanel.pivot_offset = %ResultPanel.size * 0.5
	var tween := create_tween()
	tween.tween_property(%ResultPanel, "modulate:a", 1.0, 0.25)
	tween.parallel().tween_property(%ResultPanel, "scale", Vector2.ONE, 0.4) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


# ── 3D board presentation ─────────────────────────────────────────────


## Mirrors engine state onto the 3D table: spawns Card3D nodes for new
## dinos (sliding in from the deck side), tweens cards whose slot changed
## (retreat/switch/promotion), updates HP/status labels, vanishes KOs and
## keeps the shared field card displayed beside the center line.
func _sync_board() -> void:
	var alive: Dictionary = {}
	for side in range(2):
		var player := _engine.players[side]
		var dinos := player.dinos_in_play()
		for i in range(dinos.size()):
			var dino := dinos[i]
			alive[dino] = true
			var card3d: Card3D = _card_nodes.get(dino)
			if card3d == null:
				card3d = Card3D.new()
				card3d.card_data = dino.card()
				_board.add_child(card3d)
				var enter := _slot_transform(side, i)
				enter.origin.z += 3.0 * (1.0 if side == 0 else -1.0)
				card3d.transform = enter
				card3d.clicked.connect(_on_board_card_clicked)
				_card_nodes[dino] = card3d
			elif card3d.card_data != dino.card():
				card3d.show_card(dino.card())  # evolved into a new face
			card3d.move_home(_slot_transform(side, i))
			_update_card_info(card3d, dino)

	for dino: DinoInPlay in _card_nodes.keys():
		if not alive.has(dino):
			(_card_nodes[dino] as Card3D).vanish()
			_card_nodes.erase(dino)

	_sync_environments()


func _update_card_info(card3d: Card3D, dino: DinoInPlay) -> void:
	var max_hp := _engine.max_hp_of(dino)
	var remaining := maxi(0, max_hp - dino.damage)
	var bits := PackedStringArray(["%d/%d" % [remaining, max_hp]])
	if dino.energy > 0:
		bits.append("E%d" % dino.energy)
	for status: String in dino.statuses:
		bits.append(status.substr(0, 3).to_upper())
	card3d.set_info(" ".join(bits),
		Color("6fd98a") if remaining * 2 >= max_hp else Color("ff8a7a"))


func _env_name(player: BattlePlayerState) -> String:
	if player.environment_id == "":
		return "none"
	return GameData.get_card(player.environment_id).display_name


## Each side keeps its own Environment card beside its rows.
func _sync_environments() -> void:
	for side in range(2):
		var env_id: String = _engine.players[side].environment_id
		var node: Card3D = _env_nodes[side]
		if env_id == "":
			continue
		var card := GameData.get_card(env_id)
		var forward := 1.0 if side == 0 else -1.0
		if node == null:
			node = Card3D.new()
			node.card_data = card
			_board.add_child(node)
			node.transform = Transform3D(Basis.IDENTITY, Vector3(-4.6, 0.18, 0.9 * forward))
			node.clicked.connect(_on_board_card_clicked)
			node.move_home(Transform3D(Basis.IDENTITY, Vector3(-3.6, 0.18, 0.9 * forward)))
			_env_nodes[side] = node
		elif node.card_data != card:
			node.show_card(card)
			node.pulse()


## Slot layout: active front-center, bench of 3 behind; rival mirrored and
## rotated to face its owner. play_index 0 = active, 1.. = bench.
func _slot_transform(side: int, play_index: int) -> Transform3D:
	var forward := 1.0 if side == 0 else -1.0
	var pos: Vector3
	if play_index == 0:
		pos = Vector3(0, 0.18, 0.9 * forward)
	else:
		pos = Vector3(-1.25 + (play_index - 1) * 1.25, 0.18, 1.9 * forward)
	# Both sides face the camera: an opponent's card the player cannot read
	# is worse than the tabletop realism of rotating it.
	return Transform3D(Basis.IDENTITY, pos)


## Fire-and-forget presentation for an action about to be applied.
func _animate_action(action: Dictionary, side: int) -> void:
	var player := _engine.players[side]
	match action["type"]:
		"attack":
			var attacker: Card3D = _card_nodes.get(player.active)
			var defender := _engine.players[_engine.opponent_of(side)].active
			var target: Card3D = _card_nodes.get(defender)
			if attacker != null and target != null:
				var damage := _engine.preview_damage_for(side, int(action["index"]))
				attacker.lunge(target.home_transform.origin)
				_camera_punch()
				# Impact lands a beat after the lunge starts.
				var impact := create_tween()
				impact.tween_interval(0.14)
				impact.tween_callback(func() -> void:
					if not (is_instance_valid(target) and is_instance_valid(attacker)):
						return
					target.recoil(attacker.home_transform.origin)
					target.flash(Color("ff5a48"))
					target.show_damage(damage))
		"attach", "evolve":
			var index := int(action.get("target", -1))
			var dino := player.active if index == -1 else player.bench[index]
			if _card_nodes.has(dino):
				var card3d := _card_nodes[dino] as Card3D
				card3d.pulse()
				card3d.flash(Color("ffd166") if action["type"] == "attach" else Color("6fd98a"))
		"trainer":
			# Healing and draw effects read on the active dinosaur.
			if _card_nodes.has(player.active):
				(_card_nodes[player.active] as Card3D).flash(Color("6fd98a"))


## Smooth descent from an overview to the play angle when a battle starts.
func _intro_camera() -> void:
	if Settings.reduced_motion:
		return
	var play := _camera.transform
	var overview := play
	overview.origin += Vector3(0, 3.5, 4.0)
	_camera.transform = overview
	var tween := create_tween()
	tween.tween_property(_camera, "transform", play, 1.1) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


## Brief zoom pulse that sells an attack landing.
func _camera_punch() -> void:
	if Settings.reduced_motion:
		return
	var tween := create_tween()
	tween.tween_property(_camera, "fov", _base_fov - 3.0, 0.12)
	tween.tween_property(_camera, "fov", _base_fov, 0.3)


func _on_board_card_clicked(card3d: Card3D) -> void:
	if card3d.card_data != null:
		%BattleViewer.open(card3d.card_data)


## Faint outlines on every Active/Back slot so empty zones are legible.
func _build_slot_markers() -> void:
	var mesh := QuadMesh.new()
	mesh.size = Vector2(Card3D.WIDTH * 1.06, Card3D.HEIGHT * 1.06)
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(1, 1, 1, 0.06)
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	for side in range(2):
		for slot in range(1 + BattleEngine.BENCH_SIZE):
			var marker := MeshInstance3D.new()
			marker.mesh = mesh
			marker.material_override = material
			var slot_transform := _slot_transform(side, slot)
			slot_transform.origin.y = 0.155  # just above the table surface
			marker.transform = slot_transform
			marker.rotate_object_local(Vector3.RIGHT, -PI / 2)
			$Board.add_child(marker)


# ── UI animation ──────────────────────────────────────────────────────


## Slides the HUD panels in from their own edges when a battle begins.
func _animate_hud_entrance() -> void:
	if Settings.reduced_motion:
		return
	var panels := {
		%TopBar: Vector2(0, -80),
		%ActionPanel: Vector2(300, 0),
		%LogPanel: Vector2(-300, 0),
		%HandDock: Vector2(0, 180),
	}
	for panel: Control in panels:
		var offset: Vector2 = panels[panel]
		panel.position += offset
		panel.modulate.a = 0.0
		var tween := create_tween().set_parallel()
		tween.tween_property(panel, "position", panel.position - offset, 0.45) \
			.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		tween.tween_property(panel, "modulate:a", 1.0, 0.35)


## Big centred announcement whenever the turn changes hands.
func _show_turn_banner(your_turn: bool) -> void:
	var banner: Label = %TurnBanner
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


## Newly drawn cards pop into the hand dock, staggered by draw order.
## Scale and alpha only — an HBoxContainer owns its children's positions, so
## animating `position` here would be overwritten on the next layout pass.
func _deal_in(button: Control, order: int) -> void:
	if Settings.reduced_motion:
		return
	var target_alpha := button.modulate.a  # dimmed-if-unplayable tint is set already
	button.modulate.a = 0.0
	button.scale = Vector2(0.72, 0.72)
	var delay := order * 0.07
	var tween := create_tween().set_parallel()
	tween.tween_property(button, "scale", Vector2.ONE, 0.32) \
		.set_delay(delay).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(button, "modulate:a", target_alpha, 0.26).set_delay(delay)
