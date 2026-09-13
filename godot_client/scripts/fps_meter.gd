extends Node
## In-client FPS / frame-time harness (#148). Overlay + optional file logger.
## No editor required — ship protocol; hardware numbers filled on device.

const LOG_PATH := "user://fps_samples.log"
const ROLLING_SEC := 1.0
const CONTINUOUS_INTERVAL_SEC := 2.0

var _visible: bool = false
var _layer: CanvasLayer
var _label: Label
var _accum_delta: float = 0.0
var _accum_frames: int = 0
var _avg_fps: float = 0.0
var _avg_ms: float = 0.0
var _scene_mode: String = "street"
var _continuous: bool = false
var _continuous_accum: float = 0.0
var _host: Node = null  ## optional main — for richer mode detection


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_parse_cmdline()
	_build_overlay()
	set_process(true)


func _parse_cmdline() -> void:
	var args := OS.get_cmdline_user_args()
	args.append_array(OS.get_cmdline_args())
	for a in args:
		var s := str(a).to_lower()
		if s == "--fps-log" or s == "--fps-log=1" or s.begins_with("--fps-log="):
			_continuous = true
			_visible = true


func bind_host(host: Node) -> void:
	_host = host


func set_scene_mode(mode: String) -> void:
	if mode.is_empty():
		return
	_scene_mode = mode


func scene_mode() -> String:
	return _scene_mode


func is_overlay_visible() -> bool:
	return _visible


func toggle_overlay() -> void:
	_visible = not _visible
	_sync_label_visibility()


func show_overlay(on: bool = true) -> void:
	_visible = on
	_sync_label_visibility()


func average_fps() -> float:
	return _avg_fps


func average_ms() -> float:
	return _avg_ms


func log_sample(reason: String = "manual") -> void:
	_append_log_line(reason)


func _build_overlay() -> void:
	_layer = CanvasLayer.new()
	_layer.layer = 100
	_layer.name = "FpsMeterLayer"
	add_child(_layer)
	_label = Label.new()
	_label.name = "FpsOverlay"
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_label.anchor_left = 0.0
	_label.anchor_top = 0.0
	_label.anchor_right = 0.0
	_label.anchor_bottom = 0.0
	_label.offset_left = 10.0
	_label.offset_top = 8.0
	_label.offset_right = 520.0
	_label.offset_bottom = 140.0
	_label.add_theme_color_override("font_color", Color("#89dceb"))  # Catppuccin sky
	_label.add_theme_color_override("font_outline_color", Color("#11111b"))
	_label.add_theme_constant_override("outline_size", 4)
	_label.add_theme_font_size_override("font_size", 13)
	_label.text = "FPS —"
	_layer.add_child(_label)
	_sync_label_visibility()


func _sync_label_visibility() -> void:
	if _label:
		_label.visible = _visible


func _process(delta: float) -> void:
	_accum_delta += delta
	_accum_frames += 1
	if _accum_delta >= ROLLING_SEC:
		_avg_fps = float(_accum_frames) / _accum_delta
		_avg_ms = (_accum_delta / float(_accum_frames)) * 1000.0
		_accum_delta = 0.0
		_accum_frames = 0
		if _visible:
			_refresh_label()
	if _continuous:
		_continuous_accum += delta
		if _continuous_accum >= CONTINUOUS_INTERVAL_SEC:
			_continuous_accum = 0.0
			_append_log_line("continuous")


func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey):
		return
	var ev := event as InputEventKey
	if not ev.pressed or ev.echo:
		return
	if ev.physical_keycode != KEY_F3:
		return
	# Shift+F3 → append sample; bare F3 → toggle overlay
	if ev.shift_pressed:
		_append_log_line("shift_f3")
		if _label and _visible:
			_refresh_label()
	else:
		toggle_overlay()
		if _visible:
			_refresh_label()
	get_viewport().set_input_as_handled()


func _detect_mode() -> String:
	if _host != null and _host.has_method("fps_scene_mode"):
		var m: Variant = _host.call("fps_scene_mode")
		if typeof(m) == TYPE_STRING and not str(m).is_empty():
			_scene_mode = str(m)
	return _scene_mode


func _quality_bits() -> Dictionary:
	var qname := "?"
	var msaa := 0
	var particles := false
	var build_r := 0
	var ent_r := 0
	var pool := 0
	var glow := false
	var bob := false
	var smooth := true
	if GraphicsSettings:
		qname = GraphicsSettings.quality_name()
		msaa = GraphicsSettings.msaa_3d()
		particles = GraphicsSettings.particles_enabled()
		build_r = GraphicsSettings.build_radius()
		ent_r = GraphicsSettings.entity_radius()
		pool = GraphicsSettings.max_pooled_entities()
		glow = GraphicsSettings.glow_enabled()
		bob = GraphicsSettings.head_bob()
		smooth = GraphicsSettings.look_smoothing()
	return {
		"quality": qname,
		"msaa": msaa,
		"particles": particles,
		"build_radius": build_r,
		"entity_radius": ent_r,
		"max_pooled": pool,
		"glow": glow,
		"bob": bob,
		"smooth": smooth,
	}


func _refresh_label() -> void:
	if _label == null:
		return
	var mode := _detect_mode()
	var bits := _quality_bits()
	var eng_fps := Engine.get_frames_per_second()
	var msaa_s := "off" if int(bits["msaa"]) == 0 else "2x"
	_label.text = (
		"FPS %d  (avg %.1f / %.2f ms)  [%s]\n" % [eng_fps, _avg_fps, _avg_ms, mode]
		+ "Quality %s · MSAA %s · particles %s · glow %s\n"
		% [
			bits["quality"],
			msaa_s,
			"on" if bits["particles"] else "off",
			"on" if bits["glow"] else "off",
		]
		+ "AOI build %d · entity %d · pool ≤%d\n" % [
			bits["build_radius"], bits["entity_radius"], bits["max_pooled"]
		]
		+ "Cam juice · smooth %s · bob %s (#161 cosmetic)\n"
		% [
			"on" if bits.get("smooth", true) else "off",
			"on" if bits.get("bob", false) else "off",
		]
		+ "F3 toggle · Shift+F3 log → user://fps_samples.log"
	)


func _append_log_line(reason: String) -> void:
	var mode := _detect_mode()
	var bits := _quality_bits()
	var eng_fps := Engine.get_frames_per_second()
	var fps := _avg_fps if _avg_fps > 0.0 else float(eng_fps)
	var ms := _avg_ms if _avg_ms > 0.0 else (1000.0 / maxf(fps, 0.001))
	var ts := Time.get_datetime_string_from_system(true)
	# JSONL — one object per line for easy grep / pandas
	var row := {
		"ts": ts,
		"reason": reason,
		"quality": bits["quality"],
		"mode": mode,
		"fps": snappedf(fps, 0.01),
		"ms": snappedf(ms, 0.01),
		"engine_fps": eng_fps,
		"msaa": bits["msaa"],
		"particles": bits["particles"],
		"glow": bits["glow"],
		"build_radius": bits["build_radius"],
		"entity_radius": bits["entity_radius"],
		"max_pooled": bits["max_pooled"],
	}
	var line := JSON.stringify(row) + "\n"
	var f := FileAccess.open(LOG_PATH, FileAccess.READ_WRITE)
	if f == null:
		f = FileAccess.open(LOG_PATH, FileAccess.WRITE)
	if f == null:
		push_warning("fps_meter: cannot open %s (%s)" % [LOG_PATH, FileAccess.get_open_error()])
		return
	f.seek_end()
	f.store_string(line)
	f.close()
