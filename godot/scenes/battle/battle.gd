extends Node3D
## Battle screen. The 3D table is the presentation stage; all interaction
## runs through the 2D HUD. The human plays via buttons that map 1:1 onto
## BattleEngine legal actions; the rival is driven by BattleAI with a short
## delay per action so its turn is readable.

const CARD_FACE_SCENE := preload("res://scenes/cards/card_face.tscn")
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
## Returned by _attach_target_of for a dinosaur that is not the player's.
const INVALID_TARGET := -99
## Reach of the pointer ray used to find the card under the energy well.
const RAY_LENGTH := 100.0
## Where the camera looks while you pick a dinosaur off your bench, and how
## far behind it the camera sits. Solved rather than eyeballed: 4.2 is the
## closest distance at which the whole 3.4-unit row still fits across a 4:3
## window, which is the narrowest view the game runs in.
const BENCH_FOCUS := Vector3(0, 0.18, 2.15)
const BENCH_FOCUS_DISTANCE := 4.2
## How long a tapped card keeps its drop targets lit.
const TARGET_HINT_SECONDS := 1.2

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
## Dome that follows the pointer while energy is being dragged.
var _energy_ghost: EnergyOrb = null
## Hand index being dragged, or -1. A tap lights the same targets without
## setting this, so the hint can tell itself apart from a real drag.
var _drag_index := -1
## Places the card in hand may be dropped, each {"actions": Array} plus
## either "slot" (a play index on your side of the table) or "centre": true
## for the hollow frame in the middle.
var _drag_targets: Array = []
## Open dinosaur choice: DinoInPlay -> the action that picks it.
var _choice: Dictionary = {}
## Quest-chain match being played, or -1 for a free battle.
var _quest_match := -1
@onready var _board: Node3D = $Board
@onready var _camera: Camera3D = $Camera3D
## Camera moves, HUD entrance, banners and the 2D card flights.
@onready var _fx := BattleFx.new()
## Slot outlines on the table, and the geometry drops are aimed at.
@onready var _slots := BoardSlots.new()
## The action zoom: attacks and retreat, laid on the card itself.
@onready var _zoom := BattleZoom.new()


func _ready() -> void:
	# Area3D hover/click on board cards only fires when the viewport does
	# physics picking — off by default, which silently killed 3D input.
	get_viewport().physics_object_picking = true
	add_child(_fx)
	_fx.setup(%HUD, _camera, %TurnBanner)
	_board.add_child(_slots)
	_slots.build()
	add_child(_zoom)
	_zoom.setup(%CardZoom, %ZoomBackdrop, %ZoomFaceBox)
	_zoom.attack_chosen.connect(_on_zoom_attack)
	_zoom.retreat_requested.connect(_on_retreat_pressed)
	_build_piles()
	%BackButton.pressed.connect(SceneRouter.back)
	%SetupBackButton.pressed.connect(SceneRouter.back)
	%StartButton.pressed.connect(_on_start_pressed)
	%EndTurnButton.pressed.connect(func() -> void: _apply_player_action({"type": "end_turn"}))
	%Hand.drag_started.connect(_on_hand_drag_started)
	%Hand.dragged.connect(_on_hand_dragged)
	%Hand.dropped.connect(_on_hand_dropped)
	%Hand.card_tapped.connect(_on_hand_card_tapped)
	%Hand.card_held.connect(_on_hand_card_held)
	%RivalHand.face_down = true
	%RivalHand.inverted = true
	%EnergyOrb.drag_started.connect(_on_energy_drag_started)
	%EnergyOrb.dragged.connect(_on_energy_dragged)
	%EnergyOrb.dropped.connect(_on_energy_dropped)
	%ChoiceCancel.pressed.connect(_end_choice)
	%CoinButton.pressed.connect(_on_coin_dismissed)
	%ReturnButton.pressed.connect(SceneRouter.back)
	%ClaimButton.pressed.connect(_on_claim_pressed)
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
	_quest_match = SceneRouter.quest_match

	var rival_deck: Array
	var level := BattleAI.PROFILES.size() - 1  # free battles face the sharp AI
	if _quest_match >= 0:
		rival_deck = QuestRules.build_rival_deck(_quest_match)
		level = int(QuestRules.quest(_quest_match)["level"])
	else:
		# The rival drafts a legal deck of a random type from full card access.
		var rival_owned: Dictionary = {}
		for card: CardData in GameData.all_cards():
			rival_owned[card.id] = 2
		rival_deck = DeckRules.auto_build(rival_owned, randi_range(0, 3))

	var battle_seed := randi()
	_ai.configure(level, battle_seed)
	_engine = BattleEngine.new(player_deck, rival_deck, battle_seed)
	_log_lines = _engine.log_history.duplicate()  # setup events (coin flip…)
	_engine.log_line.connect(_on_log_line)
	_reward_granted = false
	_trophy_delta = 0
	%SetupPanel.visible = false
	%HUD.visible = true
	%ClaimButton.visible = false
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
	_end_choice()
	_end_drag()
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


