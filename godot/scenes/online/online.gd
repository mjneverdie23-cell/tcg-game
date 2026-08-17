extends Control
## Versus-player lobby: pick a deck, then either open this machine to an
## opponent or type in the address of someone who already has.
##
## The screen is a thin face over the Net autoload — it holds no connection
## state of its own, it just shows Net's and forwards two buttons. When Net
## says the match has started, both machines walk into the battle together.

## What the host reads out to their opponent, in the order most likely to
## work: the internet address if the router agreed to forward the port,
## otherwise the address on the local network.
const ADDRESS_HINT := "Give your opponent this address:"

var _valid_decks: Array[int] = []


func _ready() -> void:
	%Backdrop.texture = MenuStyle.backdrop_texture()
	MenuStyle.style_button(%HostButton, true)
	MenuStyle.style_button(%JoinButton)
	MenuStyle.style_button(%CancelButton)
	MenuStyle.style_button(%BackButton)
	%LobbyPanel.add_theme_stylebox_override("panel", MenuStyle.panel())
	%StatusLabel.add_theme_color_override("font_color", MenuStyle.TEXT_DIM)
	%AddressLabel.add_theme_color_override("font_color", MenuStyle.ACCENT)

	%HostButton.pressed.connect(_on_host_pressed)
	%JoinButton.pressed.connect(_on_join_pressed)
	%CancelButton.pressed.connect(_on_cancel_pressed)
	%BackButton.pressed.connect(_on_back_pressed)
	%JoinAddress.text_submitted.connect(func(_text: String) -> void: _on_join_pressed())
	Net.state_changed.connect(_on_net_state)
	Net.match_started.connect(_on_match_started)

	_populate_decks()
	_on_net_state(Net.state, Net.detail)


func _populate_decks() -> void:
	%DeckDropdown.clear()
	_valid_decks.clear()
	for index in range(PlayerData.decks.size()):
		var deck: Dictionary = PlayerData.decks[index]
		if DeckRules.validate(deck["card_ids"]).is_empty():
			%DeckDropdown.add_item(str(deck["name"]))
			_valid_decks.append(index)
	var none := _valid_decks.is_empty()
	%HostButton.disabled = none
	%JoinButton.disabled = none
	%DeckDropdown.disabled = none
	if none:
		%StatusLabel.text = "Build a legal deck in Collection before playing online."


## The deck the player is taking into the match, or [] when they have none.
func _chosen_deck() -> Array:
	if _valid_decks.is_empty():
		return []
	var deck: Dictionary = PlayerData.decks[_valid_decks[%DeckDropdown.selected]]
	return (deck["card_ids"] as Array).duplicate()


func _on_host_pressed() -> void:
	Net.host_match(_chosen_deck())


func _on_join_pressed() -> void:
	Net.join_match(%JoinAddress.text, _chosen_deck())


func _on_cancel_pressed() -> void:
	Net.leave()
	_on_net_state(Net.state, "Match cancelled.")


func _on_back_pressed() -> void:
	Net.leave()
	SceneRouter.go_to("main_menu")


## Everything the screen shows follows from which of the four states Net is
## in, so there is one place that decides what is visible.
func _on_net_state(state: int, detail: String) -> void:
	var waiting := state == Net.HOSTING or state == Net.JOINING
	%HostButton.visible = not waiting
	%JoinRow.visible = not waiting
	%DeckRow.visible = not waiting
	%CancelButton.visible = waiting
	%Spinner.visible = waiting
	%StatusLabel.text = detail if detail != "" else "Play someone else running this build."
	%AddressBox.visible = state == Net.HOSTING
	if state == Net.HOSTING:
		%AddressHint.text = ADDRESS_HINT
		%AddressLabel.text = _host_address()


## What to read out. The internet address only appears once the router has
## actually accepted the port forward, so it is never a promise the network
## cannot keep.
func _host_address() -> String:
	if Net.public_address != "":
		return "%s   (over the internet)" % Net.public_address
	if Net.lan_address != "":
		return "%s   (same network only)" % Net.lan_address
	return "Looking up this machine's address…"


func _on_match_started() -> void:
	SceneRouter.battle_ranked = false  # no ladder over an unrefereed link
	SceneRouter.quest_match = -1
	SceneRouter.go_to("battle")
