extends Node
## Autoload: the player's profile — collection, coins, decks, ladder standing
## and the daily timers. Persisted as JSON at user://save.json; saved
## automatically after every mutation. All writes go through the methods here
## so the save file never drifts from runtime state.

signal collection_changed
signal coins_changed(new_amount: int)
signal decks_changed
## Trophies, battle record or a daily counter moved.
signal progress_changed

const SAVE_PATH := "user://save.json"
const SAVE_VERSION := 4
const STARTING_COINS := 1290
## One-off top-up applied when loading a save written before SAVE_VERSION 2,
## so existing profiles can afford a premium pack like new ones can.
const V2_COIN_GRANT := 140
## Version 3 top-up, so an existing profile has room to open several packs.
const V3_COIN_GRANT := 1000
const SECONDS_PER_DAY := 24 * 60 * 60
const DAILY_PACK_COOLDOWN_SECONDS := SECONDS_PER_DAY
const DEFAULT_NAME := "Ranger"

## Daily quest counters. Lifetime totals are tracked separately below; these
## reset when the calendar day turns over.
const COUNTERS: Array = ["battles_played", "battles_won", "packs_opened", "cards_gained"]

## card_id -> copies owned.
var owned_cards: Dictionary = {}
var coins: int = STARTING_COINS
## Unix time of the last daily-pack claim; 0 = never claimed.
var last_daily_claim: int = 0
## Unix time of the last free coin claim in the shop; 0 = never claimed.
var last_coin_claim: int = 0
## Saved decks: Array of {"name": String, "card_ids": Array[String]}.
var decks: Array = []

var player_name: String = DEFAULT_NAME
## Ladder standing; ArenaRules turns it into an arena.
var trophies: int = 0
var best_trophies: int = 0
var battles_played: int = 0
var battles_won: int = 0
var packs_opened: int = 0

## counter name -> today's count.
var daily_counters: Dictionary = {}
## Day index (unix time / 86400) the counters above belong to.
var daily_day: int = 0
## Quest ids claimed today, and whether the end-of-chain bonus is taken.
var quests_claimed: Array = []
var chain_bonus_claimed: bool = false


func _ready() -> void:
	load_game()


func add_card(card_id: String, count: int = 1) -> void:
	owned_cards[card_id] = int(owned_cards.get(card_id, 0)) + count
	collection_changed.emit()
	save_game()


func owned_count(card_id: String) -> int:
	return int(owned_cards.get(card_id, 0))


## Returns false (and changes nothing) if the player can't afford it.
func spend_coins(amount: int) -> bool:
	if coins < amount:
		return false
	coins -= amount
	coins_changed.emit(coins)
	save_game()
	return true


func earn_coins(amount: int) -> void:
	coins += amount
	coins_changed.emit(coins)
	save_game()


# ── daily timers ──────────────────────────────────────────────────────


func is_daily_pack_ready(now_unix: int) -> bool:
	return now_unix >= last_daily_claim + DAILY_PACK_COOLDOWN_SECONDS or last_daily_claim == 0


func claim_daily_pack(now_unix: int) -> void:
	last_daily_claim = now_unix
	save_game()


func is_daily_coins_ready(now_unix: int) -> bool:
	return now_unix >= last_coin_claim + DAILY_PACK_COOLDOWN_SECONDS or last_coin_claim == 0


## Takes the free daily coin stipend. Returns false if it isn't ready yet.
func claim_daily_coins(now_unix: int, amount: int) -> bool:
	if not is_daily_coins_ready(now_unix):
		return false
	last_coin_claim = now_unix
	earn_coins(amount)
	return true


# ── ladder & quest progress ───────────────────────────────────────────


## Bumps a daily quest counter (and its lifetime twin where one exists),
## rolling the daily counters over first if the day has changed.
func record_counter(counter: String, amount: int = 1) -> void:
	if not COUNTERS.has(counter):
		push_error("PlayerData: unknown counter '%s'" % counter)
		return
	_roll_daily()
	daily_counters[counter] = int(daily_counters.get(counter, 0)) + amount
	match counter:
		"battles_played":
			battles_played += amount
		"battles_won":
			battles_won += amount
		"packs_opened":
			packs_opened += amount
	progress_changed.emit()
	save_game()


