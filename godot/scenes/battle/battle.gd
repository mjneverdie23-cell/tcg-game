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
## Ghosts drawn for a single multi-card rival draw; more than this reads as
## noise rather than information.
const MAX_DRAW_GHOSTS := 3
## Where the deck and used piles stand. Solved against the projected pile
## bounds rather than eyeballed: it is the furthest right they can sit while
## still clearing the action panel at 4:3, where the narrower horizontal FOV
## throws the table's edges outward. Also clears the widest bench slot.
const PILE_X := 2.40
## Thumbnail scale in the used-cards viewer.
const USED_CARD_SCALE := 0.34
## LogPanel offset_top when the log is open and when it is rolled up. The
## panel is anchored to the bottom, so only its top edge moves.
const LOG_OPEN_TOP := -282.0
const LOG_SHUT_TOP := -215.0
## Card face scale inside the action zoom.
const ZOOM_CARD_SCALE := 1.05
## Energy balls in the zoomed card's bottom-left corner: where they sit in
## the card's own 250x350 design space, and how big each one is.
const ZOOM_ENERGY_CORNER := Vector2(14, 300)
const ZOOM_ENERGY_SIZE := 11
## Slack around a row so its hit target is comfortable to click.
const ZOOM_HIT_PADDING := 3.0
## Returned by _attach_target_of for a dinosaur that is not the player's.
const INVALID_TARGET := -99
## Reach of the pointer ray used to find the card under the energy well.
const RAY_LENGTH := 100.0

var _engine: BattleEngine = null
var _ai := BattleAI.new()
var _log_lines: PackedStringArray = []
## Indices into PlayerData.decks that pass validation, aligned with dropdown.
var _valid_decks: Array[int] = []
var _reward_granted := false
## Ladder swing from this battle, shown on the result panel (0 in practice).
var _trophy_delta := 0
## Last player index seen as current — drives the turn-change banner.
var _last_turn_owner := -1
## Card ids in the hand at the previous refresh, for deal-in animation.
var _previous_hand: Array = []
## DinoInPlay -> Card3D on the board (identity-keyed; survives promotion).
var _card_nodes: Dictionary = {}
## DinoInPlay -> owning side, so a knocked-out card knows which used pile
## to fly to after it has already been removed from the engine's zones.
var _card_sides: Dictionary = {}
var _env_nodes: Array = [null, null]  # per-player environment Card3D
## Deck sizes at the previous refresh, per side — a shrink means a draw.
var _previous_deck_sizes := PackedInt32Array([0, 0])
## "deck0" / "used0" / "deck1" / "used1" -> CardPile3D on the table.
var _pile_nodes: Dictionary = {}
## Dinosaur open in the action zoom, or null.
var _zoomed: DinoInPlay = null
## Dome that follows the pointer while energy is being dragged.
var _energy_ghost: EnergyOrb = null
@onready var _board: Node3D = $Board
@onready var _camera: Camera3D = $Camera3D
## Camera moves, HUD entrance, banners and the 2D card flights.
@onready var _fx := BattleFx.new()


func _ready() -> void:
	# Area3D hover/click on board cards only fires when the viewport does
	# physics picking — off by default, which silently killed 3D input.
	get_viewport().physics_object_picking = true
	add_child(_fx)
	_fx.setup(%HUD, _camera, %TurnBanner)
	_build_slot_markers()
	_build_piles()
	%BackButton.pressed.connect(SceneRouter.back)
	%SetupBackButton.pressed.connect(SceneRouter.back)
	%StartButton.pressed.connect(_on_start_pressed)
	%EndTurnButton.pressed.connect(func() -> void: _apply_player_action({"type": "end_turn"}))
	%Hand.card_pressed.connect(_on_hand_card_pressed)
	%RivalHand.face_down = true
	%RivalHand.inverted = true
	%EnergyOrb.drag_started.connect(_on_energy_drag_started)
	%EnergyOrb.dragged.connect(_on_energy_dragged)
	%EnergyOrb.dropped.connect(_on_energy_dropped)
	# No close button: the card is the panel, so clicking off it dismisses.
	%ZoomBackdrop.gui_input.connect(_on_zoom_backdrop_input)
	%TargetCancel.pressed.connect(func() -> void: %TargetPopup.visible = false)
	%CoinButton.pressed.connect(_on_coin_dismissed)
	%ReturnButton.pressed.connect(SceneRouter.back)
	%LogToggle.toggled.connect(_on_log_toggled)
	%UsedClose.pressed.connect(func() -> void: %UsedPanel.visible = false)
	_on_log_toggled(true)
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
	_trophy_delta = 0
	%SetupPanel.visible = false
	%HUD.visible = true
	_last_turn_owner = _engine.current  # banner waits until after the toss
	# The opening hand is already dealt, but the deal-in plays only once the
	# coin panel is out of the way — otherwise it happens behind it.
	_previous_hand = _engine.players[0].hand.duplicate()
	_previous_deck_sizes[0] = _engine.players[0].deck.size()
	_previous_deck_sizes[1] = _engine.players[1].deck.size()
	_fx.intro_camera()
	_fx.hud_entrance({
		%TopBar: Vector2(0, -80),
		%LogPanel: Vector2(-300, 0),
		%Hand: Vector2(0, 180),
		%EnergyDock: Vector2(0, 180),
	})
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
	_previous_hand = []  # deal the opening hand out of the deck pile now
	_refresh()
	if _engine.current == 1:
		_run_ai_turn()


