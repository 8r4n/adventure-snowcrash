extends CanvasLayer
class_name OnboardingBeat
## First 10 minutes Godot/Steam fantasy beat (#133 · parent #130 · related #118 / Primer #60).
## Original Metaverse prose only — reuses Payload-Zero / Primer teaching ideas, not copyrighted text.
## Persistence mirrors web localStorage via ConfigFile under user://.

signal beat_started
signal beat_completed(reason: String)
signal docks_gate_changed(gated: bool)
signal request_focus_name
signal request_jack_in
signal respawn_requested

const CONFIG_PATH := "user://snowcrash_client.cfg"
const CONFIG_SECTION := "onboarding"

enum Phase {
	BOOT,
	INTRO,
	NAME,
	BEAT,
	DEATH,
	WIN,
	DONE,
}

## Short original chapters — courier fantasy sell, one clear Payload-Zero objective.
const INTRO_CHAPTERS := [
	{
		"kicker": "METAVERSE LAYER",
		"title": "SNOWCRASH",
		"body": "Fractured franchise cities. Neon rain on asphalt. You are a freelance courier — paid to move what should not move between meatspace and the Layer.",
	},
	{
		"kicker": "STREET BRIEF",
		"title": "PAYLOAD-ZERO",
		"body": "A Faraday-sleeved neurolinguistic threat sits at the jackpoint (J). Sleeve it. Carry it to the uplink (U). Scrub it. One objective. Everything else can wait.",
	},
	{
		"kicker": "FIRST TEN MINUTES",
		"title": "JACK IN",
		"body": "Pick a courier name. Move with WASD · turn with Q/E · pick up with G · interact near the uplink. Year docks stay locked until this beat clears — no HUD soup.",
	},
]

var phase: int = Phase.BOOT
var chapter_idx: int = 0
var _gated: bool = false
var _beat_active: bool = false
var _had_payload: bool = false
var _death_count: int = 0
var _last_objective_text: String = ""
var _remembered_name: String = "Courier"

var _root: Control
var _panel: PanelContainer
var _kicker: Label
var _title: Label
var _body: RichTextLabel
var _coach: Label
var _btn_primary: Button
var _btn_secondary: Button
var _btn_skip: Button
var _name_row: HBoxContainer
var _name_edit: LineEdit
var _chk_remember: CheckBox


func _ready() -> void:
	layer = 80
	_build_ui()
	_load_config()
	_run_boot()


func is_beat_active() -> bool:
	return _beat_active


func is_gated() -> bool:
	return _gated


func remembered_name() -> String:
	return _remembered_name


func should_auto_skip_intro() -> bool:
	return _cfg_bool("skip_intro", false) or _cfg_bool("beat_complete", false)


func notify_welcome(state: Dictionary) -> void:
	if phase == Phase.NAME or phase == Phase.INTRO or phase == Phase.BOOT:
		_enter_beat(state, false)
	elif _beat_active:
		_paint_from_state(state)


func notify_snapshot(state: Dictionary) -> void:
	if not _beat_active and phase != Phase.DEATH and phase != Phase.WIN:
		return
	_paint_from_state(state)


func force_skip_beat(reason: String = "skipped") -> void:
	_complete_beat(reason)


func _run_boot() -> void:
	if should_auto_skip_intro():
		phase = Phase.DONE
		_beat_active = false
		_set_gated(false)
		_hide_overlay()
		beat_completed.emit("returning")
		return
	_show_intro(0)


func _show_intro(idx: int) -> void:
	phase = Phase.INTRO
	chapter_idx = clampi(idx, 0, INTRO_CHAPTERS.size() - 1)
	_beat_active = false
	_set_gated(true)
	_show_overlay()
	_name_row.visible = false
	_chk_remember.visible = false
	_btn_skip.visible = true
	_btn_skip.text = "Skip intro (returning)"
	_btn_secondary.visible = chapter_idx > 0
	_btn_secondary.text = "Back"
	_btn_primary.text = "Continue"
	_paint_chapter()
	_coach.text = "Steam cold-start · original Metaverse brief · docks gated until Payload-Zero"


func _paint_chapter() -> void:
	var ch: Dictionary = INTRO_CHAPTERS[chapter_idx]
	_kicker.text = str(ch.get("kicker", ""))
	_title.text = str(ch.get("title", ""))
	_body.text = str(ch.get("body", ""))


