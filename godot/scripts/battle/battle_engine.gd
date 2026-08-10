class_name BattleEngine
extends RefCounted
## The battle rules engine (official ruleset). Pure game logic: no nodes,
## no UI. The human UI and the AI drive it exclusively through
## get_legal_actions() / apply(), so neither can cheat.
##
## Rules:
## - 23-card decks (validated by DeckRules). Coin flip assigns Heads/Tails
##   and the first turn. Both players draw 6, redrawing until the hand holds
##   at least one Dinosaur and one Environment.
## - Setup: each player places one Environment on their side and one basic
##   Dinosaur into the Active slot (Environment synergy applies when types
##   match). Back slots are filled later, by each player on their own turn.
## - Energy is auto-generated: 1 unit of the player's element per turn,
##   attachable to one dinosaur. Attack costs are paid by energy count.
## - Every turn begins with a draw. Turn 1 (the player who won the toss):
##   energy + Spell cards, place basics — no attack and no Support.
##   Turn 2 onward: the full flow (draw, energy, Spells, one Support,
##   Environment replacement, evolve, retreat once, attack once).
## - Each player's Environment passively buffs their own Active while its
##   type matches; it stays until replaced.
## - Damage: base + boosts, x2 weakness, -20 resistance. Statuses:
##   poisoned / asleep / paralyzed via signature attacks.
## - Win: knock out 2 opposing Dinosaurs, or the opponent cannot promote a
##   replacement Active.

signal log_line(text: String)

const POINTS_TO_WIN := 2
const BENCH_SIZE := 3
const OPENING_HAND := 6

const STATUS_POISONED := "poisoned"
const STATUS_ASLEEP := "asleep"
const STATUS_PARALYZED := "paralyzed"
const POISON_DAMAGE := 10

## Signature attacks that inflict a status on the defender.
const ATTACK_STATUS: Dictionary = {
	"Blood Frenzy": STATUS_POISONED,
	"Drowning Grip": STATUS_ASLEEP,
	"Ground Shaker": STATUS_PARALYZED,
	"Sky Screech": STATUS_ASLEEP,
}

## Every log line so far — lets the UI catch up on setup events.
var log_history := PackedStringArray()

## Coin-toss outcome, surfaced to the UI: who called Heads and who starts.
var heads_player: int = 0
var first_player: int = 0

var players: Array[BattlePlayerState] = []
var current: int = 0
var turn_number: int = 1
## -1 while the battle is running, else the winning player index.
var winner: int = -1

var _rng := RandomNumberGenerator.new()


func _init(deck_a: Array, deck_b: Array, seed_value: int) -> void:
	_rng.seed = seed_value
	for deck: Array in [deck_a, deck_b]:
		var player := BattlePlayerState.new()
		for id: String in deck:
			player.deck.append(id)
		player.element = _dominant_type(deck)
		_shuffle(player.deck)
		players.append(player)

	# Coin flip: one player is Heads, the other Tails; Heads starts.
	var heads := 0 if _rng.randf() < 0.5 else 1
	heads_player = heads
	first_player = heads
	current = heads
	_log("Coin flip — %s is Heads, %s is Tails. %s starts." % [
		_name(heads), _name(opponent_of(heads)), _name(heads)])

	for index in range(2):
		_draw_opening_hand(players[index])
		_auto_setup(players[index], index)
	_begin_turn()


func opponent_of(index: int) -> int:
	return 1 - index


func is_over() -> bool:
	return winner != -1


# ── legal actions ─────────────────────────────────────────────────────


## Everything the current player may do right now, as action dictionaries.
func get_legal_actions() -> Array[Dictionary]:
	var actions: Array[Dictionary] = []
	if is_over():
		return actions
	var player := players[current]

	if player.energy_budget > 0:
		for t in range(player.dinos_in_play().size()):
			actions.append({"type": "attach", "target": t - 1})

	for i in range(player.hand.size()):
		var card := GameData.get_card(player.hand[i])
		if card is DinoCardData:
			_add_dino_actions(actions, player, card as DinoCardData, i)
		elif card is TrainerCardData:
			_add_trainer_actions(actions, player, card as TrainerCardData, i)
		elif card is FieldCardData and turn_number >= 2:
			if (card as FieldCardData).id != player.environment_id:
				actions.append({"type": "environment", "hand": i})

	_add_retreat_actions(actions, player)
	_add_attack_actions(actions, player)
	actions.append({"type": "end_turn"})
	return actions


