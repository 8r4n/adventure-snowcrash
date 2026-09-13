extends VBoxContainer
class_name YearDocks
## StreetNet + year docks parity for Godot thin client (#127 / Refs #118 / #132).
## Paints structured snapshot fields; actions match web YearUI / protocol.

signal chat_focus_changed(focused: bool)
signal globe_open_changed(open: bool)
signal globe_region_highlight(region_id: String)

const DOCK_DEFS := [
	{"id": "journal", "label": "Journal", "open_action": ""},
	{"id": "ice", "label": "ICE", "open_action": ""},
	{"id": "globe", "label": "Globe", "open_action": "globe"},
	{"id": "primer", "label": "Primer", "open_action": "primer"},
	{"id": "jaunte", "label": "Jaunte", "open_action": "jaunte"},
	{"id": "sleeves", "label": "Sleeves", "open_action": "sleeves"},
	{"id": "forecast", "label": "Forecast", "open_action": "forecast"},
	{"id": "ecology", "label": "Ecology", "open_action": "ecology"},
	{"id": "empathy", "label": "Empathy", "open_action": "empathy"},
]

const IRC_DEFAULT_CHANS := ["#streets", "#metaverse", "#flotilla", "#wish"]

var net: NetClient = null

var _open_id: String = ""
var _last_state: Dictionary = {}
var _dock_btns: Dictionary = {}  # id -> Button
var _mod_panel_ids: PackedStringArray = PackedStringArray()
var _jaunte_region: String = ""
var _globe_search: String = ""
var _globe_selected_id: String = ""
var _globe_ascii_only: bool = false
var _secondary_gated: bool = false
var _gate_banner: Label = null
var _jack_btn: Button = null


@onready var dock_bar: HBoxContainer = %DockBar
@onready var dock_title: Label = %DockTitle
@onready var dock_close_btn: Button = %DockCloseBtn
@onready var dock_body: VBoxContainer = %DockBody
@onready var dock_scroll: ScrollContainer = %DockScroll
@onready var irc_chan_label: Label = %IrcChanLabel
@onready var irc_topic: Label = %IrcTopic
@onready var irc_channels: HBoxContainer = %IrcChannels
@onready var irc_nicks: ItemList = %IrcNicks
@onready var chat_log: RichTextLabel = %ChatLog
@onready var chat_input: LineEdit = %ChatInput
@onready var chat_send_btn: Button = %ChatSendBtn


func setup(net_client: NetClient) -> void:
	net = net_client


func is_chat_focused() -> bool:
	return chat_input.has_focus()

func is_globe_open() -> bool:
	return _open_id == "globe"


func set_globe_selection(region_id: String) -> void:
	_globe_selected_id = str(region_id)
	if _open_id == "globe":
		_paint_open_dock(_last_state)



func set_secondary_gated(gated: bool) -> void:
	"""Hide year docks + StreetNet during first-session beat (#133 anti-HUD soup)."""
	if _secondary_gated == gated:
		_apply_gate_visibility()
		return
	_secondary_gated = gated
	if gated and not _open_id.is_empty():
		_open_id = ""
		_refresh_dock_btn_states()
		_show_empty_dock()
	_apply_gate_visibility()


func is_secondary_gated() -> bool:
	return _secondary_gated


func cycle_dock() -> void:
	"""Start / Menu on Deck: cycle year docks (accordion). Skips when gated (#133)."""
	if _secondary_gated:
		return
	var ids: Array = []
	for def in DOCK_DEFS:
		ids.append(str(def["id"]))
	for mid in _mod_panel_ids:
		ids.append(str(mid))
	if ids.is_empty():
		return
	if _open_id.is_empty():
		_toggle_dock(str(ids[0]))
		return
	var idx := ids.find(_open_id)
	if idx < 0 or idx >= ids.size() - 1:
		# Close after last
		var was_globe := _open_id == "globe"
		_open_id = ""
		_refresh_dock_btn_states()
		_show_empty_dock()
		if was_globe:
			if net != null and net.is_joined():
				net.send_action("globe_close")
			globe_open_changed.emit(false)
		return
	_toggle_dock(str(ids[idx + 1]))



func _apply_gate_visibility() -> void:
	var show_full := not _secondary_gated
	# Dock chrome
	if has_node("DockBarScroll"):
		$DockBarScroll.visible = show_full
	if has_node("DockHead"):
		$DockHead.visible = show_full
	if has_node("DockPanel"):
		$DockPanel.visible = show_full
	# StreetNet
	if has_node("IrcHead"):
		$IrcHead.visible = show_full
	if has_node("IrcTopic"):
		$IrcTopic.visible = show_full
	if has_node("IrcChannelsScroll"):
		$IrcChannelsScroll.visible = show_full
	if has_node("IrcMid"):
		$IrcMid.visible = show_full
	if has_node("ChatRow"):
		$ChatRow.visible = show_full
	_ensure_gate_banner()
	if _gate_banner:
		_gate_banner.visible = _secondary_gated


func _ensure_gate_banner() -> void:
	if _gate_banner != null and is_instance_valid(_gate_banner):
		return
	_gate_banner = Label.new()
	_gate_banner.name = "OnboardingGateBanner"
	_gate_banner.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_gate_banner.add_theme_color_override("font_color", Catppuccin.PEACH)
	_gate_banner.add_theme_font_size_override("font_size", 12)
	_gate_banner.text = (
		"Onboarding beat active — year docks & StreetNet locked.\n"
		+ "Clear Payload-Zero (jackpoint J → uplink U) or Skip beat to unlock."
	)
	# Insert at top of YearDocks
	add_child(_gate_banner)
	move_child(_gate_banner, 0)



