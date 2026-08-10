extends Node
## Headless battle-engine test: AI vs AI across seeded games, asserting the
## rules invariants hold and every game terminates. Run with:
##
##   godot --headless --path godot res://scenes/tests/battle_sim.tscn
##
## Exits 0 when all games pass; prints per-game results.

const GAMES := 25
const ACTION_SAFETY_CAP := 2000


func _ready() -> void:
	var failures := 0
	for game in range(GAMES):
		var report := _run_game(game)
		print("game %02d: %s" % [game, report])
		if report.begins_with("FAIL"):
			failures += 1
	if failures == 0:
		print("BATTLE SIM PASS — %d/%d games completed legally" % [GAMES, GAMES])
	else:
		print("BATTLE SIM FAIL — %d/%d games failed" % [failures, GAMES])
	get_tree().quit(failures)


func _run_game(seed_value: int) -> String:
	# Both sides get full-ownership auto-built decks of a seeded random type.
	var owned: Dictionary = {}
	for card: CardData in GameData.all_cards():
		owned[card.id] = 2
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var deck_a := DeckRules.auto_build(owned, rng.randi_range(0, 3))
	var deck_b := DeckRules.auto_build(owned, rng.randi_range(0, 3))
	if not DeckRules.validate(deck_a).is_empty() or not DeckRules.validate(deck_b).is_empty():
		return "FAIL: auto-built deck is not legal"

	var engine := BattleEngine.new(deck_a, deck_b, seed_value)
	var ai := BattleAI.new()
	var actions := 0
	while not engine.is_over() and actions < ACTION_SAFETY_CAP:
		if not engine.apply(ai.choose_action(engine)):
			return "FAIL: AI produced an illegal action"
		actions += 1

	if not engine.is_over():
		return "FAIL: no winner after %d actions" % ACTION_SAFETY_CAP
	if engine.winner < 0 or engine.winner > 1:
		return "FAIL: bad winner index %d" % engine.winner
	var loser := engine.opponent_of(engine.winner)
	var winner_points := engine.players[engine.winner].points
	var loser_alive := engine.players[loser].active != null
	if winner_points < BattleEngine.POINTS_TO_WIN and loser_alive:
		return "FAIL: premature win (%d points, loser alive)" % winner_points
	return "OK: winner=%d, points %d-%d, %d actions, %d turns" % [
		engine.winner, winner_points, engine.players[loser].points,
		actions, engine.turn_number]