func _add_dino_actions(
		actions: Array[Dictionary], player: BattlePlayerState,
		card: DinoCardData, hand_index: int) -> void:
	if card.stage == 1:
		if player.bench.size() < BENCH_SIZE:
			actions.append({"type": "place_basic", "hand": hand_index})
		return
	if turn_number < 2:
		return
	var targets := player.dinos_in_play()
	for t in range(targets.size()):
		var target := targets[t]
		if target.card_id == card.evolves_from and target.turn_entered < turn_number:
			actions.append({"type": "evolve", "hand": hand_index, "target": t - 1})


func _add_trainer_actions(
		actions: Array[Dictionary], player: BattlePlayerState,
		card: TrainerCardData, hand_index: int) -> void:
	if card.trainer_kind == TrainerCardData.KIND_SUPPORT:
		if turn_number < 2 or player.support_played:
			return  # Supports unlock on turn 2, one per turn
	match card.effect["type"]:
		"switch":
			if turn_number >= 2:
				for b in range(player.bench.size()):
					actions.append({"type": "trainer", "hand": hand_index, "target": b})
		"heal":
			if player.active.damage > 0:
				actions.append({"type": "trainer", "hand": hand_index})
		_:
			actions.append({"type": "trainer", "hand": hand_index})


func _add_retreat_actions(actions: Array[Dictionary], player: BattlePlayerState) -> void:
	if turn_number < 2 or player.retreated or player.bench.is_empty():
		return
	if player.active.has_status(STATUS_ASLEEP) or player.active.has_status(STATUS_PARALYZED):
		return
	if player.active.energy < retreat_cost(current):
		return
	for b in range(player.bench.size()):
		actions.append({"type": "retreat", "bench": b})


func _add_attack_actions(actions: Array[Dictionary], player: BattlePlayerState) -> void:
	if turn_number < 2:
		return  # the starting player cannot attack on turn 1
	if player.active.has_status(STATUS_ASLEEP) or player.active.has_status(STATUS_PARALYZED):
		return
	for a: int in affordable_attacks(current):
		actions.append({"type": "attack", "index": a})


# ── applying actions ──────────────────────────────────────────────────


## Applies an action for the current player. Returns false if illegal.
func apply(action: Dictionary) -> bool:
	if is_over():
		return false
	if not get_legal_actions().any(func(legal: Dictionary) -> bool: return legal == action):
		push_error("BattleEngine: illegal action %s" % str(action))
		return false

	match action["type"]:
		"attach":
			_do_attach(action["target"])
		"place_basic":
			_do_place_basic(action["hand"])
		"evolve":
			_do_evolve(action["hand"], action["target"])
		"trainer":
			_do_trainer(action["hand"], int(action.get("target", -1)))
		"environment":
			_do_environment(action["hand"])
		"retreat":
			_do_retreat(action["bench"])
		"attack":
			_do_attack(action["index"])
		"end_turn":
			_end_turn()
	return true


func _do_attach(target: int) -> void:
	var player := players[current]
	var dino := _target_dino(player, target)
	dino.energy += 1
	player.energy_budget -= 1
	_log("%s attaches %s energy to %s." % [
		_name(current), CardCatalogTypes.TYPE_NAMES[player.element], _card_name(dino.card_id)])


func _do_place_basic(hand_index: int) -> void:
	var player := players[current]
	var id: String = player.hand.pop_at(hand_index)
	player.bench.append(DinoInPlay.new(id, turn_number))
	_log("%s benches %s." % [_name(current), _card_name(id)])


func _do_evolve(hand_index: int, target: int) -> void:
	var player := players[current]
	var dino := _target_dino(player, target)
	var id: String = player.hand.pop_at(hand_index)
	_log("%s evolves %s into %s." % [_name(current), _card_name(dino.card_id), _card_name(id)])
	player.discard.append(dino.card_id)
	dino.card_id = id
	dino.clear_statuses()
	dino.turn_entered = turn_number


