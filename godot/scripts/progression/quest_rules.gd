class_name QuestRules
## The quest chain on the Battle tab: four matches against the AI, played in
## order. Each one must be won before the next unlocks, each is harder than
## the last, and each pays out once when claimed.
##
## Difficulty is not a stat multiplier — the rival never gets extra HP or
## free energy. What changes is how often it plays badly: the mistakes a new
## player makes are handed to the AI at level 0 and taken away as the chain
## goes on (see BattleAI.profile_for). The last opponent plays the same game
## you do, with no mistakes at all.
##
## The rival's deck is built from a card pool capped by rarity, so early
## opponents also field plainer cards. The cap always includes RARE because
## every Environment in the catalog is rare or better, and a deck with no
## Environment is not battle-legal.

const MATCHES: Array = [
	{
		"id": "scout",
		"title": "Field Scout",
		"detail": "A nervous tracker who forgets to feed their dinosaurs.",
		"type": CardCatalogTypes.DinoType.HERBIVORE,
		"max_rarity": CardCatalogTypes.Rarity.RARE,
		"level": 0,
		"reward": 100,
	},
	{
		"id": "tracker",
		"title": "Bone Tracker",
		"detail": "Steadier, but still wastes turns and cards.",
		"type": CardCatalogTypes.DinoType.AMPHIBIAN,
		"max_rarity": CardCatalogTypes.Rarity.EPIC,
		"level": 1,
		"reward": 120,
	},
	{
		"id": "warden",
		"title": "Ridge Warden",
		"detail": "Keeps their energy on the board and presses attacks.",
		"type": CardCatalogTypes.DinoType.PTEROSAUR,
		"max_rarity": CardCatalogTypes.Rarity.LEGENDARY,
		"level": 2,
		"reward": 150,
	},
	{
		"id": "alpha",
		"title": "The Alpha",
		"detail": "Plays the game exactly as well as you do. No mistakes.",
		"type": CardCatalogTypes.DinoType.CARNIVORE,
		"max_rarity": CardCatalogTypes.Rarity.MYTHIC,
		"level": 3,
		"reward": 200,
	},
]

## Earlier matches must be won first.
const STATE_LOCKED := "locked"
## Unlocked and not yet beaten.
const STATE_READY := "ready"
## Beaten; the reward is waiting to be claimed.
const STATE_WON := "won"
const STATE_CLAIMED := "claimed"


static func count() -> int:
	return MATCHES.size()


static func quest(index: int) -> Dictionary:
	return MATCHES[index]


static func index_of(id: String) -> int:
	for i in range(MATCHES.size()):
		if str(MATCHES[i]["id"]) == id:
			return i
	return -1


static func is_won(index: int) -> bool:
	return PlayerData.quest_wins.has(str(MATCHES[index]["id"]))


static func is_claimed(index: int) -> bool:
	return PlayerData.quests_claimed.has(str(MATCHES[index]["id"]))


## A match opens once every match before it has been won. Claiming the
## reward is not required to move on — only winning.
static func is_unlocked(index: int) -> bool:
	for i in range(index):
		if not is_won(i):
			return false
	return true


static func state_of(index: int) -> String:
	if is_claimed(index):
		return STATE_CLAIMED
	if is_won(index):
		return STATE_WON
	return STATE_READY if is_unlocked(index) else STATE_LOCKED


static func won_count() -> int:
	var won := 0
	for i in range(MATCHES.size()):
		if is_won(i):
			won += 1
	return won


## The match the player should tackle next, or -1 when the chain is done.
static func next_playable() -> int:
	for i in range(MATCHES.size()):
		if state_of(i) == STATE_READY:
			return i
	return -1


## The rival's deck for this match: legal, themed to one dinosaur type, and
## drawn only from cards at or below the match's rarity cap.
static func build_rival_deck(index: int) -> Array:
	var match_data: Dictionary = MATCHES[index]
	var cap: int = CardStyle.RARITY_ORDER[int(match_data["max_rarity"])]
	var pool: Dictionary = {}
	for card: CardData in GameData.all_cards():
		if int(CardStyle.RARITY_ORDER[card.rarity]) >= cap:
			pool[card.id] = DeckRules.MAX_COPIES
	return DeckRules.auto_build(pool, int(match_data["type"]))
