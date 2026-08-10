extends Node
## Autoload: user settings, persisted at user://settings.json.

const SETTINGS_PATH := "user://settings.json"

var music_enabled: bool = true
var sfx_enabled: bool = true
var reduced_motion: bool = false


func _ready() -> void:
	_load()


func set_setting(key: String, value: bool) -> void:
	match key:
		"music_enabled":
			music_enabled = value
		"sfx_enabled":
			sfx_enabled = value
		"reduced_motion":
			reduced_motion = value
		_:
			push_error("Settings: unknown key '%s'" % key)
			return
	_save()


func _save() -> void:
	var file := FileAccess.open(SETTINGS_PATH, FileAccess.WRITE)
	if file == null:
		push_error("Settings: cannot write %s" % SETTINGS_PATH)
		return
	file.store_string(JSON.stringify({
		"music_enabled": music_enabled,
		"sfx_enabled": sfx_enabled,
		"reduced_motion": reduced_motion,
	}, "\t"))


func _load() -> void:
	if not FileAccess.file_exists(SETTINGS_PATH):
		return
	var file := FileAccess.open(SETTINGS_PATH, FileAccess.READ)
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	var data: Dictionary = parsed
	music_enabled = bool(data.get("music_enabled", true))
	sfx_enabled = bool(data.get("sfx_enabled", true))
	reduced_motion = bool(data.get("reduced_motion", false))