func _ready() -> void:
	dock_close_btn.pressed.connect(_on_close_pressed)
	chat_send_btn.pressed.connect(_on_chat_send)
	chat_input.text_submitted.connect(func(_t): _on_chat_send())
	chat_input.focus_entered.connect(func(): chat_focus_changed.emit(true))
	chat_input.focus_exited.connect(func(): chat_focus_changed.emit(false))
	_build_dock_bar()
	_show_empty_dock()
	_apply_gate_visibility()


func _build_dock_bar() -> void:
	for c in dock_bar.get_children():
		c.queue_free()
	_dock_btns.clear()
	for def in DOCK_DEFS:
		var btn := _make_dock_btn(str(def["id"]), str(def["label"]))
		dock_bar.add_child(btn)
		_dock_btns[str(def["id"])] = btn
	# Jack-in shortcut sits with docks (web puts cyber on dock row)
	var jack := Button.new()
	jack.text = "Jack"
	jack.tooltip_text = "jack_in / jack_out"
	jack.pressed.connect(_on_jack_pressed)
	_style_btn(jack, false)
	dock_bar.add_child(jack)
	_jack_btn = jack


func _make_dock_btn(id: String, label: String) -> Button:
	var btn := Button.new()
	btn.text = label
	btn.toggle_mode = true
	btn.tooltip_text = "Open %s dock" % label
	btn.pressed.connect(func(): _toggle_dock(id))
	_style_btn(btn, false)
	return btn


func _style_btn(btn: Button, active: bool) -> void:
	btn.add_theme_font_size_override("font_size", 12)
	if active:
		btn.add_theme_color_override("font_color", Catppuccin.TEAL)
		btn.add_theme_color_override("font_hover_color", Catppuccin.SKY)
	else:
		btn.add_theme_color_override("font_color", Catppuccin.SUBTEXT1)
		btn.add_theme_color_override("font_hover_color", Catppuccin.TEXT)


func _on_close_pressed() -> void:
	var was_globe := _open_id == "globe"
	_open_id = ""
	_refresh_dock_btn_states()
	_show_empty_dock()
	if was_globe:
		if net != null and net.is_joined():
			net.send_action("globe_close")
		globe_open_changed.emit(false)


func _on_jack_pressed() -> void:
	if _secondary_gated:
		return
	if net == null or not net.is_joined():
		return
	var cyber: Dictionary = _as_dict(_last_state.get("cyberspace", {}))
	var heist: Dictionary = _as_dict(_last_state.get("ice_heist", {}))
	var mode := str(_last_state.get("mode", "play"))
	if mode == "cyberspace" or mode == "heist" or cyber.get("active") or heist.get("active"):
		net.send_action("jack_out")
	else:
		net.send_action("jack_in")


func _toggle_dock(id: String) -> void:
	if _secondary_gated:
		return
	var prev := _open_id
	if _open_id == id:
		_open_id = ""
		_refresh_dock_btn_states()
		_show_empty_dock()
		if prev == "globe":
			if net != null and net.is_joined():
				net.send_action("globe_close")
			globe_open_changed.emit(false)
		return
	_open_id = id
	_refresh_dock_btn_states()
	# Mirror web: opening some docks pings the server for fresh structured fields
	var open_action := _open_action_for(id)
	if not open_action.is_empty() and net != null and net.is_joined():
		net.send_action(open_action)
	if prev == "globe" and id != "globe":
		if net != null and net.is_joined():
			net.send_action("globe_close")
		globe_open_changed.emit(false)
	if id == "globe":
		globe_open_changed.emit(true)
	_paint_open_dock(_last_state)


func _open_action_for(id: String) -> String:
	for def in DOCK_DEFS:
		if str(def["id"]) == id:
			return str(def.get("open_action", ""))
	if id.begins_with("mod:"):
		return ""
	return ""


func _refresh_dock_btn_states() -> void:
	for id in _dock_btns.keys():
		var btn: Button = _dock_btns[id]
		var active := (id == _open_id)
		btn.set_pressed_no_signal(active)
		_style_btn(btn, active)


func paint(state: Dictionary) -> void:
	_last_state = state
	_sync_jack_btn(state)
	if _secondary_gated:
		_apply_gate_visibility()
		return
	_paint_streetnet(state)
	_ensure_mod_dock_buttons(state)
	if _open_id.is_empty():
		return
	_paint_open_dock(state)


func _sync_jack_btn(state: Dictionary) -> void:
	if _jack_btn == null:
		return
	var ice_now := Street3D.ice_active(state)
	var cyber := _as_dict(state.get("cyberspace", {}))
	if ice_now:
		_jack_btn.text = "Jack out"
		_jack_btn.tooltip_text = "jack_out / Esc — leave cyberspace or abort heist"
		_style_btn(_jack_btn, true)
	elif bool(cyber.get("can_jack_in", false)):
		_jack_btn.text = "Jack in"
		_jack_btn.tooltip_text = "jack_in at J — maze / ICE gate (heist_start for vault)"
		_style_btn(_jack_btn, true)
	else:
		_jack_btn.text = "Jack"
		_jack_btn.tooltip_text = "Reach jackpoint (J) to jack_in / heist_start"
		_style_btn(_jack_btn, false)


func _show_empty_dock() -> void:
	dock_title.text = "Docks — pick a year panel"
	_clear_dock_body()
	var hint := Label.new()
	hint.text = "Journal · ICE · Globe · Primer · Jaunte · Sleeves · Forecast · Ecology · Empathy · Hello Courier (mod)"
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.add_theme_color_override("font_color", Catppuccin.OVERLAY1)
	hint.add_theme_font_size_override("font_size", 12)
	dock_body.add_child(hint)


