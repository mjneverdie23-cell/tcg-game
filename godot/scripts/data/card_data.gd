class_name CardData
extends RefCounted
## Base class for every card. Concrete kinds: DinoCardData, TrainerCardData,
## FieldCardData, InstinctCardData. Cards are immutable data parsed from
## database/cards.json — battle state lives elsewhere.

var id: String
var display_name: String
var kind: int  # CardCatalogTypes.CardKind
var rarity: int  # CardCatalogTypes.Rarity


## Populates base fields from JSON; returns false (with an error) on bad data.
func _parse_base(data: Dictionary, expected_kind: int) -> bool:
	if not (data.has("id") and data.has("name") and data.has("rarity")):
		push_error("CardData: missing id/name/rarity in %s" % str(data))
		return false
	id = data["id"]
	display_name = data["name"]
	kind = expected_kind
	rarity = CardCatalogTypes.rarity_from_string(data["rarity"])
	if rarity == -1:
		push_error("CardData %s: unknown rarity '%s'" % [id, data["rarity"]])
		return false
	return true
