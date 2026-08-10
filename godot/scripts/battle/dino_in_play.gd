class_name DinoInPlay
extends RefCounted
## One dinosaur on the battlefield (active or benched): the card it embodies
## plus battle-only state. Damage is stored as counters taken, so healing is
## just reducing it; max HP can shift with field effects.

var card_id: String
var damage: int = 0
## Energy units attached to this dinosaur (all of the owner's element).
var energy: int = 0
## Active-position conditions: "poisoned", "asleep", "paralyzed".
var statuses: Array[String] = []
## Turn number this dinosaur entered play (or evolved) — evolution needs one
## full turn in play first.
var turn_entered: int = 0


func _init(id: String, entered: int) -> void:
	card_id = id
	turn_entered = entered


func card() -> DinoCardData:
	return GameData.get_card(card_id) as DinoCardData


func has_status(status: String) -> bool:
	return statuses.has(status)


func add_status(status: String) -> void:
	if not statuses.has(status):
		statuses.append(status)


func clear_statuses() -> void:
	statuses.clear()


