class_name CardFace
extends PanelContainer
## Renders the 2D face of any card (dino / trainer / field / instinct) from
## its CardData. Designed at CardStyle.BASE_SIZE (250x350); parents scale the
## whole face for thumbnails or the viewer. This same face is later rendered
## to a texture for the 3D battle cards, so it must stay self-contained.

## Art backdrop per field card (each field has its own scene palette).
const FIELD_ART: Dictionary = {
	"field:dense-jungle": Color("1c4a24"),
	"field:volcanic-plains": Color("5a1d0e"),
	"field:river-delta": Color("103d5c"),
	"field:mountain-cliffs": Color("39435a"),
	"field:ancient-swamp": Color("2e3a10"),
	"field:ice-valley": Color("11475c"),
}

var _card: CardData


func _ready() -> void:
	custom_minimum_size = CardStyle.BASE_SIZE
	# The face is always a free child (of a Button, holder Control or 3D
	# viewport) rather than container-managed: give it its design size.
	size = CardStyle.BASE_SIZE
	clip_contents = true
	if _card != null:
		_rebuild()


func show_card(card: CardData) -> void:
	_card = card
	if is_inside_tree():
		_rebuild()


func _rebuild() -> void:
	for child in get_children():
		child.queue_free()

	var rarity_color: Color = CardStyle.RARITY_COLORS[_card.rarity]
	add_theme_stylebox_override(
		"panel", CardStyle.make_panel(CardStyle.SURFACE, 12, rarity_color, 3))

	var margin := MarginContainer.new()
	for side in ["margin_left", "margin_right", "margin_top", "margin_bottom"]:
		margin.add_theme_constant_override(side, 10)
	add_child(margin)

	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 6)
	margin.add_child(layout)

	layout.add_child(_build_header())
	layout.add_child(_build_art())
	var body := _build_body()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(body)
	layout.add_child(_build_footer())

	# A card face is pure presentation: it must never intercept the mouse.
	# Interactivity always belongs to the wrapper (Button, Area3D, …), so
	# every node — including this root — ignores input, unconditionally.
	_set_ignore_mouse(self)


func _set_ignore_mouse(node: Control) -> void:
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for child in node.get_children():
		if child is Control:
			_set_ignore_mouse(child)


func _build_header() -> Control:
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 6)

	if _card is DinoCardData and (_card as DinoCardData).stage > 1:
		header.add_child(_badge("STAGE %d" % (_card as DinoCardData).stage, CardStyle.SURFACE_LIGHT))

	var name_label := _label(_card.display_name, 16, Color.WHITE)
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_label.clip_text = true
	header.add_child(name_label)

	if _card is DinoCardData:
		var hp_label := _label("%d HP" % (_card as DinoCardData).hp, 17, Color.WHITE)
		header.add_child(hp_label)
	return header


func _build_art() -> Control:
	var art := Control.new()
	art.custom_minimum_size = Vector2(0, 138)
	art.clip_contents = true

	var backdrop := TextureRect.new()
	backdrop.set_anchors_preset(Control.PRESET_FULL_RECT)
	backdrop.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	backdrop.texture = _art_gradient()
	art.add_child(backdrop)

	var image_path: String = _card.image if _card is DinoCardData else ""
	if image_path != "" and ResourceLoader.exists("res://" + image_path):
		var image := TextureRect.new()
		image.set_anchors_preset(Control.PRESET_FULL_RECT)
		image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		image.texture = load("res://" + image_path)
		art.add_child(image)
	elif _card is DinoCardData or _card is InstinctCardData:
		# Fallback emblem: the type icon, tinted, centered.
		var icon := TextureRect.new()
		icon.texture = CardStyle.type_icon(_get_dino_type())
		icon.custom_minimum_size = Vector2(72, 72)
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.modulate = CardStyle.TYPE_COLORS[_get_dino_type()]
		icon.set_anchors_preset(Control.PRESET_CENTER)
		icon.position = Vector2(-36, -36)
		art.add_child(icon)

	art.add_child(_art_badge())
	return art


func _art_badge() -> Control:
	var text: String
	var color: Color
	match _card.kind:
		CardCatalogTypes.CardKind.DINO, CardCatalogTypes.CardKind.INSTINCT:
			text = CardStyle.type_display_name(_get_dino_type()).to_upper()
			color = CardStyle.TYPE_COLORS[_get_dino_type()]
		CardCatalogTypes.CardKind.TRAINER:
			text = (_card as TrainerCardData).trainer_kind.to_upper()
			color = CardStyle.GOLD
		_:
			text = "ENVIRONMENT"
			color = CardStyle.TYPE_COLORS[CardCatalogTypes.DinoType.HERBIVORE]
	var badge := _badge(text, Color(0, 0, 0, 0.55), color)
	badge.position = Vector2(6, 6)
	return badge


