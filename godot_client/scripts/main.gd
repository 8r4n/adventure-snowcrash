extends Control
## Core play loop + 3D street + ASCII overlay + docks + onboarding + audio + Deck pad + quality (#141 / #118 / #127 / #132 / #133 / #134).

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
@onready var mute_btn: Button = %MuteBtn
@onready var audio_btn: Button = %AudioBtn
@onready var audio_panel: HBoxContainer = %AudioPanel
@onready var master_slider: HSlider = %MasterSlider
@onready var sfx_slider: HSlider = %SfxSlider
@onready var music_slider: HSlider = %MusicSlider
@onready var street: Street3D = %Street3D
@onready var street_host: SubViewportContainer = %StreetHost
@onready var street_vp: SubViewport = %StreetViewport
@onready var view_scroll: ScrollContainer = %ViewScroll
@onready var cam_btn: Button = %CamBtn
@onready var quality_btn: Button = %QualityBtn
@onready var ice_banner: Label = %IceBanner
@onready var ice_flash: ColorRect = %IceFlash
@onready var globe: Globe3D = %Globe3D
@onready var globe_host: SubViewportContainer = %GlobeHost
@onready var globe_vp: SubViewport = %GlobeViewport
@onready var globe_banner: Label = %GlobeBanner
@onready var ascii_overlay: Label = %AsciiOverlay

const HOLD_HZ := 8.0
const INV_DIGIT_MS := 420

var _hold_accum: float = 0.0
var _held_action: String = ""
var _move_keys: Dictionary = {}  # "w"/"a"/"s"/"d" -> true
var _view_mode: String = "3d"  # "3d" | "3d_ascii" | "fpv" | "map"
var _last_state: Dictionary = {}
var _inv_digit_buf: String = ""
var _inv_digit_accum: float = -1.0
var _mode: String = "play"
var _prev_mode: String = "play"
var _death_recap_logged: bool = false
var _was_ice: bool = false
var _globe_overlay: bool = false
var _globe_selected: String = ""
var _flash_t: float = 0.0
var _flash_in: bool = true
const ICE_FLASH_SEC := 0.5
const VIEW_CONFIG_PATH := "user://snowcrash_client.cfg"
const VIEW_CONFIG_SECTION := "view"
const NET_CONFIG_SECTION := "net"
const DEFAULT_WS_URL := "ws://127.0.0.1:8766/ws"
const VIEW_MODES := ["3d", "3d_ascii", "fpv", "map"]


func _ready() -> void:
	join_btn.pressed.connect(_on_join_pressed)
	disconnect_btn.pressed.connect(_on_disconnect_pressed)
	name_edit.text_submitted.connect(func(_t): _on_join_pressed())
	view_toggle_btn.pressed.connect(_on_view_toggle)
	if cam_btn:
		cam_btn.pressed.connect(_on_cam_toggle)
	if quality_btn:
		quality_btn.pressed.connect(_on_quality_toggle)
		_sync_quality_btn()
	if GraphicsSettings and not GraphicsSettings.quality_changed.is_connected(_on_graphics_quality):
		GraphicsSettings.quality_changed.connect(_on_graphics_quality)
	_apply_viewport_quality()
	use_btn.pressed.connect(_on_use_pressed)
	inv_list.item_selected.connect(_on_inv_selected)
	inv_list.item_activated.connect(_on_inv_activated)
	net.status_changed.connect(_on_status)
	net.welcome_received.connect(_on_welcome)
	net.snapshot_received.connect(_on_snapshot)
	net.server_error.connect(_on_server_error)
	year_docks.setup(net)
	year_docks.chat_focus_changed.connect(func(_f): pass)
	if year_docks.has_signal("globe_open_changed"):
		year_docks.globe_open_changed.connect(_on_globe_open_changed)
	if year_docks.has_signal("globe_region_highlight"):
		year_docks.globe_region_highlight.connect(_on_globe_region_highlight)
	if globe:
		globe.pin_selected.connect(_on_globe_pin_selected)
		globe.pin_activated.connect(_on_globe_pin_activated)
	_wire_onboarding()
	_wire_audio()
	_apply_ws_url_defaults()
	_on_status("disconnected — start dev server on :8766", "warn")
	hud_label.text = "HP —  · Focus —  · XP —  · $—"
	objective_label.text = "Objective: (jack in)"
	view_label.text = "(3D / 3D+ASCII / FPV / map after jack-in)"
	_load_view_mode()
	_apply_view_visibility()
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