func _clear_dock_body() -> void:
	for c in dock_body.get_children():
		c.queue_free()


func _paint_open_dock(state: Dictionary) -> void:
	_clear_dock_body()
	match _open_id:
		"journal":
			dock_title.text = "Journal"
			_paint_journal(state)
		"ice":
			dock_title.text = "ICE probes"
			_paint_ice(state)
		"globe":
			dock_title.text = "Globe / uplink hop"
			_paint_globe(state)
		"primer":
			dock_title.text = "StreetNet Primer"
			_paint_primer(state)
		"jaunte":
			dock_title.text = "Uplink Jaunte"
			_paint_jaunte(state)
		"sleeves":
			dock_title.text = "Sleeves locker"
			_paint_sleeves(state)
		"forecast":
			dock_title.text = "Season Forecast"
			_paint_forecast(state)
		"ecology":
			dock_title.text = "Scarce Ecology"
			_paint_ecology(state)
		"empathy":
			dock_title.text = "Empathy lattice"
			_paint_empathy(state)
		_:
			if _open_id.begins_with("mod:"):
				var mid := _open_id.substr(4)
				dock_title.text = "Mod · %s" % mid
				_paint_mod_panel(state, mid)
			else:
				_show_empty_dock()


# --- helpers -----------------------------------------------------------------

func _as_dict(v) -> Dictionary:
	return v if typeof(v) == TYPE_DICTIONARY else {}


func _as_arr(v) -> Array:
	return v if typeof(v) == TYPE_ARRAY else []


func _add_meta(text: String) -> void:
	var lab := Label.new()
	lab.text = text
	lab.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	lab.add_theme_color_override("font_color", Catppuccin.SUBTEXT0)
	lab.add_theme_font_size_override("font_size", 12)
	dock_body.add_child(lab)


func _add_header(text: String) -> void:
	var lab := Label.new()
	lab.text = text
	lab.add_theme_color_override("font_color", Catppuccin.LAVENDER)
	lab.add_theme_font_size_override("font_size", 13)
	dock_body.add_child(lab)


func _add_dim(text: String) -> void:
	var lab := Label.new()
	lab.text = text
	lab.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	lab.add_theme_color_override("font_color", Catppuccin.OVERLAY1)
	lab.add_theme_font_size_override("font_size", 11)
	dock_body.add_child(lab)


func _add_action_row(specs: Array) -> void:
	# specs: [{label, action, arg?, disabled?}, ...]
	var row := HFlowContainer.new()
	row.add_theme_constant_override("h_separation", 6)
	row.add_theme_constant_override("v_separation", 4)
	for spec in specs:
		if typeof(spec) != TYPE_DICTIONARY:
			continue
		var btn := Button.new()
		btn.text = str(spec.get("label", "?"))
		btn.disabled = bool(spec.get("disabled", false))
		btn.add_theme_font_size_override("font_size", 12)
		btn.add_theme_color_override("font_color", Catppuccin.TEAL)
		var act := str(spec.get("action", ""))
		var arg = spec.get("arg", null)
		btn.pressed.connect(func(): _send(act, arg))
		row.add_child(btn)
	dock_body.add_child(row)


func _send(action: String, arg = null) -> void:
	if action == "__globe_select":
		_globe_selected_id = str(arg) if arg != null else ""
		globe_region_highlight.emit(_globe_selected_id)
		if _open_id == "globe":
			_paint_open_dock(_last_state)
		return
	if net == null or not net.is_joined() or action.is_empty():
		return
	if action == "teleport" and arg != null:
		_globe_selected_id = str(arg)
		globe_region_highlight.emit(_globe_selected_id)
	if action == "globe_filter":
		_globe_ascii_only = str(arg) == "ascii"
	net.send_action(action, arg)


func _empty(msg: String) -> void:
	_add_dim(msg)


# --- StreetNet ---------------------------------------------------------------

func _paint_streetnet(state: Dictionary) -> void:
	var irc: Dictionary = _as_dict(state.get("irc", {}))
	var cur := str(irc.get("channel", "#streets"))
	irc_chan_label.text = cur
	var topics: Dictionary = _as_dict(irc.get("topics", {}))
	var topic := str(topics.get(cur, ""))
	if topic.is_empty() and cur.begins_with("@"):
		topic = "private query"
	irc_topic.text = "%s — %s" % [cur, topic if not topic.is_empty() else "no topic"]

	var joined: Array = _as_arr(irc.get("channels", []))
	if joined.is_empty():
		joined = ["#streets"]
	var shown: Array = []
	for ch in IRC_DEFAULT_CHANS:
		if ch not in shown:
			shown.append(ch)
	for ch in joined:
		var cs := str(ch)
		if cs not in shown:
			shown.append(cs)

	for c in irc_channels.get_children():
		c.queue_free()
	for ch in shown:
		var btn := Button.new()
		btn.text = str(ch)
		btn.toggle_mode = true
		btn.set_pressed_no_signal(str(ch) == cur)
		btn.add_theme_font_size_override("font_size", 11)
		if str(ch) == cur:
			btn.add_theme_color_override("font_color", Catppuccin.TEAL)
		elif str(ch) in joined:
			btn.add_theme_color_override("font_color", Catppuccin.SUBTEXT1)
		else:
			btn.add_theme_color_override("font_color", Catppuccin.OVERLAY0)
		var chan := str(ch)
		btn.pressed.connect(func(): _join_channel(chan))
		irc_channels.add_child(btn)

	irc_nicks.clear()
	var nicks: Array = _as_arr(irc.get("nicks", []))
	if nicks.is_empty():
		for op in _as_arr(state.get("players", [])):
			if typeof(op) == TYPE_DICTIONARY:
				nicks.append(op)
	for n in nicks:
		var name := "?"
		var you := false
		var glyph := ""
		if typeof(n) == TYPE_DICTIONARY:
			name = str(n.get("name", "?"))
			you = bool(n.get("you", false))
			glyph = str(n.get("glyph", ""))
		else:
			name = str(n)
		var label := ("%s %s" % [glyph, name]).strip_edges() if not glyph.is_empty() else name
		if you:
			label += " YOU"
		irc_nicks.add_item(label)

	chat_log.clear()
	var chat: Array = _as_arr(state.get("chat", []))
	for c in chat:
		chat_log.append_text(_format_chat_line(c) + "\n")


