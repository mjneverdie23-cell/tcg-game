class_name TrainerCardData
extends CardData
## Trainer card. Spells are utility effects playable freely (from turn 1);
## Supports are stronger and limited to one per turn (from turn 2).
## `effect` is a structured dictionary (e.g. {"type": "heal", "amount": 30})
## interpreted by the battle engine — new trainer cards are added purely by
## editing JSON, never by editing code, as long as the effect type exists.

const KIND_SPELL := "spell"
const KIND_SUPPORT := "support"

## Effect types the battle engine implements (Milestone 5).
const KNOWN_EFFECTS: PackedStringArray = [
	"heal", "heal-all", "draw", "draw-to", "search-dino",
	"damage-boost", "switch", "bonus-energy",
]

var trainer_kind: String  # KIND_SPELL or KIND_SUPPORT
var text: String
var effect: Dictionary


static func from_dict(data: Dictionary) -> TrainerCardData:
	var card := TrainerCardData.new()
	if not card._parse_base(data, CardCatalogTypes.CardKind.TRAINER):
		return null
	card.trainer_kind = data.get("trainer_kind", "")
	if card.trainer_kind != KIND_SPELL and card.trainer_kind != KIND_SUPPORT:
		push_error("TrainerCardData %s: bad trainer_kind" % card.id)
		return null
	card.text = data.get("text", "")
	card.effect = data.get("effect", {})
	if not KNOWN_EFFECTS.has(str(card.effect.get("type", ""))):
		push_error("TrainerCardData %s: unknown effect '%s'" % [card.id, str(card.effect)])
		return null
	return card