func _wire_audio() -> void:
	if mute_btn:
		mute_btn.pressed.connect(_on_mute_pressed)
		_sync_mute_btn()
	if audio_btn:
		audio_btn.pressed.connect(func():
			if audio_panel:
				audio_panel.visible = not audio_panel.visible
		)
	if master_slider:
		master_slider.value = AudioManager.master_linear()
		master_slider.value_changed.connect(func(v): AudioManager.set_master_linear(v))
	if sfx_slider:
		sfx_slider.value = AudioManager.sfx_linear()
		sfx_slider.value_changed.connect(func(v): AudioManager.set_sfx_linear(v))
	if music_slider:
		music_slider.value = AudioManager.music_linear()
		music_slider.value_changed.connect(func(v): AudioManager.set_music_linear(v))
	net.ping_updated.connect(_on_rtt_ping)
	# Menu bed until jack-in
	AudioManager.set_music_bed("street")


func _on_mute_pressed() -> void:
	AudioManager.toggle_mute()
	_sync_mute_btn()


func _sync_mute_btn() -> void:
	if mute_btn == null:
		return
	mute_btn.text = "Unmute" if AudioManager.is_muted() else "Mute"


func _on_rtt_ping(rtt_ms: int) -> void:
	# Throttled inside AudioManager — keeps StreetNet feeling alive
	AudioManager.notify_rtt_ping(rtt_ms)


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
		"WASD / stick move · Q/E / L1 R1 / R-stick turn · G / A get · F / X fire · "
		+ "B look · Y inv · L2 use · R2 respawn · Select 3D/3D+ASCII/FPV/map · C camera · Start docks · "
		+ "J jack in/out · Z stun · X reveal · StreetNet · M mute · F8 quality · Audio "
		+ "(Deck: docs/steam-deck.md · 3D: docs/godot-3d.md)"
	)


func _on_join_pressed() -> void:
	var n := name_edit.text.strip_edges()
	if n.is_empty():
		n = "Courier"
		name_edit.text = n
	if onboarding:
		onboarding.remember_name(n)
	AudioManager.play_confirm()
	_save_ws_url(url_edit.text.strip_edges())
	net.connect_to_server(url_edit.text, n)


func _on_disconnect_pressed() -> void:
	net.disconnect_from_server()
	AudioManager.set_music_bed("street")


func _on_view_toggle() -> void:
	var idx := VIEW_MODES.find(_view_mode)
	if idx < 0:
		idx = 0
	_view_mode = VIEW_MODES[(idx + 1) % VIEW_MODES.size()]
	_save_view_mode()
	_apply_view_visibility()
	if not _last_state.is_empty():
		_paint_view(_last_state)
	_append_log("View %s" % _view_mode_label())


func _on_cam_toggle() -> void:
	if street == null:
		return
	var cam_name := street.toggle_camera()
	if cam_btn:
		cam_btn.text = "Cam: %s" % cam_name
	_append_log("Camera %s" % cam_name)


func _on_quality_toggle() -> void:
	if GraphicsSettings == null:
		return
	var name := GraphicsSettings.toggle_quality()
	_sync_quality_btn()
	_apply_viewport_quality()
	_append_log("Quality %s (particles %s)" % [
		name,
		"on" if GraphicsSettings.particles_enabled() else "off",
	])


func _on_graphics_quality(_level: int) -> void:
	_sync_quality_btn()
	_apply_viewport_quality()


func _sync_quality_btn() -> void:
	if quality_btn == null or GraphicsSettings == null:
		return
	quality_btn.text = "Quality: %s" % GraphicsSettings.quality_name()


