class_name BattleLink
extends Node
## Keeps this screen's battle in step with the opponent's.
##
## Nothing about the board is sent across. Both machines built the same
## engine from the same decks and the same seed, so replaying the same moves
## in the same order lands them on the same state — the wire only carries
## the moves. What it also carries is a fingerprint of the state each move
## produced, and that is the whole safety net: if the two engines ever
## disagree by so much as one card, the very next move says so and the match
## stops, rather than the two players quietly playing different games.
##
## Arriving moves are checked against the rules before they are applied, so
## a modified build cannot make a play this engine would not allow, nor act
## out of turn.

## A legal move arrived. Listeners apply it; the checksum is compared as
## soon as they return, so this must be handled synchronously.
signal remote_action(action: Dictionary)
## The two games no longer match, or the opponent broke the rules.
signal desynced(reason: String)

var _engine: BattleEngine = null
var _seat := 0


func _ready() -> void:
	Net.action_received.connect(_on_action_received)


## Binds the link to the battle it is mirroring. Called once a match starts.
func attach(engine: BattleEngine, seat: int) -> void:
	_engine = engine
	_seat = seat


## Publishes a move the local player just made, with the state it produced.
func publish(action: Dictionary) -> void:
	if _engine == null:
		return
	Net.send_action(action, checksum())


## Fingerprint of everything both engines must agree on. Deliberately whole
## rather than clever: the zones, the board and the turn flags, so a drift
## anywhere shows up here rather than in a rule three turns later.
func checksum() -> int:
	if _engine == null:
		return 0
	var parts: Array = [_engine.turn_number, _engine.current, _engine.winner]
	for player: BattlePlayerState in _engine.players:
		var bench: Array = []
		for dino: DinoInPlay in player.bench:
			bench.append(_fingerprint(dino))
		parts.append([
			player.deck, player.hand, player.discard, player.points,
			player.environment_id, player.element, player.energy_budget,
			player.support_played, player.retreated, player.damage_boost,
			_fingerprint(player.active), bench,
		])
	return hash(parts)


func _fingerprint(dino: DinoInPlay) -> Array:
	if dino == null:
		return []
	return [
		dino.card_id, dino.damage, dino.energy, dino.statuses,
		dino.turn_entered, dino.slot,
	]


func _on_action_received(action: Dictionary, their_checksum: int) -> void:
	if _engine == null or _engine.is_over():
		return
	if _engine.current == _seat:
		desynced.emit("Your opponent played out of turn.")
		return
	if not _engine.get_legal_actions().any(
			func(legal: Dictionary) -> bool: return legal == action):
		desynced.emit("Your opponent sent a move the rules do not allow.")
		return
	remote_action.emit(action)
	if checksum() != their_checksum:
		desynced.emit("The two games drifted apart, so the match cannot go on.")
