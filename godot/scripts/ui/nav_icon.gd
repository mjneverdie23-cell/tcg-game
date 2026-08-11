class_name NavIcon
extends Control
## The tab-bar glyphs, drawn rather than imported.
##
## Six icons at six sizes would mean twelve texture files to keep in sync
## with the palette; these are a few dozen draw calls that scale to any tab
## size and re-tint with the active colour for free.

const SHOP := "shop"
const BATTLE := "battle"
const COLLECTION := "collection"
const PACKS := "packs"
const SETTINGS := "settings"
const PROFILE := "profile"

## Which glyph to draw; one of the constants above.
var kind: String = BATTLE:
	set(value):
		kind = value
		queue_redraw()

var color: Color = MenuStyle.TEXT_DIM:
	set(value):
		color = value
		queue_redraw()


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(queue_redraw)


func _draw() -> void:
	# Every glyph is authored in a 0..1 box and scaled to the control, so a
	# tab can change size without touching the drawing code.
	var box := minf(size.x, size.y)
	var origin := (size - Vector2(box, box)) * 0.5
	var width := maxf(1.6, box * 0.075)
	match kind:
		SHOP:
			_draw_shop(origin, box, width)
		BATTLE:
			_draw_battle(origin, box, width)
		COLLECTION:
			_draw_collection(origin, box, width)
		PACKS:
			_draw_packs(origin, box, width)
		SETTINGS:
			_draw_settings(origin, box, width)
		PROFILE:
			_draw_profile(origin, box, width)


func _at(origin: Vector2, box: float, x: float, y: float) -> Vector2:
	return origin + Vector2(x * box, y * box)


## A stack of three coins, seen slightly from the side.
func _draw_shop(origin: Vector2, box: float, width: float) -> void:
	for i in range(3):
		var y := 0.72 - i * 0.2
		_draw_ellipse(_at(origin, box, 0.5, y), box * 0.34, box * 0.13, width)
	# The rim connecting the top and bottom coin, so it reads as a stack.
	draw_line(_at(origin, box, 0.16, 0.32), _at(origin, box, 0.16, 0.72), color, width)
	draw_line(_at(origin, box, 0.84, 0.32), _at(origin, box, 0.84, 0.72), color, width)


## Crossed swords.
func _draw_battle(origin: Vector2, box: float, width: float) -> void:
	for flip: float in [1.0, -1.0]:
		var tip := _at(origin, box, 0.5 + flip * 0.36, 0.14)
		var hilt := _at(origin, box, 0.5 - flip * 0.26, 0.86)
		draw_line(tip, hilt, color, width)
		# Cross-guard, perpendicular to the blade.
		var along := (hilt - tip).normalized()
		var across := Vector2(-along.y, along.x) * box * 0.13
		var guard := tip + along * box * 0.62
		draw_line(guard - across, guard + across, color, width)


## Four cards in a grid.
func _draw_collection(origin: Vector2, box: float, width: float) -> void:
	for column in range(2):
		for row in range(2):
			var top_left := _at(origin, box, 0.12 + column * 0.44, 0.1 + row * 0.46)
			draw_rect(Rect2(top_left, Vector2(box * 0.32, box * 0.34)), color, false, width)


## A booster pack: a pouch with a torn seal across the top.
func _draw_packs(origin: Vector2, box: float, width: float) -> void:
	draw_rect(Rect2(_at(origin, box, 0.22, 0.14),
		Vector2(box * 0.56, box * 0.72)), color, false, width)
	var zigzag := PackedVector2Array()
	for i in range(7):
		zigzag.append(_at(origin, box, 0.22 + i * 0.0933, 0.32 if i % 2 == 0 else 0.26))
	draw_polyline(zigzag, color, width)


## A gear: a ring with radial teeth.
func _draw_settings(origin: Vector2, box: float, width: float) -> void:
	var center := _at(origin, box, 0.5, 0.5)
	draw_arc(center, box * 0.24, 0.0, TAU, 32, color, width)
	for i in range(8):
		var angle := TAU * float(i) / 8.0
		var direction := Vector2(cos(angle), sin(angle))
		# Short, stubby teeth: long spokes read as a sun rather than a gear.
		draw_line(center + direction * box * 0.24, center + direction * box * 0.36,
			color, width * 1.6)


## Head and shoulders.
func _draw_profile(origin: Vector2, box: float, width: float) -> void:
	draw_arc(_at(origin, box, 0.5, 0.34), box * 0.19, 0.0, TAU, 24, color, width)
	draw_arc(_at(origin, box, 0.5, 0.94), box * 0.34, PI, TAU, 24, color, width)


func _draw_ellipse(center: Vector2, radius_x: float, radius_y: float, width: float) -> void:
	var points := PackedVector2Array()
	for i in range(25):
		var angle := TAU * float(i) / 24.0
		points.append(center + Vector2(cos(angle) * radius_x, sin(angle) * radius_y))
	draw_polyline(points, color, width)
