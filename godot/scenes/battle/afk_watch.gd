class_name AfkWatch
extends Node
## Watches for a player who has stopped playing, and eventually takes their
## turn away.
##
## Nothing appears while someone is thinking: a battle where a clock starts
## ticking the moment your turn does is a battle you cannot take your time
## over. Only after GRACE_SECONDS of no input at all does the countdown
## appear, and it then gives another COUNTDOWN_SECONDS — visibly, in the
## corner — before the turn is skipped. Any input at all takes it away
## again and puts the whole wait back to the start.
##
## "Input" means literally any event: a mouse move over the board counts.
## Somebody reading their cards is not away.

## The turn was left to run out.
signal expired

## Silence before the countdown even appears.
const GRACE_SECONDS := 67.0
## How long the countdown then runs for.
const COUNTDOWN_SECONDS := 45.0

var _clock: TurnClock
## Seconds since the last input, or since this player's turn began.
var _idle := 0.0
## False whenever it is not this player's turn, or the battle is not running.
var _active := false


func setup(clock: TurnClock) -> void:
	_clock = clock


## Called whenever the turn or the state of the battle changes. Becoming
## active restarts the wait, so a turn always begins with a full clock.
func set_active(active: bool) -> void:
	if active == _active:
		return
	_active = active
	_idle = 0.0
	if not active:
		_clock.hide_countdown()


func _input(_event: InputEvent) -> void:
	# Any sign of life at all, whatever it was.
	_idle = 0.0
	if _clock.visible:
		_clock.hide_countdown()


func _process(delta: float) -> void:
	if not _active:
		return
	_idle += delta
	if _idle < GRACE_SECONDS:
		return
	var left := GRACE_SECONDS + COUNTDOWN_SECONDS - _idle
	if left <= 0.0:
		_active = false  # one skip per absence, not one per frame
		_idle = 0.0
		_clock.hide_countdown()
		expired.emit()
		return
	_clock.show_countdown(left, COUNTDOWN_SECONDS)
