extends Node
## Autoload: the online match. One copy of the game hosts, the other joins,
## and from then on the two sides exchange nothing but the moves they make.
##
## Both machines run the same BattleEngine over the same shuffled decks and
## the same seed, so a move is four numbers rather than a board state, and
## the two screens stay identical without anyone sending a board across.
## That only holds while the engine is deterministic, so every move carries
## a checksum of the state it produced: the moment the two disagree the
## match stops and says so, instead of quietly drifting apart.
##
## The trust model is "you know who you invited". The host checks that the
## guest's deck is legal and both sides check that every arriving move is
## legal, so neither can play a card they do not have or act out of turn —
## but each holds a full copy of the engine, opposing hand included, so a
## modified build could read it. Play with people you would hand your
## cards to.

## Connection state changed; `detail` is the line to show the player.
signal state_changed(state: int, detail: String)
## Both sides have decks and a seed: open the battle screen.
signal match_started
## The opponent made a move. `checksum` is their state after making it.
signal action_received(action: Dictionary, checksum: int)
## The match is over for a reason that is not the game ending.
signal match_ended(reason: String)

enum { IDLE, HOSTING, JOINING, PLAYING }

## Default UDP port. Chosen high and unassigned; the host may be reached on
## another one if the player's router maps it differently.
const PORT := 24567
## How long a guest waits for the host to answer before giving up.
const JOIN_TIMEOUT := 12.0

var state := IDLE
## Engine index of the local player: the host takes seat 0, the guest 1.
var seat := 0
## Decks in engine order, ready for BattleEngine.new().
var host_deck: Array = []
var guest_deck: Array = []
var battle_seed := 0
var opponent_name := "Rival"
## Line describing the current state, shown in the lobby.
var detail := ""
## Addresses a guest can type to reach this host — the LAN one always, the
## internet one only when the router agreed to forward the port.
var lan_address := ""
var public_address := ""

var _peer: ENetMultiplayerPeer = null
var _local_deck: Array = []
var _upnp: UPNP = null
var _upnp_thread: Thread = null
## Bumped every time a connection attempt starts, so the timeout from an
## abandoned attempt cannot cancel the one that replaced it.
var _join_token := 0


func _ready() -> void:
	multiplayer.peer_connected.connect(_on_peer_connected)
	multiplayer.peer_disconnected.connect(_on_peer_disconnected)
	multiplayer.connected_to_server.connect(_on_connected)
	multiplayer.connection_failed.connect(_on_connection_failed)
	multiplayer.server_disconnected.connect(_on_server_disconnected)


func is_online() -> bool:
	return state == PLAYING


## Opens this machine to one opponent. Returns false with a reason in
## `detail` when the port cannot be opened at all.
func host_match(deck: Array) -> bool:
	leave()
	_local_deck = deck.duplicate()
	_peer = ENetMultiplayerPeer.new()
	var opened := _peer.create_server(PORT, 1)
	if opened != OK:
		_peer = null
		_set_state(IDLE, "Cannot open port %d — is another copy already hosting?" % PORT)
		return false
	multiplayer.multiplayer_peer = _peer
	seat = 0
	lan_address = _lan_address()
	public_address = ""
	_set_state(HOSTING, "Waiting for an opponent…")
	_open_port_in_background()
	return true


## Connects to a host given "address" or "address:port".
func join_match(target: String, deck: Array) -> bool:
	leave()
	_local_deck = deck.duplicate()
	var host_text := target.strip_edges()
	var port := PORT
	# IPv6 is bracketed; anything else with a colon carries a port.
	var colon := host_text.rfind(":")
	if colon > 0 and not host_text.ends_with("]"):
		port = int(host_text.substr(colon + 1))
		host_text = host_text.substr(0, colon)
	if host_text == "":
		_set_state(IDLE, "Type the address your opponent gave you.")
		return false
	_peer = ENetMultiplayerPeer.new()
	if _peer.create_client(host_text, port) != OK:
		_peer = null
		_set_state(IDLE, "'%s' is not an address this machine can reach." % target)
		return false
	multiplayer.multiplayer_peer = _peer
	seat = 1
	_set_state(JOINING, "Connecting to %s…" % host_text)
	# ENet reports a refused connection quickly but an unroutable address not
	# at all, so the wait is bounded here rather than left hanging.
	_join_token += 1
	get_tree().create_timer(JOIN_TIMEOUT).timeout.connect(
		_on_join_timeout.bind(_join_token))
	return true


## Hangs up, whatever state the session is in. Safe to call when idle.
func leave() -> void:
	_join_token += 1  # any pending connection attempt is now stale
	_hang_up()
	state = IDLE
	detail = ""
	seat = 0


## Drops the transport. Split from leave() because it is the one part that
## must never run inside a multiplayer callback — see _end_match.
func _hang_up() -> void:
	if multiplayer.multiplayer_peer != null:
		multiplayer.multiplayer_peer = null
	if _peer != null:
		_peer.close()
		_peer = null
	_release_port()


