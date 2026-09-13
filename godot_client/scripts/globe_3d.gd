extends Node3D
class_name Globe3D
## Stylized Catppuccin neon Earth + region pins for uplink hop (#141 slice 4/5).
## Driven by snapshot `globe` / `regions` — no client simulation. Pins call existing
## `teleport` / dock selection; Street + ICE SubViewports stay separate.
## Slice 5: rim DirectionalLight + optional orbit dust; Omni budget = FillLight only.
## #157: High SSAO/SSIL/volumetric via GraphicsSettings — Low off.

signal pin_selected(region_id: String)
signal pin_activated(region_id: String)  # double-click / confirm hop

const EARTH_R := 2.35
const PIN_R := 0.055
const MAX_PINS := 64
const AUTO_SPIN := 0.18  # rad/s
const DRAG_SENS := 0.0055
const PIN_POOL := 48

@onready var earth_spin: Node3D = $EarthSpin
@onready var pin_root: Node3D = $EarthSpin/PinRoot
@onready var camera: Camera3D = $CameraPivot/Camera3D
@onready var cam_pivot: Node3D = $CameraPivot
@onready var select_label: Label3D = $SelectLabel
@onready var hud_plate: Label3D = $HudPlate
@onready var world_env: WorldEnvironment = $WorldEnvironment
@onready var rim: DirectionalLight3D = get_node_or_null("Rim")
@onready var fill_light: OmniLight3D = get_node_or_null("FillLight")

var _pins: Array = []  # {id, node: Node3D, mesh: MeshInstance3D, area: Area3D, data: Dictionary}
var _selected_id: String = ""
var _current_id: String = ""
var _filter_q: String = ""
var _filter_ascii: bool = false
var _dragging: bool = false
var _drag_moved: bool = false
var _last_click_id: String = ""
var _last_click_ms: int = 0
var _yaw: float = 0.35
var _pitch: float = 0.25
var _zoom_level: String = "globe"  # street | region | globe
var _cost: int = 15
var _cooldown: float = 0.0
var _hint: String = ""
var _mat_earth: StandardMaterial3D
var _mat_grid: StandardMaterial3D
var _mat_pin_default: StandardMaterial3D
var _mat_pin_ascii: StandardMaterial3D
var _mat_pin_home: StandardMaterial3D
var _mat_pin_here: StandardMaterial3D
var _mat_pin_sel: StandardMaterial3D
var _mat_pin_dim: StandardMaterial3D
var _sphere_mesh: SphereMesh
var _pin_mesh: SphereMesh
var _built_mats := false
var _orbit_dust: GPUParticles3D


func _ready() -> void:
	_ensure_mats()
	_build_earth()
	_ensure_orbit_dust()
	_apply_quality()
	if GraphicsSettings and not GraphicsSettings.quality_changed.is_connected(_on_quality_changed):
		GraphicsSettings.quality_changed.connect(_on_quality_changed)
	_yaw = cam_pivot.rotation.y
	_pitch = cam_pivot.rotation.x
	set_process(true)
	set_process_unhandled_input(true)


func _on_quality_changed(_level: int) -> void:
	_apply_quality()


