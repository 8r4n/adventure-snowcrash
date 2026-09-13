extends Control
## Core play loop + StreetNet/year docks + first-10 onboarding (#118 / #127 / #133).

@onready var status_label: Label = %Status
@onready var url_edit: LineEdit = %UrlEdit
@onready var name_edit: LineEdit = %NameEdit
@onready var join_btn: Button = %JoinBtn
@onready var disconnect_btn: Button = %DisconnectBtn
@onready var hud_label: Label = %Hud
@onready var objective_label: Label = %Objective
@onready var view_label: Label = %ViewLabel
@onready var view_toggle_btn: Button = %ViewToggle
@onready var inv_list: ItemList = %InvList
@onready var use_btn: Button = %UseBtn
@onready var log_box: RichTextLabel = %LogBox
@onready var hint_label: Label = %Hint
@onready var net: NetClient = %NetClient
@onready var year_docks: YearDocks = %YearDocks
@onready var onboarding: OnboardingBeat = %OnboardingBeat

const HOLD_HZ := 8.0
const INV_DIGIT_MS := 420

var _hold_accum: float = 0.0
var _held_action: String = ""
var _move_keys: Dictionary = {}  # "w"/"a"/"s"/"d" -> true
var _view_mode: String = "fpv"  # "fpv" | "map"
var _last_state: Dictionary = {}
var _inv_digit_buf: String = ""
var _inv_digit_accum: float = -1.0
var _mode: String = "play"
var _prev_mode: String = "play"
var _death_recap_logged: bool = false


func _ready() -> void:
	join_btn.pressed.connect(_on_join_pressed)
	disconnect_btn.pressed.connect(_on_disconnect_pressed)
	name_edit.text_submitted.connect(func(_t): _on_join_pressed())
	view_toggle_btn.pressed.connect(_on_view_toggle)
	use_btn.pressed.connect(_on_use_pressed)
	inv_list.item_selected.connect(_on_inv_selected)
	inv_list.item_activated.connect(_on_inv_activated)
	net.status_changed.connect(_on_status)
	net.welcome_received.connect(_on_welcome)
	net.snapshot_received.connect(_on_snapshot)
	net.server_error.connect(_on_server_error)
	year_docks.setup(net)
	year_docks.chat_focus_changed.connect(func(_f): pass)
	_wire_onboarding()
	_on_status("disconnected — start dev server on :8766", "warn")
	hud_label.text = "HP —  · Focus —  · XP —  · $—"
	objective_label.text = "Objective: (jack in)"
	view_label.text = "(FPV / map after jack-in)"
	log_box.clear()
	log_box.append_text("[color=#a6adc8]Log idle — connect to Python /ws[/color]\n")
	_apply_theme_hints()



func _wire_onboarding() -> void:
	if onboarding == null:
		return
	var remembered := onboarding.remembered_name()
	if remembered and not remembered.is_empty():
		name_edit.text = remembered
	onboarding.docks_gate_changed.connect(_on_docks_gate_changed)
	onboarding.beat_started.connect(func(): _append_log("Onboarding beat: Payload-Zero"))
	onboarding.beat_completed.connect(_on_beat_completed)
	onboarding.request_focus_name.connect(func(): name_edit.grab_focus())
	onboarding.request_jack_in.connect(_on_onboarding_jack_in)
	onboarding.respawn_requested.connect(_on_onboarding_respawn)
	if onboarding.is_gated():
		year_docks.set_secondary_gated(true)
	else:
		year_docks.set_secondary_gated(false)


func _on_docks_gate_changed(gated: bool) -> void:
	year_docks.set_secondary_gated(gated)
	if gated:
		hint_label.text = (
			"ONBOARDING · WASD move · Q/E turn · G get · F fire · . look · R respawn · "
			+ "one objective: Payload-Zero (docks locked)"
		)
	else:
		_apply_theme_hints()


func _on_beat_completed(reason: String) -> void:
	_append_log("Onboarding complete (%s) — docks unlocked" % reason)
	year_docks.set_secondary_gated(false)
	_apply_theme_hints()


func _on_onboarding_jack_in() -> void:
	var n := onboarding.get_name_for_join()
	if n and not n.is_empty():
		name_edit.text = n
	_on_join_pressed()


func _on_onboarding_respawn() -> void:
	if net.is_joined():
		net.send_action("r")


func _apply_theme_hints() -> void:
	hint_label.text = (
		"WASD move · Q/E turn · G get · F fire/hack · . look/wait · I inventory · "
		+ "0-9 select · U / Enter use · R respawn · V FPV/map · Esc close · "
		+ "dock bar year panels · StreetNet chat /join"
	)


func _on_join_pressed() -> void:
	var n := name_edit.text.strip_edges()
	if n.is_empty():
		n = "Courier"
		name_edit.text = n
	if onboarding:
		onboarding.remember_name(n)
	net.connect_to_server(url_edit.text, n)


func _on_disconnect_pressed() -> void:
	net.disconnect_from_server()


func _on_view_toggle() -> void:
	_view_mode = "map" if _view_mode == "fpv" else "fpv"
	view_toggle_btn.text = "View: %s" % _view_mode.to_upper()
	if not _last_state.is_empty():
		_paint_view(_last_state)


