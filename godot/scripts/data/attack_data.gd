class_name AttackData
extends RefCounted
## One attack on a dinosaur card.

var attack_name: String
## Energy pips: dino-type strings ("carnivore", …) or "neutral".
var cost: PackedStringArray
var damage: int


static func from_dict(data: Dictionary) -> AttackData:
	if not (data.has("name") and data.has("cost") and data.has("damage")):
		push_error("AttackData: missing fields in %s" % str(data))
		return null
	var attack := AttackData.new()
	attack.attack_name = data["name"]
	attack.cost = PackedStringArray(data["cost"])
	attack.damage = int(data["damage"])
	return attack
