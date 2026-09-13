extends Control
## Name-gate + snapshot / ASCII map for the #109 Godot spike.

@onready var status_label: Label = %Status
@onready var url_edit: LineEdit = %UrlEdit
@onready var name_edit: LineEdit = %NameEdit
@onready var join_btn: Button = %JoinBtn
@onready var summary_label: Label = %Summary
@onready var map_label: Label = %MapLabel
@onready var net: NetClient = %NetClient

const TEAL := Color(0.580, 0.886, 0.835)
const YELLOW := Color(0.976, 0.886, 0.686)
const RED := Color(0.953, 0.545, 0.659)

var _hold_accum: float = 0.0
var _held_action: String = ""
const HOLD_HZ := 8.0


func _ready() -> void:
	join_btn.pressed.connect(_on_join_pressed)
	name_edit.text_submitted.connect(func(_t): _on_join_pressed())
	net.status_changed.connect(_on_status)
	net.welcome_received.connect(_on_welcome)
	net.snapshot_received.connect(_on_snapshot)
	_on_status("disconnected — start dev server on :8766", "warn")
	summary_label.text = "Last snapshot: (none)"
	map_label.text = "(ASCII map appears after jack-in)"


func _on_join_pressed() -> void:
	net.connect_to_server(url_edit.text, name_edit.text)


func _on_status(text: String, kind: String) -> void:
	status_label.text = text
	match kind:
		"warn":
			status_label.add_theme_color_override("font_color", YELLOW)
		"err":
			status_label.add_theme_color_override("font_color", RED)
		_:
			status_label.add_theme_color_override("font_color", TEAL)


func _on_welcome(_player_id: String, state: Dictionary) -> void:
	_paint(state)


func _on_snapshot(state: Dictionary) -> void:
	_paint(state)


func _paint(state: Dictionary) -> void:
	var player: Dictionary = state.get("player", {})
	if typeof(player) != TYPE_DICTIONARY:
		player = {}
	var courier := str(player.get("name", "?"))
	var hp := player.get("hp", "?")
	var max_hp := player.get("max_hp", "?")
	var focus := player.get("focus", "?")
	var x := player.get("x", "?")
	var y := player.get("y", "?")
	var facing := str(player.get("facing_name", "?"))
	var mode := str(state.get("mode", "?"))
	var tick := state.get("tick", state.get("turn", "?"))
	var online := state.get("online_count", "?")
	var objective := str(state.get("objective", ""))
	summary_label.text = (
		"tick %s · %s online · %s  |  %s  HP %s/%s  Focus %s  (%s,%s) %s\n%s"
		% [tick, online, mode, courier, hp, max_hp, focus, x, y, facing, objective]
	)
	map_label.text = _map_crop(state)


func _map_crop(state: Dictionary) -> String:
	var rows = state.get("map", [])
	if typeof(rows) != TYPE_ARRAY or rows.is_empty():
		return "(no map in snapshot)"
	var player: Dictionary = state.get("player", {})
	var px := int(player.get("x", 0))
	var py := int(player.get("y", 0))
	var radius := 12
	var y0: int = max(0, py - radius)
	var y1: int = min(rows.size(), py + radius + 1)
	var lines: PackedStringArray = PackedStringArray()
	for yi in range(y0, y1):
		var row := str(rows[yi])
		var x0: int = max(0, px - radius * 2)
		var x1: int = min(row.length(), px + radius * 2 + 1)
		lines.append(row.substr(x0, x1 - x0))
	return "\n".join(lines)


func _process(delta: float) -> void:
	if not net.is_joined():
		return
	if name_edit.has_focus() or url_edit.has_focus():
		return
	# Facing-relative intents — same names as game.js / REL_MOVE_ACTIONS.
	var action := ""
	if Input.is_physical_key_pressed(KEY_Q):
		action = "turn_left"
	elif Input.is_physical_key_pressed(KEY_E):
		action = "turn_right"
	elif Input.is_physical_key_pressed(KEY_W):
		action = "forward"
	elif Input.is_physical_key_pressed(KEY_S):
		action = "back"
	elif Input.is_physical_key_pressed(KEY_A):
		action = "strafe_left"
	elif Input.is_physical_key_pressed(KEY_D):
		action = "strafe_right"
	if action.is_empty():
		_hold_accum = 0.0
		_held_action = ""
		return
	if action != _held_action:
		_held_action = action
		_hold_accum = 0.0
		net.send_action(action)
		return
	_hold_accum += delta
	if _hold_accum >= 1.0 / HOLD_HZ:
		_hold_accum = 0.0
		net.send_action(action)