func _apply_viewport_quality() -> void:
	var msaa := GraphicsSettings.msaa_3d() if GraphicsSettings else 1
	if street_vp:
		street_vp.msaa_3d = msaa
	if globe_vp:
		globe_vp.msaa_3d = msaa


func _apply_view_visibility() -> void:
	var is_3d := _view_mode == "3d" or _view_mode == "3d_ascii"
	var show_globe := _globe_overlay and is_3d
	var show_ascii_overlay := _view_mode == "3d_ascii" and not show_globe
	if street_host:
		street_host.visible = is_3d and not show_globe
	if globe_host:
		globe_host.visible = show_globe
	if view_scroll:
		view_scroll.visible = not is_3d
	if ascii_overlay:
		ascii_overlay.visible = show_ascii_overlay
		if not show_ascii_overlay:
			ascii_overlay.text = ""
	if view_toggle_btn:
		var label := "GLOBE" if show_globe else _view_mode_label()
		view_toggle_btn.text = "View: %s" % label
	_sync_street_vp()
	_sync_globe_vp()


func _sync_street_vp() -> void:
	if street_vp == null or street_host == null:
		return
	var sz := street_host.size
	if sz.x >= 8.0 and sz.y >= 8.0:
		street_vp.size = Vector2i(sz)


func _sync_globe_vp() -> void:
	if globe_vp == null or globe_host == null:
		return
	var sz := globe_host.size
	if sz.x >= 8.0 and sz.y >= 8.0:
		globe_vp.size = Vector2i(sz)
	# Only render while visible (Deck budget)
	if globe_vp:
		globe_vp.render_target_update_mode = (
			SubViewport.UPDATE_WHEN_VISIBLE if _globe_overlay else SubViewport.UPDATE_DISABLED
		)



func _view_mode_label() -> String:
	match _view_mode:
		"3d_ascii":
			return "3D+ASCII"
		"fpv":
			return "FPV"
		"map":
			return "MAP"
		_:
			return "3D"


func _load_view_mode() -> void:
	var cfg := ConfigFile.new()
	var err := cfg.load(VIEW_CONFIG_PATH)
	if err != OK and err != ERR_FILE_NOT_FOUND:
		push_warning("view mode: load failed %s" % err)
		return
	var raw := str(cfg.get_value(VIEW_CONFIG_SECTION, "mode", "3d")).to_lower()
	if raw in VIEW_MODES:
		_view_mode = raw
	elif raw == "ascii" or raw == "hybrid":
		_view_mode = "3d_ascii"


func _save_view_mode() -> void:
	var cfg := ConfigFile.new()
	cfg.load(VIEW_CONFIG_PATH)  # merge other sections when present
	cfg.set_value(VIEW_CONFIG_SECTION, "mode", _view_mode)
	var err := cfg.save(VIEW_CONFIG_PATH)
	if err != OK:
		push_warning("view mode: save failed %s" % err)


## Resolve WS URL for exported / Steam builds (#149).
## Precedence: SNOWCRASH_WS_URL | SNOWCRASH_WS env → CLI --ws-url= → ConfigFile [net] ws_url → scene default.
func _apply_ws_url_defaults() -> void:
	if url_edit == null:
		return
	var resolved := ""
	var env_url := OS.get_environment("SNOWCRASH_WS_URL").strip_edges()
	if env_url.is_empty():
		env_url = OS.get_environment("SNOWCRASH_WS").strip_edges()
	if not env_url.is_empty():
		resolved = env_url
	else:
		for arg in OS.get_cmdline_user_args():
			var a := str(arg)
			if a.begins_with("--ws-url="):
				resolved = a.substr("--ws-url=".length()).strip_edges()
				break
			elif a.begins_with("--snowcrash-ws="):
				resolved = a.substr("--snowcrash-ws=".length()).strip_edges()
				break
	if resolved.is_empty():
		var cfg := ConfigFile.new()
		var err := cfg.load(VIEW_CONFIG_PATH)
		if err == OK:
			resolved = str(cfg.get_value(NET_CONFIG_SECTION, "ws_url", "")).strip_edges()
	if not resolved.is_empty():
		url_edit.text = resolved
	elif url_edit.text.strip_edges().is_empty():
		url_edit.text = DEFAULT_WS_URL


