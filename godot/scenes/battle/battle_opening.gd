class_name BattleOpening
extends Node
## The moments between pressing start and playing: the coin in the air, the
## hand arriving, and the first instruction waiting for both.
##
## Split out because it is the one part of the battle that is purely a
## sequence of beats. Getting the beats wrong is what made the opening
## confusing — a line telling the player what to do appeared while the coin
## was still spinning and was gone before the cards had stopped moving, so
## nobody read it. Here they are in order, in one place.

## The coin is away; deal the opening hand.
signal dismissed
## The cards have landed. The screen may start asking things of the player.
signal settled

## How long the staggered deal-in of a full hand takes to finish landing,
## plus its landing pop.
const SETTLE_SECONDS := 1.1

var _panel: Control
var _coin: CoinFlip
var _detail: Label
var _settled := false


func setup(panel: Control, coin: CoinFlip, detail: Label) -> void:
	_panel = panel
	_coin = coin
	_detail = detail
	coin.landed.connect(_on_landed)
	coin.finished.connect(_on_finished)


## Tosses for a battle. The coin lands on the face the engine's toss
## produced; the line underneath only says what it means, and only once it
## has landed, so the result is read off the coin and not spoiled by text.
func begin(called_heads: bool, going_first: bool) -> void:
	_settled = false
	_detail.text = (
		"Heads — you go first." if called_heads else "Tails — your rival goes first.")
	_detail.add_theme_color_override(
		"font_color", CardStyle.GOLD if going_first else Color("ff8a7a"))
	_detail.modulate.a = 0.0
	_panel.visible = true
	_coin.flip(called_heads)


## True once the coin is away and the hand has arrived.
func is_settled() -> bool:
	return _settled


func _on_landed() -> void:
	if Settings.reduced_motion:
		_detail.modulate.a = 1.0
		return
	_detail.create_tween().tween_property(_detail, "modulate:a", 1.0, 0.22)


func _on_finished() -> void:
	_panel.visible = false
	dismissed.emit()
	var settle := create_tween()
	settle.tween_interval(0.0 if Settings.reduced_motion else SETTLE_SECONDS)
	settle.tween_callback(func() -> void:
		_settled = true
		settled.emit())
