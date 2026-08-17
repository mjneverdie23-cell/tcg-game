extends Control
## Home screen (the Battle tab). Two halves: your standing and the way into a
## match on the left, the daily quest chain and your coins on the right.
##
## Everything shown here is derived from PlayerData — trophies, arena, quest
## counters, coins — so the home screen has no state of its own to keep in
## sync beyond the battle mode, which is a navigation argument.

## Mode dropdown entries: label, whether trophies are staked, and whether
## BATTLE opens the online lobby instead of starting a match against the AI.
const MODES: Array = [
	{"label": "Ranked — trophies at stake", "ranked": true, "online": false},
	{"label": "Practice — no trophies", "ranked": false, "online": false},
	{"label": "Versus player — over the network", "ranked": false, "online": true},
]

var _quest_path: QuestPath = null
var _arena_badge: ArenaBadge = null


func _ready() -> void:
	_build()
	_style()
	PlayerData.coins_changed.connect(func(_amount: int) -> void: _refresh())
	PlayerData.progress_changed.connect(_refresh)
	%BattleButton.pressed.connect(_on_battle_pressed)
	%ModeSelect.item_selected.connect(_on_mode_selected)
	%MissionButton.pressed.connect(_on_mission_pressed)
	_refresh()


func _build() -> void:
	%Backdrop.texture = MenuStyle.backdrop_texture()

	# Hero emblem, tinted with the type the player collects most of — the
	# home screen and their deck always read as the same game.
	var hero := HeroEmblem.new()
	hero.dino_type = DeckRules.primary_type(PlayerData.owned_cards)
	%HeroBox.add_child(hero)
	hero.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

	_arena_badge = ArenaBadge.new()
	%ArenaBox.add_child(_arena_badge)

	_quest_path = QuestPath.new()
	_quest_path.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_quest_path.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_quest_path.quest_pressed.connect(_on_quest_pressed)
	%QuestBody.add_child(_quest_path)
	%QuestBody.move_child(_quest_path, 0)  # path left of the mission panel

	var coin := NavIcon.new()
	coin.kind = NavIcon.SHOP
	coin.color = MenuStyle.ACCENT
	coin.custom_minimum_size = Vector2(20, 20)
	%CoinsRow.add_child(coin)
	%CoinsRow.move_child(coin, 0)

	for i in range(MODES.size()):
		%ModeSelect.add_item(str(MODES[i]["label"]), i)
	%ModeSelect.set_item_tooltip(MODES.size() - 1,
		"Play someone running this same build, on your network or over the internet.")
	%ModeSelect.selected = 0 if SceneRouter.battle_ranked else 1


func _style() -> void:
	MenuStyle.style_pill(%TrophyPill)
	MenuStyle.style_pill(%CoinsPill)
	MenuStyle.style_button(%BattleButton, true)
	MenuStyle.style_button(%MissionButton, true)
	%MissionPanel.add_theme_stylebox_override("panel", MenuStyle.panel())
	%TrophyLabel.add_theme_color_override("font_color", MenuStyle.ACCENT)
	%CoinsLabel.add_theme_color_override("font_color", MenuStyle.ACCENT)
	%Divider.add_theme_constant_override("separation", 2)


func _refresh() -> void:
	%TrophyLabel.text = "Trophies %d" % PlayerData.trophies
	%CoinsLabel.text = str(PlayerData.coins)
	_arena_badge.arena_number = ArenaRules.number_for(PlayerData.trophies)
	_arena_badge.arena_name = ArenaRules.name_for(PlayerData.trophies)
	var next := ArenaRules.next_threshold(PlayerData.trophies)
	%LadderLabel.text = (
		"Top of the ladder"
		if next == -1
		else "%d trophies to Arena %d" % [
			next - PlayerData.trophies, ArenaRules.number_for(PlayerData.trophies) + 1])
	_quest_path.refresh()
	_refresh_mission()


## The panel beside the path: how far along the chain the player is, and a
## button onto whatever the chain wants from them next — play the open match,
## or collect a reward that is sitting there.
func _refresh_mission() -> void:
	var won := QuestRules.won_count()
	%MissionProgress.text = "%d/%d matches won" % [won, QuestRules.count()]
	%MissionBar.max_value = QuestRules.count()
	%MissionBar.value = won

	var unclaimed := _first_unclaimed()
	if unclaimed != -1:
		var quest := QuestRules.quest(unclaimed)
		%MissionTitle.text = str(quest["title"])
		%MissionHint.text = "Beaten! Your reward is waiting."
		%MissionButton.disabled = false
		%MissionButton.text = "Claim %d coins" % int(quest["reward"])
		return

	var next := QuestRules.next_playable()
	if next == -1:
		%MissionTitle.text = "Chain complete"
		%MissionHint.text = "Every quest match is beaten and paid out."
		%MissionButton.disabled = true
		%MissionButton.text = "All done"
		return
	var quest := QuestRules.quest(next)
	%MissionTitle.text = "%d. %s" % [next + 1, str(quest["title"])]
	%MissionHint.text = str(quest["detail"])
	%MissionButton.disabled = false
	%MissionButton.text = "Play  ·  %d coins" % int(quest["reward"])


## Index of the first match beaten but not yet paid out, or -1.
func _first_unclaimed() -> int:
	for i in range(QuestRules.count()):
		if QuestRules.state_of(i) == QuestRules.STATE_WON:
			return i
	return -1


## A node plays its match when it is open, and claims its reward when it has
## already been beaten.
func _on_quest_pressed(index: int) -> void:
	match QuestRules.state_of(index):
		QuestRules.STATE_READY:
			_start_quest_match(index)
		QuestRules.STATE_WON:
			if PlayerData.claim_quest(index):
				_refresh()


func _on_mission_pressed() -> void:
	var unclaimed := _first_unclaimed()
	if unclaimed != -1:
		if PlayerData.claim_quest(unclaimed):
			_refresh()
		return
	var next := QuestRules.next_playable()
	if next != -1:
		_start_quest_match(next)


func _start_quest_match(index: int) -> void:
	SceneRouter.quest_match = index
	SceneRouter.go_to("battle")


func _on_mode_selected(index: int) -> void:
	SceneRouter.battle_ranked = bool(MODES[index]["ranked"])
	%BattleButton.text = "FIND OPPONENT" if _versus_player() else "BATTLE"


## True when the mode dropdown is on the versus-player entry.
func _versus_player() -> bool:
	return bool(MODES[%ModeSelect.selected]["online"])


func _on_battle_pressed() -> void:
	SceneRouter.quest_match = -1  # the BATTLE button is always a free battle
	SceneRouter.go_to("online" if _versus_player() else "battle")
