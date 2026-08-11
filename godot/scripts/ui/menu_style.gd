class_name MenuStyle
## Visual language for the menu shell — the home screen, the bottom tab bar
## and the tab screens behind it. CardStyle owns how a *card* looks; this
## owns how the app around the cards looks, so the two never fight over the
## same constants.

## Backdrop gradient, top to bottom.
const BG_TOP := Color("101a3a")
const BG_BOTTOM := Color("04060f")

const PANEL := Color("111a33")
const PANEL_SOFT := Color("18244a")
const EDGE := Color("2b3a63")
const ACCENT := Color("f5b942")
const ACCENT_DEEP := Color("b57d16")
const DANGER := Color("ff6a58")
const SUCCESS := Color("43d96b")
const TEXT := Color("eef2ff")
const TEXT_DIM := Color("8b95ad")

## Height reserved at the bottom of every tab screen for the nav bar.
const NAV_HEIGHT := 88
## Screens must keep their content clear of the bar by this much.
const NAV_CLEARANCE := NAV_HEIGHT + 16


## Full-screen backdrop gradient, as a texture a TextureRect can stretch.
static func backdrop_texture() -> GradientTexture2D:
	var gradient := Gradient.new()
	gradient.set_color(0, BG_TOP)
	gradient.set_color(1, BG_BOTTOM)
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill_from = Vector2(0.5, 0.0)
	texture.fill_to = Vector2(0.5, 1.0)
	texture.width = 8  # stretched by the TextureRect; only the ramp matters
	texture.height = 256
	return texture


## Standard content panel: soft fill, hairline edge, generous padding.
static func panel(corner: int = 18, padding: int = 16,
		fill: Color = PANEL, border: Color = EDGE) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.set_corner_radius_all(corner)
	style.set_border_width_all(1)
	style.border_color = border
	style.content_margin_left = padding
	style.content_margin_right = padding
	style.content_margin_top = padding
	style.content_margin_bottom = padding
	return style


## Applies the menu button look. `primary` is the single call-to-action on a
## screen (gold, filled); everything else is a quiet outlined button.
static func style_button(button: Button, primary: bool = false) -> void:
	var fill := ACCENT if primary else PANEL_SOFT
	var text_color := Color("1a1205") if primary else TEXT
	button.add_theme_stylebox_override("normal", panel(14, 12, fill, EDGE))
	button.add_theme_stylebox_override(
		"hover", panel(14, 12, fill.lightened(0.12), ACCENT))
	button.add_theme_stylebox_override(
		"pressed", panel(14, 12, fill.darkened(0.18), ACCENT))
	button.add_theme_stylebox_override(
		"focus", panel(14, 12, Color(0, 0, 0, 0), ACCENT))
	button.add_theme_stylebox_override(
		"disabled", panel(14, 12, PANEL, EDGE))
	button.add_theme_color_override("font_color", text_color)
	button.add_theme_color_override("font_hover_color", text_color)
	button.add_theme_color_override("font_pressed_color", text_color)
	button.add_theme_color_override("font_disabled_color", TEXT_DIM)
	if primary:
		button.add_theme_font_size_override("font_size", 20)


## Pill used for the coin / trophy readouts.
static func style_pill(panel_container: PanelContainer) -> void:
	panel_container.add_theme_stylebox_override(
		"panel", panel(22, 10, PANEL_SOFT, EDGE))


static func heading(text: String, size: int = 13) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", TEXT_DIM)
	return label