func _do_environment(hand_index: int) -> void:
	var player := players[current]
	if player.environment_id != "":
		player.discard.append(player.environment_id)
	player.environment_id = player.hand.pop_at(hand_index)
	_log("%s sets Environment: %s." % [_name(current), _card_name(player.environment_id)])
	for index in range(2):
		_check_ko(index)  # losing an hp buff can down a damaged active
		if is_over():
			return


func _do_retreat(bench_index: int) -> void:
	var player := players[current]
	player.active.energy -= retreat_cost(current)
	player.active.clear_statuses()
	var benched := player.bench[bench_index]
	player.bench[bench_index] = player.active
	player.active = benched
	player.retreated = true
	_log("%s retreats to %s." % [_name(current), _card_name(player.active.card_id)])


func _do_trainer(hand_index: int, target: int) -> void:
	var player := players[current]
	var card := GameData.get_card(player.hand[hand_index]) as TrainerCardData
	player.hand.remove_at(hand_index)
	player.discard.append(card.id)
	if card.trainer_kind == TrainerCardData.KIND_SUPPORT:
		player.support_played = true
	_log("%s plays %s." % [_name(current), card.display_name])

	match card.effect["type"]:
		"heal":
			player.active.damage = maxi(0, player.active.damage - int(card.effect["amount"]))
		"heal-all":
			for dino in player.dinos_in_play():
				dino.damage = maxi(0, dino.damage - int(card.effect["amount"]))
		"draw":
			player.draw(int(card.effect["count"]))
		"draw-to":
			player.draw(maxi(0, int(card.effect["hand_size"]) - player.hand.size()))
		"search-dino":
			_search_basic_dino(player)
		"damage-boost":
			player.damage_boost += int(card.effect["amount"])
		"switch":
			var benched := player.bench[target]
			player.bench[target] = player.active
			player.active.clear_statuses()
			player.active = benched
		"bonus-energy":
			player.energy_budget += 1


func _do_attack(attack_index: int) -> void:
	var player := players[current]
	var defender := players[opponent_of(current)]
	var attack := player.active.card().attacks[attack_index]
	var damage := preview_damage(attack_index)
	defender.active.damage += damage
	_log("%s: %s uses %s for %d damage!" % [
		_name(current), _card_name(player.active.card_id), attack.attack_name, damage])

	var survived := defender.active.damage < _max_hp_of(defender.active, opponent_of(current))
	if ATTACK_STATUS.has(attack.attack_name) and survived:
		defender.active.add_status(ATTACK_STATUS[attack.attack_name])
		_log("%s is %s!" % [_card_name(defender.active.card_id), ATTACK_STATUS[attack.attack_name]])

	_check_ko(opponent_of(current))
	if not is_over():
		_end_turn()


## Damage the current player's active would deal with this attack right now.
func preview_damage(attack_index: int) -> int:
	return preview_damage_for(current, attack_index)


func preview_damage_for(attacker_index: int, attack_index: int) -> int:
	var attacker := players[attacker_index].active
	var defender := players[opponent_of(attacker_index)].active
	var attack := attacker.card().attacks[attack_index]
	var damage := attack.damage + players[attacker_index].damage_boost \
		+ _buff_amount(attacker_index, "damage-bonus")
	if defender.card().weakness == attacker.card().dino_type:
		damage *= 2
	elif defender.card().resistance == attacker.card().dino_type:
		damage = maxi(0, damage - 20)
	return damage


## Indices of the attacks `player_index`'s active can pay for (energy count).
func affordable_attacks(player_index: int) -> Array[int]:
	var result: Array[int] = []
	var active := players[player_index].active
	if active == null:
		return result
	var attacks := active.card().attacks
	for a in range(attacks.size()):
		if active.energy >= attacks[a].cost.size():
			result.append(a)
	return result


func max_hp_of(dino: DinoInPlay) -> int:
	for index in range(2):
		if players[index].dinos_in_play().has(dino):
			return _max_hp_of(dino, index)
	return dino.card().hp


# ── turn flow ─────────────────────────────────────────────────────────


func _begin_turn() -> void:
	var player := players[current]
	player.reset_turn_flags()
	_log("%s gains 1 %s energy." % [
		_name(current), CardCatalogTypes.TYPE_NAMES[player.element]])
	if player.draw() > 0:
		_log("%s draws a card." % _name(current))