## Sends a move the local player just made, with the state it produced.
func send_action(action: Dictionary, checksum: int) -> void:
	if state != PLAYING:
		return
	_take_action.rpc(action, checksum)


# ── handshake ─────────────────────────────────────────────────────────


func _on_peer_connected(_id: int) -> void:
	if state != HOSTING:
		return
	# The guest speaks next, with their deck; their peer id comes with it.
	_set_state(HOSTING, "Opponent connected — checking their deck…")


func _on_connected() -> void:
	_join_token += 1
	_set_state(JOINING, "Connected — sending your deck…")
	_offer_deck.rpc_id(1, _local_deck, PlayerData.player_name)


func _on_connection_failed() -> void:
	_end_match("The host did not answer. Check the address and that they are hosting.")


func _on_server_disconnected() -> void:
	_end_match("The host closed the match.")


func _on_peer_disconnected(_id: int) -> void:
	_end_match("Your opponent disconnected.")


func _on_join_timeout(token: int) -> void:
	if state != JOINING or token != _join_token:
		return
	leave()
	_set_state(IDLE, "No answer after %d seconds. Check the address and the host's firewall."
		% int(JOIN_TIMEOUT))


## Guest -> host. The host owns the rules of the meeting: it checks the
## deck, picks the seed, and tells both sides what they are playing.
@rpc("any_peer", "call_remote", "reliable")
func _offer_deck(deck: Array, player_name: String) -> void:
	if state != HOSTING:
		return
	var id := multiplayer.get_remote_sender_id()
	var problems := DeckRules.validate(deck)
	if not problems.is_empty():
		_refuse.rpc_id(id, "Your deck is not legal here: %s" % problems[0])
		return
	opponent_name = player_name if player_name != "" else "Rival"
	host_deck = _local_deck.duplicate()
	guest_deck = deck.duplicate()
	battle_seed = randi()
	_begin.rpc_id(id, host_deck, guest_deck, battle_seed, PlayerData.player_name)
	_set_state(PLAYING, "Playing %s" % opponent_name)
	match_started.emit()


## Host -> guest: everything needed to build the same battle.
@rpc("authority", "call_remote", "reliable")
func _begin(from_host: Array, from_guest: Array, seed_value: int, player_name: String) -> void:
	host_deck = from_host
	guest_deck = from_guest
	battle_seed = seed_value
	opponent_name = player_name if player_name != "" else "Rival"
	seat = 1
	_set_state(PLAYING, "Playing %s" % opponent_name)
	match_started.emit()


@rpc("authority", "call_remote", "reliable")
func _refuse(reason: String) -> void:
	leave()
	_set_state(IDLE, reason)


## Either side -> the other, once per move.
@rpc("any_peer", "call_remote", "reliable")
func _take_action(action: Dictionary, checksum: int) -> void:
	if state != PLAYING:
		return
	action_received.emit(action, checksum)


# ── reachability ──────────────────────────────────────────────────────


## Asks the router to forward the port, so a guest outside the house can
## reach this machine without anyone editing router settings by hand. Runs
## on its own thread: discovery talks to the network and takes seconds.
func _open_port_in_background() -> void:
	_upnp_thread = Thread.new()
	_upnp_thread.start(_map_port)


func _map_port() -> void:
	var upnp := UPNP.new()
	var found := upnp.discover()
	var address := ""
	if found == UPNP.UPNP_RESULT_SUCCESS and upnp.get_gateway() != null \
			and upnp.get_gateway().is_valid_gateway():
		if upnp.add_port_mapping(PORT, PORT, "Primordia", "UDP", 0) == UPNP.UPNP_RESULT_SUCCESS:
			address = upnp.query_external_address()
			_upnp = upnp
	call_deferred("_port_opened", address)


func _port_opened(address: String) -> void:
	public_address = address
	_set_state(state, detail)  # same state, fresh addresses to show


func _release_port() -> void:
	if _upnp_thread != null:
		_upnp_thread.wait_to_finish()
		_upnp_thread = null
	if _upnp != null:
		_upnp.delete_port_mapping(PORT, "UDP")
		_upnp = null
	public_address = ""
	lan_address = ""


## This machine's address on the local network, for opponents in the same
## house. Loopback and IPv6 link-local addresses are no use to anyone else.
func _lan_address() -> String:
	for address: String in IP.get_local_addresses():
		if address.begins_with("127.") or address == "::1" or address.contains(":"):
			continue
		if not address.begins_with("169.254."):
			return address
	return ""


func _set_state(new_state: int, new_detail: String) -> void:
	state = new_state
	detail = new_detail
	state_changed.emit(state, detail)


## Ends the session from a network event. Everything a connection callback
## can safely do happens now; closing the connection happens on the next
## idle frame, because these callbacks are raised from inside the
## multiplayer poll, and freeing the peer there frees what the poll is still
## walking — which is a crash, not an error.
func _end_match(reason: String) -> void:
	if state == IDLE:
		return
	var was_playing := state == PLAYING
	_join_token += 1
	state = IDLE
	seat = 0
	call_deferred("_hang_up")
	_set_state(IDLE, reason)
	if was_playing:
		match_ended.emit(reason)