func _save_ws_url(url: String) -> void:
	if url.is_empty():
		return
	var cfg := ConfigFile.new()
	cfg.load(VIEW_CONFIG_PATH)  # merge other sections when present
	cfg.set_value(NET_CONFIG_SECTION, "ws_url", url)
	var err := cfg.save(VIEW_CONFIG_PATH)
	if err != OK:
		push_warning("ws_url: save failed %s" % err)


## While jacked, FPV/overlay should raycast from lattice avatar — not street body at J.
func _ascii_paint_state(state: Dictionary) -> Dictionary:
	if state.is_empty() or not Street3D.ice_active(state):
		return state
	var xy := Street3D.ice_avatar_xy(state)
	var patched := state.duplicate(true)
	var player = patched.get("player", {})
	if typeof(player) != TYPE_DICTIONARY:
		player = {}
	else:
		player = player.duplicate(true)
	player["x"] = xy.x
	player["y"] = xy.y
	patched["player"] = player
	return patched


func _on_use_pressed() -> void:
	if not net.is_joined():
		return
	AudioManager.play_confirm()
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
	AudioManager.notify_welcome(state)
	if onboarding:
		onboarding.notify_welcome(state)
	_paint(state)


func _on_snapshot(state: Dictionary) -> void:
	AudioManager.notify_snapshot(state)
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

	_paint_ice_hud(state)
	_paint_view(state)
	_paint_inventory(state)
	_paint_log(state)
	year_docks.paint(state)




func _on_globe_open_changed(open: bool) -> void:
	_globe_overlay = open
	_apply_view_visibility()
	if globe_banner:
		globe_banner.visible = open


func _on_globe_region_highlight(region_id: String) -> void:
	_globe_selected = str(region_id)
	if globe:
		globe.set_selected_region(_globe_selected)


func _on_globe_pin_selected(region_id: String) -> void:
	_globe_selected = str(region_id)
	if year_docks and year_docks.has_method("set_globe_selection"):
		year_docks.set_globe_selection(_globe_selected)
	_append_log("Globe pin: %s" % _globe_selected)


func _on_globe_pin_activated(region_id: String) -> void:
	if not net.is_joined():
		return
	_globe_selected = str(region_id)
	AudioManager.play_confirm()
	net.send_action("teleport", _globe_selected)
	_append_log("Uplink hop → %s" % _globe_selected)


func _paint_globe_overlay(state: Dictionary) -> void:
	var g = state.get("globe", {})
	if typeof(g) != TYPE_DICTIONARY:
		g = {}
	if year_docks and year_docks.has_method("is_globe_open"):
		_globe_overlay = year_docks.is_globe_open()
	if globe and _globe_overlay:
		globe.apply_snapshot(state)
		if not _globe_selected.is_empty():
			globe.set_selected_region(_globe_selected)
	_sync_globe_vp()
	_apply_view_visibility()
	if globe_banner:
		if _globe_overlay and not g.is_empty():
			globe_banner.visible = true
			var cost = int(g.get("cost_credits", g.get("hop_cost", 15)))
			var cd := float(g.get("cooldown_remaining", g.get("cooldown", 0.0)))
			var cur := str(g.get("region_id", ""))
			var reg = g.get("region", {})
			if typeof(reg) == TYPE_DICTIONARY and reg.get("name"):
				cur = str(reg.get("name"))
			var cd_txt := "ready" if cd <= 0.05 else "%.0fs" % cd
			var sel := _globe_selected if not _globe_selected.is_empty() else "(pick pin)"
			globe_banner.text = (
				"GLOBE · here %s · hop %d cr · cd %s · sel %s · dbl-click pin / Teleport"
				% [cur if not cur.is_empty() else "—", cost, cd_txt, sel]
			)
			if cd > 0.05:
				globe_banner.add_theme_color_override("font_color", Catppuccin.PEACH)
			else:
				globe_banner.add_theme_color_override("font_color", Catppuccin.YELLOW)
		else:
			globe_banner.visible = false


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
	if street:
		street.apply_snapshot(state)
	_sync_street_vp()
	_paint_globe_overlay(state)
	var ascii_state := _ascii_paint_state(state)
	if _view_mode == "3d":
		if ascii_overlay:
			ascii_overlay.text = ""
		return
	if _view_mode == "3d_ascii":
		var frame := FpvAscii.render(ascii_state, 56, 18)
		var compass := FpvAscii.compass_line(ascii_state.get("player", {}))
		if ascii_overlay:
			ascii_overlay.text = "[3D+ASCII] %s\n%s" % [compass, frame]
		return
	if ascii_overlay:
		ascii_overlay.text = ""
	if _view_mode == "fpv":
		var frame2 := FpvAscii.render(ascii_state, 56, 18)
		var compass2 := FpvAscii.compass_line(ascii_state.get("player", {}))
		view_label.text = "[FPV] %s\n%s" % [compass2, frame2]
	else:
		view_label.text = FpvAscii.map_crop(ascii_state, 14)



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