func _apply_quality() -> void:
	var env: Environment = world_env.environment if world_env else null
	if env:
		var high := GraphicsSettings.is_high() if GraphicsSettings else true
		env.glow_enabled = GraphicsSettings.glow_enabled() if GraphicsSettings else true
		env.glow_intensity = GraphicsSettings.glow_intensity_globe() if GraphicsSettings else 0.62
		env.glow_bloom = GraphicsSettings.glow_bloom_globe() if GraphicsSettings else 0.14
		# #157 High stack — Low off (Deck / #148). Globe keeps Fill Omni only.
		env.ssao_enabled = GraphicsSettings.ssao_enabled() if GraphicsSettings else high
		env.ssil_enabled = GraphicsSettings.ssil_enabled() if GraphicsSettings else high
		if env.ssao_enabled:
			env.ssao_radius = 1.8
			env.ssao_intensity = 0.55
		if env.ssil_enabled:
			env.ssil_radius = 5.0
			env.ssil_intensity = 0.45
		var vol := GraphicsSettings.volumetric_fog_enabled() if GraphicsSettings else high
		env.volumetric_fog_enabled = vol
		if vol:
			env.volumetric_fog_density = GraphicsSettings.volumetric_fog_density_globe() if GraphicsSettings else 0.018
			env.volumetric_fog_albedo = Color(0.12, 0.1, 0.22)
			env.volumetric_fog_emission = Color(0.4, 0.35, 0.7)
			env.volumetric_fog_emission_energy = 0.3
			env.volumetric_fog_length = 40.0
	if rim:
		rim.visible = GraphicsSettings.rim_enabled() if GraphicsSettings else true
		rim.light_energy = 0.48 if (GraphicsSettings == null or GraphicsSettings.is_high()) else 0.0
	if fill_light:
		# Single Omni on globe — keep on Low but dimmer.
		fill_light.light_energy = 1.2 if (GraphicsSettings == null or GraphicsSettings.is_high()) else 0.75
	if _orbit_dust:
		var on := GraphicsSettings.particles_enabled() if GraphicsSettings else true
		_orbit_dust.emitting = on
		_orbit_dust.visible = on


func _ensure_orbit_dust() -> void:
	if _orbit_dust:
		return
	_orbit_dust = GPUParticles3D.new()
	_orbit_dust.name = "OrbitDust"
	_orbit_dust.amount = 40
	_orbit_dust.lifetime = 4.5
	_orbit_dust.preprocess = 1.5
	_orbit_dust.visibility_aabb = AABB(Vector3(-8, -8, -8), Vector3(16, 16, 16))
	_orbit_dust.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := ParticleProcessMaterial.new()
	mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	mat.emission_sphere_radius = 3.2
	mat.direction = Vector3(0, 1, 0)
	mat.spread = 180.0
	mat.initial_velocity_min = 0.05
	mat.initial_velocity_max = 0.25
	mat.gravity = Vector3.ZERO
	mat.scale_min = 0.02
	mat.scale_max = 0.06
	mat.color = Color(0.55, 0.85, 1.0, 0.55)
	_orbit_dust.process_material = mat
	var dm := SphereMesh.new()
	dm.radius = 0.035
	dm.height = 0.07
	var draw := StandardMaterial3D.new()
	draw.albedo_color = Color(0.55, 0.85, 1.0, 0.6)
	draw.emission_enabled = true
	draw.emission = Catppuccin.SKY
	draw.emission_energy_multiplier = 1.2
	draw.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	draw.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_orbit_dust.draw_pass_1 = dm
	_orbit_dust.material_override = draw
	add_child(_orbit_dust)


func is_globe_visible() -> bool:
	return visible


func selected_region_id() -> String:
	return _selected_id


func set_selected_region(region_id: String) -> void:
	_selected_id = str(region_id)
	_refresh_pin_look()
	_update_select_label()


func apply_snapshot(state: Dictionary) -> void:
	_ensure_mats()
	var g := _as_dict(state.get("globe", {}))
	if g.is_empty():
		hud_plate.text = "Globe offline"
		return
	_current_id = str(g.get("region_id", ""))
	if _current_id.is_empty():
		var reg := _as_dict(g.get("region", {}))
		_current_id = str(reg.get("id", g.get("region", "")))
	_cost = int(g.get("cost_credits", g.get("hop_cost", g.get("cost", 15))))
	_cooldown = float(g.get("cooldown_remaining", g.get("cooldown", 0.0)))
	_zoom_level = str(g.get("zoom", "globe"))
	_filter_q = str(g.get("search", "")).strip_edges().to_lower()
	_filter_ascii = bool(g.get("filter_ascii", false))
	_hint = str(g.get("hint", "Pick a pin · teleport"))
	var regions := _as_arr(g.get("regions", []))
	_sync_pins(regions)
	_apply_zoom_camera()
	_refresh_pin_look()
	_update_select_label()
	_update_hud_plate(g)


