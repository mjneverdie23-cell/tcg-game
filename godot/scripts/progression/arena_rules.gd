class_name ArenaRules
## Trophy ladder. Trophies are the only progression currency the ladder
## reads, so the arena a player sits in is always derivable from PlayerData
## rather than stored (and so can never drift out of sync with it).

## Trophies won and lost per ranked battle. Casual battles stake nothing.
const WIN_TROPHIES := 30
const LOSS_TROPHIES := 15

## Ordered ladder; `trophies` is the entry threshold. Index 0 is Arena 1.
const ARENAS: Array = [
	{"name": "Fossil Flats", "trophies": 0},
	{"name": "Amber Grove", "trophies": 200},
	{"name": "Tar Pits", "trophies": 450},
	{"name": "Fern Basin", "trophies": 750},
	{"name": "Bone Ridge", "trophies": 1100},
	{"name": "Ashfall Steppe", "trophies": 1500},
	{"name": "Sunken Delta", "trophies": 1950},
	{"name": "Storm Cliffs", "trophies": 2450},
	{"name": "Obsidian Caldera", "trophies": 3000},
	{"name": "Primordia Summit", "trophies": 3600},
]


## 0-based ladder index.
static func index_for(trophies: int) -> int:
	var index := 0
	for i in range(ARENAS.size()):
		if trophies >= int(ARENAS[i]["trophies"]):
			index = i
	return index


## 1-based arena number, as shown on the badge.
static func number_for(trophies: int) -> int:
	return index_for(trophies) + 1


static func name_for(trophies: int) -> String:
	return str(ARENAS[index_for(trophies)]["name"])


## Trophies needed to enter the next arena, or -1 at the top of the ladder.
static func next_threshold(trophies: int) -> int:
	var index := index_for(trophies)
	if index >= ARENAS.size() - 1:
		return -1
	return int(ARENAS[index + 1]["trophies"])


## 0..1 progress through the current arena; 1.0 once the ladder is topped.
static func progress(trophies: int) -> float:
	var next := next_threshold(trophies)
	if next == -1:
		return 1.0
	var floor_trophies := int(ARENAS[index_for(trophies)]["trophies"])
	var span := next - floor_trophies
	return clampf(float(trophies - floor_trophies) / float(span), 0.0, 1.0)


## What a ranked result is worth. Losses never push a player below zero, so
## a bad run costs progress but can't spiral.
static func delta_for(won: bool, trophies: int) -> int:
	if won:
		return WIN_TROPHIES
	return -mini(LOSS_TROPHIES, trophies)
