extends Node
## Autoload: screen navigation. Screens are addressed by name so callers never
## hardcode scene paths; `back()` retraces the visited path like a mobile app.
##
## The six names the bottom tab bar uses (see NavBar.TABS) are top-level
## destinations: switching between them replaces the visited path rather than
## stacking, so tab-hopping can never build an unbounded back stack.

const SCREENS: Dictionary = {
	"main_menu": "res://scenes/menus/main_menu.tscn",
	"settings": "res://scenes/menus/settings.tscn",
	"profile": "res://scenes/menus/profile.tscn",
	"collection": "res://scenes/collection/collection.tscn",
	"shop": "res://scenes/shop/shop.tscn",
	"packs": "res://scenes/packs/packs.tscn",
	"battle": "res://scenes/battle/battle.tscn",
}

## Screens reachable from the tab bar. Home stays the root of the stack.
const TAB_SCREENS: Array = [
	"main_menu", "shop", "collection", "packs", "settings", "profile",
]

## Battle mode picked on the home screen and read by the battle screen when
## it starts a match. Navigation-scoped: it describes the transition, not the
## profile, so it deliberately does not survive a restart.
var battle_ranked: bool = true

var _stack: Array[String] = []
var _current: String = "main_menu"


## Name of the screen currently on display — the tab bar highlights it.
func current() -> String:
	return _current


func go_to(screen: String) -> void:
	if not SCREENS.has(screen):
		push_error("SceneRouter: unknown screen '%s'" % screen)
		return
	if screen == _current:
		return
	if TAB_SCREENS.has(screen):
		# Tabs are siblings, not descendants: back from any tab means home.
		_stack = [] if screen == "main_menu" else ["main_menu"]
	else:
		_stack.append(_current)
	_change(screen)


func back() -> void:
	var previous: String = _stack.pop_back() if not _stack.is_empty() else "main_menu"
	_change(previous)


func _change(screen: String) -> void:
	_current = screen
	get_tree().change_scene_to_file(SCREENS[screen])