func _end_turn() -> void:
	_checkup()
	if is_over():
		return
	players[current].damage_boost = 0
	if players[current].active.has_status(STATUS_PARALYZED):
		players[current].active.statuses.erase(STATUS_PARALYZED)
		_log("%s's %s recovers from paralysis." % [
			_name(current), _card_name(players[current].active.card_id)])
	current = opponent_of(current)
	turn_number += 1
	_begin_turn()


## Between-turns checkup: poison ticks, sleep wake-up coins, Environment
## healing for matching actives.
func _checkup() -> void:
	for index in range(2):
		var active := players[index].active
		if active.has_status(STATUS_POISONED):
			active.damage += POISON_DAMAGE
			_log("%s takes %d poison damage." % [_card_name(active.card_id), POISON_DAMAGE])
		if active.has_status(STATUS_ASLEEP) and _rng.randf() < 0.5:
			active.statuses.erase(STATUS_ASLEEP)
			_log("%s wakes up." % _card_name(active.card_id))
		var heal := _buff_amount(index, "heal-per-turn")
		if heal > 0 and active.damage > 0:
			active.damage = maxi(0, active.damage - heal)
	for index in range(2):
		_check_ko(index)
		if is_over():
			return


## Every knockout scores exactly 1; 3 knockouts win the game.
func _check_ko(defender_index: int) -> void:
	var defender := players[defender_index]
	if defender.active == null \
			or defender.active.damage < _max_hp_of(defender.active, defender_index):
		return
	var attacker := players[opponent_of(defender_index)]
	var koed := defender.active
	_log("%s is knocked out!" % _card_name(koed.card_id))
	defender.discard.append(koed.card_id)

	attacker.points += 1
	_log("%s has %d / %d knockouts." % [
		_name(opponent_of(defender_index)), attacker.points, POINTS_TO_WIN])
	if attacker.points >= POINTS_TO_WIN:
		_declare_winner(opponent_of(defender_index))
		return
	if defender.bench.is_empty():
		defender.active = null
		_log("%s has no dinosaur to promote!" % _name(defender_index))
		_declare_winner(opponent_of(defender_index))
		return
	var best := 0
	for b in range(defender.bench.size()):
		if _remaining_hp(defender.bench[b], defender_index) \
				> _remaining_hp(defender.bench[best], defender_index):
			best = b
	defender.active = defender.bench[best]
	defender.bench.remove_at(best)
	defender.active.clear_statuses()
	_log("%s sends out %s." % [_name(defender_index), _card_name(defender.active.card_id)])


func _declare_winner(index: int) -> void:
	winner = index
	_log("%s wins the battle!" % _name(index))


# ── environment buffs ─────────────────────────────────────────────────


## Buff value of `buff_type` for this player's ACTIVE (0 when the active's
## type doesn't match the Environment's type, or no Environment is set).
func _buff_amount(player_index: int, buff_type: String) -> int:
	var player := players[player_index]
	if player.environment_id == "" or player.active == null:
		return 0
	var environment := GameData.get_card(player.environment_id) as FieldCardData
	if environment.dino_type != player.active.card().dino_type:
		return 0
	if str(environment.buff.get("type", "")) != buff_type:
		return 0
	return maxi(1, int(environment.buff.get("amount", 0)))


func _has_buff(player_index: int, buff_type: String) -> bool:
	return _buff_amount(player_index, buff_type) > 0


func _max_hp_of(dino: DinoInPlay, owner_index: int) -> int:
	var hp := dino.card().hp
	if dino == players[owner_index].active:
		if _has_buff(owner_index, "hp-bonus"):
			hp += int((GameData.get_card(players[owner_index].environment_id)
				as FieldCardData).buff["amount"])
	return hp


func retreat_cost(player_index: int) -> int:
	if _has_buff(player_index, "free-retreat"):
		return 0
	return players[player_index].active.card().retreat_cost


# ── setup + helpers ───────────────────────────────────────────────────


