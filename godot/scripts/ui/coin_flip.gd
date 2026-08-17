class_name CoinFlip
extends Control
## The opening coin, tossed. Spins edge-on through the air, slows, and comes
## down on the face that decided who goes first.
##
## Drawn rather than animated from sprites: a coin seen face-on is a circle
## squashed horizontally by the cosine of its spin, which is one line of
## maths and stays crisp at any size. The spin always ends on a half-turn
## boundary, and the number of half-turns is chosen so the face it lands on
## is the one the toss actually produced — the animation cannot disagree
## with the result.

## The coin has come down; the caller can now say what it means.
signal landed
## The whole toss is over, hold included.
signal finished

const RADIUS := 62.0
## Half-turns of spin. More than this and the toss outstays its welcome.
const HALF_TURNS := 7
const SPIN_TIME := 1.15
## How high the coin rises at the top of its arc.
const ARC_HEIGHT := 58.0
## Beat between the coin landing and the toss being over.
const HOLD_TIME := 0.9
## Edge-on the coin is a line; this keeps it from vanishing completely.
const MIN_SQUASH := 0.05

const HEADS_FACE := Color("f5b942")
const TAILS_FACE := Color("9fb0d4")

## Radians of spin so far. Half-turn boundaries are where a face is level.
var _spin := 0.0
## Rise and fall, in pixels above the resting position.
var _lift := 0.0
## Which face the toss produced. The coin starts showing heads, so it must
## land on an even number of half-turns to show heads again.
var _heads := true


func _ready() -> void:
	custom_minimum_size = Vector2(RADIUS * 2.4, RADIUS * 2.4)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


## Tosses the coin and comes down on `heads`.
func flip(heads: bool) -> void:
	_heads = heads
	_spin = 0.0
	_lift = 0.0
	queue_redraw()
	# Land level: an even count of half-turns shows the face it started on.
	var half_turns := HALF_TURNS + (1 if (HALF_TURNS % 2 == 1) == heads else 0)
	if Settings.reduced_motion:
		_spin = PI * half_turns
		queue_redraw()
		landed.emit()
		var wait := create_tween()
		wait.tween_interval(HOLD_TIME)
		wait.tween_callback(finished.emit)
		return

	var tween := create_tween()
	tween.tween_method(_set_spin, 0.0, PI * half_turns, SPIN_TIME) \
		.set_trans(Tween.TRANS_QUART).set_ease(Tween.EASE_OUT)
	# The arc is its own curve: up fast, down slower, landing with the spin.
	var arc := create_tween()
	arc.tween_method(_set_lift, 0.0, ARC_HEIGHT, SPIN_TIME * 0.4) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	arc.tween_method(_set_lift, ARC_HEIGHT, 0.0, SPIN_TIME * 0.6) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	arc.tween_callback(landed.emit)
	arc.tween_interval(HOLD_TIME)
	arc.tween_callback(finished.emit)


func _set_spin(value: float) -> void:
	_spin = value
	queue_redraw()


func _set_lift(value: float) -> void:
	_lift = value
	queue_redraw()


## The face showing right now: it swaps every half-turn, starting on heads.
func _showing_heads() -> bool:
	return int(floori(_spin / PI)) % 2 == 0


func _draw() -> void:
	var centre := size * 0.5 - Vector2(0, _lift)
	var squash := maxf(absf(cos(_spin)), MIN_SQUASH)
	# Everything below is drawn around the origin; the transform puts it in
	# place and squashes it, so the glyph narrows with the coin for free.
	draw_set_transform(centre, 0.0, Vector2(squash, 1.0))
	var face := HEADS_FACE if _showing_heads() else TAILS_FACE

	draw_circle(Vector2.ZERO, RADIUS, face.darkened(0.45))       # rim
	draw_circle(Vector2.ZERO, RADIUS - 5.0, face)                # body
	draw_circle(Vector2.ZERO, RADIUS - 5.0, face.lightened(0.25))
	draw_arc(Vector2.ZERO, RADIUS - 12.0, 0.0, TAU, 40, face.darkened(0.35), 3.0, true)
	# A dinosaur's claw for heads, a bone for tails: this game's two faces.
	if _showing_heads():
		_draw_claw(face.darkened(0.55))
	else:
		_draw_bone(face.darkened(0.5))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


## Three tapering strokes curving to a point, read as a claw.
func _draw_claw(color: Color) -> void:
	for i in range(3):
		var lean := (i - 1) * 0.42
		var points := PackedVector2Array()
		for step in range(7):
			var t := float(step) / 6.0
			# A quadratic bend: straight at the base, hooked at the tip.
			points.append(Vector2(
				lean * 26.0 + t * t * 16.0 * signf(lean if lean != 0.0 else 1.0),
				-30.0 + t * 62.0))
		draw_polyline(points, color, 7.0 - i * 0.5, true)


## A long bone with a knuckle at each end.
func _draw_bone(color: Color) -> void:
	draw_line(Vector2(-26, 18), Vector2(26, -18), color, 12.0, true)
	for end in [Vector2(-26, 18), Vector2(26, -18)]:
		var across := Vector2(-0.5, -0.87) * 11.0
		draw_circle(end + across, 10.0, color)
		draw_circle(end - across, 10.0, color)
