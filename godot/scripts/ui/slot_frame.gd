class_name SlotFrame
## The frame that marks a place on the table: a slot for a card, the
## footprint of a pile. One drawn outline shared by both, so every empty
## place on the board is marked the same way.
##
## Lives here rather than beside either user because both need it — the
## board's slots and the card piles — and a card component has no business
## depending on a battle one.

const SHADER := preload("res://scripts/ui/slot_frame.gdshader")
## Above the ground an Environment lays down, below the cards that stand on
## it: a placeholder is never buried by terrain and never covers a card.
const PRIORITY := -4


## A resting frame sized for `quad_size` (in table units). Animate it by
## tweening the shader's `lit` parameter between 0 and 1.
static func material(quad_size: Vector2) -> ShaderMaterial:
	var shader_material := ShaderMaterial.new()
	shader_material.shader = SHADER
	shader_material.render_priority = PRIORITY
	shader_material.set_shader_parameter("quad_size", quad_size)
	shader_material.set_shader_parameter("stroke_color", CardStyle.GOLD)
	shader_material.set_shader_parameter("lit", 0.0)
	return shader_material