func _on_log_line(text: String) -> void:
	_log_lines.append(text)
	if _log_lines.size() > 40:
		_log_lines.remove_at(0)


## Rolls the battle log up into its own header. The panel is anchored to the
## bottom of the screen, so collapsing it means moving its top edge down —
## the header button stays put and stays clickable either way.
func _on_log_toggled(open: bool) -> void:
	%LogLabel.visible = open
	%LogToggle.text = "Battle log  ▾" if open else "Battle log  ▸"
	var top := LOG_OPEN_TOP if open else LOG_SHUT_TOP
	if Settings.reduced_motion:
		%LogPanel.offset_top = top
		return
	var tween := %LogPanel.create_tween()
	tween.tween_property(%LogPanel, "offset_top", top, 0.18) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


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
			return "Send out as your Active" if player.active == null else "Place on bench"
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

	var turn_text := "%s  ·  Turn %d" % [
		"Your turn" if your_turn else "Rival's turn", _engine.turn_number]
	if your_turn and you.active == null:
		# The empty Active slot must be filled this turn or the battle is lost.
		turn_text += "  ·  send out a dinosaur!"
	%TurnLabel.text = turn_text
	%PointsLabel.text = "You %d — %d Rival  (first to %d)" % [
		you.points, rival.points, BattleEngine.POINTS_TO_WIN]
	%RivalStatsLabel.text = "Rival · hand %d · deck %d" % [rival.hand.size(), rival.deck.size()]
	%FieldLabel.text = "Env — You: %s  ·  Rival: %s" % [
		_env_name(you), _env_name(rival)]

	_sync_board()
	_sync_piles()
	_fill_hand(your_turn)
	%EndTurnButton.disabled = not your_turn
	var can_attach := your_turn and _engine.get_legal_actions().any(
		func(action: Dictionary) -> bool: return action["type"] == "attach")
	%EnergyOrb.color = CardStyle.TYPE_COLORS[you.element]
	%EnergyOrb.spent = not can_attach
	%EnergyOrb.tooltip_text = (
		"Drag onto one of your dinosaurs" if can_attach
		else "%s energy already attached this turn" % CardStyle.type_display_name(you.element))
	if %CardZoom.visible:
		_refresh_card_zoom()

	var tail := mini(4, _log_lines.size())
	%LogLabel.text = "\n".join(_log_lines.slice(_log_lines.size() - tail))

	if _engine.current != _last_turn_owner and not _engine.is_over():
		_last_turn_owner = _engine.current
		_fx.turn_banner(your_turn)

	if _engine.is_over():
		_show_result()


## Both fans. Yours shows faces and takes clicks; the rival's shows backs,
## because knowing how many cards they are holding is fair information and
## knowing which ones would end the game.
func _fill_hand(your_turn: bool) -> void:
	var you := _engine.players[0]

	# Which hand slots have a legal play right now — those stay bright.
	var playable: Dictionary = {}
	if your_turn:
		for action: Dictionary in _engine.get_legal_actions():
			if action.has("hand"):
				playable[int(action["hand"])] = true

	var cards: Array = []
	for id: String in you.hand:
		cards.append(GameData.get_card(id))
	%Hand.set_hand(cards, playable, your_turn)

	var backs: Array = []
	backs.resize(_engine.players[1].hand.size())
	%RivalHand.set_hand(backs, {}, false)

	# Cards that arrived since the last refresh fly in from the deck.
	var new_cards: Dictionary = {}
	for id: String in you.hand:
		new_cards[id] = int(new_cards.get(id, 0)) + 1
	for id: String in _previous_hand:
		if new_cards.has(id):
			new_cards[id] = int(new_cards[id]) - 1
	var dealt := 0
	for i in range(you.hand.size()):
		if new_cards.has(you.hand[i]) and int(new_cards[you.hand[i]]) > 0:
			new_cards[you.hand[i]] = int(new_cards[you.hand[i]]) - 1
			_fx.deal_in(%Hand.slot_at(i), dealt, _fx.screen_of(_pile_nodes["deck0"]))
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