func _format_chat_line(c) -> String:
	if typeof(c) != TYPE_DICTIONARY:
		return "[color=#a6adc8]%s[/color]" % str(c).replace("[", "(").replace("]", ")")
	var kind := str(c.get("kind", "say"))
	var name := str(c.get("name", "")).replace("[", "(").replace("]", ")")
	var text := str(c.get("text", "")).replace("[", "(").replace("]", ")")
	var ts := _irc_time(c.get("t", null))
	match kind:
		"system", "join", "part", "nick":
			return "[color=#6c7086][%s]*** %s[/color]" % [ts, text]
		"notice":
			return "[color=#f9e2af][%s]-irc- %s[/color]" % [ts, text]
		"action":
			return "[color=#cba6f7][%s]* %s %s[/color]" % [ts, name, text]
		"pm":
			return "[color=#f5c2e7][%s][%s] %s[/color]" % [ts, name, text]
		_:
			return "[color=#89dceb][%s][/color][color=#b4befe]%s[/color][color=#cdd6f4] %s[/color]" % [ts, name, text]


func _irc_time(t) -> String:
	if t == null:
		return "--:--"
	# Server may send unix seconds or ms; treat large as ms
	var n := float(t)
	if n > 1e12:
		n = n / 1000.0
	var unix := int(n)
	# Display as HH:MM UTC-ish from unix; good enough for dock
	var mins := int((unix / 60) % (24 * 60))
	return "%02d:%02d" % [mins / 60, mins % 60]


func _join_channel(ch: String) -> void:
	if net == null or not net.is_joined():
		return
	net.send_chat("/join %s" % ch)


func _on_chat_send() -> void:
	if _secondary_gated:
		return
	if net == null or not net.is_joined():
		return
	var raw := chat_input.text.strip_edges()
	if raw.is_empty():
		return
	net.send_chat(raw)
	chat_input.text = ""


# --- Journal -----------------------------------------------------------------

func _paint_journal(state: Dictionary) -> void:
	var j = state.get("journal", null)
	var list: Array = []
	var header := ""
	if typeof(j) == TYPE_ARRAY:
		list = j
	else:
		var jo := _as_dict(j)
		if not _as_arr(jo.get("quests", [])).is_empty():
			list = _as_arr(jo.get("quests", []))
		elif not _as_arr(jo.get("steps", [])).is_empty():
			var arc := str(jo.get("arc", jo.get("title", jo.get("name", "Quest"))))
			var cur := int(jo.get("step", -1)) if jo.get("step") != null else -1
			header = "%s%s" % [arc.replace("_", " "), ("  step %d" % cur) if cur >= 0 else ""]
			var i := 0
			for step in _as_arr(jo.get("steps", [])):
				if typeof(step) == TYPE_STRING:
					list.append({
						"id": "step-%d" % i,
						"title": "Step %d" % (i + 1),
						"text": str(step),
						"status": "active" if i + 1 == cur else ("done" if i + 1 < cur else "pending"),
					})
				elif typeof(step) == TYPE_DICTIONARY:
					var done := bool(step.get("done", step.get("completed", false))) or (cur > 0 and i + 1 < cur)
					var active := not done and (cur < 0 or i + 1 == cur or str(step.get("id", "")) == str(jo.get("current", "")))
					list.append({
						"id": str(step.get("id", step.get("key", "step-%d" % i))),
						"title": str(step.get("title", step.get("name", step.get("id", "step-%d" % i)))),
						"text": str(step.get("text", step.get("objective", step.get("desc", "")))),
						"status": "done" if done else ("active" if active else str(step.get("status", "pending"))),
					})
				i += 1
	if not header.is_empty():
		_add_header(header)
	if list.is_empty():
		_empty("No active quests")
	else:
		for q in list:
			if typeof(q) != TYPE_DICTIONARY:
				continue
			var id := str(q.get("id", q.get("key", "")))
			var title := str(q.get("title", q.get("name", id if not id.is_empty() else "Quest")))
			var st := str(q.get("status", "done" if q.get("done") else "active"))
			var obj := str(q.get("objective", q.get("text", q.get("desc", ""))))
			_add_meta("[%s] %s" % [st, title])
			if not obj.is_empty():
				_add_dim(obj)
			if not id.is_empty():
				_add_action_row([{"label": "Track", "action": "journal_track", "arg": id}])
	var jo2 := _as_dict(j)
	for note in _as_arr(jo2.get("notes", [])).slice(maxi(0, _as_arr(jo2.get("notes", [])).size() - 4)):
		_add_dim("· %s" % str(note))