func _on_use_pressed() -> void:
	if not net.is_joined():
		return
	net.send_action("u")


func _on_inv_selected(index: int) -> void:
	if not net.is_joined():
		return
	net.send_action("inv_select", str(index))


func _on_inv_activated(index: int) -> void:
	if not net.is_joined():
		return
	net.send_action("inv_select", str(index))
	net.send_action("u")


func _on_status(text: String, kind: String) -> void:
	status_label.text = text
	match kind:
		"warn":
			status_label.add_theme_color_override("font_color", Catppuccin.YELLOW)
		"err":
			status_label.add_theme_color_override("font_color", Catppuccin.RED)
		_:
			status_label.add_theme_color_override("font_color", Catppuccin.TEAL)


func _on_server_error(text: String) -> void:
	_append_log("[err] %s" % text)


func _on_welcome(_player_id: String, state: Dictionary) -> void:
	_append_log("Jacked in as %s" % str(state.get("player", {}).get("name", "?")))
	if onboarding:
		onboarding.notify_welcome(state)
	_paint(state)


func _on_snapshot(state: Dictionary) -> void:
	if onboarding:
		onboarding.notify_snapshot(state)
	_paint(state)


func _paint(state: Dictionary) -> void:
	_last_state = state
	var player: Dictionary = state.get("player", {})
	if typeof(player) != TYPE_DICTIONARY:
		player = {}
	_mode = str(state.get("mode", "play"))
	var hp = player.get("hp", "?")
	var max_hp = player.get("max_hp", "?")
	var focus = player.get("focus", state.get("focus", "?"))
	var max_focus = player.get("max_focus", "?")
	var xp = state.get("xp", 0)
	var xp_next = state.get("xp_next", "?")
	var level = state.get("level", 1)
	var credits = state.get("credits", 0)
	var facing := FpvAscii.compass_line(player)
	var x = player.get("x", "?")
	var y = player.get("y", "?")
	var tick = state.get("tick", state.get("turn", "?"))
	hud_label.text = (
		"Lv %s  HP %s/%s  Focus %s/%s  XP %s/%s  $%s  ·  (%s,%s) %s  ·  t%s  ·  %s"
		% [level, hp, max_hp, focus, max_focus, xp, xp_next, credits, x, y, facing, tick, _mode]
	)
	var objective := _format_objective(state)
	objective_label.text = "Objective: %s" % objective
	var dead_now := bool(state.get("dead")) or _mode == "dead" or bool(state.get("lost"))
	if state.get("won") or _mode == "won":
		objective_label.text += "  [WON]"
		objective_label.add_theme_color_override("font_color", Catppuccin.GREEN)
	elif dead_now:
		objective_label.text += "  [DEAD — press R]"
		objective_label.add_theme_color_override("font_color", Catppuccin.RED)
		if onboarding == null or not onboarding.is_beat_active():
			_append_death_recap_once(state)
	else:
		objective_label.add_theme_color_override("font_color", Catppuccin.PEACH)
		_death_recap_logged = false
	_prev_mode = _mode

	_paint_view(state)
	_paint_inventory(state)
	_paint_log(state)
	year_docks.paint(state)



func _format_objective(state: Dictionary) -> String:
	var obj = state.get("objective", "")
	if typeof(obj) == TYPE_DICTIONARY:
		var text := str(obj.get("text", ""))
		var compass := str(obj.get("compass", ""))
		var dist = obj.get("dist", null)
		var bits: PackedStringArray = PackedStringArray()
		if not text.is_empty():
			bits.append(text)
		if not compass.is_empty() and compass != "·":
			bits.append(str(compass))
		if dist != null:
			bits.append("%sm" % dist)
		return " · ".join(bits) if bits.size() else "(none)"
	var s := str(obj).strip_edges()
	return s if not s.is_empty() else "(none)"


func _append_death_recap_once(state: Dictionary) -> void:
	if _death_recap_logged:
		return
	_death_recap_logged = true
	var cause = state.get("death_cause", "Courier down")
	if typeof(cause) == TYPE_DICTIONARY:
		cause = cause.get("cause", cause.get("by", "Courier down"))
	_append_log("DEATH RECAP: %s — press R to respawn" % str(cause))


func _paint_view(state: Dictionary) -> void:
	if _view_mode == "fpv":
		var frame := FpvAscii.render(state, 56, 18)
		var compass := FpvAscii.compass_line(state.get("player", {}))
		view_label.text = "[FPV] %s\n%s" % [compass, frame]
	else:
		view_label.text = FpvAscii.map_crop(state, 14)


func _paint_inventory(state: Dictionary) -> void:
	var inv = state.get("inventory", [])
	var selected := int(state.get("selected_inv", 0))
	inv_list.clear()
	if typeof(inv) != TYPE_ARRAY or inv.is_empty():
		inv_list.add_item("(empty)")
		inv_list.set_item_disabled(0, true)
		return
	for i in range(inv.size()):
		var it = inv[i]
		var label := "?"
		if typeof(it) == TYPE_DICTIONARY:
			label = str(it.get("name", it.get("id", "?")))
			var glyph := str(it.get("glyph", ""))
			if not glyph.is_empty():
				label = "%s %s" % [glyph, label]
		else:
			label = str(it)
		inv_list.add_item("%d  %s" % [i, label])
	if selected >= 0 and selected < inv_list.item_count:
		inv_list.select(selected)