func _send_jack_intent() -> void:
	if not net.is_joined():
		return
	if Street3D.ice_active(_last_state):
		net.send_action("jack_out")
		return
	var cyber: Dictionary = _last_state.get("cyberspace", {})
	if typeof(cyber) != TYPE_DICTIONARY:
		cyber = {}
	if bool(cyber.get("can_jack_in", false)):
		net.send_action("jack_in")


func _ui_focused() -> bool:
	if name_edit.has_focus() or url_edit.has_focus():
		return true
	if year_docks != null and year_docks.is_chat_focused():
		return true
	# Dock LineEdits (globe search / jaunte region) — any LineEdit focus blocks move
	var focus := get_viewport().gui_get_focus_owner()
	return focus is LineEdit


func _paint_ice_hud(state: Dictionary) -> void:
	var ice_now := Street3D.ice_active(state)
	if ice_now != _was_ice:
		_begin_ice_flash(ice_now)
		if ice_now:
			_append_log("Jack-in — lattice overlay (ICE bed)")
		else:
			_append_log("Jack-out — street restored")
		_was_ice = ice_now
	if ice_banner:
		ice_banner.visible = ice_now
		if ice_now:
			ice_banner.text = Street3D.ice_banner_text(state)
			var heist = state.get("ice_heist", {})
			if typeof(heist) == TYPE_DICTIONARY and bool(heist.get("active", false)):
				ice_banner.add_theme_color_override("font_color", Catppuccin.MAUVE)
			else:
				ice_banner.add_theme_color_override("font_color", Catppuccin.SKY)


func _begin_ice_flash(entering: bool) -> void:
	_flash_t = ICE_FLASH_SEC
	_flash_in = entering
	if ice_flash:
		ice_flash.visible = true
		ice_flash.color = Color(Catppuccin.SKY.r, Catppuccin.SKY.g, Catppuccin.SKY.b, 0.0) if entering else Color(Catppuccin.TEAL.r, Catppuccin.TEAL.g, Catppuccin.TEAL.b, 0.0)


func _tick_ice_flash(delta: float) -> void:
	if ice_flash == null:
		return
	if _flash_t <= 0.0:
		ice_flash.visible = false
		return
	_flash_t = maxf(0.0, _flash_t - delta)
	var a := sin((1.0 - _flash_t / ICE_FLASH_SEC) * PI) * 0.42
	var c: Color = ice_flash.color
	c.a = a
	ice_flash.color = c
	ice_flash.visible = a > 0.01


