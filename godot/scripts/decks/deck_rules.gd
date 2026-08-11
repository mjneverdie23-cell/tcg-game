class_name DeckRules
## Deck construction rules — the single source of truth for the deck
## builder, the starter-deck grant and battle setup.
##
## Official ruleset: exactly 23 cards; at most 6 Support, 6 Spell and 2
## Environment cards; every remaining card must be a Dinosaur; max 2 copies
## of any card id; never more copies than owned. A deck also needs at least
## one Environment and one basic Dinosaur (setup must be able to place
## both), and Energy is auto-generated — energy cards are not deck cards.

const DECK_SIZE := 23
const MAX_COPIES := 2
const MAX_SUPPORT := 6
const MAX_SPELL := 6
const MAX_ENVIRONMENT := 2


static func count_copies(card_ids: Array, card_id: String) -> int:
	var count := 0
	for id: String in card_ids:
		if id == card_id:
			count += 1
	return count


## Cards counted per category: {"dino": n, "support": n, "spell": n, "environment": n}.
static func category_counts(card_ids: Array) -> Dictionary:
	var counts := {"dino": 0, "support": 0, "spell": 0, "environment": 0, "other": 0}
	for id: String in card_ids:
		# Decks saved under older rulesets can hold ids that no longer
		# exist; count them as "other" rather than erroring on lookup.
		if not GameData.has_card(id):
			counts["other"] += 1
			continue
		counts[_category(GameData.get_card(id))] += 1
	return counts


static func _category(card: CardData) -> String:
	if card is DinoCardData:
		return "dino"
	if card is FieldCardData:
		return "environment"
	if card is TrainerCardData:
		return (
			"support" if (card as TrainerCardData).trainer_kind == TrainerCardData.KIND_SUPPORT
			else "spell")
	return "other"  # energy cards etc. — never deck-legal


## Whether one more copy of `card` may join the deck, given owned copies.
static func can_add(card_ids: Array, card: CardData, owned: int) -> bool:
	if card_ids.size() >= DECK_SIZE:
		return false
	if count_copies(card_ids, card.id) >= mini(owned, MAX_COPIES):
		return false
	var counts := category_counts(card_ids)
	match _category(card):
		"support":
			return counts["support"] < MAX_SUPPORT
		"spell":
			return counts["spell"] < MAX_SPELL
		"environment":
			return counts["environment"] < MAX_ENVIRONMENT
		"dino":
			return true
		_:
			return false


## Human-readable problems; an empty result means the deck is battle-legal.
static func validate(card_ids: Array) -> PackedStringArray:
	var issues := PackedStringArray()
	if card_ids.size() != DECK_SIZE:
		issues.append("Deck has %d / %d cards." % [card_ids.size(), DECK_SIZE])

	var counts := category_counts(card_ids)
	if counts["support"] > MAX_SUPPORT:
		issues.append("More than %d Support cards." % MAX_SUPPORT)
	if counts["spell"] > MAX_SPELL:
		issues.append("More than %d Spell cards." % MAX_SPELL)
	if counts["environment"] > MAX_ENVIRONMENT:
		issues.append("More than %d Environment cards." % MAX_ENVIRONMENT)
	if counts["other"] > 0:
		issues.append("Deck contains %d card(s) that are no longer playable." % counts["other"])
	if counts["environment"] == 0 and not card_ids.is_empty():
		issues.append("Needs at least one Environment (setup places one).")

	var counted: Dictionary = {}
	var has_basic := false
	for id: String in card_ids:
		if not GameData.has_card(id):
			issues.append("Unknown card id '%s'." % id)
			continue
		counted[id] = int(counted.get(id, 0)) + 1
		var card := GameData.get_card(id)
		if card is DinoCardData and (card as DinoCardData).stage == 1:
			has_basic = true
	for id: String in counted:
		if counted[id] > MAX_COPIES:
			issues.append("More than %d copies of %s." % [
				MAX_COPIES, GameData.get_card(id).display_name])
	if not has_basic and not card_ids.is_empty():
		issues.append("Needs at least one basic Dinosaur.")
	return issues


## Composition summary for the builder's balance panel.
static func breakdown(card_ids: Array) -> String:
	var counts := category_counts(card_ids)
	return "Dinos %d  ·  Supports %d/%d  ·  Spells %d/%d  ·  Environments %d/%d" % [
		counts["dino"], counts["support"], MAX_SUPPORT,
		counts["spell"], MAX_SPELL, counts["environment"], MAX_ENVIRONMENT]


## Builds a legal 23-card deck from the owned collection around
## `forced_type` (or the type the player owns the most dinosaurs of):
## dinos first, then environments matching the type, spells, supports.
static func auto_build(owned: Dictionary, forced_type: int = -1) -> Array:
	var primary := forced_type if forced_type != -1 else primary_type(owned)
	var deck: Array = []

	var dinos: Array[DinoCardData] = []
	for card: DinoCardData in GameData.dinos:
		if card.dino_type == primary and int(owned.get(card.id, 0)) > 0:
			dinos.append(card)
	dinos.sort_custom(func(a: DinoCardData, b: DinoCardData) -> bool:
		var order_a: int = CardStyle.RARITY_ORDER[a.rarity]
		var order_b: int = CardStyle.RARITY_ORDER[b.rarity]
		if order_a != order_b:
			return order_a < order_b
		return a.display_name < b.display_name)
	for card in dinos:
		while deck.size() < 13 and can_add(deck, card, int(owned.get(card.id, 0))):
			deck.append(card.id)

	for card: FieldCardData in GameData.fields:
		if card.dino_type == primary:
			while deck.size() < 15 and can_add(deck, card, int(owned.get(card.id, 0))):
				deck.append(card.id)
	# Guarantee at least one environment even off-type.
	if category_counts(deck)["environment"] == 0:
		for card: FieldCardData in GameData.fields:
			if can_add(deck, card, int(owned.get(card.id, 0))):
				deck.append(card.id)
				break

	var trainers := GameData.trainers.duplicate()
	trainers.sort_custom(func(a: TrainerCardData, b: TrainerCardData) -> bool:
		var order_a: int = CardStyle.RARITY_ORDER[a.rarity]
		var order_b: int = CardStyle.RARITY_ORDER[b.rarity]
		if order_a != order_b:
			return order_a > order_b  # commons first: cheap, dependable effects
		return a.display_name < b.display_name)
	for card: TrainerCardData in trainers:
		while deck.size() < DECK_SIZE and can_add(deck, card, int(owned.get(card.id, 0))):
			deck.append(card.id)

	# Sparse collections: pad with any remaining addable cards (more dinos).
	if deck.size() < DECK_SIZE:
		for card: CardData in GameData.all_cards():
			while deck.size() < DECK_SIZE and can_add(deck, card, int(owned.get(card.id, 0))):
				deck.append(card.id)
	return deck


## The dinosaur type the player owns the most of. auto_build() centres a
## generated deck on it; the home screen picks its hero emblem from it.
static func primary_type(owned: Dictionary) -> int:
	var totals: Dictionary = {}
	for card: DinoCardData in GameData.dinos:
		var copies := int(owned.get(card.id, 0))
		if copies > 0:
			totals[card.dino_type] = int(totals.get(card.dino_type, 0)) + copies
	var best: int = CardCatalogTypes.DinoType.CARNIVORE
	var best_count := -1
	for dino_type: int in totals:
		if totals[dino_type] > best_count:
			best = dino_type
			best_count = totals[dino_type]
	return best