func set_client_filter(query: String, ascii_only: bool) -> void:
	"""Local filter mirror while typing before server echo."""
	_filter_q = query.strip_edges().to_lower()
	_filter_ascii = ascii_only
	_refresh_pin_look()


func _process(delta: float) -> void:
	if not visible:
		return
	if not _dragging:
		_yaw += AUTO_SPIN * delta
	cam_pivot.rotation = Vector3(_pitch, _yaw, 0.0)
	# Soft pulse on selected pin
	if not _selected_id.is_empty():
		for p in _pins:
			if str(p.get("id", "")) == _selected_id:
				var n: Node3D = p.get("node")
				if n:
					var s := 1.0 + 0.12 * sin(Time.get_ticks_msec() * 0.008)
					n.scale = Vector3(s, s, s)
				break


func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_LEFT:
			if mb.pressed:
				_dragging = true
				_drag_moved = false
			else:
				if _dragging and not _drag_moved:
					_try_pick_at(mb.position)
				_dragging = false
		elif mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			_nudge_zoom(-0.15)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			_nudge_zoom(0.15)
	elif event is InputEventMouseMotion and _dragging:
		var mm := event as InputEventMouseMotion
		if mm.relative.length() > 0.4:
			_drag_moved = true
		_yaw -= mm.relative.x * DRAG_SENS
		_pitch = clampf(_pitch - mm.relative.y * DRAG_SENS, -1.15, 1.15)
	elif event is InputEventScreenTouch:
		var st := event as InputEventScreenTouch
		if st.pressed:
			_dragging = true
			_drag_moved = false
		else:
			if _dragging and not _drag_moved:
				_try_pick_at(st.position)
			_dragging = false
	elif event is InputEventScreenDrag:
		var sd := event as InputEventScreenDrag
		_dragging = true
		if sd.relative.length() > 0.4:
			_drag_moved = true
		_yaw -= sd.relative.x * DRAG_SENS
		_pitch = clampf(_pitch - sd.relative.y * DRAG_SENS, -1.15, 1.15)
	elif event.is_action_pressed("ui_accept") and not _selected_id.is_empty():
		pin_activated.emit(_selected_id)


func orbit_stick(x: float, y: float, delta: float) -> void:
	"""Right-stick orbit while globe overlay is up (Deck)."""
	if absf(x) < 0.2 and absf(y) < 0.2:
		return
	_yaw -= x * 1.8 * delta
	_pitch = clampf(_pitch - y * 1.4 * delta, -1.15, 1.15)


func _nudge_zoom(delta_z: float) -> void:
	camera.position.z = clampf(camera.position.z + delta_z, 4.2, 9.5)


func _try_pick_at(screen_pos: Vector2) -> void:
	if camera == null:
		return
	var from := camera.project_ray_origin(screen_pos)
	var dir := camera.project_ray_normal(screen_pos)
	var space := get_world_3d().direct_space_state
	if space == null:
		return
	var q := PhysicsRayQueryParameters3D.create(from, from + dir * 40.0)
	q.collide_with_areas = true
	q.collide_with_bodies = false
	var hit := space.intersect_ray(q)
	if hit.is_empty():
		return
	var collider = hit.get("collider")
	if collider == null:
		return
	var rid := str(collider.get_meta("region_id", ""))
	if rid.is_empty():
		return
	_on_pin_hit(rid)


func _on_pin_hit(region_id: String) -> void:
	var now := Time.get_ticks_msec()
	var dbl := (region_id == _last_click_id and now - _last_click_ms < 380)
	_last_click_id = region_id
	_last_click_ms = now
	_selected_id = region_id
	_refresh_pin_look()
	_update_select_label()
	pin_selected.emit(region_id)
	if dbl:
		pin_activated.emit(region_id)


