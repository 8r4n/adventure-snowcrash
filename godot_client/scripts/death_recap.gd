extends CanvasLayer
class_name DeathRecapOverlay
## Post-beat death / respawn UX parity with web death-overlay (#118).
## OnboardingBeat owns death UI during the first-session beat; this covers normal play.

signal respawn_requested(option_id: String)

var _visible_dead: bool = false
var _last_objective: String = ""
var _panel: PanelContainer = null
var _title: Label = null
var _cause: Label = null
var _objective: Label = null
var _options: VBoxContainer = null
var _default_btn: Button = null
var _dim: ColorRect = null


func _ready() -> void:
	layer = 42
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build_ui()
	visible = false


func is_showing() -> bool:
	return _visible_dead


func set_last_objective(text: String) -> void:
	_last_objective = str(text).strip_edges()


func apply_snapshot(state: Dictionary, suppress: bool = false) -> void:
	var mode := str(state.get("mode", "play"))
	var dead_now := bool(state.get("dead")) or mode == "dead" or bool(state.get("lost"))
	if suppress or not dead_now:
		_hide_overlay()
		return
	_show_overlay(state)


func _show_overlay(state: Dictionary) -> void:
	_visible_dead = true
	visible = true
	if _dim:
		_dim.visible = true
	if _panel:
		_panel.visible = true
	_title.text = "SIGNAL LOST"
	_cause.text = _cause_text(state)
	var obj := _last_objective
	if obj.is_empty():
		obj = _objective_from_state(state)
	_objective.text = "Last objective: %s" % (obj if not obj.is_empty() else "(none)")
	_rebuild_options(state)


func _hide_overlay() -> void:
	_visible_dead = false
	visible = false
	if _dim:
		_dim.visible = false
	if _panel:
		_panel.visible = false
	_clear_option_buttons()


func _cause_text(state: Dictionary) -> String:
	var cause = state.get("death_cause", null)
	var msg := ""
	if typeof(cause) == TYPE_DICTIONARY:
		msg = str(cause.get("cause", cause.get("by", "")))
	elif cause != null:
		msg = str(cause)
	if msg.is_empty():
		var dead = state.get("dead", null)
		if typeof(dead) == TYPE_DICTIONARY:
			msg = str(dead.get("cause", dead.get("by", "")))
		elif typeof(dead) == TYPE_STRING:
			msg = str(dead)
	if msg.is_empty():
		msg = "Courier down"
	var sh = state.get("soft_hardcore", {})
	if typeof(sh) == TYPE_DICTIONARY and bool(sh.get("enabled")):
		var pen = sh.get("last_penalty", {})
		if typeof(pen) == TYPE_DICTIONARY and pen.get("summary"):
			var summary := str(pen.get("summary"))
			if summary not in msg:
				msg = "%s  %s" % [msg, summary]
		elif "soft hardcore" not in msg.to_lower():
			msg = "%s  Soft hardcore is armed." % msg
	return msg


func _objective_from_state(state: Dictionary) -> String:
	var obj = state.get("objective", "")
	if typeof(obj) == TYPE_DICTIONARY:
		return str(obj.get("text", ""))
	return str(obj).strip_edges()


func _rebuild_options(state: Dictionary) -> void:
	_clear_option_buttons()
	var opts = state.get("respawn_options", [])
	if typeof(opts) != TYPE_ARRAY:
		opts = []
	for o in opts:
		if typeof(o) != TYPE_DICTIONARY:
			continue
		var oid := str(o.get("id", o.get("key", o.get("name", "safe_pad"))))
		var label := str(o.get("label", o.get("name", oid)))
		if o.get("cost") != null:
			label = "%s ($%s)" % [label, str(o.get("cost"))]
		var btn := Button.new()
		btn.text = label
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.pressed.connect(_on_option_pressed.bind(oid))
		_options.add_child(btn)
	_default_btn.text = "Respawn (R) — safe pad"
	_default_btn.visible = true


func _clear_option_buttons() -> void:
	if _options == null:
		return
	for c in _options.get_children():
		c.queue_free()


func _on_option_pressed(option_id: String) -> void:
	respawn_requested.emit(str(option_id))


func _on_default_pressed() -> void:
	respawn_requested.emit("safe_pad")


func _build_ui() -> void:
	_dim = ColorRect.new()
	_dim.name = "DeathDim"
	_dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_dim.color = Color(0.02, 0.03, 0.05, 0.72)
	_dim.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_dim)

	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center)

	_panel = PanelContainer.new()
	_panel.custom_minimum_size = Vector2(420, 0)
	center.add_child(_panel)

	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 18)
	margin.add_theme_constant_override("margin_right", 18)
	margin.add_theme_constant_override("margin_top", 16)
	margin.add_theme_constant_override("margin_bottom", 16)
	_panel.add_child(margin)

	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	margin.add_child(col)

	_title = Label.new()
	_title.text = "SIGNAL LOST"
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_title.add_theme_font_size_override("font_size", 22)
	_title.add_theme_color_override("font_color", Color(0.953, 0.545, 0.659))
	col.add_child(_title)

	_cause = Label.new()
	_cause.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_cause.add_theme_color_override("font_color", Color(0.804, 0.839, 0.957))
	col.add_child(_cause)

	_objective = Label.new()
	_objective.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_objective.add_theme_color_override("font_color", Color(0.980, 0.702, 0.529))
	col.add_child(_objective)

	var tip := Label.new()
	tip.text = "Pick a pad or press R for the default safe street respawn."
	tip.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	tip.add_theme_color_override("font_color", Color(0.651, 0.678, 0.784))
	tip.add_theme_font_size_override("font_size", 12)
	col.add_child(tip)

	_options = VBoxContainer.new()
	_options.add_theme_constant_override("separation", 6)
	col.add_child(_options)

	_default_btn = Button.new()
	_default_btn.text = "Respawn (R) — safe pad"
	_default_btn.pressed.connect(_on_default_pressed)
	col.add_child(_default_btn)