func _paint_log(state: Dictionary) -> void:
	var msgs = state.get("messages", [])
	if typeof(msgs) != TYPE_ARRAY:
		return
	log_box.clear()
	for m in msgs:
		var line := str(m)
		var color := "#cdd6f4"
		var low := line.to_lower()
		if "level up" in low or "picked" in low:
			color = "#a6e3a1"
		elif "hurt" in low or "dead" in low or "kill" in low:
			color = "#f38ba8"
		elif "wait" in low or "neon" in low:
			color = "#a6adc8"
		log_box.append_text("[color=%s]%s[/color]\n" % [color, line.replace("[", "(").replace("]", ")")])


func _append_log(text: String) -> void:
	log_box.append_text("[color=#89dceb]%s[/color]\n" % text.replace("[", "(").replace("]", ")"))


func _ui_focused() -> bool:
	if name_edit.has_focus() or url_edit.has_focus():
		return true
	if year_docks != null and year_docks.is_chat_focused():
		return true
	# Dock LineEdits (globe search / jaunte region) — any LineEdit focus blocks move
	var focus := get_viewport().gui_get_focus_owner()
	return focus is LineEdit


func _process(delta: float) -> void:
	if _inv_digit_accum >= 0.0:
		_inv_digit_accum += delta
		if _inv_digit_accum >= INV_DIGIT_MS / 1000.0:
			if not _inv_digit_buf.is_empty() and net.is_joined():
				net.send_action("inv_select", _inv_digit_buf)
			_inv_digit_buf = ""
			_inv_digit_accum = -1.0

	if not net.is_joined() or _ui_focused():
		_hold_accum = 0.0
		_held_action = ""
		return

	var action := _chord_move_action()
	if action.is_empty():
		# Hold turn keys
		if Input.is_physical_key_pressed(KEY_Q) or Input.is_physical_key_pressed(KEY_LEFT):
			action = "turn_left"
		elif Input.is_physical_key_pressed(KEY_E) or Input.is_physical_key_pressed(KEY_RIGHT):
			action = "turn_right"

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


func _chord_move_action() -> String:
	var w := _move_keys.get("w", false) or Input.is_physical_key_pressed(KEY_W) or Input.is_physical_key_pressed(KEY_UP)
	var a := _move_keys.get("a", false) or Input.is_physical_key_pressed(KEY_A)
	var s := _move_keys.get("s", false) or Input.is_physical_key_pressed(KEY_S) or Input.is_physical_key_pressed(KEY_DOWN)
	var d := _move_keys.get("d", false) or Input.is_physical_key_pressed(KEY_D)
	if w and a and not s and not d:
		return "forward_left"
	if w and d and not s and not a:
		return "forward_right"
	if s and a and not w and not d:
		return "back_left"
	if s and d and not w and not a:
		return "back_right"
	if w and not s:
		return "forward"
	if s and not w:
		return "back"
	if a and not d:
		return "strafe_left"
	if d and not a:
		return "strafe_right"
	return ""


func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey):
		return
	var ev := event as InputEventKey
	if not ev.pressed or ev.echo:
		return
	if _ui_focused():
		return
	if not net.is_joined():
		return

	var keycode := ev.physical_keycode
	# View toggle
	if keycode == KEY_V:
		_on_view_toggle()
		get_viewport().set_input_as_handled()
		return

	# Inventory digit select (play or inventory mode)
	if keycode >= KEY_0 and keycode <= KEY_9:
		var digit := str(keycode - KEY_0)
		_inv_digit_buf += digit
		_inv_digit_accum = 0.0
		get_viewport().set_input_as_handled()
		return

	if _mode == "inventory":
		if keycode == KEY_ESCAPE:
			net.send_action("escape")
			get_viewport().set_input_as_handled()
			return
		if keycode == KEY_ENTER or keycode == KEY_KP_ENTER or keycode == KEY_U:
			net.send_action("u")
			get_viewport().set_input_as_handled()
			return
		if keycode == KEY_E:
			net.send_action("e")
			get_viewport().set_input_as_handled()
			return

	match keycode:
		KEY_G:
			net.send_action("g")
		KEY_F:
			net.send_action("f")
		KEY_I:
			net.send_action("i")
		KEY_U:
			net.send_action("u")
		KEY_R:
			net.send_action("r")
		KEY_PERIOD, KEY_SPACE:
			# look / wait — web maps space to "."; also send look for status line
			if keycode == KEY_PERIOD:
				net.send_action("look")
			else:
				net.send_action(".")
		KEY_ESCAPE:
			net.send_action("escape")
		KEY_ENTER, KEY_KP_ENTER:
			if _mode == "inventory":
				net.send_action("u")
			else:
				net.send_action("look")
		_:
			return
	get_viewport().set_input_as_handled()
