class_name HeroEmblem
extends Control
## The home screen's hero: a flat theropod silhouette over a soft bloom,
## tinted with the type the player collects most of.
##
## Drawn rather than imported. The card icons are 64 px line art that turns to
## mush when blown up to hero size, and a silhouette this simple is cheaper to
## keep in the repo as 35 coordinates than as an image per type.

## Outline in a 1x1 design box, clockwise from the tip of the snout. The
## shape spans the full width and y SHAPE_TOP..SHAPE_BOTTOM.
const SHAPE: Array = [
	Vector2(0.020, 0.175), Vector2(0.120, 0.115), Vector2(0.180, 0.085),
	Vector2(0.250, 0.115), Vector2(0.270, 0.205), Vector2(0.340, 0.245),
	Vector2(0.440, 0.295), Vector2(0.560, 0.285), Vector2(0.680, 0.315),
	Vector2(0.800, 0.345), Vector2(1.000, 0.440), Vector2(0.860, 0.445),
	Vector2(0.750, 0.465), Vector2(0.780, 0.610), Vector2(0.740, 0.760),
	Vector2(0.800, 0.900), Vector2(0.820, 0.960), Vector2(0.670, 0.960),
	Vector2(0.690, 0.850), Vector2(0.670, 0.690), Vector2(0.630, 0.570),
	Vector2(0.590, 0.690), Vector2(0.540, 0.850), Vector2(0.580, 0.960),
	Vector2(0.420, 0.960), Vector2(0.460, 0.840), Vector2(0.500, 0.670),
	Vector2(0.430, 0.530), Vector2(0.360, 0.470), Vector2(0.310, 0.560),
	Vector2(0.300, 0.475), Vector2(0.280, 0.375), Vector2(0.220, 0.285),
	Vector2(0.130, 0.245), Vector2(0.020, 0.215),
]
const SHAPE_TOP := 0.085
const SHAPE_BOTTOM := 0.960
const EYE := Vector2(0.165, 0.155)
const EYE_RADIUS := 0.019
## Concentric passes behind the silhouette; more passes = softer bloom.
const GLOW_RINGS := 12

var dino_type: int = CardCatalogTypes.DinoType.CARNIVORE:
	set(value):
		dino_type = value
		queue_redraw()


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(queue_redraw)


func _draw() -> void:
	var span := SHAPE_BOTTOM - SHAPE_TOP
	var unit := minf(size.x, size.y / span)
	if unit <= 0.0:
		return
	var origin := (size - Vector2(unit, unit * span)) * 0.5
	var color: Color = CardStyle.TYPE_COLORS[dino_type]

	# Bloom: overlapping translucent discs, which sum to a radial falloff.
	var center := origin + Vector2(0.5, 0.45 - SHAPE_TOP) * unit
	for i in range(GLOW_RINGS):
		var radius := unit * 0.62 * (1.0 - float(i) / float(GLOW_RINGS))
		draw_circle(center, radius, Color(color.r, color.g, color.b, 0.035))

	var points := PackedVector2Array()
	for point: Vector2 in SHAPE:
		points.append(origin + Vector2(point.x, point.y - SHAPE_TOP) * unit)
	draw_colored_polygon(points, color)
	draw_circle(origin + Vector2(EYE.x, EYE.y - SHAPE_TOP) * unit,
		EYE_RADIUS * unit, MenuStyle.BG_BOTTOM)
