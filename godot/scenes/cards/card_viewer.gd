class_name CardViewer
extends Control
## Full-screen card inspector: dimmed backdrop, enlarged card face, rarity
## and description below. Instanced (hidden) by any screen that shows cards;
## call open(card) to display.

const CARD_FACE_SCENE := preload("res://scenes/cards/card_face.tscn")
const VIEW_SCALE := 1.35


func _ready() -> void:
	# Hidden in the scene file too — a script error must never leave a
	# full-screen input-eating overlay behind.
	visible = false
	%Backdrop.gui_input.connect(_on_backdrop_input)
	%CloseButton.pressed.connect(close)


func open(card: CardData) -> void:
	for child in %CardHolder.get_children():
		child.queue_free()
	var face: CardFace = CARD_FACE_SCENE.instantiate()
	face.scale = Vector2(VIEW_SCALE, VIEW_SCALE)
	%CardHolder.custom_minimum_size = CardStyle.BASE_SIZE * VIEW_SCALE
	%CardHolder.add_child(face)
	face.show_card(card)

	%RarityLabel.text = CardStyle.rarity_display_name(card.rarity)
	%RarityLabel.add_theme_color_override("font_color", CardStyle.RARITY_COLORS[card.rarity])
	%DescriptionLabel.text = card.description if card is DinoCardData else ""
	%DescriptionLabel.visible = %DescriptionLabel.text != ""
	visible = true


func close() -> void:
	visible = false


func _on_backdrop_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		accept_event()  # don't let the click fall through to the grid
		close()
