extends Control
## Home screen (the Battle tab). Two halves: your standing and the way into a
## match on the left, the daily quest chain and your coins on the right.
##
## Everything shown here is derived from PlayerData — trophies, arena, quest
## counters, coins — so the home screen has no state of its own to keep in
## sync beyond the battle mode, which is a navigation argument.

## Mode dropdown entries: label, whether trophies are staked, and whether the
## entry can be picked at all.
const MODES: Array = [
	{"label": "Ranked — trophies at stake", "ranked": true, "enabled": true},
	{"label": "Practice — no trophies", "ranked": false, "enabled": true},
	{"label": "Versus player — online only", "ranked": false, "enabled": false},
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
	%MissionButton.pressed.connect(_on_bonus_pressed)
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
		if not bool(MODES[i]["enabled"]):
			%ModeSelect.set_item_disabled(i, true)
			%ModeSelect.set_item_tooltip(
				i, "This build runs entirely offline — there is no matchmaking server.")
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


func _refresh_mission() -> void:
	var claimed := QuestRules.claimed_count()
	%MissionProgress.text = "%d/%d completed" % [claimed, QuestRules.count()]
	%MissionBar.max_value = QuestRules.count()
	%MissionBar.value = claimed
	if PlayerData.chain_bonus_claimed:
		%MissionButton.text = "Bonus collected"
		%MissionButton.disabled = true
		%MissionHint.text = "Fresh quests arrive tomorrow."
		return
	%MissionButton.disabled = not QuestRules.bonus_ready()
	%MissionButton.text = "Collect +%d" % QuestRules.CHAIN_BONUS
	%MissionHint.text = (
		"Chain bonus ready!"
		if QuestRules.bonus_ready()
		else "Clear all %d quests for +%d coins." % [
			QuestRules.count(), QuestRules.CHAIN_BONUS])


func _on_quest_pressed(index: int) -> void:
	if PlayerData.claim_quest(index):
		_refresh()


func _on_bonus_pressed() -> void:
	if PlayerData.claim_chain_bonus():
		_refresh()


func _on_mode_selected(index: int) -> void:
	SceneRouter.battle_ranked = bool(MODES[index]["ranked"])


func _on_battle_pressed() -> void:
	SceneRouter.go_to("battle")
