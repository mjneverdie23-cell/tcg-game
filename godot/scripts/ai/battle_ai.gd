class_name BattleAI
extends RefCounted
## The battle opponent (Milestone 6). Drives the game exclusively through
## BattleEngine.get_legal_actions() / apply(), so it plays by exactly the
## same rules as the human — it never cheats or peeks at hidden zones.
##
## Decision priority each step:
##   1. take a KO if one is available right now (least overkill first)
##   2. evolve (strictly better stats), bench a reserve basic
##   3. set an Environment matching its Active (live passive buff)
##   4. flee a doomed matchup (Dino Handler switch first — it's free —
##      else retreat) when the opponent can KO us and we can't KO back
##   5. attach the turn energy where it unlocks attacks
##   6. play trainers with sensible timing
##   7. strongest affordable attack
##   8. pass

const HEAL_THRESHOLD := 30
const BENCH_TARGET := 2

## How often the rival makes each of the mistakes a new player makes. One
## profile per quest-chain step; level 3 is the same sharp AI as before, with
## every rate at zero.
##
##   skip_energy    leaves the turn's energy unattached
##   end_early      ends the turn on the spot, wasting everything in hand
##   idle_retreat   retreats with no reason, burning the retreat cost
##   waste_trainer  plays a Spell or Support that does nothing useful
##   stop_attacking having attacked once, stops bothering to attack again
const PROFILES: Array = [
	{  # 0 — Field Scout: forgets the basics constantly
		"skip_energy": 0.5, "end_early": 0.3, "idle_retreat": 0.25,
		"waste_trainer": 0.5, "stop_attacking": 0.45,
	},
	{  # 1 — Bone Tracker: still sloppy, but attacks more
		"skip_energy": 0.28, "end_early": 0.15, "idle_retreat": 0.12,
		"waste_trainer": 0.3, "stop_attacking": 0.2,
	},
	{  # 2 — Ridge Warden: only the occasional slip
		"skip_energy": 0.1, "end_early": 0.04, "idle_retreat": 0.04,
		"waste_trainer": 0.12, "stop_attacking": 0.06,
	},
	{  # 3 — The Alpha: plays it straight
		"skip_energy": 0.0, "end_early": 0.0, "idle_retreat": 0.0,
		"waste_trainer": 0.0, "stop_attacking": 0.0,
	},
]

## Mistake rates in force, and the source of the rolls against them.
var profile: Dictionary = PROFILES[PROFILES.size() - 1]

var _rng := RandomNumberGenerator.new()
## Attacks landed this battle — `stop_attacking` only bites after the first.
var _attacks_made := 0


## Picks one action for the engine's current player. Called repeatedly until
## it returns a turn-ending action (attack / end_turn). Pickers are tried in
## priority order; the first non-empty candidate wins.
func choose_action(engine: BattleEngine) -> Dictionary:
	var actions := engine.get_legal_actions()
	# The Environment is set before anything else can happen.
	if engine.players[engine.current].environment_id == "":
		var setup := _pick_environment(engine, actions)
		if not setup.is_empty():
			return setup
	# With an empty Active slot, fielding one is the only legal move.
	if engine.players[engine.current].active == null:
		return _pick_opening_active(engine, actions)
	# Mistake: walk away from the turn with cards still in hand and energy
	# unspent. Never on turn 1, where there is nothing to give away yet.
	if engine.turn_number > 1 and _blunders("end_early"):
		return {"type": "end_turn"}
	var idle := _pick_idle_retreat(engine, actions)
	if not idle.is_empty():
		return idle
	var candidates: Array[Dictionary] = [
		_pick_ko_attack(engine, actions),
		_pick_development(engine, actions),
		_pick_field(engine, actions),
		_pick_escape_if_doomed(engine, actions),
		_pick_attach(engine, actions),
		_pick_trainer(engine, actions),
		_pick_best_attack(engine, actions),
	]
	for candidate: Dictionary in candidates:
		if not candidate.is_empty():
			if candidate["type"] == "attack":
				_attacks_made += 1
			return candidate
	return {"type": "end_turn"}


## Sets the mistake profile for this battle. `rng_seed` keeps a given match
## reproducible, which is what makes the quest chain testable.
func configure(level: int, rng_seed: int) -> void:
	profile = PROFILES[clampi(level, 0, PROFILES.size() - 1)]
	_rng.seed = rng_seed
	_attacks_made = 0


## True when the rival should make mistake `kind` this time.
func _blunders(kind: String) -> bool:
	var rate := float(profile.get(kind, 0.0))
	return rate > 0.0 and _rng.randf() < rate