# --- ICE ---------------------------------------------------------------------

func _paint_ice(state: Dictionary) -> void:
	var ice := _as_dict(state.get("ice", {}))
	var probes := _as_arr(ice.get("probes", []))
	var nearby := _as_arr(ice.get("nearby", []))
	var player := _as_dict(state.get("player", {}))
	var focus = ice.get("focus", player.get("focus", state.get("focus", "?")))
	var max_f = ice.get("max_focus", player.get("max_focus", state.get("max_focus", "?")))
	if Street3D.ice_active(state):
		_add_header(Street3D.ice_banner_text(state))
		var heist := _as_dict(state.get("ice_heist", {}))
		var cyber := _as_dict(state.get("cyberspace", {}))
		if bool(heist.get("active", false)):
			_add_dim(str(heist.get("layer_hint", heist.get("hint", ""))))
		elif bool(cyber.get("active", false)):
			_add_dim(str(cyber.get("hint", "")))
		_add_dim("3D lattice is live — Z stun / X reveal melt I. Esc or Jack out.")
	if probes.is_empty():
		_empty("ICE layer offline")
		return
	_add_meta("Focus %s/%s" % [focus, max_f])
	_add_dim(str(ice.get("hint", "Spend Focus on StreetNet ICE probes.")))
	var has_any := not nearby.is_empty()
	var has_hostile := false
	for t in nearby:
		if typeof(t) != TYPE_DICTIONARY:
			continue
		var k := str(t.get("kind", ""))
		if k == "drone" or k == "thug_deck":
			has_hostile = true
			break
	var specs: Array = []
	for p in probes:
		if typeof(p) != TYPE_DICTIONARY:
			continue
		var id := str(p.get("id", ""))
		var name := str(p.get("name", id))
		var cost := int(p.get("focus_cost", 0))
		var ready_in := float(p.get("ready_in", 0))
		var ready := bool(p.get("ready", false)) or ready_in <= 0.05
		var need_target := false
		if id == "stun" and not has_any:
			need_target = true
		elif id == "scramble" and not has_hostile:
			need_target = true
		var focus_n := float(focus) if typeof(focus) != TYPE_STRING else 0.0
		var disabled := (not ready) or (focus_n < cost) or need_target
		var probe_labels := {"stun": "Stun", "reveal": "Reveal", "scramble": "Scramble"}
		var btn_label := str(probe_labels.get(id, ""))
		if btn_label.is_empty():
			var parts := name.split(" ")
			btn_label = parts[0] if parts.size() else name
		specs.append({
			"label": "%s (%d)" % [btn_label, cost],
			"action": "ice_probe",
			"arg": id,
			"disabled": disabled,
		})
		_add_dim("%s — %s" % [name, str(p.get("desc", ""))])
	_add_action_row(specs)
	_add_header("Nearby ICE")
	if nearby.is_empty():
		_empty("No cameras / drones / thug decks in range")
	else:
		for t in nearby.slice(0, mini(8, nearby.size())):
			if typeof(t) != TYPE_DICTIONARY:
				continue
			var flags: PackedStringArray = PackedStringArray()
			if t.get("stunned"):
				flags.append("STUN")
			if t.get("scrambled"):
				flags.append("SCRAM")
			var flag_s := (" · " + " ".join(flags)) if flags.size() else ""
			_add_dim("%s · %s · d%s%s" % [t.get("kind", "?"), t.get("name", "?"), t.get("dist", 0), flag_s])
	_add_action_row([
		{"label": "List probes", "action": "ice_probe", "arg": "list"},
	])


# --- Globe -------------------------------------------------------------------