# ── energy: drag the well onto a dinosaur ─────────────────────────────
# Godot's Control drag-and-drop can only hand data between Controls, and the
# drop targets here are 3D cards, so the gesture is hand-rolled: the orb
# reports pointer moves and the release point, and a ray into the world says
# which dinosaur was under it.


func _on_energy_drag_started() -> void:
	if _energy_ghost != null:
		_energy_ghost.queue_free()
	_energy_ghost = EnergyOrb.new()
	_energy_ghost.color = CardStyle.TYPE_COLORS[_engine.players[0].element]
	_energy_ghost.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_energy_ghost.z_index = 20
	%HUD.add_child(_energy_ghost)
	_energy_ghost.size = Vector2(58, 58)
	_on_energy_dragged(get_viewport().get_mouse_position())


func _on_energy_dragged(at: Vector2) -> void:
	if _energy_ghost != null:
		_energy_ghost.global_position = at - _energy_ghost.size * 0.5
	# Light up whatever the energy is hovering, so the drop target reads.
	var target := _dino_under(at)
	for dino: DinoInPlay in _card_nodes:
		var node := _card_nodes[dino] as Card3D
		node.set_selected(node == target and _attach_target_of(dino) != INVALID_TARGET)


func _on_energy_dropped(at: Vector2) -> void:
	if _energy_ghost != null:
		_energy_ghost.queue_free()
		_energy_ghost = null
	for dino: DinoInPlay in _card_nodes:
		(_card_nodes[dino] as Card3D).set_selected(false)

	var target := _dino_under(at)
	if target == null:
		# Released on the well itself: treat the gesture as a plain click and
		# fall back to picking a target from a list.
		if %EnergyOrb.get_global_rect().has_point(at):
			_on_energy_pressed()
		return
	var dropped_on := _dino_for_node(target)
	if dropped_on == null:
		return
	var slot := _attach_target_of(dropped_on)
	if slot == INVALID_TARGET:
		return
	for action: Dictionary in _engine.get_legal_actions():
		if action["type"] == "attach" and int(action["target"]) == slot:
			_apply_player_action(action)
			return
	_on_log_line("That dinosaur cannot take energy right now.")
	_refresh()


## Attach-action target index for one of your dinosaurs: -1 for the Active,
## 0.. for the bench, INVALID_TARGET when it is not yours.
func _attach_target_of(dino: DinoInPlay) -> int:
	var you := _engine.players[0]
	if dino == you.active:
		return -1
	for b in range(you.bench.size()):
		if you.bench[b] == dino:
			return b
	return INVALID_TARGET


## The board card under a viewport position, via a ray against the pickable
## areas — the same ones that make cards clickable.
func _dino_under(at: Vector2) -> Card3D:
	var origin := _camera.project_ray_origin(at)
	var query := PhysicsRayQueryParameters3D.create(
		origin, origin + _camera.project_ray_normal(at) * RAY_LENGTH)
	query.collide_with_areas = true
	query.collide_with_bodies = false
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return null
	return (hit["collider"] as Node).get_parent() as Card3D


# ── card zoom: energy, attacks and retreat ────────────────────────────


func _open_card_zoom(dino: DinoInPlay) -> void:
	_zoomed = dino
	%CardZoom.visible = true
	_refresh_card_zoom()