## Mistake: retreating for no reason, which throws away the retreat cost and
## puts a fresh dinosaur in front of an attack it did not need to face.
func _pick_idle_retreat(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	if _is_doomed(engine) or not _blunders("idle_retreat"):
		return {}  # a retreat while doomed is sound play, not a blunder
	for action: Dictionary in actions:
		if action["type"] == "retreat":
			return action
	return {}


## The opening Active: prefer a basic matching our Environment (its passive
## buff only applies to a matching Active), then the toughest body.
## The Environment to lay down, preferring the one whose type the most
## dinosaurs in hand will actually benefit from. Empty when there is none to
## place, which is also how the caller knows to move on.
func _pick_environment(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	var me := engine.players[engine.current]
	var best: Dictionary = {}
	var best_matches := -1
	for action: Dictionary in actions:
		if action["type"] != "environment":
			continue
		var env := GameData.get_card(me.hand[int(action["hand"])]) as FieldCardData
		var matches := 0
		for id: String in me.hand:
			var card := GameData.get_card(id)
			if card is DinoCardData and (card as DinoCardData).dino_type == env.dino_type:
				matches += 1
		if matches > best_matches:
			best_matches = matches
			best = action
	return best


func _pick_opening_active(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	var me := engine.players[engine.current]
	var env_type := -1
	if me.environment_id != "":
		env_type = (GameData.get_card(me.environment_id) as FieldCardData).dino_type
	var best: Dictionary = {}
	var best_score := -1
	for action: Dictionary in actions:
		if action["type"] != "place_basic":
			continue
		var card := GameData.get_card(me.hand[action["hand"]]) as DinoCardData
		var score := card.hp + (500 if card.dino_type == env_type else 0)
		if score > best_score:
			best_score = score
			best = action
	return best if not best.is_empty() else {"type": "end_turn"}


## Evolutions always; bench a reserve basic while below the target.
func _pick_development(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	for action: Dictionary in actions:
		if action["type"] == "evolve":
			return action
	if engine.players[engine.current].bench.size() < BENCH_TARGET:
		for action: Dictionary in actions:
			if action["type"] == "place_basic":
				return action
	return {}


func _pick_escape_if_doomed(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	return _pick_escape(engine, actions) if _is_doomed(engine) else {}


# ── attacking ─────────────────────────────────────────────────────────


## A KO-securing attack with the least overkill, if any.
func _pick_ko_attack(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	var defender := engine.players[engine.opponent_of(engine.current)].active
	if defender == null:
		return {}
	var remaining := engine.max_hp_of(defender) - defender.damage
	var best: Dictionary = {}
	var best_damage := 0
	for action: Dictionary in actions:
		if action["type"] != "attack":
			continue
		var damage := engine.preview_damage(int(action["index"]))
		if damage >= remaining and (best.is_empty() or damage < best_damage):
			best = action
			best_damage = damage
	return best


func _pick_best_attack(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	# Mistake: attacking once early on and then never pressing the advantage.
	if _attacks_made > 0 and _blunders("stop_attacking"):
		return {}
	var me := engine.players[engine.current]
	var best: Dictionary = {}
	var best_score := 0
	for action: Dictionary in actions:
		if action["type"] != "attack":
			continue
		var attack := me.active.card().attacks[action["index"]]
		var score := engine.preview_damage(int(action["index"]))
		if BattleEngine.ATTACK_STATUS.has(attack.attack_name):
			score += 15  # statuses carry value beyond damage (and break walls)
		if best.is_empty() or score > best_score:
			best = action
			best_score = score
	# An attack worth nothing at all is worse than developing the board.
	return {} if best_score <= 0 else best


# ── fleeing ───────────────────────────────────────────────────────────


## Biggest hit the opponent's active can land on us next turn (with what it
## has attached right now — a fair, non-psychic estimate).
func _incoming_threat(engine: BattleEngine) -> int:
	var opponent := engine.opponent_of(engine.current)
	if engine.players[opponent].active == null:
		return 0
	var threat := 0
	for a: int in engine.affordable_attacks(opponent):
		threat = maxi(threat, engine.preview_damage_for(opponent, a))
	return threat


## Doomed = the opponent can KO our active before it can KO theirs.
func _is_doomed(engine: BattleEngine) -> bool:
	var me := engine.players[engine.current]
	var remaining := engine.max_hp_of(me.active) - me.active.damage
	if _incoming_threat(engine) < remaining:
		return false
	var defender := engine.players[engine.opponent_of(engine.current)].active
	if defender == null:
		return false  # nothing can hit us yet
	var their_remaining := engine.max_hp_of(defender) - defender.damage
	for a: int in engine.affordable_attacks(engine.current):
		if engine.preview_damage(a) >= their_remaining:
			return false  # we trade first — stay and take the point
	return true


## Prefer the free switch (Dino Handler) over paying retreat costs; pick the
## healthiest bench dinosaur to take over.
func _pick_escape(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	var me := engine.players[engine.current]
	var best_bench := -1
	for b in range(me.bench.size()):
		if best_bench == -1 or _remaining(engine, me.bench[b]) > _remaining(engine, me.bench[best_bench]):
			best_bench = b
	if best_bench == -1:
		return {}
	for action: Dictionary in actions:
		if action["type"] == "trainer" and int(action.get("target", -99)) == best_bench:
			var card := GameData.get_card(me.hand[action["hand"]]) as TrainerCardData
			if card.effect["type"] == "switch":
				return action
	for action: Dictionary in actions:
		if action["type"] == "retreat" and int(action["bench"]) == best_bench:
			return action
	return {}


func _remaining(engine: BattleEngine, dino: DinoInPlay) -> int:
	return engine.max_hp_of(dino) - dino.damage


# ── energy ────────────────────────────────────────────────────────────


## Ramp the active until all its attacks are payable, then fuel the bench.
func _pick_attach(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	# Mistake: the turn's energy is free and never comes back if unused.
	if _blunders("skip_energy"):
		return {}
	var me := engine.players[engine.current]
	var best: Dictionary = {}
	var best_score := -1
	for action: Dictionary in actions:
		if action["type"] != "attach":
			continue
		var target := int(action["target"])
		var dino := me.active if target == -1 else me.bench[target]
		var score := 0
		if target == -1:
			if engine.affordable_attacks(engine.current).size() < dino.card().attacks.size():
				score += 4  # active still ramping up
		elif dino.energy < 2:
			score += 2  # prepare the next attacker
		if score > best_score:
			best_score = score
			best = action
	return {} if best_score <= 0 else best


# ── trainers ──────────────────────────────────────────────────────────


func _pick_trainer(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	var me := engine.players[engine.current]
	for action: Dictionary in actions:
		if action["type"] != "trainer":
			continue
		var card := GameData.get_card(me.hand[action["hand"]]) as TrainerCardData
		# Mistake: firing off a Spell or Support that changes nothing, and
		# spending the one Support this turn allows on it.
		if _trainer_is_worth_it(engine, me, card) or _blunders("waste_trainer"):
			return action
	return {}


func _trainer_is_worth_it(
		engine: BattleEngine, me: BattlePlayerState, card: TrainerCardData) -> bool:
	var worth := false
	match str(card.effect["type"]):
		"heal":
			worth = me.active.damage >= HEAL_THRESHOLD
		"heal-all":
			var healing := 0
			for dino in me.dinos_in_play():
				healing += mini(dino.damage, int(card.effect["amount"]))
			worth = healing >= HEAL_THRESHOLD
		"draw":
			worth = me.hand.size() <= 4
		"draw-to":
			worth = me.hand.size() < int(card.effect["hand_size"])
		"search-dino":
			worth = me.dinos_in_play().size() < 2 or not me.has_basic_in_hand()
		"damage-boost":
			worth = _boost_secures_ko(engine, int(card.effect["amount"]))
		"bonus-energy":
			worth = engine.players[engine.current].energy_budget > 0
		_:
			worth = false  # switch is handled by the escape logic
	return worth


## Only burn Adrenaline Gland when +N turns an available attack into a KO.
func _boost_secures_ko(engine: BattleEngine, amount: int) -> bool:
	var defender := engine.players[engine.opponent_of(engine.current)].active
	if defender == null:
		return false  # nothing to knock out yet — the boost would be wasted
	var remaining := engine.max_hp_of(defender) - defender.damage
	for a: int in engine.affordable_attacks(engine.current):
		var damage := engine.preview_damage(a)
		if damage < remaining and damage + amount >= remaining:
			return true
	return false


# ── environments ──────────────────────────────────────────────────────


## Replace our Environment when a hand Environment matches our Active's
## type and the current one doesn't (synergy = live passive buff).
func _pick_field(engine: BattleEngine, actions: Array[Dictionary]) -> Dictionary:
	var me := engine.players[engine.current]
	var active_type := me.active.card().dino_type
	var current_matches := false
	if me.environment_id != "":
		current_matches = (
			GameData.get_card(me.environment_id) as FieldCardData).dino_type == active_type
	if current_matches:
		return {}
	for action: Dictionary in actions:
		if action["type"] != "environment":
			continue
		var card := GameData.get_card(me.hand[action["hand"]]) as FieldCardData
		if card.dino_type == active_type:
			return action
	return {}