func _paint_globe(state: Dictionary) -> void:
	var g := _as_dict(state.get("globe", {}))
	var regions := _as_arr(g.get("regions", []))
	if regions.is_empty() and g.is_empty():
		_empty("Globe layer offline")
		return
	var cur := str(g.get("region_id", ""))
	var reg := _as_dict(g.get("region", {}))
	if reg.is_empty():
		# legacy fallbacks
		cur = str(g.get("region", g.get("current", cur)))
		for r in regions:
			if typeof(r) == TYPE_DICTIONARY and str(r.get("id", "")) == cur:
				reg = r
				break
	elif cur.is_empty():
		cur = str(reg.get("id", ""))
	var cost = g.get("cost_credits", g.get("hop_cost", g.get("cost", "?")))
	var cd := float(g.get("cooldown_remaining", g.get("cooldown", 0)))
	var zoom := str(g.get("zoom", "globe"))
	_add_meta("%s · hop %s cr · cd %s · zoom %s" % [
		str(reg.get("name", cur if not cur.is_empty() else "—")),
		str(cost),
		("ready" if cd <= 0.05 else "%.0fs" % cd),
		zoom,
	])
	_add_dim(str(g.get("hint", "3D Earth left · pick a pin or Teleport below.")))
	_add_dim("Hybrid: SubViewport 3D globe overlays the street view while this dock is open.")
	if not _globe_selected_id.is_empty():
		_add_meta("Selected pin: %s" % _globe_selected_id)
		_add_action_row([{"label": "Teleport selected", "action": "teleport", "arg": _globe_selected_id}])
	_add_action_row([
		{"label": "Street", "action": "globe_zoom", "arg": "street"},
		{"label": "Regions", "action": "globe_zoom", "arg": "region"},
		{"label": "Globe", "action": "globe_zoom", "arg": "globe"},
		{"label": "Recall home", "action": "globe_recall"},
		{"label": "Refresh", "action": "globe"},
	])
	# Search field
	var search_row := HBoxContainer.new()
	var search := LineEdit.new()
	search.placeholder_text = "Search region / city"
	search.text = _globe_search if not _globe_search.is_empty() else str(g.get("search", ""))
	search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	search.text_submitted.connect(func(t):
		_globe_search = t
		_send("globe_search", t)
	)
	search.focus_exited.connect(func():
		_globe_search = search.text
	)
	var go := Button.new()
	go.text = "Search"
	go.pressed.connect(func():
		_globe_search = search.text
		_send("globe_search", search.text)
	)
	search_row.add_child(search)
	search_row.add_child(go)
	dock_body.add_child(search_row)
	_globe_ascii_only = bool(g.get("filter_ascii", _globe_ascii_only))
	_add_action_row([
		{"label": "ASCII filter", "action": "globe_filter", "arg": "ascii"},
		{"label": "All filter", "action": "globe_filter", "arg": "all"},
	])
	var q := _globe_search.strip_edges().to_lower()
	if q.is_empty():
		q = str(g.get("search", "")).strip_edges().to_lower()
	var shown := 0
	for r in regions:
		if typeof(r) != TYPE_DICTIONARY:
			continue
		var id := str(r.get("id", ""))
		var name := str(r.get("name", id))
		if _globe_ascii_only and not bool(r.get("has_ascii_shard", false)) and not bool(r.get("home", false)):
			continue
		if not q.is_empty():
			var hay := (id + " " + name + " " + str(r.get("continent", "")) + " " + str(r.get("label", ""))).to_lower()
			if q not in hay:
				continue
		shown += 1
		if shown > 24:
			_add_dim("… truncated")
			break
		var mark := ""
		if id == cur:
			mark += " ★"
		if id == _globe_selected_id:
			mark += " ▶"
		if bool(r.get("has_ascii_shard", false)):
			mark += " ascii"
		_add_meta("%s%s" % [name, mark])
		_add_dim("%s · %s,%s" % [id, r.get("lat", "?"), r.get("lon", "?")])
		var hop_id := id
		_add_action_row([
			{"label": "Select", "action": "__globe_select", "arg": hop_id},
			{"label": "Teleport", "action": "teleport", "arg": hop_id},
		])


# --- Primer ------------------------------------------------------------------

func _paint_primer(state: Dictionary) -> void:
	var pr := _as_dict(state.get("primer", {}))
	var quests := _as_arr(pr.get("quests", []))
	if quests.is_empty():
		_empty("StreetNet Primer offline")
		return
	var voice = pr.get("voice_level", pr.get("player_level", 1))
	_add_meta("voice Lv %s · lessons %s/%s" % [voice, pr.get("lessons_done", 0), pr.get("quest_count", quests.size())])
	_add_dim(str(pr.get("hint", "Adaptive chapters teach ICE, globe, crews.")))
	for q in quests:
		if typeof(q) != TYPE_DICTIONARY:
			continue
		var id := str(q.get("id", ""))
		var status := str(q.get("status", "locked"))
		_add_meta("[%s] %s  %s/%s · %s" % [
			status, q.get("title", id), q.get("progress", 0), q.get("goal", 1), q.get("teaches", "")
		])
		_add_dim(str(q.get("blurb", "")))
		if status == "done" or status == "locked":
			_add_dim("(%s)" % status)
		else:
			_add_action_row([{"label": "Start" if status != "active" else "Active", "action": "primer_start", "arg": id}])
	_add_action_row([
		{"label": "Refresh", "action": "primer"},
		{"label": "Close", "action": "primer_close"},
	])


# --- Jaunte ------------------------------------------------------------------

func _paint_jaunte(state: Dictionary) -> void:
	var j := _as_dict(state.get("jaunte", {}))
	if j.is_empty():
		_empty("Uplink Hop offline")
		return
	var rank := int(j.get("rank", 0))
	var cd := float(j.get("cooldown", 0))
	var ready := bool(j.get("ready", false)) or cd <= 0.05
	var costs := _as_dict(j.get("focus_costs", {}))
	_add_meta("%s · rank %d · xp %s%s · cd %s" % [
		j.get("rank_name", "Untrained"),
		rank,
		j.get("xp", 0),
		("/%s" % j.get("xp_next")) if j.get("xp_next") != null else "",
		"ready" if ready else "%.0fs" % cd,
	])
	_add_dim(str(j.get("hint", "Train short → district → globe hops.")))
	_add_dim("Focus short %s · district %s · globe %s" % [
		costs.get("short", 3), costs.get("district", 6), costs.get("globe", 8)
	])
	_add_action_row([
		{"label": "Short", "action": "jaunte_short"},
		{"label": "District", "action": "jaunte_district"},
		{"label": "Train", "action": "jaunte_train"},
		{"label": "Status", "action": "jaunte_status"},
		{"label": "Close", "action": "jaunte_close"},
		{"label": "Refresh", "action": "jaunte"},
	])
	var hop_row := HBoxContainer.new()
	var region_edit := LineEdit.new()
	region_edit.placeholder_text = "globe region id e.g. neo_tokyo"
	region_edit.text = _jaunte_region
	region_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	region_edit.text_submitted.connect(func(t):
		_jaunte_region = t.strip_edges()
		if not _jaunte_region.is_empty():
			_send("jaunte_globe", _jaunte_region)
	)
	var hop_btn := Button.new()
	hop_btn.text = "Globe hop"
	hop_btn.pressed.connect(func():
		_jaunte_region = region_edit.text.strip_edges()
		if not _jaunte_region.is_empty():
			_send("jaunte_globe", _jaunte_region)
	)
	hop_row.add_child(region_edit)
	hop_row.add_child(hop_btn)
	dock_body.add_child(hop_row)
	var chips: Array = []
	for r in _as_arr(_as_dict(state.get("globe", {})).get("regions", [])).slice(0, 8):
		if typeof(r) != TYPE_DICTIONARY:
			continue
		var rid := str(r.get("id", ""))
		if rid.is_empty():
			continue
		chips.append({"label": rid, "action": "jaunte_globe", "arg": rid})
	if not chips.is_empty():
		_add_action_row(chips)