func _dominant_type(deck: Array) -> int:
	var totals: Dictionary = {}
	for id: String in deck:
		var card := GameData.get_card(id)
		if card is DinoCardData:
			var t := (card as DinoCardData).dino_type
			totals[t] = int(totals.get(t, 0)) + 1
	var best: int = CardCatalogTypes.DinoType.CARNIVORE
	var best_count := -1
	for t: int in totals:
		if totals[t] > best_count:
			best = t
			best_count = totals[t]
	return best


## Draw 6; redraw until the hand holds a basic Dinosaur AND an Environment.
func _draw_opening_hand(player: BattlePlayerState) -> void:
	player.draw(OPENING_HAND)
	while not (player.has_basic_in_hand() and player.has_environment_in_hand()):
		player.deck.append_array(player.hand)
		player.hand.clear()
		_shuffle(player.deck)
		player.draw(OPENING_HAND)


## Setup: place the Environment, the best Active (preferring Environment
## synergy, then HP) and up to 3 more basics on the Back slots.
func _auto_setup(player: BattlePlayerState, index: int) -> void:
	var environments: Array[String] = []
	var basics: Array[String] = []
	for id: String in player.hand:
		var card := GameData.get_card(id)
		if card is FieldCardData:
			environments.append(id)
		elif card is DinoCardData and (card as DinoCardData).stage == 1:
			basics.append(id)

	# Prefer the Environment whose type matches the most basics in hand.
	var best_env := environments[0]
	var best_matches := -1
	for env_id: String in environments:
		var env := GameData.get_card(env_id) as FieldCardData
		var matches := 0
		for id: String in basics:
			if (GameData.get_card(id) as DinoCardData).dino_type == env.dino_type:
				matches += 1
		if matches > best_matches:
			best_matches = matches
			best_env = env_id
	player.environment_id = best_env
	player.hand.erase(best_env)
	var env_card := GameData.get_card(best_env) as FieldCardData
	_log("%s sets Environment: %s." % [_name(index), env_card.display_name])

	basics.sort_custom(func(a: String, b: String) -> bool:
		var card_a := GameData.get_card(a) as DinoCardData
		var card_b := GameData.get_card(b) as DinoCardData
		var match_a := 1 if card_a.dino_type == env_card.dino_type else 0
		var match_b := 1 if card_b.dino_type == env_card.dino_type else 0
		if match_a != match_b:
			return match_a > match_b
		return card_a.hp > card_b.hp)

	player.active = DinoInPlay.new(basics[0], 0)
	player.hand.erase(basics[0])
	_log("%s sends out %s." % [_name(index), _card_name(player.active.card_id)])
	if (GameData.get_card(player.active.card_id) as DinoCardData).dino_type \
			== env_card.dino_type:
		_log("%s's Environment empowers %s!" % [
			_name(index), _card_name(player.active.card_id)])
	# Back slots stay empty here: a player fills their own bench during their
	# own turn, so neither side sees the other develop before acting.


func _search_basic_dino(player: BattlePlayerState) -> void:
	var candidates: Array[int] = []
	for i in range(player.deck.size()):
		var card := GameData.get_card(player.deck[i])
		if card is DinoCardData and (card as DinoCardData).stage == 1:
			candidates.append(i)
	if candidates.is_empty():
		_log("…but found no basic dinosaur in the deck.")
		return
	var pick := candidates[_rng.randi_range(0, candidates.size() - 1)]
	var id: String = player.deck.pop_at(pick)
	player.hand.append(id)
	_log("%s adds %s to their hand." % [_name(current), _card_name(id)])


## `-1` targets the active dino, `0..` the bench.
func _target_dino(player: BattlePlayerState, target: int) -> DinoInPlay:
	return player.active if target == -1 else player.bench[target]


func _remaining_hp(dino: DinoInPlay, owner_index: int) -> int:
	return _max_hp_of(dino, owner_index) - dino.damage


func _shuffle(cards: Array) -> void:
	for i in range(cards.size() - 1, 0, -1):
		var j := _rng.randi_range(0, i)
		var tmp: Variant = cards[i]
		cards[i] = cards[j]
		cards[j] = tmp


func _name(index: int) -> String:
	return "You" if index == 0 else "Rival"


func _card_name(id: String) -> String:
	return GameData.get_card(id).display_name


func _log(text: String) -> void:
	log_history.append(text)
	log_line.emit(text)
