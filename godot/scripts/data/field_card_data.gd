class_name FieldCardData
extends CardData
## Environment card. Each player keeps their own Environment on their side
## of the battlefield (placed during setup, replaceable in later turns).
## Its passive `buff` applies to the owner's Active Dinosaur only while that
## dinosaur's type matches the Environment's type.

## Buff types the battle engine implements.
const KNOWN_BUFFS: PackedStringArray = [
	"hp-bonus", "damage-bonus", "heal-per-turn", "free-retreat",
]

var dino_type: int  # CardCatalogTypes.DinoType this Environment empowers
var text: String
var buff: Dictionary  # {"type": String, "amount": int}


static func from_dict(data: Dictionary) -> FieldCardData:
	var card := FieldCardData.new()
	if not card._parse_base(data, CardCatalogTypes.CardKind.FIELD):
		return null
	card.dino_type = CardCatalogTypes.type_from_string(data.get("type", ""))
	if card.dino_type == -1:
		push_error("FieldCardData %s: unknown type '%s'" % [card.id, data.get("type", "")])
		return null
	card.text = data.get("text", "")
	card.buff = data.get("buff", {})
	if not KNOWN_BUFFS.has(str(card.buff.get("type", ""))):
		push_error("FieldCardData %s: unknown buff '%s'" % [card.id, str(card.buff)])
		return null
	return card
