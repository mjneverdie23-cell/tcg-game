extends Node
## Headless test: every script in the project compiles. Run with:
##
##   godot --headless --path godot res://scenes/tests/compile_check.tscn
##
## GDScript is only compiled when something loads it, so a script nobody
## touched on the way through a test can carry a broken identifier for a
## long time and only fail in front of a player. Loading all of them here
## makes that a build error instead.
##
## This has to run inside the game rather than through `--check-only`,
## because a script that mentions an autoload does not compile without the
## autoloads registered — which is exactly what running the project does.

const ROOT := "res://"
## Directories with nothing to compile.
const SKIP := [".godot", ".import", "assets", "database"]


func _ready() -> void:
	var scripts := _find_scripts(ROOT)
	scripts.sort()
	var failed: Array[String] = []
	for path: String in scripts:
		# A script that fails to compile prints its own errors and loads as
		# null; that is the whole test.
		if load(path) == null:
			failed.append(path)
	print("compiled %d / %d scripts" % [scripts.size() - failed.size(), scripts.size()])
	if failed.is_empty():
		print("COMPILE CHECK PASS")
		get_tree().quit(0)
		return
	for path: String in failed:
		print("  FAILED: %s" % path)
	print("COMPILE CHECK FAIL — %d script(s) did not compile" % failed.size())
	get_tree().quit(1)


func _find_scripts(directory: String) -> Array[String]:
	var found: Array[String] = []
	var dir := DirAccess.open(directory)
	if dir == null:
		return found
	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		var path := directory.path_join(entry)
		if dir.current_is_dir():
			if not SKIP.has(entry):
				found.append_array(_find_scripts(path))
		elif entry.ends_with(".gd"):
			found.append(path)
		entry = dir.get_next()
	dir.list_dir_end()
	return found