func _process(delta: float) -> void:
	_tick_ice_flash(delta)
	if _inv_digit_accum >= 0.0:
		_inv_digit_accum += delta
		if _inv_digit_accum >= INV_DIGIT_MS / 1000.0:
			if not _inv_digit_buf.is_empty() and net.is_joined():
				net.send_action("inv_select", _inv_digit_buf)
			_inv_digit_buf = ""
			_inv_digit_accum = -1.0

	# Globe overlay: right stick orbits Earth instead of turning courier
	if _globe_overlay and globe and not _ui_focused():
		var lx := Input.get_action_strength("look_right") - Input.get_action_strength("look_left")
		# Fallback axes if look_* unbound
		if absf(lx) < 0.01:
			lx = Input.get_joy_axis(0, JOY_AXIS_RIGHT_X)
		var ly := Input.get_joy_axis(0, JOY_AXIS_RIGHT_Y)
		globe.orbit_stick(lx, ly, delta)
		# A / interact confirms selected pin hop
		if Input.is_action_just_pressed("interact_get") and not _globe_selected.is_empty() and net.is_joined():
			_on_globe_pin_activated(_globe_selected)
		_hold_accum = 0.0
		_held_action = ""
		return

	if not net.is_joined() or _ui_focused():
		_hold_accum = 0.0
		_held_action = ""
		return

	var action := _chord_move_action()
	if action.is_empty():
		# Hold turn keys + gamepad L1/R1 (InputMap turn_left / turn_right)
		if (
			Input.is_physical_key_pressed(KEY_Q)
			or Input.is_physical_key_pressed(KEY_LEFT)
			or Input.is_action_pressed("turn_left")
			or Input.is_action_pressed("look_left")
		):
			action = "turn_left"
		elif (
			Input.is_physical_key_pressed(KEY_E)
			or Input.is_physical_key_pressed(KEY_RIGHT)
			or Input.is_action_pressed("turn_right")
			or Input.is_action_pressed("look_right")
		):
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
	# Keyboard + Deck/gamepad InputMap (move_* from left stick / d-pad).
	var w := (
		_move_keys.get("w", false)
		or Input.is_physical_key_pressed(KEY_W)
		or Input.is_physical_key_pressed(KEY_UP)
		or Input.is_action_pressed("move_forward")
	)
	var a := (
		_move_keys.get("a", false)
		or Input.is_physical_key_pressed(KEY_A)
		or Input.is_action_pressed("move_left")
	)
	var s := (
		_move_keys.get("s", false)
		or Input.is_physical_key_pressed(KEY_S)
		or Input.is_physical_key_pressed(KEY_DOWN)
		or Input.is_action_pressed("move_back")
	)
	var d := (
		_move_keys.get("d", false)
		or Input.is_physical_key_pressed(KEY_D)
		or Input.is_action_pressed("move_right")
	)
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
	# Mute
	if keycode == KEY_M:
		_on_mute_pressed()
		get_viewport().set_input_as_handled()
		return

	# View cycle: 3D / 3D+ASCII / FPV / map
	if keycode == KEY_V:
		_on_view_toggle()
		get_viewport().set_input_as_handled()
		return
	if keycode == KEY_C:
		_on_cam_toggle()
		get_viewport().set_input_as_handled()
		return
	if keycode == KEY_F8:
		_on_quality_toggle()
		get_viewport().set_input_as_handled()
		return
	# Web parity: j jack_in at J / jack_out while jacked (#47 / #56 / #141).
	if keycode == KEY_J:
		_send_jack_intent()
		get_viewport().set_input_as_handled()
		return
	if keycode == KEY_Z:
		net.send_action("ice_probe", "stun")
		get_viewport().set_input_as_handled()
		return
	if keycode == KEY_X:
		net.send_action("ice_probe", "reveal")
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


func _unhandled_input(event: InputEvent) -> void:
	# Discrete Deck / gamepad face buttons (#132). Hold-to-move is in _process.
	if _ui_focused() or not net.is_joined():
		return
	if event.is_action_pressed("interact_get"):
		net.send_action("g")
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("interact_fire"):
		net.send_action("f")
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("look_wait"):
		net.send_action("look")
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("inventory"):
		net.send_action("i")
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("use_item"):
		net.send_action("u")
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("respawn"):
		net.send_action("r")
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("toggle_view"):
		_on_view_toggle()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("toggle_camera"):
		_on_cam_toggle()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("toggle_docks"):
		if year_docks != null:
			year_docks.cycle_dock()
		get_viewport().set_input_as_handled()

