class_name PackRules
## Pack definitions and opening logic. Openings roll a rarity per slot, then
## draw a card of that rarity with duplicate protection: no repeats within a
## pack, and unowned cards are strongly preferred over duplicates.

const CARDS_PER_PACK := 5

const RARITY_NAMES_ORDERED: PackedStringArray = [
	"common", "rare", "epic", "legendary", "mythic",
]

const STANDARD_SLOT: Dictionary = {
	"common": 72, "rare": 24, "epic": 4, "legendary": 0, "mythic": 0,
}
const PREMIUM_SLOT: Dictionary = {
	"common": 0, "rare": 58, "epic": 30, "legendary": 9, "mythic": 3,
}
const CHASE_SLOT: Dictionary = {
	"common": 0, "rare": 0, "epic": 62, "legendary": 28, "mythic": 10,
}

const PACKS: Array = [
	{
		"id": "dawn",
		"name": "Dawn Pack",
		"price": 0,
		"description": "Your free pack — a new one hatches every 24 hours.",
		"slots": [STANDARD_SLOT, STANDARD_SLOT, STANDARD_SLOT, STANDARD_SLOT, PREMIUM_SLOT],
	},
	{
		"id": "primal",
		"name": "Primal Pack",
		"price": 100,
		"description": "Five cards with a guaranteed epic-or-better chase slot.",
		"slots": [STANDARD_SLOT, STANDARD_SLOT, STANDARD_SLOT, PREMIUM_SLOT, CHASE_SLOT],
	},
]


## Cards that can appear in packs: dinos, trainers and fields (not energy —
## Instinct is granted in the starter collection).
static func pool() -> Array[CardData]:
	var cards: Array[CardData] = []
	cards.append_array(GameData.dinos)
	cards.append_array(GameData.trainers)
	cards.append_array(GameData.fields)
	return cards


static func open_pack(
		pack: Dictionary, owned: Dictionary, rng: RandomNumberGenerator) -> Array[CardData]:
	var result: Array[CardData] = []
	var drawn: Dictionary = {}
	var all_cards := pool()

	for slot: Dictionary in pack["slots"]:
		var rarity := _roll_rarity(slot, rng)
		var candidates: Array[CardData] = []
		for card: CardData in all_cards:
			var card_rarity: String = CardCatalogTypes.RARITY_NAMES[card.rarity]
			if card_rarity == rarity and not drawn.has(card.id):
				candidates.append(card)
		if candidates.is_empty():  # rolled rarity exhausted — widen to anything
			for card: CardData in all_cards:
				if not drawn.has(card.id):
					candidates.append(card)

		var fresh: Array[CardData] = candidates.filter(
			func(card: CardData) -> bool: return not owned.has(card.id))
		var pick: CardData = candidates[rng.randi_range(0, candidates.size() - 1)]
		for _reroll in range(4):
			if not owned.has(pick.id) or fresh.is_empty():
				break
			pick = fresh[rng.randi_range(0, fresh.size() - 1)]
		drawn[pick.id] = true
		result.append(pick)
	return result


static func _roll_rarity(weights: Dictionary, rng: RandomNumberGenerator) -> String:
	var total := 0
	for rarity: String in RARITY_NAMES_ORDERED:
		total += int(weights.get(rarity, 0))
	var roll := rng.randf() * total
	for rarity: String in RARITY_NAMES_ORDERED:
		roll -= int(weights.get(rarity, 0))
		if roll < 0:
			return rarity
	return "common"