func _sync_pins(regions: Array) -> void:
	# Reuse pool; hide extras
	var need := mini(regions.size(), MAX_PINS)
	while _pins.size() < need:
		_pins.append(_make_pin())
	for i in range(_pins.size()):
		var entry: Dictionary = _pins[i]
		var node: Node3D = entry["node"]
		if i >= need:
			node.visible = false
			entry["id"] = ""
			continue
		var r = regions[i]
		if typeof(r) != TYPE_DICTIONARY:
			node.visible = false
			continue
		var id := str(r.get("id", ""))
		var lat := float(r.get("lat", 0.0))
		var lon := float(r.get("lon", 0.0))
		entry["id"] = id
		entry["data"] = r
		node.visible = true
		node.position = _lat_lon_to_point(lat, lon, EARTH_R + 0.04)
		node.look_at(Vector3.ZERO, Vector3.UP)
		node.rotate_object_local(Vector3.RIGHT, PI * 0.5)
		var area: Area3D = entry["area"]
		area.set_meta("region_id", id)
		area.input_ray_pickable = true


func _make_pin() -> Dictionary:
	var node := Node3D.new()
	pin_root.add_child(node)
	var mesh := MeshInstance3D.new()
	mesh.mesh = _pin_mesh
	mesh.set_surface_override_material(0, _mat_pin_default)
	node.add_child(mesh)
	var area := Area3D.new()
	area.monitoring = false
	area.monitorable = false
	area.input_ray_pickable = true
	area.collision_layer = 1
	area.collision_mask = 0
	var cs := CollisionShape3D.new()
	var sphere := SphereShape3D.new()
	sphere.radius = PIN_R * 2.2
	cs.shape = sphere
	area.add_child(cs)
	node.add_child(area)
	area.input_event.connect(func(_cam, event, _pos, _normal, _shape):
		if event is InputEventMouseButton:
			var mb := event as InputEventMouseButton
			if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
				var rid := str(area.get_meta("region_id", ""))
				if not rid.is_empty():
					_on_pin_hit(rid)
	)
	var label := Label3D.new()
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 18
	label.pixel_size = 0.006
	label.outline_size = 6
	label.modulate = Catppuccin.TEXT
	label.outline_modulate = Catppuccin.CRUST
	label.position = Vector3(0, 0.12, 0)
	label.visible = false
	node.add_child(label)
	return {"id": "", "node": node, "mesh": mesh, "area": area, "label": label, "data": {}}


func _refresh_pin_look() -> void:
	for p in _pins:
		var node: Node3D = p.get("node")
		if node == null or not node.visible:
			continue
		var id := str(p.get("id", ""))
		var data: Dictionary = p.get("data", {})
		var mesh: MeshInstance3D = p.get("mesh")
		var label: Label3D = p.get("label")
		var pass_filter := _pin_passes_filter(id, data)
		node.visible = pass_filter or id == _current_id or id == _selected_id
		if not pass_filter and id != _current_id and id != _selected_id:
			continue
		var mat := _mat_pin_default
		if id == _selected_id:
			mat = _mat_pin_sel
		elif id == _current_id:
			mat = _mat_pin_here
		elif bool(data.get("home", false)):
			mat = _mat_pin_home
		elif bool(data.get("has_ascii_shard", false)):
			mat = _mat_pin_ascii
		elif not pass_filter:
			mat = _mat_pin_dim
		mesh.set_surface_override_material(0, mat)
		if label:
			var show_lbl := id == _selected_id or id == _current_id or bool(data.get("home", false))
			label.visible = show_lbl
			if show_lbl:
				label.text = str(data.get("name", id))
		if id != _selected_id:
			node.scale = Vector3.ONE