func daily_count(counter: String) -> int:
	_roll_daily()
	return int(daily_counters.get(counter, 0))


## Records a finished battle and applies its trophy swing. `ranked` false
## (practice) still counts toward quests but stakes no trophies. Returns the
## trophy delta so the result screen can show it.
func record_battle(won: bool, ranked: bool) -> int:
	var delta := ArenaRules.delta_for(won, trophies) if ranked else 0
	trophies = maxi(0, trophies + delta)
	best_trophies = maxi(best_trophies, trophies)
	record_counter("battles_played")  # emits progress_changed and saves
	if won:
		record_counter("battles_won")
	return delta


## Pays out a quest reward once. Returns false if it was already claimed or
## isn't finished yet, so a double click can't double-pay.
func claim_quest(index: int) -> bool:
	if QuestRules.state_of(index) != QuestRules.STATE_READY:
		return false
	quests_claimed.append(str(QuestRules.quest(index)["id"]))
	earn_coins(int(QuestRules.quest(index)["reward"]))
	progress_changed.emit()
	save_game()
	return true


func claim_chain_bonus() -> bool:
	if not QuestRules.bonus_ready():
		return false
	chain_bonus_claimed = true
	earn_coins(QuestRules.CHAIN_BONUS)
	progress_changed.emit()
	save_game()
	return true


## Clears the daily counters and quest claims when the calendar day turns
## over. Called before every counter read or write, so the home screen can
## never show yesterday's progress.
func _roll_daily() -> void:
	@warning_ignore("integer_division")
	var today := int(Time.get_unix_time_from_system()) / SECONDS_PER_DAY
	if today == daily_day:
		return
	daily_day = today
	daily_counters = {}
	quests_claimed = []
	chain_bonus_claimed = false


# ── collection economy ────────────────────────────────────────────────


## Sells every surplus copy, keeping DeckRules.MAX_COPIES of each card.
## Returns {"copies": n, "value": coins} describing what was actually sold.
func sell_surplus() -> Dictionary:
	var sold := CollectionEconomy.surplus_of(owned_cards)
	if int(sold["copies"]) == 0:
		return sold
	for card_id: String in owned_cards.keys():
		if not GameData.has_card(card_id):
			continue
		if int(owned_cards[card_id]) > DeckRules.MAX_COPIES:
			owned_cards[card_id] = DeckRules.MAX_COPIES
	collection_changed.emit()
	earn_coins(int(sold["value"]))
	return sold


func set_player_name(new_name: String) -> void:
	var trimmed := new_name.strip_edges()
	player_name = trimmed if trimmed != "" else DEFAULT_NAME
	save_game()


# ── decks ─────────────────────────────────────────────────────────────


## Stores a deck as {"name": String, "card_ids": Array}. index -1 appends a
## new deck; otherwise the deck at that index is replaced.
func save_deck(index: int, deck_name: String, card_ids: Array) -> int:
	var deck := {"name": deck_name, "card_ids": card_ids.duplicate()}
	if index < 0 or index >= decks.size():
		decks.append(deck)
		index = decks.size() - 1
	else:
		decks[index] = deck
	decks_changed.emit()
	save_game()
	return index


func delete_deck(index: int) -> void:
	if index < 0 or index >= decks.size():
		return
	decks.remove_at(index)
	decks_changed.emit()
	save_game()


# ── persistence ───────────────────────────────────────────────────────


func save_game() -> void:
	var payload := {
		"version": SAVE_VERSION,
		"owned_cards": owned_cards,
		"coins": coins,
		"last_daily_claim": last_daily_claim,
		"last_coin_claim": last_coin_claim,
		"decks": decks,
		"player_name": player_name,
		"trophies": trophies,
		"best_trophies": best_trophies,
		"battles_played": battles_played,
		"battles_won": battles_won,
		"packs_opened": packs_opened,
		"daily_counters": daily_counters,
		"daily_day": daily_day,
		"quests_claimed": quests_claimed,
		"chain_bonus_claimed": chain_bonus_claimed,
	}
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file == null:
		push_error("PlayerData: cannot write %s" % SAVE_PATH)
		return
	file.store_string(JSON.stringify(payload, "\t"))


