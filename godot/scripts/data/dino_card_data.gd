class_name DinoCardData
extends CardData
## A dinosaur card: the creature identity plus its battle stats.

var dino_type: int  # CardCatalogTypes.DinoType
var hp: int
## 1 = basic (playable from hand), 2+ = evolution stages.
var stage: int
## Card id of the previous stage; "" for basic dinosaurs.
var evolves_from: String
var attacks: Array[AttackData]
var weakness: int  # CardCatalogTypes.DinoType
var resistance: int  # CardCatalogTypes.DinoType
var retreat_cost: int
var description: String
## Path under res://assets/textures/cards/, "" if art is unavailable.
var image: String
## Optional res:// path to a 3D model (.glb / .gltf / .tscn) shown standing
## on the card in battle. "" — the default for every card in the catalog —
## means the card renders as a flat face. See assets/models/README.md.
var model: String
## Uniform scale applied to that model, so a single asset can be reused at
## the size the card slot needs.
var model_scale: float


static func from_dict(data: Dictionary) -> DinoCardData:
	var card := DinoCardData.new()
	if not card._parse_base(data, CardCatalogTypes.CardKind.DINO):
		return null
	card.dino_type = CardCatalogTypes.type_from_string(data.get("type", ""))
	if card.dino_type == -1:
		push_error("DinoCardData %s: unknown type '%s'" % [card.id, data.get("type", "")])
		return null
	card.hp = int(data.get("hp", 0))
	if card.hp <= 0:
		push_error("DinoCardData %s: invalid hp" % card.id)
		return null
	card.stage = int(data.get("stage", 1))
	card.evolves_from = data.get("evolves_from", "")
	card.weakness = CardCatalogTypes.weakness_of(card.dino_type)
	card.resistance = CardCatalogTypes.resistance_of(card.dino_type)
	card.retreat_cost = int(data.get("retreat_cost", 1))
	card.description = data.get("description", "")
	card.image = data.get("image", "")
	card.model = data.get("model", "")
	card.model_scale = maxf(0.001, float(data.get("model_scale", 1.0)))
	for attack_dict: Dictionary in data.get("attacks", []):
		var attack := AttackData.from_dict(attack_dict)
		if attack == null:
			return null
		card.attacks.append(attack)
	if card.attacks.is_empty():
		push_error("DinoCardData %s: needs at least one attack" % card.id)
		return null
	return card
