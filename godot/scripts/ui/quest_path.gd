class_name QuestPath
extends Control
## The quest-match chain on the home screen: circular nodes wired together by
## a winding trail. Nodes are laid out as fractions of the control, so the
## path reflows with the panel instead of being pinned to pixel positions.
##
## A node reads its state at a glance: locked is grey with a padlock, the
## next match is gold, a beaten match with its reward still waiting pulses,
## and a claimed one is a green tick.

signal quest_pressed(index: int)

const NODE_RADIUS := 34.0
## Node centres in 0..1 space, in chain order — a descending zig-zag.
const LAYOUT: Array = [
	Vector2(0.22, 0.12),
	Vector2(0.62, 0.36),
	Vector2(0.18, 0.62),
	Vector2(0.56, 0.88),
]

var _buttons: Array[Button] = []


func _ready() -> void:
	custom_minimum_size = Vector2(250, 380)
	for i in range(QuestRules.count()):
		var button := Button.new()
		button.flat = true
		button.focus_mode = Control.FOCUS_NONE
		button.size = Vector2(NODE_RADIUS * 2.0, NODE_RADIUS * 2.0)
		button.pressed.connect(quest_pressed.emit.bind(i))
		add_child(button)
		_buttons.append(button)
	resized.connect(_layout_nodes)
	_layout_nodes()
	refresh()


## Re-reads quest state: node colours, tooltips and which nodes are clickable.
func refresh() -> void:
	for i in range(_buttons.size()):
		var quest := QuestRules.quest(i)
		var state := QuestRules.state_of(i)
		var button := _buttons[i]
		button.disabled = state == QuestRules.STATE_LOCKED \
			or state == QuestRules.STATE_CLAIMED
		button.tooltip_text = "%d. %s\n%s\nReward: %d coins\n%s" % [
			i + 1, str(quest["title"]), str(quest["detail"]),
			int(quest["reward"]), _state_hint(state)]
	queue_redraw()


func _state_hint(state: String) -> String:
	match state:
		QuestRules.STATE_CLAIMED:
			return "Beaten and claimed."
		QuestRules.STATE_WON:
			return "Beaten — click to claim the reward."
		QuestRules.STATE_READY:
			return "Click to play this match."
		_:
			return "Locked until you win the match before it."


func _layout_nodes() -> void:
	for i in range(_buttons.size()):
		_buttons[i].position = _center_of(i) - Vector2(NODE_RADIUS, NODE_RADIUS)


func _center_of(index: int) -> Vector2:
	var fraction: Vector2 = LAYOUT[index]
	# Keep whole nodes inside the control at any panel size.
	return Vector2(
		lerpf(NODE_RADIUS, size.x - NODE_RADIUS, fraction.x),
		lerpf(NODE_RADIUS, size.y - NODE_RADIUS, fraction.y))


func _draw() -> void:
	for i in range(QuestRules.count() - 1):
		_draw_trail(_center_of(i), _center_of(i + 1), QuestRules.is_won(i))
	for i in range(QuestRules.count()):
		_draw_node(i)


## A soft S-curve between two nodes, dashed while the leg is still ahead of
## the player and solid once the quest behind it has been claimed.
func _draw_trail(from: Vector2, to: Vector2, walked: bool) -> void:
	var span := to - from
	var start := from + span.normalized() * NODE_RADIUS
	var end := to - span.normalized() * NODE_RADIUS
	var sway := Vector2(-span.y, span.x).normalized() * span.length() * 0.22
	var color := MenuStyle.ACCENT if walked else MenuStyle.EDGE
	var points := PackedVector2Array()
	for i in range(17):
		var t := float(i) / 16.0
		points.append(start.bezier_interpolate(
			start + sway, end - sway, end, t))
	if walked:
		draw_polyline(points, color, 3.0, true)
		return
	# Dashed: draw every other segment of the same curve.
	for i in range(0, points.size() - 1, 2):
		draw_line(points[i], points[i + 1], color, 3.0, true)


func _draw_node(index: int) -> void:
	var center := _center_of(index)
	var state := QuestRules.state_of(index)
	var rim := MenuStyle.EDGE
	var fill := MenuStyle.PANEL
	match state:
		QuestRules.STATE_READY:
			rim = MenuStyle.ACCENT
			fill = MenuStyle.ACCENT_DEEP
		QuestRules.STATE_WON:
			rim = MenuStyle.ACCENT
			fill = MenuStyle.PANEL_SOFT
		QuestRules.STATE_CLAIMED:
			rim = MenuStyle.SUCCESS
			fill = MenuStyle.PANEL_SOFT
	draw_circle(center, NODE_RADIUS, fill)
	draw_arc(center, NODE_RADIUS, 0.0, TAU, 40, rim, 3.0, true)

	if state == QuestRules.STATE_CLAIMED:
		_draw_check(center, MenuStyle.SUCCESS)
		return
	if state == QuestRules.STATE_LOCKED:
		_draw_lock(center)
		return
	# Playable or waiting to be claimed: the match number, with a second ring
	# on a reward that has not been collected yet.
	if state == QuestRules.STATE_WON:
		draw_arc(center, NODE_RADIUS - 7.0, 0.0, TAU, 40, MenuStyle.ACCENT, 2.0, true)
	var font := ThemeDB.fallback_font
	var text := str(index + 1)
	var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 22).x
	draw_string(font, center + Vector2(-width * 0.5, 8.0), text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 22, MenuStyle.TEXT)


## Padlock body and shackle for a match that is not open yet.
func _draw_lock(center: Vector2) -> void:
	draw_rect(Rect2(center + Vector2(-9, -2), Vector2(18, 14)), MenuStyle.TEXT_DIM)
	draw_arc(center + Vector2(0, -2), 6.0, PI, TAU, 16, MenuStyle.TEXT_DIM, 3.0, true)


func _draw_check(center: Vector2, color: Color) -> void:
	draw_polyline(PackedVector2Array([
		center + Vector2(-13, 0),
		center + Vector2(-4, 10),
		center + Vector2(14, -11),
	]), color, 4.0, true)
