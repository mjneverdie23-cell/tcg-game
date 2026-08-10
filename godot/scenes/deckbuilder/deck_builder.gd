extends Control
## Deck builder: owned cards on the left (click to add), the working deck on
## the right (click a row to remove a copy). Validation, composition
## breakdown and copy limits update live; decks persist through PlayerData.

const CARD_FACE_SCENE := preload("res://scenes/cards/card_face.tscn")
const THUMB_SCALE := 0.52
const THUMB_SIZE := Vector2(250 * THUMB_SCALE, 350 * THUMB_SCALE)

## Index into PlayerData.decks being edited; -1 = a new, unsaved deck.
var _editing_index: int = -1
var _card_ids: Array = []
var _search_text: String = ""
## card id -> {button: Button, badge: Label, card: CardData} for live updates.
var _grid_items: Dictionary = {}


func _ready() -> void:
	%BackButton.pressed.connect(SceneRouter.back)
	%SearchEdit.text_changed.connect(_on_search_changed)
	for option: String in CardStyle.KIND_FILTERS:
		%KindFilter.add_item(option.capitalize())
	%KindFilter.item_selected.connect(func(_index: int) -> void: _apply_pool_filters())
	%DeckDropdown.item_selected.connect(_on_deck_selected)
	%NewDeckButton.pressed.connect(_start_new_deck)
	%AutoBuildButton.pressed.connect(_on_auto_build)
	%SaveButton.pressed.connect(_on_save)
	%DeleteButton.pressed.connect(_on_delete)

	_build_grid()
	_refresh_deck_dropdown()
	if PlayerData.decks.is_empty():
		_start_new_deck()
	else:
		%DeckDropdown.select(0)
		_on_deck_selected(0)


# ── deck selection / persistence ──────────────────────────────────────


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
	_update_grid_states()


func _start_new_deck() -> void:
	_editing_index = -1
	_card_ids = []
	%NameEdit.text = "New Deck"
	%DeckDropdown.select(%DeckDropdown.item_count - 1)
	_refresh_deck_panel()
	_update_grid_states()


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
	_refresh_deck_dropdown()
	if PlayerData.decks.is_empty():
		_start_new_deck()
	else:
		%DeckDropdown.select(0)
		_on_deck_selected(0)


func _on_auto_build() -> void:
	_card_ids = DeckRules.auto_build(PlayerData.owned_cards)
	_refresh_deck_panel()
	_update_grid_states()


# ── card pool grid ────────────────────────────────────────────────────


func _on_search_changed(text: String) -> void:
	_search_text = text.strip_edges().to_lower()
	_apply_pool_filters()


## Built once from the owned collection; filters only toggle visibility.
func _build_grid() -> void:
	var cards: Array[CardData] = []
	for card: CardData in GameData.all_cards():
		if PlayerData.owned_count(card.id) > 0:
			cards.append(card)
	cards.sort_custom(func(a: CardData, b: CardData) -> bool:
		if a.kind != b.kind:
			return a.kind < b.kind
		return a.display_name < b.display_name)

	for card: CardData in cards:
		var button := Button.new()
		button.custom_minimum_size = THUMB_SIZE
		button.flat = true
		button.tooltip_text = card.display_name
		button.pressed.connect(_on_pool_card_pressed.bind(card))

		var face: CardFace = CARD_FACE_SCENE.instantiate()
		face.scale = Vector2(THUMB_SCALE, THUMB_SCALE)
		button.add_child(face)
		face.show_card(card)

		var badge := Label.new()
		badge.add_theme_font_size_override("font_size", 11)
		badge.add_theme_color_override("font_color", CardStyle.GOLD)
		badge.z_index = 1
		button.add_child(badge)
		badge.position = Vector2(6, THUMB_SIZE.y - 20)

		%Grid.add_child(button)
		_grid_items[card.id] = {"button": button, "badge": badge, "card": card}


func _apply_pool_filters() -> void:
	var kind_choice: String = CardStyle.KIND_FILTERS[%KindFilter.selected]
	for id: String in _grid_items:
		var item: Dictionary = _grid_items[id]
		var card: CardData = item["card"]
		var visible_now := CardStyle.matches_kind(card, kind_choice)
		if visible_now and _search_text != "":
			visible_now = card.display_name.to_lower().contains(_search_text)
		(item["button"] as Button).visible = visible_now


func _on_pool_card_pressed(card: CardData) -> void:
	if DeckRules.can_add(_card_ids, card, PlayerData.owned_count(card.id)):
		_card_ids.append(card.id)
		_refresh_deck_panel()
		_update_grid_states()


## Refreshes copy badges and add-availability dimming without rebuilding.
func _update_grid_states() -> void:
	for id: String in _grid_items:
		var item: Dictionary = _grid_items[id]
		var card: CardData = item["card"]
		var in_deck := DeckRules.count_copies(_card_ids, id)
		var owned := PlayerData.owned_count(id)
		(item["badge"] as Label).text = "%d / %d in deck" % [in_deck, owned] if in_deck > 0 else ""
		var addable := DeckRules.can_add(_card_ids, card, owned)
		(item["button"] as Button).modulate = (
			Color.WHITE if addable else Color(0.6, 0.62, 0.7, 0.55))


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
	elif card is InstinctCardData:
		chip_color = CardStyle.TYPE_COLORS[(card as InstinctCardData).dino_type]
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
	_update_grid_states()