func _enter_name_gate() -> void:
	phase = Phase.NAME
	_show_overlay()
	_kicker.text = "COURIER IDENTITY"
	_title.text = "NAME THE SLEEVE"
	_body.text = "Your StreetNet handle sticks to this pad. Returning players can skip the intro next time."
	_coach.text = "Then Jack in — one street objective waits on the shared layer."
	_name_row.visible = true
	_chk_remember.visible = true
	_chk_remember.button_pressed = true
	_name_edit.text = _remembered_name if not _remembered_name.is_empty() else "Courier"
	_btn_secondary.visible = true
	_btn_secondary.text = "Back"
	_btn_primary.text = "Jack in"
	_btn_skip.visible = true
	_btn_skip.text = "Skip onboarding"
	_name_edit.grab_focus()
	request_focus_name.emit()


func _enter_beat(state: Dictionary, resume: bool = false) -> void:
	phase = Phase.BEAT
	_beat_active = true
	_set_gated(true)
	if not resume:
		_had_payload = false
	_show_overlay()
	_name_row.visible = false
	_chk_remember.visible = false
	_btn_secondary.visible = false
	_btn_primary.text = "Dismiss coach"
	_btn_skip.visible = true
	_btn_skip.text = "Skip beat · unlock docks"
	_kicker.text = "ACTIVE BEAT" if not resume else "BEAT RESUMED"
	_title.text = "PAYLOAD-ZERO"
	_body.text = (
		"Find the jackpoint (J), sleeve Payload-Zero (G), reach the uplink (U), scrub the sleeve. "
		+ "Year docks and StreetNet stay quiet until you clear this — or skip."
	)
	_paint_from_state(state)
	if not resume:
		beat_started.emit()


func _paint_from_state(state: Dictionary) -> void:
	var mode := str(state.get("mode", "play"))
	var dead := bool(state.get("dead")) or mode == "dead" or bool(state.get("lost"))
	var won := bool(state.get("won")) or mode == "won"
	var obj_text := _objective_text(state)
	_last_objective_text = obj_text
	var has_payload := false
	var player: Dictionary = state.get("player", {}) if typeof(state.get("player", {})) == TYPE_DICTIONARY else {}
	# Snapshot may expose inventory or quest.has_payload
	var quest = state.get("quest", {})
	if typeof(quest) == TYPE_DICTIONARY and quest.has("has_payload"):
		has_payload = bool(quest.get("has_payload"))
	else:
		has_payload = "payload" in obj_text.to_lower() and "scrub" in obj_text.to_lower()
		var inv = state.get("inventory", [])
		if typeof(inv) == TYPE_ARRAY:
			for it in inv:
				if typeof(it) == TYPE_DICTIONARY and str(it.get("id", "")) == "payload_zero":
					has_payload = true
					break
	if has_payload:
		_had_payload = true

	if won and _beat_active:
		if phase != Phase.WIN:
			_enter_win(state)
		return
	if dead and _beat_active:
		if phase != Phase.DEATH:
			_enter_death(state)
		return
	if phase == Phase.DEATH and _beat_active and not dead:
		# Respawned — resume coach
		_enter_beat(state, true)
		return

	if phase == Phase.BEAT:
		var step := "1 / 2 · Reach jackpoint (J) · sleeve Payload-Zero"
		if has_payload or "uplink" in obj_text.to_lower() or "scrub" in obj_text.to_lower():
			step = "2 / 2 · Reach uplink (U) · scrub Payload-Zero"
		_coach.text = "%s\nObjective: %s\nWASD move · Q/E turn · G get · F fire · R respawn" % [step, obj_text]


func _enter_death(state: Dictionary) -> void:
	phase = Phase.DEATH
	_death_count += 1
	_show_overlay()
	_name_row.visible = false
	_chk_remember.visible = false
	_btn_secondary.visible = false
	_btn_primary.text = "Respawn (R)"
	_btn_skip.visible = true
	_btn_skip.text = "Skip beat · unlock docks"
	_kicker.text = "COURIER DOWN"
	_title.text = "DEATH RECAP"
	var cause := _death_cause_text(state)
	var tip := "You still owe the street Payload-Zero. Press R (or the button) to respawn at a safe pad and continue the beat."
	if _had_payload:
		tip = "Payload-Zero may have dropped — re-sleeve at the jackpoint (J) if needed, then push the uplink (U)."
	_body.text = (
		"Cause: %s\n\nLast objective: %s\nDeaths this session: %d\n\n%s"
		% [cause, _last_objective_text if not _last_objective_text.is_empty() else "(unknown)", _death_count, tip]
	)
	_coach.text = "Clear feedback · Cogmind-style info design · docks still gated"