## Everything lives on the card itself: the energy attached to it sits in the
## bottom-left corner, and each attack row and the retreat cell carry an
## invisible hit target. Nothing is repeated in rows underneath — the card
## already says what every attack costs and does.
func _refresh_card_zoom() -> void:
	if _zoomed == null or not _engine.players[0].dinos_in_play().has(_zoomed):
		%CardZoom.visible = false
		_zoomed = null
		return
	var card := _zoomed.card()
	var is_active := _zoomed == _engine.players[0].active
	var your_turn := _engine.current == 0 and not _engine.is_over()

	%ZoomTitle.text = "%s  ·  %d / %d HP" % [
		card.display_name, maxi(0, _engine.max_hp_of(_zoomed) - _zoomed.damage),
		_engine.max_hp_of(_zoomed)]

	for child in %ZoomFaceBox.get_children():
		child.queue_free()
	var holder := Control.new()
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.custom_minimum_size = CardStyle.BASE_SIZE * ZOOM_CARD_SCALE
	var face: CardFace = CARD_FACE_SCENE.instantiate()
	face.scale = Vector2(ZOOM_CARD_SCALE, ZOOM_CARD_SCALE)
	holder.add_child(face)
	face.show_card(card)
	%ZoomFaceBox.add_child(holder)

	# The card face and its rows are Containers: a child added to them gets
	# laid out, not positioned. So the overlays are parented to the plain
	# holder and placed over the rows' rects — which only exist after a
	# layout pass, hence the one-frame wait.
	var settle := holder.create_tween()
	settle.tween_interval(0.02)
	settle.tween_callback(_place_zoom_overlays.bind(holder, face, is_active, your_turn))


func _place_zoom_overlays(
		holder: Control, face: CardFace, is_active: bool, your_turn: bool) -> void:
	if not (is_instance_valid(holder) and is_instance_valid(face)) or _zoomed == null:
		return
	_add_zoom_energy(holder)

	var legal: Dictionary = {}
	if is_active and your_turn:
		for action: Dictionary in _engine.get_legal_actions():
			if action["type"] == "attack":
				legal[int(action["index"])] = action

	for index in range(_zoomed.card().attacks.size()):
		var row := face.attack_row(index)
		if row == null:
			continue
		var hit := _zoom_hit_target(holder, row, legal.has(index))
		if legal.has(index):
			hit.tooltip_text = "Attack for %d damage" % _engine.preview_damage(index)
			hit.pressed.connect(_on_zoom_attack.bind(legal[index]))
		else:
			hit.tooltip_text = _attack_block_reason(is_active, your_turn)

	var cell := face.retreat_cell()
	if cell == null:
		return
	var can_retreat := your_turn and is_active and _engine.get_legal_actions().any(
		func(action: Dictionary) -> bool: return action["type"] == "retreat")
	var retreat_hit := _zoom_hit_target(holder, cell, can_retreat)
	if can_retreat:
		retreat_hit.tooltip_text = "Retreat for %d energy" % _engine.retreat_cost(0)
		retreat_hit.pressed.connect(_on_retreat_pressed)
	else:
		retreat_hit.tooltip_text = (
			"Only your Active dinosaur can retreat" if not is_active
			else "Not enough energy to retreat")


## Energy attached to this dinosaur, as balls in the card's bottom-left
## corner — the same ball the player dragged off the well.
func _add_zoom_energy(holder: Control) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 3)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(row)
	row.position = ZOOM_ENERGY_CORNER * ZOOM_CARD_SCALE
	for i in range(_zoomed.energy):
		var ball := EnergyOrb.new()
		ball.color = CardStyle.TYPE_COLORS[_engine.players[0].element]
		ball.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ball.custom_minimum_size = Vector2.ONE * ZOOM_ENERGY_SIZE * ZOOM_CARD_SCALE
		row.add_child(ball)


## A transparent button covering `over`, added to `holder`. Never `flat`:
## a flat Button skips stylebox drawing altogether, which silently threw
## away the hover glow. Instead every state carries its own box — fully
## transparent when the action is unavailable, a faint gold outline when it
## is, and a thicker outline with a soft bloom under the cursor.
func _zoom_hit_target(holder: Control, over: Control, enabled: bool) -> Button:
	var hit := Button.new()
	hit.focus_mode = Control.FOCUS_NONE
	hit.disabled = not enabled
	hit.add_theme_stylebox_override("disabled", _hit_box(0.0, 0, false))
	if enabled:
		hit.add_theme_stylebox_override("normal", _hit_box(0.0, 2, false))
		hit.add_theme_stylebox_override("hover", _hit_box(0.16, 3, true))
		hit.add_theme_stylebox_override("pressed", _hit_box(0.26, 3, true))
	holder.add_child(hit)
	var rect := over.get_global_rect().grow(ZOOM_HIT_PADDING)
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