func _pin_passes_filter(id: String, data: Dictionary) -> bool:
	if _filter_ascii and not bool(data.get("has_ascii_shard", false)) and not bool(data.get("home", false)):
		return false
	if _filter_q.is_empty():
		return true
	var hay := (
		id + " " + str(data.get("name", "")) + " " + str(data.get("continent", ""))
		+ " " + str(data.get("label", ""))
	).to_lower()
	return _filter_q in hay


func _update_select_label() -> void:
	if _selected_id.is_empty():
		select_label.text = "click pin · dbl = hop"
		select_label.modulate = Catppuccin.OVERLAY1
		return
	var name := _selected_id
	for p in _pins:
		if str(p.get("id", "")) == _selected_id:
			var d: Dictionary = p.get("data", {})
			name = str(d.get("name", _selected_id))
			break
	select_label.text = "▶ %s" % name
	select_label.modulate = Catppuccin.YELLOW


func _update_hud_plate(g: Dictionary) -> void:
	var cur_name := _current_id
	var reg := _as_dict(g.get("region", {}))
	if not reg.is_empty():
		cur_name = str(reg.get("name", _current_id))
	var cd := "ready" if _cooldown <= 0.05 else "%.0fs" % _cooldown
	var zoom := _zoom_level.to_upper()
	hud_plate.text = "%s · hop %d cr · cd %s · %s" % [cur_name, _cost, cd, zoom]
	if _cooldown > 0.05:
		hud_plate.modulate = Catppuccin.PEACH
	else:
		hud_plate.modulate = Catppuccin.SKY


func _apply_zoom_camera() -> void:
	match _zoom_level:
		"street":
			camera.position = Vector3(0, 0.2, 5.2)
			camera.fov = 58.0
		"region":
			camera.position = Vector3(0, 0.15, 6.4)
			camera.fov = 55.0
		_:
			camera.position = Vector3(0, 0.1, 7.4)
			camera.fov = 50.0


func _lat_lon_to_point(lat: float, lon: float, radius: float) -> Vector3:
	# Geographic → Godot Y-up: lat [-90,90], lon [-180,180]
	var phi := deg_to_rad(90.0 - lat)  # colatitude from +Y
	var theta := deg_to_rad(lon)
	var x := radius * sin(phi) * cos(theta)
	var y := radius * cos(phi)
	var z := radius * sin(phi) * sin(theta)
	return Vector3(x, y, z)


func _ensure_mats() -> void:
	if _built_mats:
		return
	_built_mats = true
	_sphere_mesh = SphereMesh.new()
	_sphere_mesh.radius = EARTH_R
	_sphere_mesh.height = EARTH_R * 2.0
	_sphere_mesh.radial_segments = 32
	_sphere_mesh.rings = 16
	_pin_mesh = SphereMesh.new()
	_pin_mesh.radius = PIN_R
	_pin_mesh.height = PIN_R * 2.0
	_pin_mesh.radial_segments = 10
	_pin_mesh.rings = 6

	_mat_earth = StandardMaterial3D.new()
	_mat_earth.albedo_color = Color(Catppuccin.MANTLE.r, Catppuccin.MANTLE.g, Catppuccin.MANTLE.b, 1.0)
	_mat_earth.metallic = 0.35
	_mat_earth.roughness = 0.55
	_mat_earth.emission_enabled = true
	_mat_earth.emission = Catppuccin.SURFACE0
	_mat_earth.emission_energy_multiplier = 0.48

	_mat_grid = StandardMaterial3D.new()
	_mat_grid.albedo_color = Color(Catppuccin.TEAL.r, Catppuccin.TEAL.g, Catppuccin.TEAL.b, 0.22)
	_mat_grid.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_mat_grid.emission_enabled = true
	_mat_grid.emission = Catppuccin.TEAL
	_mat_grid.emission_energy_multiplier = 0.72
	_mat_grid.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_mat_grid.cull_mode = BaseMaterial3D.CULL_DISABLED

	_mat_pin_default = _make_pin_mat(Catppuccin.MAUVE, 0.7)
	_mat_pin_ascii = _make_pin_mat(Catppuccin.SKY, 1.1)
	_mat_pin_home = _make_pin_mat(Catppuccin.GREEN, 1.0)
	_mat_pin_here = _make_pin_mat(Catppuccin.TEAL, 1.4)
	_mat_pin_sel = _make_pin_mat(Catppuccin.YELLOW, 1.8)
	_mat_pin_dim = _make_pin_mat(Catppuccin.OVERLAY0, 0.25)