# ── playing a card: drag it out of the hand ───────────────────────────
# A card is never played by clicking it. Dinosaurs are dropped onto the
# place they will take on the table; Spells, Supports and Environments are
# dropped into the hollow frame in the middle, because they are aimed at the
# game rather than at a place on the board. A drop anywhere else is not a
# play at all — the card goes back to the hand having cost nothing, which is
# what makes picking a card up safe.


func _on_hand_drag_started(index: int) -> void:
	_show_targets(index)
	_drag_index = index


func _on_hand_dragged(_index: int, at: Vector2) -> void:
	var armed := _target_under(at)
	for i in range(_drag_targets.size()):
		_light_target(_drag_targets[i], BoardSlots.ARMED if i == armed else BoardSlots.LEGAL)


func _on_hand_dropped(index: int, at: Vector2) -> void:
	var hit := _target_under(at)
	var targets := _drag_targets
	_end_drag()
	# The card goes back to the fan first, whatever happens next: playing it
	# takes it out of the hand on the very next refresh, and a card that is
	# not played must never be left hanging where it was dropped.
	%Hand.return_card(index)
	if hit == -1:
		if targets.is_empty():
			_on_log_line("There is nowhere to play that card right now.")
			_flush_log()
		return
	var actions: Array = targets[hit]["actions"]
	if actions.size() == 1:
		_apply_player_action(actions[0])
		return
	# One card, several dinosaurs it could be aimed at: the drop commits to
	# playing it, and the choice that follows says at what.
	_begin_choice("Use it on which dinosaur?", actions)


## A tap plays nothing. It lights up where the card could have gone, which
## is the whole of what the gesture has to teach.
func _on_hand_card_tapped(index: int) -> void:
	_show_targets(index)
	if _drag_targets.is_empty():
		_on_log_line("There is nowhere to play that card right now.")
		_flush_log()
		return
	var hint := create_tween()
	hint.tween_interval(TARGET_HINT_SECONDS)
	hint.tween_callback(func() -> void:
		if _drag_index == -1:  # a real drag started meanwhile; leave it alone
			_end_drag())


## Held still: read the card, full size, without playing it.
func _on_hand_card_held(index: int) -> void:
	var hand: Array = _engine.players[0].hand
	if index < 0 or index >= hand.size():
		return
	%BattleViewer.open(GameData.get_card(hand[index]))


## Lights every place the card at `hand_index` could go.
func _show_targets(hand_index: int) -> void:
	_end_drag()
	_drag_targets = _targets_for(hand_index)
	var centre := false
	for target: Dictionary in _drag_targets:
		_light_target(target, BoardSlots.LEGAL)
		centre = centre or target.has("centre")
	%PlaySlot.visible = centre
	if centre:
		%PlaySlot.set_prompt(_play_prompt(hand_index))


## Drop targets for one card in hand. Dinosaurs name a slot on the table;
## everything else goes to the middle. Several actions can share one target
## when they differ only in which dinosaur they are aimed at.
func _targets_for(hand_index: int) -> Array:
	var by_slot: Dictionary = {}
	var centre: Array = []
	for action: Dictionary in _engine.get_legal_actions():
		if int(action.get("hand", -99)) != hand_index:
			continue
		match action["type"]:
			"place_basic":
				by_slot[_open_slot()] = [action]
			"evolve":
				var slot := _play_index_of(_dino_of_action(action))
				if slot != -1:
					by_slot[slot] = [action]
			_:
				centre.append(action)
	var targets: Array = []
	for slot: int in by_slot:
		targets.append({"slot": slot, "actions": by_slot[slot]})
	if not centre.is_empty():
		targets.append({"centre": true, "actions": centre})
	return targets