func load_game() -> void:
	if not FileAccess.file_exists(SAVE_PATH):
		_grant_starter_collection()
		return
	var file := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if file == null:
		push_error("PlayerData: cannot read %s" % SAVE_PATH)
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("PlayerData: corrupt save file, starting fresh")
		return
	var data: Dictionary = parsed
	owned_cards = data.get("owned_cards", {})
	coins = int(data.get("coins", STARTING_COINS))
	last_daily_claim = int(data.get("last_daily_claim", 0))
	last_coin_claim = int(data.get("last_coin_claim", 0))
	decks = data.get("decks", [])
	player_name = str(data.get("player_name", DEFAULT_NAME))
	trophies = int(data.get("trophies", 0))
	best_trophies = maxi(trophies, int(data.get("best_trophies", 0)))
	battles_played = int(data.get("battles_played", 0))
	battles_won = int(data.get("battles_won", 0))
	packs_opened = int(data.get("packs_opened", 0))
	daily_counters = data.get("daily_counters", {})
	daily_day = int(data.get("daily_day", 0))
	quests_claimed = data.get("quests_claimed", [])
	chain_bonus_claimed = bool(data.get("chain_bonus_claimed", false))
	_migrate_save(int(data.get("version", 1)))
	_migrate_decks()


## Applies upgrades for saves written by an older SAVE_VERSION. Version 4
## added ladder and quest fields, which default cleanly above — no grant.
func _migrate_save(loaded_version: int) -> void:
	var granted := 0
	if loaded_version < 2:
		granted += V2_COIN_GRANT
	if loaded_version < 3:
		granted += V3_COIN_GRANT
	if granted > 0:
		coins += granted
		coins_changed.emit(coins)
	if loaded_version < SAVE_VERSION:
		save_game()


## Older saves may hold decks from previous rulesets (20 cards, energy
## cards). If no deck is battle-legal anymore, grant a fresh starter deck.
func _migrate_decks() -> void:
	for deck: Dictionary in decks:
		if DeckRules.validate(deck.get("card_ids", [])).is_empty():
			return
	var starter := DeckRules.auto_build(owned_cards)
	if starter.size() == DeckRules.DECK_SIZE:
		decks.append({"name": "Starter Deck", "card_ids": starter})
		save_game()


## Deletes the save and restores a fresh profile (Settings -> reset).
func reset_all() -> void:
	owned_cards = {}
	coins = STARTING_COINS
	last_daily_claim = 0
	last_coin_claim = 0
	decks = []
	player_name = DEFAULT_NAME
	trophies = 0
	best_trophies = 0
	battles_played = 0
	battles_won = 0
	packs_opened = 0
	daily_counters = {}
	daily_day = 0
	quests_claimed = []
	chain_bonus_claimed = false
	_grant_starter_collection()
	collection_changed.emit()
	coins_changed.emit(coins)
	progress_changed.emit()


## New players start with a playable base: commons and rares of every type
## plus basic Spells/Supports and the rare Environments. Everything else
## comes from packs. Rule-based, so it adapts to the card catalog.
func _grant_starter_collection() -> void:
	for card: DinoCardData in GameData.dinos:
		if card.rarity == CardCatalogTypes.Rarity.COMMON:
			owned_cards[card.id] = 2
		elif card.rarity == CardCatalogTypes.Rarity.RARE:
			owned_cards[card.id] = 1
	for card: TrainerCardData in GameData.trainers:
		owned_cards[card.id] = 2 if card.rarity == CardCatalogTypes.Rarity.COMMON else 1
	for card: FieldCardData in GameData.fields:
		if card.rarity == CardCatalogTypes.Rarity.RARE:
			owned_cards[card.id] = 1
	# A ready-to-play deck so Battle works out of the box.
	var starter_deck := DeckRules.auto_build(owned_cards)
	if starter_deck.size() == DeckRules.DECK_SIZE:
		decks = [{"name": "Starter Deck", "card_ids": starter_deck}]
	save_game()
