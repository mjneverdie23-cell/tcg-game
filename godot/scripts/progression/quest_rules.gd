class_name QuestRules
## The daily quest chain shown on the home screen.
##
## Quests are a chain: a node unlocks only once the node before it has been
## claimed, which is what gives the home screen its path. Progress itself is
## read from PlayerData's daily counters, so a quest can already be complete
## the moment it unlocks — the counters run all day whether or not the node
## that reads them is open yet.

## `counter` names a PlayerData daily counter (see PlayerData.COUNTERS).
const QUESTS: Array = [
	{
		"id": "skirmish",
		"title": "Enter the arena",
		"detail": "Play 2 battles",
		"counter": "battles_played",
		"target": 2,
		"reward": 60,
	},
	{
		"id": "victor",
		"title": "Claim a victory",
		"detail": "Win 1 battle",
		"counter": "battles_won",
		"target": 1,
		"reward": 90,
	},
	{
		"id": "excavate",
		"title": "Excavate",
		"detail": "Open 1 card pack",
		"counter": "packs_opened",
		"target": 1,
		"reward": 70,
	},
	{
		"id": "curator",
		"title": "Grow the collection",
		"detail": "Add 5 cards",
		"counter": "cards_gained",
		"target": 5,
		"reward": 120,
	},
]

## Paid out once the whole chain has been claimed.
const CHAIN_BONUS := 250

const STATE_LOCKED := "locked"
const STATE_ACTIVE := "active"
const STATE_READY := "ready"
const STATE_CLAIMED := "claimed"


static func count() -> int:
	return QUESTS.size()


static func quest(index: int) -> Dictionary:
	return QUESTS[index]


## Progress toward this quest's target, capped at the target.
static func progress_of(index: int) -> int:
	var q: Dictionary = QUESTS[index]
	return mini(PlayerData.daily_count(str(q["counter"])), int(q["target"]))


static func is_claimed(index: int) -> bool:
	return PlayerData.quests_claimed.has(str(QUESTS[index]["id"]))


## A quest is reachable once every earlier quest has been claimed.
static func is_unlocked(index: int) -> bool:
	for i in range(index):
		if not is_claimed(i):
			return false
	return true


static func state_of(index: int) -> String:
	# progress_of() first: reading a counter is what rolls the day over, so
	# asking it before the claim checks keeps them from seeing stale claims.
	var finished := progress_of(index) >= int(QUESTS[index]["target"])
	if is_claimed(index):
		return STATE_CLAIMED
	if not is_unlocked(index):
		return STATE_LOCKED
	return STATE_READY if finished else STATE_ACTIVE


static func claimed_count() -> int:
	var claimed := 0
	for i in range(QUESTS.size()):
		# state_of() rolls the day over before answering, so a chain cleared
		# yesterday cannot pay its bonus a second time after midnight.
		if state_of(i) == STATE_CLAIMED:
			claimed += 1
	return claimed


static func chain_complete() -> bool:
	return claimed_count() == QUESTS.size()


## True when the end-of-chain bonus is sitting there waiting to be taken.
static func bonus_ready() -> bool:
	return chain_complete() and not PlayerData.chain_bonus_claimed