## Index into _drag_targets under a viewport position, or -1.
func _target_under(at: Vector2) -> int:
	for i in range(_drag_targets.size()):
		if _rect_of_target(_drag_targets[i]).has_point(at):
			return i
	return -1


func _rect_of_target(target: Dictionary) -> Rect2:
	if target.has("centre"):
		return %PlaySlot.get_global_rect()
	return _slots.screen_rect(_camera, 0, int(target["slot"]))


## Lights one target at a level. An occupied slot lights the card standing
## in it as well: the outline alone is barely wider than the card covering
## it, which is no signal at all.
func _light_target(target: Dictionary, level: int) -> void:
	if target.has("centre"):
		%PlaySlot.active = level == BoardSlots.ARMED
		return
	var slot := int(target["slot"])
	_slots.highlight(0, slot, level)
	var dino := _dino_at(slot)
	if dino == null or not _card_nodes.has(dino):
		return
	var node := _card_nodes[dino] as Card3D
	node.set_highlighted(level != BoardSlots.OFF)
	node.set_selected(level == BoardSlots.ARMED)


func _end_drag() -> void:
	for target: Dictionary in _drag_targets:
		_light_target(target, BoardSlots.OFF)
	_drag_targets = []
	_drag_index = -1
	%PlaySlot.active = false
	%PlaySlot.visible = false


func _play_prompt(hand_index: int) -> String:
	var card := GameData.get_card(_engine.players[0].hand[hand_index])
	if card is FieldCardData:
		return "Set\nEnvironment"
	if card is TrainerCardData:
		return "Play\n%s" % (card as TrainerCardData).trainer_kind.capitalize()
	return "Play"


## Where the next basic dinosaur you field will stand: the Active slot while
## it is empty, otherwise the first free place on the bench.
func _open_slot() -> int:
	var you := _engine.players[0]
	return 0 if you.active == null else 1 + you.bench.size()


# ── choosing a dinosaur ───────────────────────────────────────────────
# Retreating, playing a switch card and clicking the energy well all end in
# the same question: which of your dinosaurs? Instead of a list of names in
# a panel, the camera pushes in on the row and every candidate lights up, so
# the answer is given by pointing at the card you mean.


func _begin_choice(prompt: String, actions: Array) -> void:
	_end_choice()
	var bench_only := true
	for action: Dictionary in actions:
		var dino := _dino_of_action(action)
		if dino == null:
			continue
		_choice[dino] = action
		bench_only = bench_only and dino != _engine.players[0].active
	if _choice.is_empty():
		return
	for dino: DinoInPlay in _choice:
		if _card_nodes.has(dino):
			(_card_nodes[dino] as Card3D).set_highlighted(true)
	%ChoiceLabel.text = prompt
	%ChoicePanel.visible = true
	if bench_only:
		_fx.focus_point(BENCH_FOCUS, BENCH_FOCUS_DISTANCE)


func _end_choice() -> void:
	if _choice.is_empty():
		return
	for dino: DinoInPlay in _choice:
		if _card_nodes.has(dino):
			var node := _card_nodes[dino] as Card3D
			node.set_highlighted(false)
			node.set_selected(false)
	_choice.clear()
	%ChoicePanel.visible = false
	_fx.release_focus()


func _on_energy_pressed() -> void:
	_begin_choice("Attach energy to…", _actions_of_type("attach"))


func _on_retreat_pressed() -> void:
	_begin_choice("Swap in which dinosaur?", _actions_of_type("retreat"))


func _actions_of_type(kind: String) -> Array:
	var out: Array = []
	for action: Dictionary in _engine.get_legal_actions():
		if action["type"] == kind:
			out.append(action)
	return out


