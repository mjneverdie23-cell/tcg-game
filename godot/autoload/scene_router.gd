extends Node
## Autoload: screen navigation. Screens are addressed by name so callers never
## hardcode scene paths; `back()` retraces the visited path like a mobile app.

const SCREENS: Dictionary = {
	"main_menu": "res://scenes/menus/main_menu.tscn",
	"settings": "res://scenes/menus/settings.tscn",
	"collection": "res://scenes/collection/collection.tscn",
	"deck_builder": "res://scenes/deckbuilder/deck_builder.tscn",
	"shop": "res://scenes/shop/shop.tscn",
	"battle": "res://scenes/battle/battle.tscn",
}

var _stack: Array[String] = []
var _current: String = "main_menu"


func go_to(screen: String) -> void:
	if not SCREENS.has(screen):
		push_error("SceneRouter: unknown screen '%s'" % screen)
		return
	if screen == _current:
		return
	_stack.append(_current)
	_change(screen)


func back() -> void:
	var previous: String = _stack.pop_back() if not _stack.is_empty() else "main_menu"
	_change(previous)


func _change(screen: String) -> void:
	_current = screen
	get_tree().change_scene_to_file(SCREENS[screen])
