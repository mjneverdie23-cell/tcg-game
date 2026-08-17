class_name BattleEngine
extends RefCounted
## The battle rules engine (official ruleset). Pure game logic: no nodes,
## no UI. The human UI and the AI drive it exclusively through
## get_legal_actions() / apply(), so neither can cheat.
##
## Rules:
## - 23-card decks (validated by DeckRules). Coin flip assigns Heads/Tails
##   and the first turn. Both players draw 6, redrawing until the hand holds
##   an Environment and (deck permitting) two basic Dinosaurs, so a single
##   knockout can never end the game on the spot.
## - Setup places only each player's Environment. Every dinosaur — the
##   Active included — is fielded by its owner during their own turn, so
##   neither side sees the other develop before acting.
## - Energy is auto-generated: 1 unit of the player's element per turn,
##   attachable to one dinosaur. Attack costs are paid by energy count.
## - Every turn begins with a draw. Turn 1 (the player who won the toss):
##   energy + Spell cards, place basics, retreat — no attack, no Support.
##   Turn 2 onward: the full flow (draw, energy, Spells, one Support,
##   Environment replacement, evolve, retreat once, attack once).
## - Each player's Environment passively buffs their own Active while its
##   type matches; it stays until replaced.
## - Damage: base + boosts, x2 weakness, -20 resistance. Statuses:
##   poisoned / asleep / paralyzed via signature attacks.
## - Win: knock out 2 opposing Dinosaurs, or the opponent cannot promote a
##   replacement Active. Promotion is judged at the START of the affected
##   player's turn, after their draw — losing your last dinosaur leaves the
##   Active slot empty (and unattackable) instead of ending the battle
##   immediately, so an unlucky opening hand is survivable.

signal log_line(text: String)

const POINTS_TO_WIN := 2
const BENCH_SIZE := 3
const OPENING_HAND := 6
## Basic Dinosaurs the opening hand aims for. One is the hard minimum (the
## first turn must field an Active); the second is what keeps a knockout
## from being an instant loss.
const MIN_OPENING_BASICS := 2
## Cap on redraws spent chasing MIN_OPENING_BASICS. A deck that simply does
## not hold two basics would otherwise mulligan forever.
const MULLIGAN_ATTEMPTS := 20

## A player is never beaten for an empty Active slot before this turn is
## past: an unlucky opening is something to draw out of, not something to
## lose to before anyone has played a card.
const EMPTY_ACTIVE_GRACE_TURNS := 2
## Conceding unlocks after this turn. Long enough that a match cannot be
## thrown away in its opening moments; the point is to leave a battle that
## is already lost, not to skip one.
const SURRENDER_TURN := 10

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

	# The Environment goes down before anything else: it is the ground the
	# battle is fought on, and both players set theirs on their first turn.
	# Gated on actually holding one — a hand that drew none must still be
	# playable, and can set one whenever it turns up.
	if player.environment_id == "" and player.has_environment_in_hand():
		for i in range(player.hand.size()):
			if GameData.get_card(player.hand[i]) is FieldCardData:
				actions.append({"type": "environment", "hand": i})
		return actions

	# A player with an empty Active slot must field a dinosaur first.
	if player.active == null:
		for i in range(player.hand.size()):
			var card := GameData.get_card(player.hand[i])
			if card is DinoCardData and (card as DinoCardData).stage == 1:
				# Slot -1 is the Active place, which is the only one on offer
				# while it stands empty.
				actions.append({"type": "place_basic", "hand": i, "slot": -1})
		if actions.is_empty():
			actions.append({"type": "end_turn"})  # nothing to field this turn
		if turn_number > SURRENDER_TURN:
			# Conceding stays available with an empty Active slot: a player
			# with nothing left to field is exactly who wants to concede.
			actions.append({"type": "surrender"})
		return actions

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
			# Replacing one already down; the first is handled by the gate
			# at the top, which is legal on any turn.
			if (card as FieldCardData).id != player.environment_id:
				actions.append({"type": "environment", "hand": i})

	_add_retreat_actions(actions, player)
	_add_attack_actions(actions, player)
	if turn_number > SURRENDER_TURN:
		actions.append({"type": "surrender"})
	actions.append({"type": "end_turn"})
	return actions


## Bench places nobody is standing in, left to right. The bench array is
## packed, so this is derived from where its dinosaurs say they stand.
func free_bench_slots(player: BattlePlayerState) -> Array[int]:
	var taken: Dictionary = {}
	for dino: DinoInPlay in player.bench:
		taken[dino.slot] = true
	var free: Array[int] = []
	for slot in range(BENCH_SIZE):
		if not taken.has(slot):
			free.append(slot)
	return free


func _add_dino_actions(
		actions: Array[Dictionary], player: BattlePlayerState,
		card: DinoCardData, hand_index: int) -> void:
	if card.stage == 1:
		# One action per empty bench place: where a dinosaur stands is the
		# player's to choose, not the order they happened to play them in.
		for slot: int in free_bench_slots(player):
			actions.append({"type": "place_basic", "hand": hand_index, "slot": slot})
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
			# Same as retreat: the turn-1 rule is about attacks and Supports,
			# and a Support has already been filtered out above.
			for b in range(player.bench.size()):
				actions.append({"type": "trainer", "hand": hand_index, "target": b})
		"heal":
			if player.active.damage > 0:
				actions.append({"type": "trainer", "hand": hand_index})
		_:
			actions.append({"type": "trainer", "hand": hand_index})


