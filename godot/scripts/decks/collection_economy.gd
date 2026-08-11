class_name CollectionEconomy
## What surplus cards are worth. A deck may hold at most DeckRules.MAX_COPIES
## of any id, so copies beyond that can never be played — which is what makes
## them safe to convert into coins with a single button.

## Coins paid for one surplus copy, by rarity.
const SELL_VALUES: Dictionary = {
	CardCatalogTypes.Rarity.COMMON: 8,
	CardCatalogTypes.Rarity.RARE: 20,
	CardCatalogTypes.Rarity.EPIC: 55,
	CardCatalogTypes.Rarity.LEGENDARY: 140,
	CardCatalogTypes.Rarity.MYTHIC: 320,
}


## {"copies": n, "value": coins} for everything sellable in `owned`
## (card_id -> copies). Unknown ids from older saves are skipped rather than
## valued at zero, so they are never silently destroyed.
static func surplus_of(owned: Dictionary) -> Dictionary:
	var copies := 0
	var value := 0
	for card_id: String in owned:
		if not GameData.has_card(card_id):
			continue
		var extra := int(owned[card_id]) - DeckRules.MAX_COPIES
		if extra <= 0:
			continue
		copies += extra
		value += extra * int(SELL_VALUES.get(GameData.get_card(card_id).rarity, 0))
	return {"copies": copies, "value": value}


static func value_of(card: CardData) -> int:
	return int(SELL_VALUES.get(card.rarity, 0))