func _on_zoom_backdrop_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		%CardZoom.visible = false
		_zoomed = null


func _on_zoom_attack(action: Dictionary) -> void:
	%CardZoom.visible = false
	_zoomed = null
	_apply_player_action(action)


func _show_result() -> void:
	var won := _engine.winner == 0
	%ResultLabel.text = "Victory!" if won else "Defeat"
	if not _reward_granted:
		_reward_granted = true
		PlayerData.earn_coins(WIN_COINS if won else LOSS_COINS)
		# Ranked stakes trophies; practice counts toward quests but not the
		# ladder. The mode was chosen on the home screen.
		_trophy_delta = PlayerData.record_battle(won, SceneRouter.battle_ranked)
	%RewardLabel.text = "+%d coins%s" % [
		WIN_COINS if won else LOSS_COINS,
		"" if _trophy_delta == 0 else "  ·  %+d trophies" % _trophy_delta]
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


# ── deck & used-card piles ────────────────────────────────────────────
# Both piles sit on the table beside their owner's rows, the way they would
# in a real game: a slab that grows with the cards in it and a floating
# count. Only your own used pile is clickable — the rival's discard is
# public information in most card games, but showing it here would clutter
# the board without giving the player anything to act on.


## Builds the four piles once. `_pile_nodes` is keyed "deck0" / "used1" etc.
func _build_piles() -> void:
	for side in range(2):
		for kind: String in ["deck", "used"]:
			var pile := CardPile3D.new()
			$Board.add_child(pile)
			pile.transform = _pile_transform(side, kind == "deck")
			pile.setup(
				"DECK" if kind == "deck" else "USED",
				Color("16224a") if kind == "deck" else Color("3a1f2a"),
				side == 0 and kind == "used")
			if side == 0 and kind == "used":
				pile.clicked.connect(_on_used_pile_clicked)
			_pile_nodes["%s%d" % [kind, side]] = pile


## Piles flank the rows on the right: the deck level with the bench, the
## used pile level with the Active.
func _pile_transform(side: int, is_deck: bool) -> Transform3D:
	var forward := 1.0 if side == 0 else -1.0
	var depth := 2.15 if is_deck else 0.7
	return Transform3D(Basis.IDENTITY, Vector3(PILE_X, 0.155, depth * forward))


func _sync_piles() -> void:
	var you := _engine.players[0]
	var rival := _engine.players[1]
	(_pile_nodes["deck0"] as CardPile3D).set_count(you.deck.size())
	(_pile_nodes["used0"] as CardPile3D).set_count(you.discard.size())
	(_pile_nodes["deck1"] as CardPile3D).set_count(rival.deck.size())
	(_pile_nodes["used1"] as CardPile3D).set_count(rival.discard.size())

	# The player's own draws are animated card by card as they land in the
	# hand dock (_deal_in); the rival's hand is hidden, so its draws are only
	# visible as cards leaving its deck.
	var rival_drawn := _previous_deck_sizes[1] - rival.deck.size()
	for i in range(mini(rival_drawn, MAX_DRAW_GHOSTS)):
		_fx.fly(null, _fx.screen_of(_pile_nodes["deck1"]), _rival_hand_anchor(),
			BattleFx.DRAW_FLIGHT, i * 0.09)
	_previous_deck_sizes[0] = you.deck.size()
	_previous_deck_sizes[1] = rival.deck.size()


func _on_used_pile_clicked(_pile: CardPile3D) -> void:
	_show_used_cards()


## Every card the player has used this battle, most recent first.
func _show_used_cards() -> void:
	for child in %UsedGrid.get_children():
		child.queue_free()
	var discard: Array = _engine.players[0].discard
	%UsedTitle.text = "Used cards — %d" % discard.size()
	for i in range(discard.size() - 1, -1, -1):
		var holder := Control.new()
		holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
		holder.custom_minimum_size = CardStyle.BASE_SIZE * USED_CARD_SCALE
		var face: CardFace = CARD_FACE_SCENE.instantiate()
		face.scale = Vector2(USED_CARD_SCALE, USED_CARD_SCALE)
		holder.add_child(face)
		face.show_card(GameData.get_card(discard[i]))
		%UsedGrid.add_child(holder)
	%UsedPanel.visible = true


func _center_of(control: Control) -> Vector2:
	return control.global_position + control.size * 0.5


