extends Control
## Collection tab — browsing the catalog and building decks, in one screen.
##
## Both jobs need the same thing: every card, laid out in a filterable grid.
## So there is one grid, built exactly once, and a mode switch that changes
## what a thumbnail *means*:
##
##   Browse — the whole catalog, unowned cards dimmed, click to inspect.
##   Decks  — owned cards only, click to add a copy to the working deck,
##            with the deck panel open on the right.
##
## The grid is never rebuilt after load. Search, filters, mode changes and
## ownership updates only flip visibility, badges and tints; an earlier
## version tore down ~2300 nodes per keystroke and stalled for whole frames.

const CARD_FACE_SCENE := preload("res://scenes/cards/card_face.tscn")
const THUMB_SCALE := 0.58
const THUMB_SIZE := Vector2(250 * THUMB_SCALE, 350 * THUMB_SCALE)
const UNOWNED_TINT := Color(0.55, 0.58, 0.68, 0.4)
## Dimming for a card that cannot join the deck (no copies left to add).
const UNADDABLE_TINT := Color(0.6, 0.62, 0.7, 0.55)
## Columns that fit either body width: a 145 px thumb plus a 10 px gutter,
## against 1240 px of content with the 380 px deck panel closed (1075 used)
## or open (765 of ~830).
const BROWSE_COLUMNS := 7
const DECK_COLUMNS := 5

## One entry per card in the catalog: {card, button, face, badge}.
var _items: Array[Dictionary] = []
var _search_text: String = ""
var _deck_mode: bool = false

## Index into PlayerData.decks being edited; -1 = a new, unsaved deck.
var _editing_index: int = -1
var _card_ids: Array = []


func _ready() -> void:
	%BackButton.pressed.connect(SceneRouter.back)
	%SearchEdit.text_changed.connect(_on_search_changed)
	for option: String in CardStyle.KIND_FILTERS:
		%KindFilter.add_item(option.capitalize())
	%KindFilter.item_selected.connect(func(_index: int) -> void: _apply_filters())
	%OwnedToggle.toggled.connect(func(_on: bool) -> void: _apply_filters())
	%BrowseTab.pressed.connect(_set_deck_mode.bind(false))
	%DecksTab.pressed.connect(_set_deck_mode.bind(true))
	%DeckDropdown.item_selected.connect(_on_deck_selected)
	%NewDeckButton.pressed.connect(_start_new_deck)
	%AutoBuildButton.pressed.connect(_on_auto_build)
	%SaveButton.pressed.connect(_on_save)
	%DeleteButton.pressed.connect(_on_delete)
	PlayerData.collection_changed.connect(_refresh_items)

	_style()
	_build_grid()
	_load_first_deck()
	_set_deck_mode(false)


func _style() -> void:
	%DeckPanel.add_theme_stylebox_override("panel", MenuStyle.panel())
	MenuStyle.style_tab(%BrowseTab)
	MenuStyle.style_tab(%DecksTab)
	MenuStyle.style_button(%BackButton)
	MenuStyle.style_button(%SaveButton, true)
	MenuStyle.style_button(%AutoBuildButton)
	MenuStyle.style_button(%DeleteButton)
	MenuStyle.style_button(%NewDeckButton)
	%ProgressLabel.add_theme_color_override("font_color", MenuStyle.TEXT_DIM)


# ── mode ──────────────────────────────────────────────────────────────


func _set_deck_mode(on: bool) -> void:
	_deck_mode = on
	%DeckPanel.visible = on
	%Grid.columns = DECK_COLUMNS if on else BROWSE_COLUMNS
	%TitleLabel.text = "Decks" if on else "Collection"
	%SearchEdit.placeholder_text = "Search owned cards…" if on else "Search cards…"
	# Deck building can only use cards you own, so the filter is forced on
	# (and locked) rather than silently ignored.
	if on:
		%OwnedToggle.button_pressed = true
	%OwnedToggle.disabled = on
	_refresh_items()


# ── card grid ─────────────────────────────────────────────────────────


func _on_search_changed(text: String) -> void:
	_search_text = text.strip_edges().to_lower()
	_apply_filters()