# --- Sleeves -----------------------------------------------------------------

func _paint_sleeves(state: Dictionary) -> void:
	var sl := _as_dict(state.get("sleeves", {}))
	var shells := _as_arr(sl.get("shells", []))
	if shells.is_empty():
		_empty("Sleeves locker offline")
		return
	var at_home := bool(sl.get("at_safehouse", false))
	var cur := str(sl.get("current", "street"))
	var st := _as_dict(sl.get("stats", {}))
	_add_meta("%s · ATK %s DEF %s HACK %s · HP %s FOC %s" % [
		sl.get("current_name", cur),
		st.get("attack", 0), st.get("defense", 0), st.get("hack", 0),
		st.get("max_hp", 0), st.get("max_focus", 0),
	])
	_add_dim("Safehouse: %s · hops %s" % [
		"OPEN — hop ready" if at_home else "closed — enter with house",
		sl.get("hops", 0),
	])
	for sh in shells:
		if typeof(sh) != TYPE_DICTIONARY:
			continue
		var id := str(sh.get("id", ""))
		var is_cur := bool(sh.get("current", false)) or id == cur
		var accessible := bool(sh.get("accessible", false))
		var premium := bool(sh.get("premium", false))
		var rent := int(sh.get("rent_credits", 0))
		_add_meta("%s%s" % [sh.get("name", id), " [ACTIVE]" if is_cur else ""])
		_add_dim(str(sh.get("tagline", "")))
		_add_dim(str(sh.get("tradeoffs", "")))
		if is_cur:
			continue
		if not at_home:
			_add_dim("(enter safehouse first)")
		elif not accessible and premium:
			_add_action_row([
				{"label": "Rent %d" % rent, "action": "sleeve_rent", "arg": id},
				{"label": "Rent+Hop", "action": "sleeve", "arg": id},
			])
		else:
			_add_action_row([{"label": "Hop", "action": "sleeve", "arg": id}])
	_add_action_row([
		{"label": "Toggle safehouse", "action": "house"},
		{"label": "Status", "action": "sleeve_status"},
		{"label": "Refresh", "action": "sleeves"},
	])


# --- Forecast ----------------------------------------------------------------

func _paint_forecast(state: Dictionary) -> void:
	var fc := _as_dict(state.get("forecast", {}))
	if fc.is_empty() or fc.get("metrics") == null:
		_empty("Forecast lattice offline")
		return
	_add_meta("week %s · %s ticks left" % [fc.get("week", 1), fc.get("week_ticks_left", 0)])
	_add_dim(str(fc.get("headline", "")))
	for m in _as_arr(fc.get("metrics", [])):
		if typeof(m) != TYPE_DICTIONARY:
			continue
		var id := str(m.get("id", ""))
		_add_meta("%s · %s · %s%%" % [m.get("label", id), m.get("band", "moderate"), m.get("pct", 0)])
		_add_dim(str(m.get("hint", "")))
		_add_action_row([
			{"label": "− nudge", "action": "forecast_nudge", "arg": "%s down" % id},
			{"label": "+ nudge", "action": "forecast_nudge", "arg": "%s up" % id},
		])
	_add_dim("Nudge cd %ss · cost %s Focus · your nudges %s" % [
		ceili(float(fc.get("nudge_cooldown", 0))),
		fc.get("nudge_focus_cost", 2),
		fc.get("player_nudges", 0),
	])
	_add_action_row([
		{"label": "Refresh", "action": "forecast"},
		{"label": "Status", "action": "forecast_status"},
		{"label": "Close", "action": "forecast_close"},
	])


# --- Ecology -----------------------------------------------------------------

func _paint_ecology(state: Dictionary) -> void:
	var eco := _as_dict(state.get("ecology", {}))
	if eco.is_empty():
		_empty("Ecology lattice offline")
		return
	_add_meta("Scarce Resource Ecology · %s nodes / %s regions" % [
		eco.get("node_count", 0), eco.get("region_count", 0)
	])
	_add_dim(str(eco.get("hint", "")))
	for n in _as_arr(eco.get("nodes", [])).slice(0, 16):
		if typeof(n) != TYPE_DICTIONARY:
			continue
		var id := str(n.get("id", n.get("node_id", "")))
		_add_meta("%s · %s · ctrl %s" % [
			n.get("name", id), n.get("resource", "?"), n.get("controller", "none")
		])
		_add_action_row([
			{"label": "Claim", "action": "ecology_claim", "arg": id},
			{"label": "Raid", "action": "ecology_raid", "arg": id},
		])
	for line in _as_arr(eco.get("streetnet", [])).slice(maxi(0, _as_arr(eco.get("streetnet", [])).size() - 4)):
		_add_dim(str(line))
	_add_action_row([
		{"label": "Refresh", "action": "ecology"},
		{"label": "List", "action": "ecology_list"},
		{"label": "Contract", "action": "ecology_contract"},
		{"label": "Status", "action": "ecology_status"},
		{"label": "Close", "action": "ecology_close"},
	])


