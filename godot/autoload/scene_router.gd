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
## Quest-chain match index the next battle should run, or -1 for a free
## battle against a randomly drafted rival. Same scope as battle_ranked:
## it describes the transition, not the profile.
var quest_match: int = -1

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
	var previous := _current
	if not _change(screen):
		return  # the visited path only records journeys that happened
	if TAB_SCREENS.has(screen):
		# Tabs are siblings, not descendants: back from any tab means home.
		# Rebuilt in place rather than reassigned — an array literal is an
		# untyped Array, which cannot be assigned to an Array[String].
		_stack.clear()
		if screen != "main_menu":
			_stack.append("main_menu")
	else:
		_stack.append(previous)


func back() -> void:
	var previous: String = _stack.pop_back() if not _stack.is_empty() else "main_menu"
	_change(previous)


## Swaps in a screen. Returns false (and says why) when the scene cannot be
## loaded: change_scene_to_file() reports that by return code rather than by
## raising, so without this check a broken scene would leave the player
## staring at an unchanged screen with nothing in the log — and `_current`
## would still have advanced, making that screen permanently unreachable
## because go_to() would then treat it as where we already are.
func _change(screen: String) -> bool:
	var path: String = SCREENS[screen]
	var result := get_tree().change_scene_to_file(path)
	if result != OK:
		push_error("SceneRouter: cannot open '%s' (%s) — error %d." % [screen, path, result])
		return false
	_current = screen
	return true
