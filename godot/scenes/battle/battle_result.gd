class_name BattleResult
extends Node
## The panel that closes a battle: what happened, what it paid out, and the
## Claim button a quest match needs.
##
## Also the only place a battle turns into profile changes, so a battle can
## never pay twice however many times the screen refreshes after it ends.

## The player collected a quest reward; the screen may want to refresh.
signal claimed

const WIN_COINS := 50
const LOSS_COINS := 10

var _panel: Control
var _title: Label
var _detail: Label
var _claim: Button
## Set the first time an outcome is recorded. Everything else here is
## presentation and may run again; this must not.
var _paid := false
## Ladder swing from this battle, shown beside the coins (0 in practice).
var _trophy_delta := 0
var _quest_match := -1


func setup(panel: Control, title: Label, detail: Label, claim: Button) -> void:
	_panel = panel
	_title = title
	_detail = detail
	_claim = claim
	_claim.pressed.connect(_on_claim_pressed)


## A fresh battle: nothing paid, nothing shown.
func reset() -> void:
	_paid = false
	_trophy_delta = 0
	_quest_match = -1
	_claim.visible = false


func is_shown() -> bool:
	return _panel.visible


## The battle finished under its own rules. `quest_match` is the chain match
## being played or -1; `ranked` decides whether trophies are at stake.
func show_outcome(won: bool, quest_match: int, ranked: bool) -> void:
	_quest_match = quest_match
	# A quest match pays its own reward, and only when the player claims it,
	# so the automatic battle coins are skipped for a quest win.
	var quest_win := won and quest_match >= 0
	_title.text = "You won!" if won else "Defeat"
	if not _paid:
		_paid = true
		if quest_win:
			PlayerData.record_quest_win(quest_match)
		else:
			PlayerData.earn_coins(WIN_COINS if won else LOSS_COINS)
		_trophy_delta = PlayerData.record_battle(won, ranked)

	if quest_win:
		var reward := int(QuestRules.quest(quest_match)["reward"])
		var collected := QuestRules.state_of(quest_match) == QuestRules.STATE_CLAIMED
		_detail.text = "%s beaten  ·  reward %d coins" % [
			str(QuestRules.quest(quest_match)["title"]), reward]
		_claim.visible = true
		_claim.disabled = collected
		_claim.text = ("Claimed  ·  +%d coins" if collected else "Claim %d coins") % reward
	else:
		_claim.visible = false
		_detail.text = "+%d coins%s" % [
			WIN_COINS if won else LOSS_COINS,
			"" if _trophy_delta == 0 else "  ·  %+d trophies" % _trophy_delta]
	_open()


## The battle stopped for a reason outside the rules — an opponent who left,
## a link that fell apart. Nothing is paid: neither player finished.
func show_stopped(reason: String) -> void:
	if _panel.visible:
		return
	_title.text = "Match ended"
	_detail.text = reason
	_claim.visible = false
	_open()


func _on_claim_pressed() -> void:
	if not PlayerData.claim_quest(_quest_match):
		return
	_claim.disabled = true
	# Same wording show_outcome() uses, so a refresh cannot reword it.
	_claim.text = "Claimed  ·  +%d coins" % int(QuestRules.quest(_quest_match)["reward"])
	claimed.emit()


func _open() -> void:
	if _panel.visible:
		return  # already up; don't replay the entrance
	_panel.visible = true
	if Settings.reduced_motion:
		return
	_panel.modulate.a = 0.0
	_panel.scale = Vector2(0.85, 0.85)
	_panel.pivot_offset = _panel.size * 0.5
	var tween := _panel.create_tween()
	tween.tween_property(_panel, "modulate:a", 1.0, 0.25)
	tween.parallel().tween_property(_panel, "scale", Vector2.ONE, 0.4) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