func _make_pin_mat(col: Color, emit: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = col
	m.metallic = 0.2
	m.roughness = 0.35
	m.emission_enabled = true
	m.emission = col
	m.emission_energy_multiplier = emit
	return m


func _build_earth() -> void:
	# Core sphere
	var core := MeshInstance3D.new()
	core.name = "EarthCore"
	core.mesh = _sphere_mesh
	core.set_surface_override_material(0, _mat_earth)
	earth_spin.add_child(core)
	# Wire latitude rings (stylized grid — Deck-cheap, no textures)
	for lat in [-60.0, -30.0, 0.0, 30.0, 60.0]:
		var ring := _make_lat_ring(lat, EARTH_R * 1.01)
		earth_spin.add_child(ring)
	for lon in [0.0, 45.0, 90.0, 135.0]:
		var mer := _make_meridian(lon, EARTH_R * 1.01)
		earth_spin.add_child(mer)
	# Atmosphere shell
	var atmo_mesh := SphereMesh.new()
	atmo_mesh.radius = EARTH_R * 1.045
	atmo_mesh.height = EARTH_R * 2.09
	atmo_mesh.radial_segments = 24
	atmo_mesh.rings = 12
	var atmo := MeshInstance3D.new()
	atmo.mesh = atmo_mesh
	var atmo_mat := StandardMaterial3D.new()
	atmo_mat.albedo_color = Color(Catppuccin.SKY.r, Catppuccin.SKY.g, Catppuccin.SKY.b, 0.08)
	atmo_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	atmo_mat.emission_enabled = true
	atmo_mat.emission = Catppuccin.BLUE
	atmo_mat.emission_energy_multiplier = 0.25
	atmo_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	atmo_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	atmo.set_surface_override_material(0, atmo_mat)
	earth_spin.add_child(atmo)


func _make_lat_ring(lat: float, radius: float) -> MeshInstance3D:
	var imm := ImmediateMesh.new()
	var mi := MeshInstance3D.new()
	var y := radius * sin(deg_to_rad(lat))
	var r := radius * cos(deg_to_rad(lat))
	imm.surface_begin(Mesh.PRIMITIVE_LINE_STRIP, _mat_grid)
	for i in range(49):
		var a := TAU * float(i) / 48.0
		imm.surface_add_vertex(Vector3(r * cos(a), y, r * sin(a)))
	imm.surface_end()
	mi.mesh = imm
	return mi


func _make_meridian(lon: float, radius: float) -> MeshInstance3D:
	var imm := ImmediateMesh.new()
	var mi := MeshInstance3D.new()
	var th := deg_to_rad(lon)
	imm.surface_begin(Mesh.PRIMITIVE_LINE_STRIP, _mat_grid)
	for i in range(49):
		var phi := PI * float(i) / 48.0  # 0..PI
		var x := radius * sin(phi) * cos(th)
		var y := radius * cos(phi)
		var z := radius * sin(phi) * sin(th)
		imm.surface_add_vertex(Vector3(x, y, z))
	imm.surface_end()
	mi.mesh = imm
	return mi


func _as_dict(v) -> Dictionary:
	return v if typeof(v) == TYPE_DICTIONARY else {}


func _as_arr(v) -> Array:
	return v if typeof(v) == TYPE_ARRAY else []
