extends Control
## Settings screen: audio/motion toggles bound to the Settings autoload,
## plus a confirm-gated save reset.

var _confirming_reset: bool = false


func _ready() -> void:
	%MusicToggle.button_pressed = Settings.music_enabled
	%SfxToggle.button_pressed = Settings.sfx_enabled
	%ReducedMotionToggle.button_pressed = Settings.reduced_motion
	%MusicToggle.toggled.connect(func(on: bool) -> void: Settings.set_setting("music_enabled", on))
	%SfxToggle.toggled.connect(func(on: bool) -> void: Settings.set_setting("sfx_enabled", on))
	%ReducedMotionToggle.toggled.connect(func(on: bool) -> void:
		Settings.set_setting("reduced_motion", on))
	%ResetButton.pressed.connect(_on_reset_pressed)
	%BackButton.pressed.connect(SceneRouter.back)


func _on_reset_pressed() -> void:
	if not _confirming_reset:
		_confirming_reset = true
		%ResetButton.text = "Press again to confirm"
		return
	PlayerData.reset_all()
	_confirming_reset = false
	%ResetButton.text = "Reset save data"