func _add_retreat_actions(actions: Array[Dictionary], player: BattlePlayerState) -> void:
	# Turn 1 withholds attacks and Supports, nothing else. Retreating costs
	# energy and a card's place on the Active slot, so there is no reason to
	# lock it out of the opening turn as well.
	if player.retreated or player.bench.is_empty():
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
	if players[opponent_of(current)].active == null:
		return  # nothing on the other side to hit yet
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
			_do_place_basic(action["hand"], int(action["slot"]))
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
		"surrender":
			_do_surrender()
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


func _do_place_basic(hand_index: int, slot: int) -> void:
	var player := players[current]
	var id: String = player.hand.pop_at(hand_index)
	if slot < 0:
		player.active = DinoInPlay.new(id, turn_number)
		_log("%s sends out %s." % [_name(current), _card_name(id)])
		if player.environment_id != "":
			var env := GameData.get_card(player.environment_id) as FieldCardData
			if (GameData.get_card(id) as DinoCardData).dino_type == env.dino_type:
				_log("%s's Environment empowers %s!" % [_name(current), _card_name(id)])
		return
	var benched := DinoInPlay.new(id, turn_number)
	benched.slot = slot
	player.bench.append(benched)
	_log("%s benches %s." % [_name(current), _card_name(id)])


## Trades the Active for a benched dinosaur. The one stepping back takes
## the place the one stepping up was standing in, so the row never opens a
## hole and nothing shuffles sideways on the table.
func _swap_active_with_bench(player: BattlePlayerState, bench_index: int) -> void:
	var incoming := player.bench[bench_index]
	var outgoing := player.active
	outgoing.slot = incoming.slot
	incoming.slot = -1
	player.bench[bench_index] = outgoing
	player.active = incoming


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
	_swap_active_with_bench(player, bench_index)
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
			player.active.clear_statuses()
			_swap_active_with_bench(player, target)
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
	# A side that has not fielded an Active yet has no HP to report; callers
	# probing the opposing board rely on this rather than crashing.
	if dino == null:
		return 0
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
	# Promotion check. A player caught between dinosaurs keeps their empty
	# Active slot until their own turn comes round, so the draw above is
	# their last chance to find a replacement — only now can they truly be
	# said to be unable to promote.
	if player.active == null and not player.has_basic_in_hand():
		if turn_number <= EMPTY_ACTIVE_GRACE_TURNS:
			# Too early to lose a battle nobody has played yet: an opening
			# hand with no dinosaur in it gets another draw to find one.
			_log("%s has no dinosaur to send out yet." % _name(current))
		else:
			_log("%s cannot send out a dinosaur — none left in hand!" % _name(current))
			_declare_winner(opponent_of(current))


func _end_turn() -> void:
	_checkup()
	if is_over():
		return
	players[current].damage_boost = 0
	if players[current].active != null and players[current].active.has_status(STATUS_PARALYZED):
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
		if active == null:
			continue  # this player has not fielded an Active yet
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


## Every knockout scores exactly 1; POINTS_TO_WIN of them win the game.
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
		# Dinosaurs are fielded in-turn now, so an empty bench is a normal
		# state early on rather than proof the player is finished. The slot
		# simply stays empty — nothing can attack an empty Active — and the
		# player sends out a replacement on their own turn. _begin_turn ends
		# the battle if their draw still leaves them with nothing to field.
		defender.active = null
		if defender.has_basic_in_hand() or not defender.deck.is_empty():
			_log("%s must send out a new dinosaur next turn — nothing is in play!"
				% _name(defender_index))
			return
		_log("%s cannot promote a replacement Active!" % _name(defender_index))
		_declare_winner(opponent_of(defender_index))
		return
	var best := 0
	for b in range(defender.bench.size()):
		if _remaining_hp(defender.bench[b], defender_index) \
				> _remaining_hp(defender.bench[best], defender_index):
			best = b
	defender.active = defender.bench[best]
	defender.bench.remove_at(best)
	defender.active.slot = -1  # it is standing in the Active place now
	defender.active.clear_statuses()
	_log("%s sends out %s." % [_name(defender_index), _card_name(defender.active.card_id)])


## Conceding. Only legal from SURRENDER_TURN onward — see get_legal_actions.
func _do_surrender() -> void:
	_log("%s surrenders." % _name(current))
	_declare_winner(opponent_of(current))


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


## Draws the opening hand.
##
## Hard requirement — deck legality guarantees it is reachable, so this loop
## is unbounded: one basic Dinosaur (the first turn must field an Active)
## and one Environment (setup places one).
##
## Soft requirement — retried at most MULLIGAN_ATTEMPTS times: a second basic
## Dinosaur. Opening with a single dinosaur used to mean the first knockout
## ended the battle outright, which reads as losing to the shuffle rather
## than to the rival.
func _draw_opening_hand(player: BattlePlayerState) -> void:
	var mulligans := 0
	player.draw(OPENING_HAND)
	while not _hand_is_playable(player) or (mulligans < MULLIGAN_ATTEMPTS
			and player.count_basics_in_hand() < MIN_OPENING_BASICS):
		player.deck.append_array(player.hand)
		player.hand.clear()
		_shuffle(player.deck)
		player.draw(OPENING_HAND)
		mulligans += 1


func _hand_is_playable(player: BattlePlayerState) -> bool:
	return player.has_basic_in_hand() and player.has_environment_in_hand()


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