## Where the rival's (hidden) hand conceptually sits — top centre of screen.
func _rival_hand_anchor() -> Vector2:
	return Vector2(%HUD.size.x * 0.5, 30.0)


## Where a card being played leaves from: the actual hand card for the
## player, the rival's unseen hand for the AI.
func _hand_origin(side: int, hand_index: int) -> Vector2:
	if side != 0:
		return _rival_hand_anchor()
	var slot: Control = %Hand.slot_at(hand_index)
	if slot != null:
		return slot.get_global_rect().get_center()
	return %Hand.get_global_rect().get_center()


## A card leaving the hand or the table lands on its owner's used pile.
func _fly_to_used(card: CardData, from: Vector2, side: int) -> void:
	var pile := _pile_nodes["used%d" % side] as CardPile3D
	_fx.fly(card, from, _fx.screen_of(pile), BattleFx.DISCARD_FLIGHT, 0.0, _fx.pile_thump.bind(pile))


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
				_card_sides[dino] = side
			elif card3d.card_data != dino.card():
				card3d.show_card(dino.card())  # evolved into a new face
			card3d.move_home(_slot_transform(side, i))
			_update_card_info(card3d, dino)

	# Leaving _card_nodes means leaving play, which only happens on a
	# knockout: the body is cleared off the table and the card itself lands
	# on its owner's used pile.
	for dino: DinoInPlay in _card_nodes.keys():
		if not alive.has(dino):
			var node := _card_nodes[dino] as Card3D
			_fly_to_used(dino.card(), _fx.screen_of(node), int(_card_sides.get(dino, 0)))
			node.vanish()
			_card_nodes.erase(dino)
			_card_sides.erase(dino)

	_sync_environments()


func _update_card_info(card3d: Card3D, dino: DinoInPlay) -> void:
	var max_hp := _engine.max_hp_of(dino)
	var remaining := maxi(0, max_hp - dino.damage)
	# Energy is no longer in this line: it sits on the card as domes, where
	# the player just dropped it.
	var bits := PackedStringArray(["%d/%d" % [remaining, max_hp]])
	for status: String in dino.statuses:
		bits.append(status.substr(0, 3).to_upper())
	card3d.set_info(" ".join(bits),
		Color("6fd98a") if remaining * 2 >= max_hp else Color("ff8a7a"))
	card3d.set_energy(dino.energy,
		CardStyle.TYPE_COLORS[_engine.players[int(_card_sides.get(dino, 0))].element])


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
			node.transform = Transform3D(Basis.IDENTITY, Vector3(-4.6, 0.18, 0.7 * forward))
			node.clicked.connect(_on_board_card_clicked)
			node.move_home(Transform3D(Basis.IDENTITY, Vector3(-3.6, 0.18, 0.7 * forward)))
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
		pos = Vector3(0, 0.18, 0.7 * forward)
	else:
		pos = Vector3(-1.25 + (play_index - 1) * 1.25, 0.18, 2.15 * forward)
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
				_fx.camera_punch()
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
			if action["type"] == "evolve":
				# The pre-evolution card is used up as the new stage lands.
				_fly_to_used(dino.card(), _fx.screen_of(_card_nodes.get(dino) as Node3D), side)
		"trainer":
			# Healing and draw effects read on the active dinosaur.
			if _card_nodes.has(player.active):
				(_card_nodes[player.active] as Card3D).flash(Color("6fd98a"))
			# Spells and Supports are spent the moment they resolve.
			_fly_to_used(GameData.get_card(player.hand[int(action["hand"])]),
				_hand_origin(side, int(action["hand"])), side)
		"environment":
			# Setting an Environment discards the one it replaces.
			if player.environment_id != "":
				_fly_to_used(GameData.get_card(player.environment_id),
					_fx.screen_of(_env_nodes[side] as Node3D), side)


## Your own dinosaurs open the action zoom — energy, attacks and retreat.
## Anything else (the rival's board, Environments) opens the plain viewer.
func _on_board_card_clicked(card3d: Card3D) -> void:
	if card3d.card_data == null:
		return
	var dino := _dino_for_node(card3d)
	if dino != null and int(_card_sides.get(dino, 1)) == 0:
		_open_card_zoom(dino)
		return
	%BattleViewer.open(card3d.card_data)


func _dino_for_node(card3d: Card3D) -> DinoInPlay:
	for dino: DinoInPlay in _card_nodes:
		if _card_nodes[dino] == card3d:
			return dino
	return null


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