## Instantiates every card thumbnail once, in display order.
func _build_grid() -> void:
	var cards: Array[CardData] = []
	cards.assign(GameData.all_cards())
	cards.sort_custom(_sort_cards)

	for card: CardData in cards:
		var button := Button.new()
		button.custom_minimum_size = THUMB_SIZE
		button.flat = true
		button.pressed.connect(_on_card_pressed.bind(card))

		var face: CardFace = CARD_FACE_SCENE.instantiate()
		face.scale = Vector2(THUMB_SCALE, THUMB_SCALE)
		button.add_child(face)
		face.show_card(card)

		var badge := Label.new()
		badge.add_theme_font_size_override("font_size", 12)
		badge.z_index = 1
		button.add_child(badge)
		badge.position = THUMB_SIZE - Vector2(64, 24)
		badge.custom_minimum_size = Vector2(58, 0)
		badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT

		%Grid.add_child(button)
		_items.append({"card": card, "button": button, "face": face, "badge": badge})


## Dinos first (grouped by type), then rarity (mythic first), then name.
func _sort_cards(a: CardData, b: CardData) -> bool:
	if a.kind != b.kind:
		return a.kind < b.kind
	if a is DinoCardData and b is DinoCardData:
		var type_a := (a as DinoCardData).dino_type
		var type_b := (b as DinoCardData).dino_type
		if type_a != type_b:
			return type_a < type_b
	var rarity_a: int = CardStyle.RARITY_ORDER[a.rarity]
	var rarity_b: int = CardStyle.RARITY_ORDER[b.rarity]
	if rarity_a != rarity_b:
		return rarity_a < rarity_b
	return a.display_name < b.display_name


## Clicking a card inspects it while browsing and adds a copy while building.
func _on_card_pressed(card: CardData) -> void:
	if not _deck_mode:
		%Viewer.open(card)
		return
	if DeckRules.can_add(_card_ids, card, PlayerData.owned_count(card.id)):
		_card_ids.append(card.id)
		_refresh_deck_panel()
		_refresh_items()


## Badges, tints and tooltips for the current mode; also the progress
## readout. Called on load, on mode changes and whenever the collection or
## the working deck changes.
func _refresh_items() -> void:
	var owned_distinct := 0
	for item: Dictionary in _items:
		var card: CardData = item["card"]
		var owned := PlayerData.owned_count(card.id)
		if owned > 0:
			owned_distinct += 1
		var badge: Label = item["badge"]
		var button: Button = item["button"]
		var face: CardFace = item["face"]
		if _deck_mode:
			var in_deck := DeckRules.count_copies(_card_ids, card.id)
			badge.text = "%d/%d" % [in_deck, owned] if in_deck > 0 else ""
			badge.add_theme_color_override("font_color", CardStyle.GOLD)
			face.modulate = Color.WHITE
			button.modulate = (
				Color.WHITE if DeckRules.can_add(_card_ids, card, owned) else UNADDABLE_TINT)
			button.tooltip_text = "%s — %d in deck of %d owned" % [
				card.display_name, in_deck, owned]
		else:
			badge.text = "x%d" % owned if owned > 1 else ""
			badge.add_theme_color_override("font_color", Color.WHITE)
			face.modulate = Color.WHITE if owned > 0 else UNOWNED_TINT
			button.modulate = Color.WHITE
			button.tooltip_text = card.display_name
	%ProgressLabel.text = "Collected %d / %d" % [owned_distinct, _items.size()]
	_apply_filters()


## Search / kind / owned-only only toggle visibility — never rebuild.
func _apply_filters() -> void:
	var kind_choice: String = CardStyle.KIND_FILTERS[%KindFilter.selected]
	var owned_only: bool = %OwnedToggle.button_pressed
	for item: Dictionary in _items:
		var card: CardData = item["card"]
		var visible_now := CardStyle.matches_kind(card, kind_choice)
		if visible_now and owned_only:
			visible_now = PlayerData.owned_count(card.id) > 0
		if visible_now and _search_text != "":
			visible_now = card.display_name.to_lower().contains(_search_text)
		(item["button"] as Button).visible = visible_now


# ── deck selection / persistence ──────────────────────────────────────


func _load_first_deck() -> void:
	_refresh_deck_dropdown()
	if PlayerData.decks.is_empty():
		_start_new_deck()
		return
	%DeckDropdown.select(0)
	_on_deck_selected(0)


