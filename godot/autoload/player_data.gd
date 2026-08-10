extends Node
## Autoload: the player's profile — collection, coins, decks and the daily
## pack timer. Persisted as JSON at user://save.json; saved automatically
## after every mutation. All writes go through the methods here so the save
## file never drifts from runtime state.

signal collection_changed
signal coins_changed(new_amount: int)
signal decks_changed

const SAVE_PATH := "user://save.json"
const SAVE_VERSION := 2
const STARTING_COINS := 290
## One-off top-up applied when loading a save written before SAVE_VERSION 2,
## so existing profiles can afford a premium pack like new ones can.
const V2_COIN_GRANT := 140
const DAILY_PACK_COOLDOWN_SECONDS := 24 * 60 * 60

## card_id -> copies owned.
var owned_cards: Dictionary = {}
var coins: int = STARTING_COINS
## Unix time of the last daily-pack claim; 0 = never claimed.
var last_daily_claim: int = 0
## Saved decks: Array of {"name": String, "card_ids": Array[String]}.
var decks: Array = []


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


func is_daily_pack_ready(now_unix: int) -> bool:
	return now_unix >= last_daily_claim + DAILY_PACK_COOLDOWN_SECONDS or last_daily_claim == 0


func claim_daily_pack(now_unix: int) -> void:
	last_daily_claim = now_unix
	save_game()


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


func save_game() -> void:
	var payload := {
		"version": SAVE_VERSION,
		"owned_cards": owned_cards,
		"coins": coins,
		"last_daily_claim": last_daily_claim,
		"decks": decks,
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
	decks = data.get("decks", [])
	_migrate_save(int(data.get("version", 1)))
	_migrate_decks()


## Applies upgrades for saves written by an older SAVE_VERSION.
func _migrate_save(loaded_version: int) -> void:
	if loaded_version < 2:
		coins += V2_COIN_GRANT
		coins_changed.emit(coins)
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
	decks = []
	_grant_starter_collection()
	collection_changed.emit()
	coins_changed.emit(coins)


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