## The dinosaur an action is aimed at, or null when it is aimed at nothing.
func _dino_of_action(action: Dictionary) -> DinoInPlay:
	var you := _engine.players[0]
	if action["type"] == "retreat":
		return you.bench[int(action["bench"])]
	if not action.has("target"):
		return null
	var target := int(action["target"])
	if action["type"] == "trainer":  # switch cards name a bench dinosaur
		return you.bench[target] if target < you.bench.size() else null
	return you.active if target == -1 else you.bench[target]


## Your dinosaur standing in a slot (0 = Active, 1.. = bench), or null.
func _dino_at(slot: int) -> DinoInPlay:
	var dinos := _engine.players[0].dinos_in_play()
	return dinos[slot] if slot >= 0 and slot < dinos.size() else null


func _play_index_of(dino: DinoInPlay) -> int:
	return _engine.players[0].dinos_in_play().find(dino)


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
	if _zoom.is_open():
		_zoom.refresh()
	_flush_log()

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


## Repaints the log tail on its own. A full _refresh() rebuilds the hand,
## which is exactly what must not happen while a card is being carried out
## of it — so anything the player is told mid-drag comes through here.
func _flush_log() -> void:
	var tail := mini(4, _log_lines.size())
	%LogLabel.text = "\n".join(_log_lines.slice(_log_lines.size() - tail))


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


## Pays out a quest match's reward. PlayerData refuses a second claim, so the
## button only needs to reflect what happened.
func _on_claim_pressed() -> void:
	if PlayerData.claim_quest(_quest_match):
		%ClaimButton.disabled = true
		%ClaimButton.text = "Claimed  ·  +%d coins" % int(
			QuestRules.quest(_quest_match)["reward"])


func _on_zoom_attack(action: Dictionary) -> void:
	_apply_player_action(action)


func _show_result() -> void:
	var won := _engine.winner == 0
	# A quest match pays its own reward, and only when the player claims it —
	# so the automatic battle coins are skipped for a quest win.
	var quest_win := won and _quest_match >= 0
	%ResultLabel.text = "You won!" if won else "Defeat"
	if not _reward_granted:
		_reward_granted = true
		if quest_win:
			PlayerData.record_quest_win(_quest_match)
		else:
			PlayerData.earn_coins(WIN_COINS if won else LOSS_COINS)
		# Ranked stakes trophies; practice counts toward quests but not the
		# ladder. The mode was chosen on the home screen.
		_trophy_delta = PlayerData.record_battle(won, SceneRouter.battle_ranked)

	if quest_win:
		var reward := int(QuestRules.quest(_quest_match)["reward"])
		var claimed := QuestRules.state_of(_quest_match) == QuestRules.STATE_CLAIMED
		%RewardLabel.text = "%s beaten  ·  reward %d coins" % [
			str(QuestRules.quest(_quest_match)["title"]), reward]
		%ClaimButton.visible = true
		%ClaimButton.disabled = claimed
		%ClaimButton.text = "Reward claimed" if claimed else "Claim %d coins" % reward
	else:
		%ClaimButton.visible = false
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
				var enter := BoardSlots.transform_for(side, i)
				enter.origin.z += 3.0 * (1.0 if side == 0 else -1.0)
				card3d.transform = enter
				card3d.clicked.connect(_on_board_card_clicked)
				_card_nodes[dino] = card3d
				_card_sides[dino] = side
			elif card3d.card_data != dino.card():
				card3d.show_card(dino.card())  # evolved into a new face
			card3d.move_home(BoardSlots.transform_for(side, i))
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
## While a choice is open the board answers that question and nothing else:
## a click meant for the bench must never open a zoom on top of it.
func _on_board_card_clicked(card3d: Card3D) -> void:
	if card3d.card_data == null:
		return
	var dino := _dino_for_node(card3d)
	if not _choice.is_empty():
		if dino != null and _choice.has(dino):
			var action: Dictionary = _choice[dino]
			_end_choice()
			_apply_player_action(action)
		return
	if dino != null and int(_card_sides.get(dino, 1)) == 0:
		_zoom.open(_engine, dino)
		return
	%BattleViewer.open(card3d.card_data)


func _dino_for_node(card3d: Card3D) -> DinoInPlay:
	for dino: DinoInPlay in _card_nodes:
		if _card_nodes[dino] == card3d:
			return dino
	return null


# ── UI animation ──────────────────────────────────────────────────────


