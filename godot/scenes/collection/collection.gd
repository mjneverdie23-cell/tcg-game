extends Control
## Collection screen. The grid is built exactly once; search, kind filter,
## owned-toggle and ownership changes only flip visibility and restyle
## badges — the screen never re-instantiates nodes after load. (The previous
## implementation tore down and rebuilt ~2300 nodes per keystroke, which
## caused multi-frame stalls and dropped input.)

const CARD_FACE_SCENE := preload("res://scenes/cards/card_face.tscn")
const THUMB_SCALE := 0.62
const THUMB_SIZE := Vector2(250 * THUMB_SCALE, 350 * THUMB_SCALE)
const UNOWNED_TINT := Color(0.55, 0.58, 0.68, 0.4)

## One entry per card in the catalog: {card, button, face, badge}.
var _items: Array[Dictionary] = []
var _search_text: String = ""


func _ready() -> void:
	%BackButton.pressed.connect(SceneRouter.back)
	%SearchEdit.text_changed.connect(_on_search_changed)
	for option: String in CardStyle.KIND_FILTERS:
		%KindFilter.add_item(option.capitalize())
	%KindFilter.item_selected.connect(func(_index: int) -> void: _apply_filters())
	%OwnedToggle.toggled.connect(func(_on: bool) -> void: _apply_filters())
	PlayerData.collection_changed.connect(_refresh_ownership)
	_build_grid()
	_refresh_ownership()


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
		button.tooltip_text = card.display_name
		button.pressed.connect(func() -> void: %Viewer.open(card))

		var face: CardFace = CARD_FACE_SCENE.instantiate()
		face.scale = Vector2(THUMB_SCALE, THUMB_SCALE)
		button.add_child(face)
		face.show_card(card)

		var badge := Label.new()
		badge.add_theme_font_size_override("font_size", 12)
		badge.add_theme_color_override("font_color", Color.WHITE)
		badge.z_index = 1
		button.add_child(badge)
		badge.position = THUMB_SIZE - Vector2(34, 24)

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


## Updates counts, dimming and the progress label (on load and whenever the
## collection changes), then re-applies filters.
func _refresh_ownership() -> void:
	var owned_distinct := 0
	for item: Dictionary in _items:
		var owned := PlayerData.owned_count((item["card"] as CardData).id)
		if owned > 0:
			owned_distinct += 1
		(item["badge"] as Label).text = "x%d" % owned if owned > 1 else ""
		(item["face"] as CardFace).modulate = Color.WHITE if owned > 0 else UNOWNED_TINT
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
