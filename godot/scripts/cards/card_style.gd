class_name CardStyle
## Shared visual constants for card rendering: type colors, rarity colors,
## art-fallback gradients and sizing. Used by CardFace, the collection grid,
## the viewer and (later) the 3D battle cards.

## Card faces are designed at this size and scaled where needed.
const BASE_SIZE := Vector2(250, 350)

const TYPE_COLORS: Dictionary = {
	CardCatalogTypes.DinoType.CARNIVORE: Color("ff5a48"),
	CardCatalogTypes.DinoType.HERBIVORE: Color("43d96b"),
	CardCatalogTypes.DinoType.PTEROSAUR: Color("b18aff"),
	CardCatalogTypes.DinoType.AMPHIBIAN: Color("38a8ff"),
}

## Dark backdrop for each type's art area (fallback when no image exists).
const TYPE_ART_DARK: Dictionary = {
	CardCatalogTypes.DinoType.CARNIVORE: Color("4a1210"),
	CardCatalogTypes.DinoType.HERBIVORE: Color("123c1e"),
	CardCatalogTypes.DinoType.PTEROSAUR: Color("2c2158"),
	CardCatalogTypes.DinoType.AMPHIBIAN: Color("0c2f4a"),
}

const RARITY_COLORS: Dictionary = {
	CardCatalogTypes.Rarity.COMMON: Color("9aa4b8"),
	CardCatalogTypes.Rarity.RARE: Color("3fa7ff"),
	CardCatalogTypes.Rarity.EPIC: Color("b45cff"),
	CardCatalogTypes.Rarity.LEGENDARY: Color("ffb938"),
	CardCatalogTypes.Rarity.MYTHIC: Color("ff4fa0"),
}

## Sort weight, mythic first.
const RARITY_ORDER: Dictionary = {
	CardCatalogTypes.Rarity.MYTHIC: 0,
	CardCatalogTypes.Rarity.LEGENDARY: 1,
	CardCatalogTypes.Rarity.EPIC: 2,
	CardCatalogTypes.Rarity.RARE: 3,
	CardCatalogTypes.Rarity.COMMON: 4,
}

const BACKGROUND := Color("060913")
const SURFACE := Color("0e1730")
const SURFACE_LIGHT := Color("1a2547")
const TEXT_DIM := Color("8b95ad")
const GOLD := Color("f5b942")

const TYPE_ICONS: Dictionary = {
	CardCatalogTypes.DinoType.CARNIVORE: "res://assets/textures/icons/carnivore.svg",
	CardCatalogTypes.DinoType.HERBIVORE: "res://assets/textures/icons/herbivore.svg",
	CardCatalogTypes.DinoType.PTEROSAUR: "res://assets/textures/icons/pterosaur.svg",
	CardCatalogTypes.DinoType.AMPHIBIAN: "res://assets/textures/icons/amphibian.svg",
}


## Filter choices shared by the collection screen and the deck builder.
const KIND_FILTERS: Array = [
	"all", "carnivore", "herbivore", "pterosaur", "amphibian",
	"supports", "spells", "environments",
]


static func matches_kind(card: CardData, choice: String) -> bool:
	match choice:
		"all":
			return true
		"supports":
			return (card is TrainerCardData
				and (card as TrainerCardData).trainer_kind == TrainerCardData.KIND_SUPPORT)
		"spells":
			return (card is TrainerCardData
				and (card as TrainerCardData).trainer_kind == TrainerCardData.KIND_SPELL)
		"environments":
			return card.kind == CardCatalogTypes.CardKind.FIELD
		_:
			var type_id := CardCatalogTypes.type_from_string(choice)
			return card is DinoCardData and (card as DinoCardData).dino_type == type_id


static func type_icon(dino_type: int) -> Texture2D:
	return load(TYPE_ICONS[dino_type])


static func type_display_name(dino_type: int) -> String:
	return String(CardCatalogTypes.TYPE_NAMES[dino_type]).capitalize()


static func rarity_display_name(rarity: int) -> String:
	return String(CardCatalogTypes.RARITY_NAMES[rarity]).capitalize()


## Rounded panel used for card frames and badges.
static func make_panel(bg: Color, corner: int = 10, border: Color = Color.TRANSPARENT,
		border_width: int = 0) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.set_corner_radius_all(corner)
	if border_width > 0:
		style.set_border_width_all(border_width)
		style.border_color = border
	return style