func _enter_win(state: Dictionary) -> void:
	phase = Phase.WIN
	_show_overlay()
	_name_row.visible = false
	_chk_remember.visible = false
	_btn_secondary.visible = false
	_btn_primary.text = "Enter the Street"
	_btn_skip.visible = false
	_kicker.text = "BEAT CLEAR"
	_title.text = "UPLINK SCRUBBED"
	_body.text = (
		"Payload-Zero is gone. Personal quest done — the shared street stays hot. "
		+ "Year docks and StreetNet unlock now. Primer chapters (#60) can teach ICE / globe / crews when you want depth."
	)
	_coach.text = _objective_text(state)
	# Persist before emit so returning skip works immediately
	_cfg_set("beat_complete", true)
	_cfg_set("skip_intro", true)
	_save_config()


func _complete_beat(reason: String) -> void:
	_beat_active = false
	phase = Phase.DONE
	_set_gated(false)
	_hide_overlay()
	if reason == "skipped" or reason == "won" or reason == "dismiss_win":
		_cfg_set("beat_complete", true)
		_cfg_set("skip_intro", true)
		_save_config()
	beat_completed.emit(reason)


func _set_gated(gated: bool) -> void:
	if _gated == gated:
		return
	_gated = gated
	docks_gate_changed.emit(gated)


func _objective_text(state: Dictionary) -> String:
	var obj = state.get("objective", "")
	if typeof(obj) == TYPE_DICTIONARY:
		var text := str(obj.get("text", ""))
		var compass := str(obj.get("compass", ""))
		var dist = obj.get("dist", null)
		var bits: PackedStringArray = PackedStringArray()
		if not text.is_empty():
			bits.append(text)
		if not compass.is_empty() and compass != "·":
			bits.append(compass)
		if dist != null:
			bits.append("%sm" % dist)
		return " · ".join(bits) if bits.size() else "(none)"
	var s := str(obj)
	return s if not s.is_empty() else "(none)"


func _death_cause_text(state: Dictionary) -> String:
	var cause = state.get("death_cause", null)
	if typeof(cause) == TYPE_DICTIONARY:
		return str(cause.get("cause", cause.get("by", cause.get("summary", "Courier down"))))
	if cause != null and str(cause).strip_edges() != "":
		return str(cause)
	var dead = state.get("dead", null)
	if typeof(dead) == TYPE_DICTIONARY:
		return str(dead.get("cause", dead.get("by", "Courier down")))
	return "Courier down — street hostiles or hazard"


func _on_primary() -> void:
	match phase:
		Phase.INTRO:
			if chapter_idx < INTRO_CHAPTERS.size() - 1:
				_show_intro(chapter_idx + 1)
			else:
				_enter_name_gate()
		Phase.NAME:
			_remember_from_ui()
			_hide_overlay()
			request_jack_in.emit()
		Phase.BEAT:
			_hide_overlay()
			# Stay in beat; coach can be reopened by failing / death / win
		Phase.DEATH:
			respawn_requested.emit()
		Phase.WIN:
			_complete_beat("won")
		_:
			pass


func _on_secondary() -> void:
	match phase:
		Phase.INTRO:
			if chapter_idx > 0:
				_show_intro(chapter_idx - 1)
		Phase.NAME:
			_show_intro(INTRO_CHAPTERS.size() - 1)
		_:
			pass


func _on_skip() -> void:
	match phase:
		Phase.INTRO:
			_cfg_set("skip_intro", true)
			_save_config()
			_enter_name_gate()
		Phase.NAME, Phase.BEAT, Phase.DEATH:
			_remember_from_ui()
			_complete_beat("skipped")
		_:
			pass


func consume_primary_as_respawn() -> bool:
	return phase == Phase.DEATH


func _remember_from_ui() -> void:
	if _name_edit and not _name_edit.text.strip_edges().is_empty():
		_remembered_name = _name_edit.text.strip_edges()
	if _chk_remember and _chk_remember.button_pressed:
		_cfg_set("remembered_name", _remembered_name)
		_save_config()


