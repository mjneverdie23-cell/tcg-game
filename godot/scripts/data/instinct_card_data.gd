class_name InstinctCardData
extends CardData
## Instinct (energy) card. One per dinosaur type; attached to power attacks.

var dino_type: int  # CardCatalogTypes.DinoType
var text: String


static func from_dict(data: Dictionary) -> InstinctCardData:
	var card := InstinctCardData.new()
	if not card._parse_base(data, CardCatalogTypes.CardKind.INSTINCT):
		return null
	card.dino_type = CardCatalogTypes.type_from_string(data.get("type", ""))
	if card.dino_type == -1:
		push_error("InstinctCardData %s: unknown type" % card.id)
		return null
	card.text = data.get("text", "")
	return card
