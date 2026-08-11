extends Control
## Shop tab — where coins come from.
##
## This build has no payment backend, so coins are earned rather than bought:
## a free daily stipend on a 24 h timer, and a conversion that turns surplus
## card copies (anything beyond the two a deck may legally hold) into coins.
## Packs are spent on the Packs tab; nothing here consumes coins.

const DAILY_COINS := 200

var _tick_accumulator := 0.0


func _ready() -> void:
	%BackButton.pressed.connect(SceneRouter.back)
	%ClaimButton.pressed.connect(_on_claim_pressed)
	%SellButton.pressed.connect(_on_sell_pressed)
	PlayerData.coins_changed.connect(func(_amount: int) -> void: _refresh())
	PlayerData.collection_changed.connect(_refresh)
	_style()
	_refresh()


func _process(delta: float) -> void:
	_tick_accumulator += delta
	if _tick_accumulator >= 1.0:  # the countdown only needs second resolution
		_tick_accumulator = 0.0
		_refresh_claim()


func _style() -> void:
	%DailyPanel.add_theme_stylebox_override("panel", MenuStyle.panel())
	%SellPanel.add_theme_stylebox_override("panel", MenuStyle.panel())
	MenuStyle.style_pill(%CoinsPill)
	MenuStyle.style_button(%ClaimButton, true)
	MenuStyle.style_button(%SellButton, true)
	MenuStyle.style_button(%BackButton)
	%DailyReward.text = "+%d coins" % DAILY_COINS


func _refresh() -> void:
	%CoinsLabel.text = "%d" % PlayerData.coins
	_refresh_claim()
	_refresh_sell()


func _refresh_claim() -> void:
	var now := int(Time.get_unix_time_from_system())
	if PlayerData.is_daily_coins_ready(now):
		%ClaimButton.text = "Claim"
		%ClaimButton.disabled = false
		%DailyStatus.text = "Ready to collect."
		return
	var wait := PlayerData.last_coin_claim + PlayerData.DAILY_PACK_COOLDOWN_SECONDS - now
	%ClaimButton.text = "Collected"
	%ClaimButton.disabled = true
	%DailyStatus.text = "Next stipend in %s." % _format_countdown(wait)


func _refresh_sell() -> void:
	var surplus := CollectionEconomy.surplus_of(PlayerData.owned_cards)
	var copies := int(surplus["copies"])
	%SellSummary.text = (
		"No surplus copies right now."
		if copies == 0
		else "%d spare copy(s) worth %d coins." % [copies, int(surplus["value"])])
	%SellButton.disabled = copies == 0
	%SellButton.text = "Convert" if copies == 0 else "Convert for %d" % int(surplus["value"])


func _on_claim_pressed() -> void:
	if PlayerData.claim_daily_coins(int(Time.get_unix_time_from_system()), DAILY_COINS):
		%DailyStatus.text = "+%d coins collected." % DAILY_COINS


func _on_sell_pressed() -> void:
	var sold := PlayerData.sell_surplus()
	if int(sold["copies"]) > 0:
		%SellSummary.text = "Converted %d copy(s) into %d coins." % [
			int(sold["copies"]), int(sold["value"])]


func _format_countdown(seconds: int) -> String:
	seconds = maxi(0, seconds)
	@warning_ignore("integer_division")
	return "%dh %02dm %02ds" % [seconds / 3600, (seconds % 3600) / 60, seconds % 60]
