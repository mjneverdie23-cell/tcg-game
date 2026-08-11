class_name NavBar
extends PanelContainer
## The persistent bottom tab bar. Instanced into every top-level screen so
## navigation never disappears; the tab matching the screen it is sitting in
## lights up, and the rest route through SceneRouter.
##
## Tabs are built in code from TABS rather than laid out in the scene: the
## six of them are identical apart from three strings, and a data-driven bar
## can't drift out of sync with SceneRouter's screen names.

## screen name -> label + NavIcon kind, in bar order.
const TABS: Array = [
	{"screen": "shop", "label": "Shop", "icon": NavIcon.SHOP},
	{"screen": "main_menu", "label": "Battle", "icon": NavIcon.BATTLE},
	{"screen": "collection", "label": "Collection", "icon": NavIcon.COLLECTION},
	{"screen": "packs", "label": "Packs", "icon": NavIcon.PACKS},
	{"screen": "settings", "label": "Settings", "icon": NavIcon.SETTINGS},
	{"screen": "profile", "label": "Profile", "icon": NavIcon.PROFILE},
]

const ICON_SIZE := 30


func _ready() -> void:
	add_theme_stylebox_override("panel", _bar_style())
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 0)
	add_child(row)
	for tab: Dictionary in TABS:
		row.add_child(_build_tab(tab, str(tab["screen"]) == SceneRouter.current()))


func _bar_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color("070c1c")
	style.border_width_top = 1
	style.border_color = MenuStyle.EDGE
	style.corner_radius_top_left = 20
	style.corner_radius_top_right = 20
	style.content_margin_top = 8
	style.content_margin_bottom = 8
	style.content_margin_left = 6
	style.content_margin_right = 6
	return style


func _build_tab(tab: Dictionary, active: bool) -> Control:
	var button := Button.new()
	button.flat = true
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.custom_minimum_size = Vector2(0, MenuStyle.NAV_HEIGHT - 24)
	button.tooltip_text = str(tab["label"])
	button.focus_mode = Control.FOCUS_NONE
	if active:
		button.disabled = true  # already here; nothing to navigate to
	else:
		button.pressed.connect(SceneRouter.go_to.bind(str(tab["screen"])))

	var tint := MenuStyle.ACCENT if active else MenuStyle.TEXT_DIM
	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	column.add_theme_constant_override("separation", 4)
	button.add_child(column)
	# Buttons are not containers, so the column has to claim the button's
	# rect itself — only meaningful once it has that parent.
	column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

	# A lit strip along the top edge marks the tab you are standing on.
	var marker := ColorRect.new()
	marker.custom_minimum_size = Vector2(0, 3)
	marker.color = MenuStyle.ACCENT if active else Color(0, 0, 0, 0)
	marker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(marker)

	var icon := NavIcon.new()
	icon.kind = str(tab["icon"])
	icon.color = tint
	icon.custom_minimum_size = Vector2(ICON_SIZE, ICON_SIZE)
	icon.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	column.add_child(icon)

	var label := Label.new()
	label.text = str(tab["label"])
	label.add_theme_font_size_override("font_size", 12)
	label.add_theme_color_override("font_color", tint)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(label)
	return button