func _art_gradient() -> GradientTexture2D:
	var dark: Color
	match _card.kind:
		CardCatalogTypes.CardKind.DINO, CardCatalogTypes.CardKind.INSTINCT:
			dark = CardStyle.TYPE_ART_DARK[_get_dino_type()]
		CardCatalogTypes.CardKind.FIELD:
			dark = FIELD_ART.get(_card.id, CardStyle.SURFACE_LIGHT)
		_:
			dark = CardStyle.SURFACE_LIGHT
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 1.0])
	gradient.colors = PackedColorArray([dark, CardStyle.BACKGROUND])
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill_from = Vector2(0.1, 0.0)
	texture.fill_to = Vector2(0.9, 1.0)
	return texture


func _build_body() -> Control:
	if _card is DinoCardData:
		return _build_dino_body(_card as DinoCardData)
	var text_label := _label(_get_card_text(), 12, Color(0.85, 0.88, 0.95))
	text_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	return text_label


func _build_dino_body(dino: DinoCardData) -> Control:
	var body := VBoxContainer.new()
	body.add_theme_constant_override("separation", 4)
	body.alignment = BoxContainer.ALIGNMENT_CENTER

	for attack in dino.attacks:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 6)

		var pips := HBoxContainer.new()
		pips.add_theme_constant_override("separation", 2)
		for pip: String in attack.cost:
			var dot := Panel.new()
			dot.custom_minimum_size = Vector2(13, 13)
			var pip_type := CardCatalogTypes.type_from_string(pip)
			var pip_color: Color = (
				CardStyle.TYPE_COLORS[pip_type] if pip_type != -1 else Color("788196"))
			dot.add_theme_stylebox_override("panel", CardStyle.make_panel(pip_color, 7))
			pips.add_child(dot)
		row.add_child(pips)

		var attack_label := _label(attack.attack_name, 13, Color.WHITE)
		attack_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		attack_label.clip_text = true
		row.add_child(attack_label)
		row.add_child(_label(str(attack.damage), 16, Color.WHITE))
		body.add_child(row)

	if dino.description != "":
		var flavor := _label(dino.description, 9, CardStyle.TEXT_DIM)
		flavor.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		flavor.custom_minimum_size = Vector2(0, 0)
		flavor.max_lines_visible = 3
		body.add_child(flavor)
	return body


func _build_footer() -> Control:
	var footer := HBoxContainer.new()
	var info_text := ""
	match _card.kind:
		CardCatalogTypes.CardKind.DINO:
			var dino := _card as DinoCardData
			info_text = "Weak %s  ·  Res %s  ·  Retreat %d" % [
				CardStyle.type_display_name(dino.weakness),
				CardStyle.type_display_name(dino.resistance),
				dino.retreat_cost,
			]
		CardCatalogTypes.CardKind.TRAINER:
			var trainer := _card as TrainerCardData
			info_text = (
				"Spell — play any number" if trainer.trainer_kind == TrainerCardData.KIND_SPELL
				else "Support — one per turn")
		CardCatalogTypes.CardKind.FIELD:
			info_text = "Replaces your Environment"
		CardCatalogTypes.CardKind.INSTINCT:
			info_text = "Attach one per turn"

	var info := _label(info_text, 9, CardStyle.TEXT_DIM)
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.add_child(info)
	footer.add_child(_label(
		CardStyle.rarity_display_name(_card.rarity), 10, CardStyle.RARITY_COLORS[_card.rarity]))
	return footer


func _get_dino_type() -> int:
	if _card is DinoCardData:
		return (_card as DinoCardData).dino_type
	return (_card as InstinctCardData).dino_type


func _get_card_text() -> String:
	match _card.kind:
		CardCatalogTypes.CardKind.TRAINER:
			return (_card as TrainerCardData).text
		CardCatalogTypes.CardKind.FIELD:
			return (_card as FieldCardData).text
		CardCatalogTypes.CardKind.INSTINCT:
			return (_card as InstinctCardData).text
	return ""


func _label(text: String, size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	return label


func _badge(text: String, bg: Color, text_color: Color = Color.WHITE) -> PanelContainer:
	var badge := PanelContainer.new()
	badge.add_theme_stylebox_override("panel", CardStyle.make_panel(bg, 8))
	var label := _label(" %s " % text, 9, text_color)
	badge.add_child(label)
	return badge
