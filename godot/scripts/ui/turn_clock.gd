class_name TurnClock
extends Control
## The countdown that appears when a player has stopped playing: a dial that
## empties as their remaining time runs out, with the seconds in the middle.
##
## Drawn rather than themed, like everything else here, which is what lets
## the ring change colour as it drains without needing four of anything.
## It knows nothing about turns or players — it is given a number of seconds
## and how many it started from, and draws that.

const RING_WIDTH := 7.0
## Under this many seconds the dial turns red and starts to pulse.
const URGENT_SECONDS := 10.0
const CALM := Color("f5b942")
const URGENT := Color("ff6a58")

## Seconds left, and what the countdown began at.
var remaining := 0.0
var total := 1.0

## Grows and shrinks while the countdown is urgent, so the corner of the
## screen catches the eye of somebody who has looked away.
var _pulse := 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(78, 78)
	visible = false
	set_process(false)


func show_countdown(seconds_left: float, seconds_total: float) -> void:
	remaining = maxf(0.0, seconds_left)
	total = maxf(0.001, seconds_total)
	visible = true
	set_process(not Settings.reduced_motion)
	queue_redraw()


func hide_countdown() -> void:
	visible = false
	set_process(false)
	_pulse = 0.0


func _process(delta: float) -> void:
	if remaining > URGENT_SECONDS:
		_pulse = 0.0
		return
	_pulse += delta * 6.0
	queue_redraw()


func _draw() -> void:
	var centre := size * 0.5
	var urgent := remaining <= URGENT_SECONDS
	var beat := 1.0 + (sin(_pulse) * 0.05 if urgent else 0.0)
	var radius := (minf(size.x, size.y) * 0.5 - RING_WIDTH) * beat
	var color := URGENT if urgent else CALM

	draw_circle(centre, radius + RING_WIDTH * 0.5, Color(0.02, 0.03, 0.07, 0.85))
	draw_arc(centre, radius, 0.0, TAU, 48, Color(color, 0.18), RING_WIDTH, true)
	# The remaining arc runs clockwise from noon, so it empties the way a
	# clock face does rather than filling up.
	var swept := TAU * clampf(remaining / total, 0.0, 1.0)
	if swept > 0.0:
		draw_arc(centre, radius, -PI * 0.5, -PI * 0.5 + swept, 48, color, RING_WIDTH, true)

	var font := ThemeDB.fallback_font
	var label := "%d" % ceili(remaining)
	var font_size := int(radius * 0.95)
	var extent := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
	draw_string(font, centre + Vector2(-extent.x * 0.5, extent.y * 0.34),
		label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)
