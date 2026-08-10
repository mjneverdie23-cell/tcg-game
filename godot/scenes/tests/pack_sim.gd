extends Node
## Headless pack-opening test. Run with:
##
##   godot --headless --path godot res://scenes/tests/pack_sim.tscn
##
## Asserts across seeded openings: 5 cards per pack, no duplicates within a
## pack, slot rarity floors respected (primal chase slot is epic or better),
## and duplicate protection strongly favors unowned cards.

const OPENINGS := 200


func _ready() -> void:
	var failures := PackedStringArray()
	var rng := RandomNumberGenerator.new()

	for pack: Dictionary in PackRules.PACKS:
		for i in range(OPENINGS):
			rng.seed = hash("%s:%d" % [pack["id"], i])
			var cards := PackRules.open_pack(pack, {}, rng)
			if cards.size() != PackRules.CARDS_PER_PACK:
				failures.append("%s #%d: %d cards" % [pack["id"], i, cards.size()])
			var ids: Dictionary = {}
			for card: CardData in cards:
				ids[card.id] = true
			if ids.size() != cards.size():
				failures.append("%s #%d: duplicate within pack" % [pack["id"], i])
			if pack["id"] == "primal":
				var chase := cards[4]
				if chase.rarity in [CardCatalogTypes.Rarity.COMMON, CardCatalogTypes.Rarity.RARE]:
					failures.append("primal #%d: chase slot rolled %s" % [
						i, CardCatalogTypes.RARITY_NAMES[chase.rarity]])

	# Duplicate protection: own everything except one common card; it should
	# appear far more often than raw odds would give it.
	var pool := PackRules.pool()
	var target: CardData = null
	var owned: Dictionary = {}
	for card: CardData in pool:
		owned[card.id] = 2
	for card: CardData in pool:
		if card.rarity == CardCatalogTypes.Rarity.COMMON:
			target = card
			owned.erase(card.id)
			break
	var hits := 0
	for i in range(100):
		rng.seed = hash("pity:%d" % i)
		var cards := PackRules.open_pack(PackRules.PACKS[0], owned, rng)
		for card: CardData in cards:
			if card.id == target.id:
				hits += 1
				break
	if hits < 40:
		failures.append("duplicate protection weak: target hit %d/100" % hits)

	if failures.is_empty():
		print("PACK SIM PASS — %d openings per pack, pity hits OK" % OPENINGS)
	else:
		for failure: String in failures:
			print("FAIL: %s" % failure)
	get_tree().quit(failures.size())
