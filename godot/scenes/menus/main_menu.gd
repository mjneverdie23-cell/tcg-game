extends Control
## Main menu: entry point to every screen. Buttons route through SceneRouter;
## the coin balance stays in sync with PlayerData.


func _ready() -> void:
	%CoinsLabel.text = "%d coins" % PlayerData.coins
	PlayerData.coins_changed.connect(func(amount: int) -> void:
		%CoinsLabel.text = "%d coins" % amount)
	%BattleButton.pressed.connect(func() -> void: SceneRouter.go_to("battle"))
	%CollectionButton.pressed.connect(func() -> void: SceneRouter.go_to("collection"))
	%DeckBuilderButton.pressed.connect(func() -> void: SceneRouter.go_to("deck_builder"))
	%ShopButton.pressed.connect(func() -> void: SceneRouter.go_to("shop"))
	%SettingsButton.pressed.connect(func() -> void: SceneRouter.go_to("settings"))
