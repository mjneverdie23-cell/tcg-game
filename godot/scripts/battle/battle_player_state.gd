class_name BattlePlayerState
extends RefCounted
## One player's side of the battle: zones, points and per-turn flags.

var deck: Array[String] = []
var hand: Array[String] = []
var discard: Array[String] = []
var active: DinoInPlay = null
var bench: Array[DinoInPlay] = []
## Opposing dinosaurs this player has knocked out (3 wins the game).
var points: int = 0
## This player's Environment card id ("" until setup places one).
var environment_id: String = ""
## The element this player's auto-generated energy has (a DinoType).
var element: int = 0

# Per-turn flags, reset by the engine at turn start.
var energy_budget: int = 1  # energy units left to attach (Egg Incubator +1)
var support_played: bool = false
var retreated: bool = false
var damage_boost: int = 0  # from Adrenaline Gland, this turn only


func reset_turn_flags() -> void:
	energy_budget = 1
	support_played = false
	retreated = false
	damage_boost = 0


func draw(count: int = 1) -> int:
	var drawn := 0
	for _i in range(count):
		if deck.is_empty():
			break
		hand.append(deck.pop_front())
		drawn += 1
	return drawn


## Every dinosaur this player has in play, active first.
func dinos_in_play() -> Array[DinoInPlay]:
	var dinos: Array[DinoInPlay] = []
	if active != null:
		dinos.append(active)
	dinos.append_array(bench)
	return dinos


func has_basic_in_hand() -> bool:
	for id: String in hand:
		var card := GameData.get_card(id)
		if card is DinoCardData and (card as DinoCardData).stage == 1:
			return true
	return false


func has_environment_in_hand() -> bool:
	for id: String in hand:
		if GameData.get_card(id) is FieldCardData:
			return true
	return false