func _refresh_deck_dropdown() -> void:
	%DeckDropdown.clear()
	for deck: Dictionary in PlayerData.decks:
		%DeckDropdown.add_item(deck["name"])
	%DeckDropdown.add_item("(new deck)")


func _on_deck_selected(index: int) -> void:
	if index >= PlayerData.decks.size():
		_start_new_deck()
		return
	_editing_index = index
	var deck: Dictionary = PlayerData.decks[index]
	%NameEdit.text = deck["name"]
	_card_ids = (deck["card_ids"] as Array).duplicate()
	_refresh_deck_panel()
	_refresh_items()


func _start_new_deck() -> void:
	_editing_index = -1
	_card_ids = []
	%NameEdit.text = "New Deck"
	%DeckDropdown.select(%DeckDropdown.item_count - 1)
	_refresh_deck_panel()
	_refresh_items()


func _on_save() -> void:
	var deck_name: String = %NameEdit.text.strip_edges()
	if deck_name == "":
		deck_name = "Unnamed Deck"
	_editing_index = PlayerData.save_deck(_editing_index, deck_name, _card_ids)
	_refresh_deck_dropdown()
	%DeckDropdown.select(_editing_index)


func _on_delete() -> void:
	if _editing_index >= 0:
		PlayerData.delete_deck(_editing_index)
	_load_first_deck()


func _on_auto_build() -> void:
	_card_ids = DeckRules.auto_build(PlayerData.owned_cards)
	_refresh_deck_panel()
	_refresh_items()


# ── deck panel ────────────────────────────────────────────────────────


func _refresh_deck_panel() -> void:
	for child in %DeckList.get_children():
		child.queue_free()

	# Group copies into one row per card, dinos first then by name.
	var unique_ids: Array = []
	for id: String in _card_ids:
		if not unique_ids.has(id):
			unique_ids.append(id)
	unique_ids.sort_custom(func(a: String, b: String) -> bool:
		var card_a := GameData.get_card(a)
		var card_b := GameData.get_card(b)
		if card_a.kind != card_b.kind:
			return card_a.kind < card_b.kind
		return card_a.display_name < card_b.display_name)

	for id: String in unique_ids:
		%DeckList.add_child(_make_deck_row(GameData.get_card(id)))

	%CountLabel.text = "%d / %d" % [_card_ids.size(), DeckRules.DECK_SIZE]
	%BreakdownLabel.text = DeckRules.breakdown(_card_ids)
	var issues := DeckRules.validate(_card_ids)
	%SaveButton.disabled = not issues.is_empty()  # invalid decks cannot be saved
	%IssuesLabel.text = "\n".join(issues) if not issues.is_empty() else "Deck is battle-ready."
	%IssuesLabel.add_theme_color_override(
		"font_color", Color("ff8a7a") if not issues.is_empty() else Color("6fd98a"))


func _make_deck_row(card: CardData) -> Control:
	var row := Button.new()
	row.tooltip_text = "Remove one copy"
	row.pressed.connect(_on_deck_row_pressed.bind(card.id))

	var content := HBoxContainer.new()
	content.add_theme_constant_override("separation", 8)
	content.set_anchors_preset(Control.PRESET_FULL_RECT)
	content.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(content)

	var chip := Panel.new()
	chip.custom_minimum_size = Vector2(6, 24)
	var chip_color := CardStyle.GOLD
	if card is DinoCardData:
		chip_color = CardStyle.TYPE_COLORS[(card as DinoCardData).dino_type]
	chip.add_theme_stylebox_override("panel", CardStyle.make_panel(chip_color, 3))
	chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(chip)

	var name_label := Label.new()
	name_label.text = "%d ×  %s" % [DeckRules.count_copies(_card_ids, card.id), card.display_name]
	name_label.add_theme_font_size_override("font_size", 13)
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_label.clip_text = true
	name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(name_label)

	row.custom_minimum_size = Vector2(0, 30)
	return row


func _on_deck_row_pressed(card_id: String) -> void:
	_card_ids.erase(card_id)  # removes the first matching copy
	_refresh_deck_panel()
	_refresh_items()