func remember_name(n: String) -> void:
	var cleaned := n.strip_edges()
	if cleaned.is_empty():
		cleaned = "Courier"
	_remembered_name = cleaned
	_cfg_set("remembered_name", cleaned)
	_save_config()


func get_name_for_join() -> String:
	if _name_edit and _name_row.visible and not _name_edit.text.strip_edges().is_empty():
		return _name_edit.text.strip_edges()
	return _remembered_name


# ---- Config (web localStorage analogue) ----

var _cfg := ConfigFile.new()


func _load_config() -> void:
	_cfg = ConfigFile.new()
	var err := _cfg.load(CONFIG_PATH)
	if err != OK:
		_remembered_name = "Courier"
		return
	_remembered_name = str(_cfg.get_value(CONFIG_SECTION, "remembered_name", "Courier"))


func _save_config() -> void:
	var err := _cfg.save(CONFIG_PATH)
	if err != OK:
		push_warning("OnboardingBeat: could not save %s (%s)" % [CONFIG_PATH, error_string(err)])


func _cfg_bool(key: String, default: bool) -> bool:
	return bool(_cfg.get_value(CONFIG_SECTION, key, default))


func _cfg_set(key: String, value) -> void:
	_cfg.set_value(CONFIG_SECTION, key, value)


# ---- UI chrome ----

func _build_ui() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_root)

	var dim := ColorRect.new()
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.color = Color(0.067, 0.067, 0.106, 0.82)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP
	_root.add_child(dim)

	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(center)

	_panel = PanelContainer.new()
	_panel.custom_minimum_size = Vector2(560, 320)
	center.add_child(_panel)

	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 18)
	margin.add_theme_constant_override("margin_top", 14)
	margin.add_theme_constant_override("margin_right", 18)
	margin.add_theme_constant_override("margin_bottom", 14)
	_panel.add_child(margin)

	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	margin.add_child(v)

	_kicker = Label.new()
	_kicker.add_theme_color_override("font_color", Catppuccin.SKY)
	_kicker.add_theme_font_size_override("font_size", 12)
	v.add_child(_kicker)

	_title = Label.new()
	_title.add_theme_color_override("font_color", Catppuccin.TEAL)
	_title.add_theme_font_size_override("font_size", 26)
	v.add_child(_title)

	_body = RichTextLabel.new()
	_body.bbcode_enabled = false
	_body.fit_content = true
	_body.scroll_active = false
	_body.custom_minimum_size = Vector2(520, 96)
	_body.add_theme_color_override("default_color", Catppuccin.TEXT)
	_body.add_theme_font_size_override("normal_font_size", 14)
	v.add_child(_body)

	_coach = Label.new()
	_coach.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_coach.add_theme_color_override("font_color", Catppuccin.PEACH)
	_coach.add_theme_font_size_override("font_size", 12)
	v.add_child(_coach)

	_name_row = HBoxContainer.new()
	_name_row.add_theme_constant_override("separation", 8)
	_name_row.visible = false
	v.add_child(_name_row)
	var name_cap := Label.new()
	name_cap.text = "Name"
	name_cap.add_theme_color_override("font_color", Catppuccin.SUBTEXT1)
	_name_row.add_child(name_cap)
	_name_edit = LineEdit.new()
	_name_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_name_edit.placeholder_text = "display name"
	_name_edit.text_submitted.connect(func(_t): _on_primary())
	_name_row.add_child(_name_edit)

	_chk_remember = CheckBox.new()
	_chk_remember.text = "Remember name / skip intro next time"
	_chk_remember.visible = false
	_chk_remember.add_theme_color_override("font_color", Catppuccin.SUBTEXT0)
	v.add_child(_chk_remember)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	v.add_child(row)

	_btn_secondary = Button.new()
	_btn_secondary.text = "Back"
	_btn_secondary.pressed.connect(_on_secondary)
	row.add_child(_btn_secondary)

	_btn_primary = Button.new()
	_btn_primary.text = "Continue"
	_btn_primary.pressed.connect(_on_primary)
	row.add_child(_btn_primary)

	_btn_skip = Button.new()
	_btn_skip.text = "Skip"
	_btn_skip.pressed.connect(_on_skip)
	row.add_child(_btn_skip)

	_hide_overlay()


func _show_overlay() -> void:
	_root.visible = true


func _hide_overlay() -> void:
	_root.visible = false


func reopen_coach_if_beat() -> void:
	if _beat_active and phase == Phase.BEAT:
		_show_overlay()
