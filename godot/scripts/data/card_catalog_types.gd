class_name CardCatalogTypes
## Shared enums and string mappings for the card system.
##
## JSON stores types/rarities as lowercase strings; gameplay code uses these
## enums. The class match-up wheel (X beats Y => Y is weak to X, X resists Y):
##   carnivore -> herbivore -> amphibian -> pterosaur -> carnivore

enum DinoType { CARNIVORE, HERBIVORE, PTEROSAUR, AMPHIBIAN }
enum Rarity { COMMON, RARE, EPIC, LEGENDARY, MYTHIC }
enum CardKind { DINO, TRAINER, FIELD, INSTINCT }

const TYPE_NAMES: Dictionary = {
	DinoType.CARNIVORE: "carnivore",
	DinoType.HERBIVORE: "herbivore",
	DinoType.PTEROSAUR: "pterosaur",
	DinoType.AMPHIBIAN: "amphibian",
}

const RARITY_NAMES: Dictionary = {
	Rarity.COMMON: "common",
	Rarity.RARE: "rare",
	Rarity.EPIC: "epic",
	Rarity.LEGENDARY: "legendary",
	Rarity.MYTHIC: "mythic",
}

## X beats Y — used to derive weakness/resistance and by field/AI logic.
const CLASS_WHEEL: Dictionary = {
	DinoType.CARNIVORE: DinoType.HERBIVORE,
	DinoType.HERBIVORE: DinoType.AMPHIBIAN,
	DinoType.AMPHIBIAN: DinoType.PTEROSAUR,
	DinoType.PTEROSAUR: DinoType.CARNIVORE,
}


static func type_from_string(value: String) -> int:
	for type_id: int in TYPE_NAMES:
		if TYPE_NAMES[type_id] == value:
			return type_id
	return -1


static func rarity_from_string(value: String) -> int:
	for rarity_id: int in RARITY_NAMES:
		if RARITY_NAMES[rarity_id] == value:
			return rarity_id
	return -1


## The type that beats `dino_type` (its weakness).
static func weakness_of(dino_type: int) -> int:
	for predator: int in CLASS_WHEEL:
		if CLASS_WHEEL[predator] == dino_type:
			return predator
	return -1


## The type `dino_type` beats (its resistance).
static func resistance_of(dino_type: int) -> int:
	return CLASS_WHEEL[dino_type]
