extends Node
class_name NetClient
## Thin WebSocket client mirroring snowcrash/static/game.js Net (#109 / #118 / #132).
## Python GameWorld stays the authority — we only join / intent / paint.
## Deck/mobile suspend: pause ping on focus-out; nudge reconnect on resume.

signal status_changed(text: String, kind: String)
signal welcome_received(player_id: String, state: Dictionary)
signal snapshot_received(state: Dictionary)
signal server_error(text: String)
signal ping_updated(rtt_ms: int)

const DEFAULT_URL := "ws://127.0.0.1:8766/ws"
const PING_INTERVAL := 2.5
const RECONNECT_SEC := 1.2
const MAX_RECONNECT_SEC := 8.0

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
var _reconnect_delay: float = RECONNECT_SEC
var _waiting_reconnect: bool = false
var _last_ping_sent_ms: int = 0
var _last_rtt_ms: int = -1
var _online_hint: int = 0


func is_joined() -> bool:
	return _joined


func player_id() -> String:
	return _player_id


func courier_name() -> String:
	return _courier_name


func last_rtt_ms() -> int:
	return _last_rtt_ms


func connect_to_server(url: String, courier_name: String) -> void:
	_url = url.strip_edges()
	_courier_name = courier_name.strip_edges()
	if _courier_name.is_empty():
		_courier_name = "Courier"
	_want_open = true
	_waiting_reconnect = false
	_reconnect_accum = 0.0
	_reconnect_delay = RECONNECT_SEC
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


func send_respawn(option_id: String = "safe_pad") -> bool:
	# Prefer action "r" + arg (same as web death overlay); server also accepts type "respawn".
	oid := str(option_id).strip_edges()
	if oid.is_empty() or oid == "default":
		oid = "safe_pad"
	return send_action("r", oid)



func _notification(what: int) -> void:
	# Steam Deck sleep / OS suspend / window focus — same class as mobile.md visibility.
	match what:
		NOTIFICATION_APPLICATION_PAUSED, NOTIFICATION_APPLICATION_FOCUS_OUT:
			_on_app_background()
		NOTIFICATION_APPLICATION_RESUMED, NOTIFICATION_APPLICATION_FOCUS_IN:
			_on_app_foreground()


func _on_app_background() -> void:
	# Stop pinging while frozen; keep _want_open so resume can rejoin.
	_ping_accum = 0.0
	if _want_open and _joined:
		status_changed.emit("background — WS may drop", "warn")


func _on_app_foreground() -> void:
	if not _want_open:
		return
	_ping_accum = 0.0
	var state := WebSocketPeer.STATE_CLOSED
	if socket != null:
		state = socket.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		_last_ping_sent_ms = Time.get_ticks_msec()
		_send({"type": "ping", "t": _last_ping_sent_ms})
		status_changed.emit("foreground — ping", "warn")
	else:
		# Immediate reconnect nudge (don't wait out a long backoff after sleep).
		_reconnect_delay = RECONNECT_SEC
		_waiting_reconnect = false
		_reconnect_accum = 0.0
		status_changed.emit("resume — reconnecting…", "warn")
		_open_socket()


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
	status_changed.emit("reconnecting in %.1fs…" % _reconnect_delay, "warn")


func _process(delta: float) -> void:
	if _waiting_reconnect:
		_reconnect_accum += delta
		if _reconnect_accum >= _reconnect_delay:
			_waiting_reconnect = false
			_open_socket()
		return

	if socket == null:
		return

	socket.poll()
	var state := socket.get_ready_state()

	if state == WebSocketPeer.STATE_OPEN:
		if _last_state != WebSocketPeer.STATE_OPEN:
			_reconnect_delay = RECONNECT_SEC
			_send_join()
		while socket.get_available_packet_count() > 0:
			var packet := socket.get_packet()
			var text := packet.get_string_from_utf8()
			_handle_text(text)
		_ping_accum += delta
		if _ping_accum >= PING_INTERVAL:
			_ping_accum = 0.0
			_last_ping_sent_ms = Time.get_ticks_msec()
			_send({"type": "ping", "t": _last_ping_sent_ms})
	elif state == WebSocketPeer.STATE_CLOSING:
		pass
	elif state == WebSocketPeer.STATE_CLOSED:
		if _last_state != WebSocketPeer.STATE_CLOSED:
			_joined = false
			_join_sent = false
			var code := socket.get_close_code()
			status_changed.emit("closed (%s)" % code, "warn")
			if _want_open:
				_reconnect_delay = minf(_reconnect_delay * 1.5, MAX_RECONNECT_SEC)
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
			_reconnect_delay = RECONNECT_SEC
			_emit_online_status()
			var st: Dictionary = msg.get("state", {})
			if typeof(st) == TYPE_DICTIONARY:
				_online_hint = int(st.get("online_count", _online_hint))
				welcome_received.emit(_player_id, st)
		"snapshot":
			var st2 = msg.get("state", {})
			if typeof(st2) == TYPE_DICTIONARY:
				_online_hint = int(st2.get("online_count", _online_hint))
				if _joined:
					_emit_online_status()
				snapshot_received.emit(st2)
		"pong":
			if _last_ping_sent_ms > 0:
				_last_rtt_ms = maxi(0, Time.get_ticks_msec() - _last_ping_sent_ms)
				ping_updated.emit(_last_rtt_ms)
				_emit_online_status()
		"error":
			var err_text := str(msg.get("error", "unknown"))
			status_changed.emit("error: %s" % err_text, "err")
			server_error.emit(err_text)


func _emit_online_status() -> void:
	var bits: PackedStringArray = PackedStringArray()
	bits.append("ONLINE")
	if not _player_id.is_empty():
		bits.append(_player_id)
	if _last_rtt_ms >= 0:
		bits.append("%dms" % _last_rtt_ms)
	if _online_hint > 0:
		bits.append("%d online" % _online_hint)
	status_changed.emit(" · ".join(bits), "")
