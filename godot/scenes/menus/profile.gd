extends Control
## Profile tab: who you are, where you sit on the ladder, and the career
## totals behind it. Every figure is read from PlayerData rather than stored
## here, so the screen can never disagree with the save file.


func _ready() -> void:
	%BackButton.pressed.connect(SceneRouter.back)
	%CollectionButton.pressed.connect(func() -> void: SceneRouter.go_to("collection"))
	%NameEdit.text_submitted.connect(_on_name_submitted)
	%NameEdit.focus_exited.connect(func() -> void: _on_name_submitted(%NameEdit.text))
	_style()
	_refresh()


func _style() -> void:
	%IdentityPanel.add_theme_stylebox_override("panel", MenuStyle.panel())
	%StatsPanel.add_theme_stylebox_override("panel", MenuStyle.panel())
	MenuStyle.style_button(%CollectionButton, true)
	MenuStyle.style_button(%BackButton)
	var avatar := NavIcon.new()
	avatar.kind = NavIcon.PROFILE
	avatar.color = MenuStyle.ACCENT
	avatar.custom_minimum_size = Vector2(96, 96)
	%AvatarBox.add_child(avatar)


func _refresh() -> void:
	%NameEdit.text = PlayerData.player_name
	%ArenaLabel.text = "Arena %d — %s" % [
		ArenaRules.number_for(PlayerData.trophies), ArenaRules.name_for(PlayerData.trophies)]
	%TrophyLabel.text = "%d trophies" % PlayerData.trophies
	var next := ArenaRules.next_threshold(PlayerData.trophies)
	%LadderLabel.text = (
		"Top of the ladder."
		if next == -1
		else "%d trophies to the next arena." % (next - PlayerData.trophies))
	%LadderBar.value = ArenaRules.progress(PlayerData.trophies) * 100.0
	_fill_stats()


func _fill_stats() -> void:
	for child in %StatsGrid.get_children():
		child.queue_free()
	var played := PlayerData.battles_played
	var won := PlayerData.battles_won
	var win_rate := "—" if played == 0 else "%d%%" % roundi(100.0 * float(won) / float(played))
	var catalog := GameData.all_cards().size()
	var collected := 0
	for card_id: String in PlayerData.owned_cards:
		if GameData.has_card(card_id) and int(PlayerData.owned_cards[card_id]) > 0:
			collected += 1
	for row: Array in [
		["Battles played", str(played)],
		["Battles won", str(won)],
		["Win rate", win_rate],
		["Best trophies", str(PlayerData.best_trophies)],
		["Packs opened", str(PlayerData.packs_opened)],
		["Cards collected", "%d / %d" % [collected, catalog]],
		["Decks saved", str(PlayerData.decks.size())],
		["Coins", str(PlayerData.coins)],
	]:
		%StatsGrid.add_child(MenuStyle.heading(str(row[0])))
		var value := Label.new()
		value.text = str(row[1])
		value.add_theme_font_size_override("font_size", 17)
		value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		value.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		%StatsGrid.add_child(value)


func _on_name_submitted(new_name: String) -> void:
	PlayerData.set_player_name(new_name)
	%NameEdit.text = PlayerData.player_name
	%NameEdit.release_focus()
