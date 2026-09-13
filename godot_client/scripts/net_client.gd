extends Node
class_name NetClient
## Thin WebSocket clone of snowcrash/static/game.js Net (#109).
## Python GameWorld stays the authority — we only join / intent / paint.

signal status_changed(text: String, kind: String)
signal welcome_received(player_id: String, state: Dictionary)
signal snapshot_received(state: Dictionary)
signal server_error(text: String)

const DEFAULT_URL := "ws://127.0.0.1:8766/ws"
const PING_INTERVAL := 2.5
const RECONNECT_SEC := 1.2

var socket := WebSocketPeer.new()
var _url: String = DEFAULT_URL
var _courier_name: String = "Courier"
var _player_id: String = ""
var _want_open: bool = false
var _join_sent: bool = false
var _joined: bool = false
var _last_state: int = WebSocketPeer.STATE_CLOSED
var _ping_accum: float = 0.0
var _reconnect_accum: float = 0.0
var _waiting_reconnect: bool = false

func is_joined() -> bool:
	return _joined


func player_id() -> String:
	return _player_id


func connect_to_server(url: String, courier_name: String) -> void:
	_url = url.strip_edges()
	_courier_name = courier_name.strip_edges()
	if _courier_name.is_empty():
		_courier_name = "Courier"
	_want_open = true
	_waiting_reconnect = false
	_reconnect_accum = 0.0
	_open_socket()


func disconnect_from_server() -> void:
	_want_open = false
	_joined = false
	_join_sent = false
	_waiting_reconnect = false
	if socket.get_ready_state() != WebSocketPeer.STATE_CLOSED:
		socket.close()
	status_changed.emit("disconnected", "")


func send_action(action: String, arg = null) -> bool:
	return _send({"type": "action", "action": action, "arg": arg})


func send_chat(text: String) -> bool:
	return _send({"type": "chat", "text": text})


func _open_socket() -> void:
	_join_sent = false
	_joined = false
	_ping_accum = 0.0
	socket = WebSocketPeer.new()
	status_changed.emit("connecting…", "warn")
	var err := socket.connect_to_url(_url)
	if err != OK:
		status_changed.emit("connect_to_url failed (%s)" % err, "err")
		_schedule_reconnect()


func _schedule_reconnect() -> void:
	if not _want_open:
		return
	_waiting_reconnect = true
	_reconnect_accum = 0.0
	status_changed.emit("reconnecting…", "warn")


func _process(delta: float) -> void:
	if _waiting_reconnect:
		_reconnect_accum += delta
		if _reconnect_accum >= RECONNECT_SEC:
			_waiting_reconnect = false
			_open_socket()
		return

	if socket == null:
		return

	socket.poll()
	var state := socket.get_ready_state()

	if state == WebSocketPeer.STATE_OPEN:
		if _last_state != WebSocketPeer.STATE_OPEN:
			_send_join()
		while socket.get_available_packet_count() > 0:
			var packet := socket.get_packet()
			var text := packet.get_string_from_utf8()
			_handle_text(text)
		_ping_accum += delta
		if _ping_accum >= PING_INTERVAL:
			_ping_accum = 0.0
			_send({"type": "ping", "t": Time.get_ticks_msec()})
	elif state == WebSocketPeer.STATE_CLOSING:
		pass
	elif state == WebSocketPeer.STATE_CLOSED:
		if _last_state != WebSocketPeer.STATE_CLOSED:
			_joined = false
			_join_sent = false
			var code := socket.get_close_code()
			status_changed.emit("closed (%s)" % code, "warn")
			if _want_open:
				_schedule_reconnect()

	_last_state = state


func _send_join() -> void:
	if _join_sent:
		return
	var payload := {"type": "join", "name": _courier_name}
	if not _player_id.is_empty():
		payload["id"] = _player_id
	if _send(payload):
		_join_sent = true
		status_changed.emit("join sent…", "warn")


func _send(obj: Dictionary) -> bool:
	if socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return false
	var err := socket.send_text(JSON.stringify(obj))
	return err == OK


func _handle_text(text: String) -> void:
	var parsed = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	var msg: Dictionary = parsed
	var mtype := str(msg.get("type", ""))
	match mtype:
		"welcome":
			_player_id = str(msg.get("you", ""))
			_joined = true
			status_changed.emit("ONLINE · %s" % _player_id, "")
			var st: Dictionary = msg.get("state", {})
			if typeof(st) == TYPE_DICTIONARY:
				welcome_received.emit(_player_id, st)
		"snapshot":
			var st2 = msg.get("state", {})
			if typeof(st2) == TYPE_DICTIONARY:
				snapshot_received.emit(st2)
		"pong":
			pass
		"error":
			var err_text := str(msg.get("error", "unknown"))
			status_changed.emit("error: %s" % err_text, "err")
			server_error.emit(err_text)