# --- Empathy -----------------------------------------------------------------

func _paint_empathy(state: Dictionary) -> void:
	var em := _as_dict(state.get("empathy", {}))
	if em.is_empty() or (em.get("bounties") == null and em.get("hint") == null and em.get("question") == null and em.get("synth_glyph") == null):
		_empty("Empathy lattice offline")
		return
	_add_meta("StreetNet Empathy · glyph %s" % em.get("synth_glyph", "σ"))
	_add_dim(str(em.get("hint", "")))
	if em.get("audit_active") and typeof(em.get("question")) == TYPE_DICTIONARY:
		var q: Dictionary = em.get("question")
		_add_header("Audit %s/%s" % [q.get("index", 1), q.get("total", 3)])
		_add_meta(str(q.get("prompt", "")))
		var answers: Array = []
		for c in _as_arr(q.get("choices", [])):
			if typeof(c) != TYPE_DICTIONARY:
				continue
			var cid := str(c.get("id", ""))
			answers.append({
				"label": "[%s] %s" % [cid, c.get("text", "")],
				"action": "empathy_answer",
				"arg": cid,
			})
		_add_action_row(answers)
	else:
		_add_action_row([{"label": "Start audit", "action": "empathy_audit"}])
	_add_header("Rogue synth bounty board")
	var bounties := _as_arr(em.get("bounties", []))
	if bounties.is_empty():
		_empty("No synth bounties posted")
	else:
		for b in bounties:
			if typeof(b) != TYPE_DICTIONARY:
				continue
			var typ := str(b.get("type", b.get("id", "")))
			var status := str(b.get("status", "open"))
			_add_meta("[%s] %s" % [status, b.get("name", typ)])
			_add_dim(str(b.get("desc", "")))
			_add_dim("+%s cr · +%s rep · %s" % [
				b.get("reward_credits", 0), b.get("reward_rep", 0), b.get("hint", "")
			])
			var specs: Array = []
			if status == "open" or status == "available":
				specs.append({"label": "Accept", "action": "bounty_accept", "arg": typ})
			elif status == "active":
				if typ == "reclaim":
					specs.append({"label": "Bind", "action": "bounty_reclaim"})
				specs.append({"label": "Abandon", "action": "bounty_abandon"})
			elif status == "ready":
				specs.append({"label": "Turn in", "action": "bounty_turnin", "arg": typ})
			if not specs.is_empty():
				_add_action_row(specs)
	_add_action_row([
		{"label": "Refresh", "action": "empathy"},
		{"label": "Status", "action": "empathy_status"},
		{"label": "Close", "action": "empathy_close"},
	])


# --- Mod ui_panel (Hello Courier) --------------------------------------------

func _ensure_mod_dock_buttons(state: Dictionary) -> void:
	var mods := _as_dict(state.get("mods", {}))
	var panels := _as_arr(mods.get("panels", mods.get("ui_panels", [])))
	var seen: Dictionary = {}
	for panel in panels:
		if typeof(panel) != TYPE_DICTIONARY:
			continue
		var pid := str(panel.get("id", ""))
		if pid.is_empty():
			continue
		seen[pid] = true
		var key := "mod:%s" % pid
		if _dock_btns.has(key):
			continue
		var label := str(panel.get("dock_label", panel.get("title", "Mod"))).substr(0, 10)
		var btn := _make_dock_btn(key, label)
		btn.tooltip_text = "%s (mod)" % panel.get("title", pid)
		dock_bar.add_child(btn)
		_dock_btns[key] = btn
		if not pid in _mod_panel_ids:
			_mod_panel_ids.append(pid)
	# Remove stale mod buttons
	var to_drop: Array = []
	for id in _dock_btns.keys():
		if str(id).begins_with("mod:"):
			var mid := str(id).substr(4)
			if not seen.has(mid):
				to_drop.append(id)
	for id in to_drop:
		var btn: Button = _dock_btns[id]
		btn.queue_free()
		_dock_btns.erase(id)
		if _open_id == id:
			_open_id = ""
			_show_empty_dock()


func _paint_mod_panel(state: Dictionary, panel_id: String) -> void:
	var mods := _as_dict(state.get("mods", {}))
	var panels := _as_arr(mods.get("panels", mods.get("ui_panels", [])))
	var panel: Dictionary = {}
	for p in panels:
		if typeof(p) == TYPE_DICTIONARY and str(p.get("id", "")) == panel_id:
			panel = p
			break
	if panel.is_empty():
		_empty("Mod panel offline: %s" % panel_id)
		return
	_add_header(str(panel.get("title", panel_id)))
	var body := str(panel.get("body", ""))
	# Strip light markdown for Label (no HTML)
	var plain := body.replace("**", "").replace("`", "")
	for line in plain.split("\n"):
		var t := line.strip_edges()
		if t.is_empty():
			continue
		if t.begins_with("### "):
			_add_dim(t.substr(4))
		elif t.begins_with("## "):
			_add_header(t.substr(3))
		elif t.begins_with("# "):
			_add_header(t.substr(2))
		elif t.begins_with("- ") or t.begins_with("* "):
			_add_dim("• " + t.substr(2))
		else:
			_add_meta(t)
	var specs: Array = []
	for a in _as_arr(panel.get("actions", [])):
		if typeof(a) != TYPE_DICTIONARY:
			continue
		var act := str(a.get("action", ""))
		if act.is_empty():
			continue
		specs.append({
			"label": str(a.get("label", act)),
			"action": act,
			"arg": a.get("arg", null),
		})
	if not specs.is_empty():
		_add_action_row(specs)
