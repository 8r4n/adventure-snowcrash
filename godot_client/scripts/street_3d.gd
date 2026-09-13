extends Node3D
class_name Street3D
## Snapshot map → neon 3D street + cyberspace/ICE lattice (#141). Python /ws remains authority.
## #150: landmark readability (J/U/$) + subtle objective world marker / compass tick (no HUD soup · #133).
## Slice 5: lighting / particles / Low-High quality (GraphicsSettings) — Omni budget unchanged.
## Slice 3: jack-in visual language — grid/node lattice, neon ICE walls, layer plates.
## Slice 2: distinct entity silhouettes, facing chevrons, vendor/J/U landmarks.
## Glyphs become PrimitiveMesh instances + Catppuccin emission materials.

const TILE := 1.0
const WALL_H := 2.55
const BUILD_RADIUS_DEFAULT := 18
const ENTITY_RADIUS_DEFAULT := 16
const REBUILD_STEP := 3
const LERP_POS := 11.0
const LERP_YAW := 9.0

## Glyph → mesh role (slice 1). Keep in sync with docs/godot-3d.md.
const GLYPH_ROLE := {
	"#": "wall",
	".": "floor",
	"=": "street",
	",": "grass",
	"~": "water",
	"+": "door",
	" ": "void",
	"J": "jackpoint",
	"U": "uplink",
	"o": "manhole",
	"<": "stairs_up",
	">": "stairs_down",
	"*": "pickup",
	"@": "self",
	"&": "npc",
	"i": "infected",
	"t": "thug",
	"d": "drone",
	"c": "camera",
	"I": "ice",
	"%": "core",
	"X": "exit",
	"$": "vendor",
	"B": "boss",
}

const TERRAIN_BUILD := {
	"#": "wall",
	".": "floor",
	"=": "street",
	",": "grass",
	"~": "water",
	"+": "door",
	"o": "manhole",
	"<": "stairs_up",
	">": "stairs_down",
}

const FACING_YAW := [0.0, -PI / 2.0, PI, PI / 2.0]

enum CamMode { FIRST, THIRD }

@onready var map_root: Node3D = $MapRoot
@onready var entity_root: Node3D = $EntityRoot
@onready var landmark_root: Node3D = $LandmarkRoot
@onready var courier: Node3D = $Courier
@onready var cam_pivot: Node3D = $Courier/CameraPivot
@onready var camera: Camera3D = $Courier/CameraPivot/Camera3D
@onready var courier_mesh: MeshInstance3D = $Courier/Body
@onready var eye_light: OmniLight3D = $Courier/EyeLight
@onready var nameplate: Label3D = $Courier/Nameplate
@onready var world_env: WorldEnvironment = $WorldEnvironment
@onready var moon: DirectionalLight3D = $Moon
@onready var rim: DirectionalLight3D = $Rim
@onready var fx_root: Node3D = $FxRoot

var cam_mode: int = CamMode.THIRD
var _build_radius: int = BUILD_RADIUS_DEFAULT
var _entity_radius: int = ENTITY_RADIUS_DEFAULT
var _max_pooled: int = 48
var _rain: GPUParticles3D
var _dust: GPUParticles3D
var _spark: GPUParticles3D
var _fx_ready: bool = false
var _quality_dirty: bool = true
var _mats: Dictionary = {}
var _meshes: Dictionary = {}
var _entity_pool: Array = []
var _last_map_fp: String = ""
var _last_origin: Vector2i = Vector2i(-99999, -99999)
var _target_pos: Vector3 = Vector3(0.5, 0.0, 0.5)
var _target_yaw: float = 0.0
var _have_pose: bool = false
var _jack_light: OmniLight3D
var _uplink_light: OmniLight3D
var _pulse: float = 0.0
var _last_landmark_fp: String = ""
var _courier_facing: MeshInstance3D
## #150 — objective cue (world marker + courier compass tick). Not a dock dump.
var _objective_root: Node3D
var _objective_beam: MeshInstance3D
var _objective_ring: MeshInstance3D
var _objective_lab: Label3D
var _compass_tick: Node3D
var _compass_wedge: MeshInstance3D
var _compass_lab: Label3D
var _obj_target: Vector2i = Vector2i(-99999, -99999)
var _obj_active: bool = false
var _obj_id: String = ""
var _obj_glyph: String = ""
var _ice_mode: bool = false
var _trans_t: float = 0.0
var _trans_dir: int = 0  # +1 jack-in, -1 jack-out
## Deck: reuse shared PrimitiveMesh + materials; entity nodes are pooled (no free/alloc per snap).
const MAX_POOLED_ENTITIES := 48
const LANDMARK_VENDOR_RADIUS := 22
const ICE_WALL_H := 2.9
const ICE_TRANS_SEC := 0.55
const HEIST_LAYER_NAMES := ["", "Perimeter Scrub", "Honeycomb Lattice", "Core Sanctum"]
## Street WorldEnvironment defaults (street.tscn Env_neon) — restored on jack-out.
const STREET_BG := Color(0.0666667, 0.0666667, 0.105882, 1)
const STREET_AMB := Color(0.22, 0.2, 0.35, 1)
const STREET_FOG := Color(0.14, 0.12, 0.22, 1)


func _ready() -> void:
	_ensure_resources()
	_ensure_courier_parts()
	_ensure_objective_cue()
	_ensure_fx()
	_apply_cam_rig()
	_apply_quality(true)
	if GraphicsSettings:
		if not GraphicsSettings.quality_changed.is_connected(_on_quality_changed):
			GraphicsSettings.quality_changed.connect(_on_quality_changed)
	set_process(true)


func _on_quality_changed(_level: int) -> void:
	_apply_quality(true)


func _apply_quality(force_rebuild: bool = false) -> void:
	## Knobs from GraphicsSettings. Omni count stays ≤3 (courier + J + U).
	if GraphicsSettings:
		_build_radius = GraphicsSettings.build_radius()
		_entity_radius = GraphicsSettings.entity_radius()
		_max_pooled = GraphicsSettings.max_pooled_entities()
	else:
		_build_radius = BUILD_RADIUS_DEFAULT
		_entity_radius = ENTITY_RADIUS_DEFAULT
		_max_pooled = MAX_POOLED_ENTITIES
	_apply_environment_quality()
	_sync_particles()
	if rim:
		rim.visible = GraphicsSettings.rim_enabled() if GraphicsSettings else true
		rim.light_energy = GraphicsSettings.rim_energy() if GraphicsSettings else 0.42
	if force_rebuild:
		_last_map_fp = ""
		_last_landmark_fp = ""
		_quality_dirty = true


func camera_mode_name() -> String:
	return "1st" if cam_mode == CamMode.FIRST else "3rd"


func toggle_camera() -> String:
	cam_mode = CamMode.THIRD if cam_mode == CamMode.FIRST else CamMode.FIRST
	_apply_cam_rig()
	return camera_mode_name()


## Same trigger the web client uses (game.js renderCyberHint / overlay).
static func ice_active(state: Dictionary) -> bool:
	if state.is_empty():
		return false
	var mode := str(state.get("mode", "play"))
	if mode == "cyberspace" or mode == "heist":
		return true
	var cyber = state.get("cyberspace", {})
	if typeof(cyber) == TYPE_DICTIONARY and bool(cyber.get("active", false)):
		return true
	var heist = state.get("ice_heist", {})
	if typeof(heist) == TYPE_DICTIONARY and bool(heist.get("active", false)):
		return true
	return false


## Street body stays parked at J. Avatar lives in cyberspace.px/py or ice_heist.px/py
## (web overlay + swapped snapshot map). Fallback: scan swapped map for @.
static func ice_avatar_xy(state: Dictionary) -> Vector2i:
	var heist = state.get("ice_heist", {})
	if typeof(heist) == TYPE_DICTIONARY and bool(heist.get("active", false)) and heist.has("px"):
		return Vector2i(int(heist.get("px", 0)), int(heist.get("py", 0)))
	var cyber = state.get("cyberspace", {})
	if typeof(cyber) == TYPE_DICTIONARY and bool(cyber.get("active", false)) and cyber.has("px"):
		return Vector2i(int(cyber.get("px", 0)), int(cyber.get("py", 0)))
	var rows = state.get("map", [])
	if typeof(rows) == TYPE_ARRAY:
		for y in range(rows.size()):
			var idx := str(rows[y]).find("@")
			if idx >= 0:
				return Vector2i(idx, y)
	var player: Dictionary = state.get("player", {})
	if typeof(player) != TYPE_DICTIONARY:
		player = {}
	return Vector2i(int(player.get("x", 0)), int(player.get("y", 0)))


static func ice_banner_text(state: Dictionary) -> String:
	var heist = state.get("ice_heist", {})
	if typeof(heist) == TYPE_DICTIONARY and bool(heist.get("active", false)):
		var layer := int(heist.get("layer", 1))
		var layers := int(heist.get("layers", 3))
		var name := ""
		if layer >= 1 and layer < HEIST_LAYER_NAMES.size():
			name = str(HEIST_LAYER_NAMES[layer])
		var ice_n = heist.get("ice_remaining", "?")
		var bits: PackedStringArray = PackedStringArray()
		bits.append("HEIST · L%d/%d" % [layer, layers])
		if not name.is_empty():
			bits.append(name)
		bits.append("ICE %s" % str(ice_n))
		var ai = heist.get("ai", null)
		if typeof(ai) == TYPE_DICTIONARY and not ai.is_empty():
			bits.append("%s %s/%s" % [str(ai.get("name", "AI")), str(ai.get("hp", "?")), str(ai.get("max_hp", "?"))])
		if bool(heist.get("loot_taken", false)):
			bits.append("CORE TAKEN")
		return " · ".join(bits)
	var cyber = state.get("cyberspace", {})
	if typeof(cyber) == TYPE_DICTIONARY and bool(cyber.get("active", false)):
		var nt := str(cyber.get("node_type", "node")).to_upper().replace("_", " ")
		var ice_c = cyber.get("ice_remaining", 0)
		var loot := "LOOT TAKEN" if bool(cyber.get("loot_taken", false)) else ""
		var bits2: PackedStringArray = PackedStringArray()
		bits2.append("CYBER · %s" % nt)
		bits2.append("ICE %s" % str(ice_c))
		if not loot.is_empty():
			bits2.append(loot)
		return " · ".join(bits2)
	return "CYBERSPACE"


func apply_snapshot(state: Dictionary) -> void:
	if state.is_empty():
		return
	var ice_now := ice_active(state)
	if ice_now != _ice_mode:
		_ice_mode = ice_now
		_begin_ice_transition(ice_now)
		_have_pose = false
		_last_map_fp = ""
		_last_landmark_fp = ""
		_apply_ice_environment(ice_now)
	var player: Dictionary = state.get("player", {})
	if typeof(player) != TYPE_DICTIONARY:
		player = {}
	var px: int
	var py: int
	if _ice_mode:
		var xy := ice_avatar_xy(state)
		px = xy.x
		py = xy.y
	else:
		px = int(player.get("x", 0))
		py = int(player.get("y", 0))
	var facing := FpvAscii.facing_index(player)
	_target_pos = Vector3(float(px) + 0.5, 0.12 if _ice_mode else 0.0, float(py) + 0.5)
	_target_yaw = FACING_YAW[facing]
	if not _have_pose:
		courier.position = _target_pos
		courier.rotation.y = _target_yaw
		_have_pose = true
	var nm := str(player.get("name", "Courier"))
	if nameplate:
		nameplate.text = nm
	_rebuild_map_if_needed(state, px, py)
	_paint_landmarks(state, px, py)
	_update_objective_cue(state, px, py)
	_paint_entities(state, px, py, str(state.get("you", player.get("id", ""))))


func _process(delta: float) -> void:
	if _trans_t > 0.0 and camera:
		_trans_t = maxf(0.0, _trans_t - delta)
		var t := 1.0 - (_trans_t / ICE_TRANS_SEC)
		var punch := sin(t * PI) * (18.0 if _trans_dir > 0 else -12.0)
		camera.fov = 70.0 + punch
		if _trans_t <= 0.0:
			camera.fov = 70.0
	if not _have_pose:
		return
	courier.position = courier.position.lerp(_target_pos, clampf(LERP_POS * delta, 0.0, 1.0))
	courier.rotation.y = lerp_angle(courier.rotation.y, _target_yaw, clampf(LERP_YAW * delta, 0.0, 1.0))
	_pulse += delta
	var pulse := 1.0 + 0.35 * sin(_pulse * 3.2)
	if _jack_light:
		_jack_light.light_energy = 2.85 * pulse
	if _uplink_light:
		_uplink_light.light_energy = 3.05 * pulse
	_pulse_objective_cue(pulse)
	_orient_compass_tick()
	_follow_fx()
	if _ice_mode:
		var ice_e := 1.2 + 0.55 * sin(_pulse * 4.2)
		_pulse_mat("ice_barrier", ice_e)
		_pulse_mat("ice_node", 1.4 + 0.5 * sin(_pulse * 3.6))
		_pulse_mat("core", 1.5 + 0.7 * sin(_pulse * 5.0))
		_pulse_mat("ice_frame", 1.1 + 0.35 * sin(_pulse * 2.4))


func _apply_cam_rig() -> void:
	if cam_pivot == null or camera == null:
		return
	if cam_mode == CamMode.FIRST:
		cam_pivot.position = Vector3(0.0, 1.52, 0.0)
		camera.position = Vector3(0.0, 0.0, 0.12)
		camera.rotation_degrees = Vector3(0.0, 0.0, 0.0)
		if courier_mesh:
			courier_mesh.visible = false
		var head_1st := courier.get_node_or_null("Head") as MeshInstance3D
		if head_1st:
			head_1st.visible = false
		if _courier_facing:
			_courier_facing.visible = false
		if nameplate:
			nameplate.visible = false
	else:
		cam_pivot.position = Vector3(0.0, 1.28, 0.0)
		camera.position = Vector3(0.0, 0.72, 3.35)
		camera.rotation_degrees = Vector3(-14.0, 0.0, 0.0)
		if courier_mesh:
			courier_mesh.visible = true
		var head_3rd := courier.get_node_or_null("Head") as MeshInstance3D
		if head_3rd:
			head_3rd.visible = true
		if _courier_facing:
			_courier_facing.visible = true
		if nameplate:
			nameplate.visible = true
	camera.current = true


func _ensure_resources() -> void:
	if not _mats.is_empty():
		return
	_mats["wall"] = _mat(Catppuccin.TEAL.darkened(0.32), 0.72, 0.22)
	_mats["wall_hi"] = _mat(Catppuccin.SKY.darkened(0.15), 1.05, 0.28)
	_mats["floor"] = _mat(Catppuccin.SURFACE0, 0.04, 0.08)
	_mats["street"] = _mat(Catppuccin.MANTLE.lightened(0.1), 0.14, 0.32)
	_mats["grass"] = _mat(Catppuccin.GREEN.darkened(0.55), 0.05, 0.0)
	_mats["water"] = _mat(Color(0.29, 0.56, 0.85, 0.72), 0.35, 0.4)
	_mats["door"] = _mat(Catppuccin.YELLOW, 0.7, 0.2)
	_mats["void"] = _mat(Catppuccin.CRUST, 0.0, 0.0)
	_mats["manhole"] = _mat(Catppuccin.OVERLAY0, 0.15, 0.6)
	_mats["stairs"] = _mat(Catppuccin.LAVENDER.darkened(0.25), 0.25, 0.15)
	_mats["loot"] = _mat(Catppuccin.YELLOW, 1.1, 0.1)
	_mats["jack"] = _mat(Catppuccin.SKY, 2.55, 0.12)
	_mats["uplink"] = _mat(Catppuccin.PEACH, 2.65, 0.15)
	_mats["self"] = _mat(Catppuccin.TEAL, 0.7, 0.2)
	_mats["npc"] = _mat(Catppuccin.LAVENDER, 0.55, 0.1)
	_mats["infected"] = _mat(Catppuccin.GREEN, 0.7, 0.05)
	_mats["thug"] = _mat(Catppuccin.PEACH, 0.75, 0.1)
	_mats["drone"] = _mat(Catppuccin.MAUVE, 1.0, 0.35)
	_mats["camera"] = _mat(Catppuccin.RED, 1.2, 0.2)
	_mats["ice"] = _mat(Catppuccin.BLUE, 1.1, 0.25)
	_mats["core"] = _mat(Catppuccin.PINK, 1.4, 0.15)
	_mats["exit"] = _mat(Catppuccin.GREEN, 1.0, 0.1)
	_mats["other"] = _mat(Catppuccin.BLUE, 0.65, 0.15)
	_mats["other_hi"] = _mat(Catppuccin.SKY, 0.95, 0.2)
	_mats["vendor"] = _mat(Catppuccin.YELLOW, 2.4, 0.2)
	_mats["vendor_trim"] = _mat(Catppuccin.PEACH, 1.85, 0.25)
	_mats["pickup"] = _mat(Catppuccin.YELLOW, 1.35, 0.1)
	_mats["boss"] = _mat(Catppuccin.RED, 1.15, 0.2)
	_mats["facing"] = _mat(Catppuccin.TEAL, 1.4, 0.15)
	_mats["facing_other"] = _mat(Catppuccin.SKY, 1.3, 0.15)
	_mats["obj_beam"] = _mat(Catppuccin.TEAL, 2.1, 0.1)
	_mats["obj_ring"] = _mat(Catppuccin.YELLOW, 2.0, 0.15)
	_mats["compass"] = _mat(Catppuccin.TEAL, 1.8, 0.1)
	_mats["jack_shaft"] = _mat(Catppuccin.SKY, 2.8, 0.08)
	_mats["uplink_shaft"] = _mat(Catppuccin.PEACH, 2.9, 0.08)
	_mats["vendor_shaft"] = _mat(Catppuccin.YELLOW, 2.6, 0.1)
	_mats["prop"] = _mat(Catppuccin.SURFACE1, 0.2, 0.2)
	_mats["npc_head"] = _mat(Catppuccin.LAVENDER.lightened(0.12), 0.7, 0.1)
	_mats["infected_head"] = _mat(Catppuccin.GREEN.darkened(0.15), 0.85, 0.05)
	_mats["thug_head"] = _mat(Catppuccin.PEACH.darkened(0.1), 0.9, 0.15)
	# Slice 3 — cyberspace / ICE lattice (distinct from street brick).
	_mats["ice_wall"] = _mat_alpha(Color(0.25, 0.55, 0.85, 0.38), 0.55, 0.45, 0.38)
	_mats["ice_frame"] = _mat(Catppuccin.SKY, 1.35, 0.55)
	_mats["ice_floor"] = _mat(Color(0.08, 0.12, 0.22, 1), 0.12, 0.35)
	_mats["ice_grid"] = _mat(Catppuccin.SKY, 1.6, 0.2)
	_mats["ice_barrier"] = _mat_alpha(Color(0.35, 0.62, 1.0, 0.5), 1.4, 0.2, 0.5)
	_mats["ice_node"] = _mat(Catppuccin.MAUVE, 1.6, 0.15)
	_mats["ice_void"] = _mat(Color(0.02, 0.03, 0.07, 1), 0.0, 0.0)
	_mats["ice_exit_ring"] = _mat(Catppuccin.GREEN, 1.7, 0.15)
	if _mats["water"] is StandardMaterial3D:
		(_mats["water"] as StandardMaterial3D).transparency = BaseMaterial3D.TRANSPARENCY_ALPHA

	var box := BoxMesh.new()
	box.size = Vector3(1, 1, 1)
	_meshes["box"] = box
	var floor_m := BoxMesh.new()
	floor_m.size = Vector3(1.0, 0.08, 1.0)
	_meshes["floor"] = floor_m
	var cyl := CylinderMesh.new()
	cyl.top_radius = 0.22
	cyl.bottom_radius = 0.28
	cyl.height = 2.4
	_meshes["pillar"] = cyl
	var disc := CylinderMesh.new()
	disc.top_radius = 0.42
	disc.bottom_radius = 0.42
	disc.height = 0.12
	_meshes["disc"] = disc
	var sph := SphereMesh.new()
	sph.radius = 0.28
	sph.height = 0.56
	_meshes["sphere"] = sph
	var cap := CapsuleMesh.new()
	cap.radius = 0.26
	cap.height = 1.35
	_meshes["capsule"] = cap
	var cap_tall := CapsuleMesh.new()
	cap_tall.radius = 0.24
	cap_tall.height = 1.55
	_meshes["capsule_tall"] = cap_tall
	var cap_short := CapsuleMesh.new()
	cap_short.radius = 0.3
	cap_short.height = 1.05
	_meshes["capsule_short"] = cap_short
	var head := SphereMesh.new()
	head.radius = 0.18
	head.height = 0.36
	_meshes["head"] = head
	var wedge := PrismMesh.new()
	wedge.size = Vector3(0.28, 0.12, 0.42)
	_meshes["facing"] = wedge
	var kiosk := BoxMesh.new()
	kiosk.size = Vector3(0.7, 1.0, 0.55)
	_meshes["kiosk"] = kiosk
	var canopy := BoxMesh.new()
	canopy.size = Vector3(0.95, 0.12, 0.7)
	_meshes["canopy"] = canopy
	var shaft := BoxMesh.new()
	shaft.size = Vector3(0.14, 1.0, 0.14)
	_meshes["shaft"] = shaft
	var glyph_disc := CylinderMesh.new()
	glyph_disc.top_radius = 0.55
	glyph_disc.bottom_radius = 0.55
	glyph_disc.height = 0.08
	_meshes["glyph_disc"] = glyph_disc
	var obj_beam := BoxMesh.new()
	obj_beam.size = Vector3(0.1, 1.0, 0.1)
	_meshes["obj_beam"] = obj_beam
	var ring := TorusMesh.new()
	ring.inner_radius = 0.22
	ring.outer_radius = 0.38
	_meshes["ring"] = ring
	var plane := PlaneMesh.new()
	plane.size = Vector2(float(_build_radius * 2 + 6), float(_build_radius * 2 + 6))
	_meshes["ground"] = plane


func _mat(color: Color, emission_energy: float = 0.0, metallic: float = 0.15) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.42
	m.metallic = metallic
	if emission_energy > 0.0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = emission_energy
	return m


func _mat_alpha(color: Color, emission_energy: float, metallic: float, alpha: float) -> StandardMaterial3D:
	var m := _mat(color, emission_energy, metallic)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color.a = alpha
	return m


func _pulse_mat(key: String, energy: float) -> void:
	if not _mats.has(key):
		return
	var m = _mats[key]
	if m is StandardMaterial3D:
		(m as StandardMaterial3D).emission_energy_multiplier = energy


func _rebuild_map_if_needed(state: Dictionary, px: int, py: int) -> void:
	var origin := Vector2i(px, py)
	var fp := _map_fingerprint(state, px, py)
	var moved := maxi(absi(origin.x - _last_origin.x), absi(origin.y - _last_origin.y))
	if fp == _last_map_fp and moved < REBUILD_STEP:
		return
	_last_map_fp = fp
	_last_origin = origin
	_rebuild_map(state, px, py)


func _map_fingerprint(state: Dictionary, px: int, py: int) -> String:
	var rows = state.get("map", [])
	if typeof(rows) != TYPE_ARRAY:
		return "nomap"
	var bits: PackedStringArray = PackedStringArray()
	bits.append("%d:%d:r%d" % [int(px / REBUILD_STEP), int(py / REBUILD_STEP), _build_radius])
	var y0 := maxi(0, py - _build_radius)
	var y1 := mini(rows.size(), py + _build_radius + 1)
	for y in range(y0, y1):
		var row := str(rows[y])
		var x0 := maxi(0, px - _build_radius)
		var x1 := mini(row.length(), px + _build_radius + 1)
		bits.append(row.substr(x0, x1 - x0))
	bits.append(str(state.get("jackpoint", [])))
	bits.append(str(state.get("uplink", [])))
	bits.append(str(state.get("plane", state.get("z", 0))))
	bits.append("ice" if _ice_mode else "street")
	if _ice_mode:
		var cyber = state.get("cyberspace", {})
		var heist = state.get("ice_heist", {})
		if typeof(heist) == TYPE_DICTIONARY:
			bits.append("h%s:%s" % [str(heist.get("layer", 0)), str(heist.get("ice_remaining", 0))])
		if typeof(cyber) == TYPE_DICTIONARY:
			bits.append("c%s:%s" % [str(cyber.get("node_type", "")), str(cyber.get("ice_remaining", 0))])
	return "".join(bits)


func _rebuild_map(state: Dictionary, px: int, py: int) -> void:
	_ensure_resources()
	for c in map_root.get_children():
		c.free()
	var rows = state.get("map", [])
	if typeof(rows) != TYPE_ARRAY or rows.is_empty():
		return

	var ground := MeshInstance3D.new()
	ground.mesh = _meshes["ground"]
	ground.material_override = _mats["ice_void"] if _ice_mode else _mats["void"]
	ground.position = Vector3(float(px) + 0.5, -0.05, float(py) + 0.5)
	map_root.add_child(ground)

	var y0 := maxi(0, py - _build_radius)
	var y1 := mini(rows.size(), py + _build_radius + 1)
	for y in range(y0, y1):
		var row := str(rows[y])
		var x0 := maxi(0, px - _build_radius)
		var x1 := mini(row.length(), px + _build_radius + 1)
		for x in range(x0, x1):
			var ch := row.substr(x, 1)
			if ch == " ":
				continue
			_place_tile(ch, x, y, (x + y) & 1 == 0)


func _place_tile(ch: String, x: int, y: int, alt: bool) -> void:
	var origin := Vector3(float(x) + 0.5, 0.0, float(y) + 0.5)
	if _ice_mode:
		_place_ice_tile(ch, origin, alt)
		return
	var role := str(TERRAIN_BUILD.get(ch, GLYPH_ROLE.get(ch, "prop")))
	if role in ["jackpoint", "uplink", "self", "npc", "infected", "thug", "drone", "camera", "ice", "core", "exit", "pickup", "vendor", "boss"]:
		_add_mesh(map_root, _meshes["floor"], _mats["floor"], origin + Vector3(0, 0.04, 0))
		# Dynamic entities / landmarks own the upright mesh — floor only here.
		return
	if not TERRAIN_BUILD.has(ch) and ch.length() == 1:
		# Unknown visible glyph (other courier letter, item) — walkable floor.
		_add_mesh(map_root, _meshes["floor"], _mats["floor"], origin + Vector3(0, 0.04, 0))
		return

	match role:
		"wall":
			var mat = _mats["wall_hi"] if alt else _mats["wall"]
			_add_mesh(map_root, _meshes["box"], mat, origin + Vector3(0, WALL_H * 0.5, 0), Vector3(1.0, WALL_H, 1.0))
		"floor":
			_add_mesh(map_root, _meshes["floor"], _mats["floor"], origin + Vector3(0, 0.04, 0))
		"street":
			_add_mesh(map_root, _meshes["floor"], _mats["street"], origin + Vector3(0, 0.04, 0))
			# Neon lane tick
			_add_mesh(map_root, _meshes["box"], _mats["door"], origin + Vector3(0, 0.07, 0), Vector3(0.12, 0.02, 0.55))
		"grass":
			_add_mesh(map_root, _meshes["floor"], _mats["grass"], origin + Vector3(0, 0.04, 0))
		"water":
			_add_mesh(map_root, _meshes["floor"], _mats["water"], origin + Vector3(0, 0.02, 0), Vector3(1.0, 0.7, 1.0))
		"door":
			_add_mesh(map_root, _meshes["floor"], _mats["floor"], origin + Vector3(0, 0.04, 0))
			_add_mesh(map_root, _meshes["box"], _mats["door"], origin + Vector3(0, 1.15, 0), Vector3(0.18, 2.2, 0.92))
			_add_mesh(map_root, _meshes["box"], _mats["door"], origin + Vector3(0, 1.15, 0), Vector3(0.92, 2.2, 0.18))
		"manhole":
			_add_mesh(map_root, _meshes["floor"], _mats["floor"], origin + Vector3(0, 0.04, 0))
			_add_mesh(map_root, _meshes["disc"], _mats["manhole"], origin + Vector3(0, 0.1, 0))
		"stairs_up", "stairs_down":
			_add_mesh(map_root, _meshes["floor"], _mats["floor"], origin + Vector3(0, 0.04, 0))
			var h := 0.55 if role == "stairs_up" else 0.28
			_add_mesh(map_root, _meshes["box"], _mats["stairs"], origin + Vector3(0, h * 0.5, 0), Vector3(0.85, h, 0.85))
		_:
			_add_mesh(map_root, _meshes["floor"], _mats["floor"], origin + Vector3(0, 0.04, 0))


func _paint_landmarks(state: Dictionary, px: int, py: int) -> void:
	if _ice_mode:
		_paint_ice_layer_plate(state, px, py)
		_sync_particles()
		return
	var jack = state.get("jackpoint", [])
	var uplink = state.get("uplink", [])
	var marks = state.get("landmarks", [])
	var fp := "%s|%s|%s|%d:%d" % [str(jack), str(uplink), str(marks), int(px / REBUILD_STEP), int(py / REBUILD_STEP)]
	if fp == _last_landmark_fp and landmark_root.get_child_count() > 0:
		return
	_last_landmark_fp = fp
	for c in landmark_root.get_children():
		c.free()
	_jack_light = null
	_uplink_light = null
	var seen: Dictionary = {}
	if typeof(jack) == TYPE_ARRAY and jack.size() >= 2:
		_spawn_jack_uplink(int(jack[0]), int(jack[1]), px, py, true)
		seen["%d:%d" % [int(jack[0]), int(jack[1])]] = true
	if typeof(uplink) == TYPE_ARRAY and uplink.size() >= 2:
		_spawn_jack_uplink(int(uplink[0]), int(uplink[1]), px, py, false)
		seen["%d:%d" % [int(uplink[0]), int(uplink[1])]] = true
	if typeof(marks) == TYPE_ARRAY:
		for m in marks:
			if typeof(m) != TYPE_DICTIONARY:
				continue
			var mx := int(m.get("x", -999))
			var my := int(m.get("y", -999))
			var key := "%d:%d" % [mx, my]
			if seen.get(key, false):
				continue
			var g := str(m.get("glyph", ""))
			var nm := str(m.get("name", g))
			if g == "$" or str(m.get("id", "")).begins_with("vendor"):
				_spawn_vendor(mx, my, px, py, nm)
				seen[key] = true
			elif g == "*" or str(m.get("id", "")).begins_with("signal"):
				_spawn_pickup_beacon(mx, my, px, py, nm if nm else "Loot")
				seen[key] = true
	_sync_particles()


func _spawn_jack_uplink(x: int, y: int, px: int, py: int, is_jack: bool) -> void:
	## #150 — taller silhouette + emissive shaft + big glyph disc readable at street AOI.
	if maxi(absi(x - px), absi(y - py)) > _build_radius + 8:
		return
	var origin := Vector3(float(x) + 0.5, 0.0, float(y) + 0.5)
	var holder := Node3D.new()
	holder.position = origin
	landmark_root.add_child(holder)
	var mat: Material = _mats["jack"] if is_jack else _mats["uplink"]
	var shaft_mat: Material = _mats["jack_shaft"] if is_jack else _mats["uplink_shaft"]
	# Tall readable silhouette: wide plinth + pillar + crown + vertical emissive shaft.
	_add_mesh(holder, _meshes["box"], mat, Vector3(0, 0.2, 0), Vector3(0.95, 0.4, 0.95))
	_add_mesh(holder, _meshes["pillar"], mat, Vector3(0, 1.55, 0), Vector3(1.15, 1.35, 1.15) if is_jack else Vector3(1.0, 1.55, 1.0))
	_add_mesh(holder, _meshes["shaft"], shaft_mat, Vector3(0, 2.35, 0), Vector3(0.85, 3.6, 0.85) if is_jack else Vector3(0.75, 4.1, 0.75))
	_add_mesh(holder, _meshes["sphere"], mat, Vector3(0, 3.35, 0), Vector3(1.1, 1.1, 1.1) if is_jack else Vector3(1.35, 1.35, 1.35))
	_add_mesh(holder, _meshes["glyph_disc"], mat, Vector3(0, 3.85, 0), Vector3(1.15, 1.0, 1.15) if is_jack else Vector3(1.25, 1.0, 1.25))
	if not is_jack:
		_add_mesh(holder, _meshes["ring"], mat, Vector3(0, 2.85, 0), Vector3(1.15, 1.0, 1.15))
		_add_mesh(holder, _meshes["ring"], mat, Vector3(0, 3.55, 0), Vector3(0.85, 0.85, 0.85))
	var light := OmniLight3D.new()
	light.light_color = Catppuccin.SKY if is_jack else Catppuccin.PEACH
	light.light_energy = 2.85 if is_jack else 3.05
	light.omni_range = 13.5
	light.omni_attenuation = 1.15
	light.shadow_enabled = false
	light.position = Vector3(0, 3.1, 0)
	holder.add_child(light)
	if is_jack:
		_jack_light = light
	else:
		_uplink_light = light
	# Big single-glyph billboard (street distance) + quiet subtitle — not HUD soup.
	var glyph := Label3D.new()
	glyph.text = "J" if is_jack else "U"
	glyph.position = Vector3(0, 4.55, 0)
	glyph.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	glyph.font_size = 96
	glyph.outline_size = 22
	glyph.modulate = Catppuccin.SKY if is_jack else Catppuccin.PEACH
	glyph.outline_modulate = Catppuccin.CRUST
	glyph.pixel_size = 0.01
	holder.add_child(glyph)
	var lab := Label3D.new()
	lab.text = "JACKPOINT" if is_jack else "UPLINK"
	lab.position = Vector3(0, 5.15, 0)
	lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lab.font_size = 28
	lab.outline_size = 10
	lab.modulate = Catppuccin.SKY if is_jack else Catppuccin.PEACH
	lab.outline_modulate = Catppuccin.CRUST
	lab.pixel_size = 0.008
	holder.add_child(lab)


func _spawn_vendor(x: int, y: int, px: int, py: int, label: String) -> void:
	## #150 — taller $ silhouette + emissive mast (no Omni — Deck budget stays courier + J + U).
	if maxi(absi(x - px), absi(y - py)) > LANDMARK_VENDOR_RADIUS:
		return
	var holder := Node3D.new()
	holder.position = Vector3(float(x) + 0.5, 0.0, float(y) + 0.5)
	landmark_root.add_child(holder)
	_add_mesh(holder, _meshes["box"], _mats["vendor_trim"], Vector3(0, 0.1, 0), Vector3(1.0, 0.14, 0.8))
	_add_mesh(holder, _meshes["kiosk"], _mats["vendor"], Vector3(0, 0.95, 0), Vector3(1.1, 1.15, 1.05))
	_add_mesh(holder, _meshes["canopy"], _mats["vendor_trim"], Vector3(0, 1.75, 0), Vector3(1.15, 1.0, 1.1))
	_add_mesh(holder, _meshes["shaft"], _mats["vendor_shaft"], Vector3(0, 2.55, 0), Vector3(0.7, 2.4, 0.7))
	_add_mesh(holder, _meshes["sphere"], _mats["vendor"], Vector3(0, 3.35, 0), Vector3(0.7, 0.7, 0.7))
	_add_mesh(holder, _meshes["glyph_disc"], _mats["vendor"], Vector3(0, 3.75, 0), Vector3(1.05, 1.0, 1.05))
	var glyph := Label3D.new()
	glyph.text = "$"
	glyph.position = Vector3(0, 4.35, 0)
	glyph.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	glyph.font_size = 88
	glyph.outline_size = 20
	glyph.modulate = Catppuccin.YELLOW
	glyph.outline_modulate = Catppuccin.CRUST
	glyph.pixel_size = 0.01
	holder.add_child(glyph)
	var lab := Label3D.new()
	lab.text = label if label else "VENDOR"
	lab.position = Vector3(0, 4.95, 0)
	lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lab.font_size = 26
	lab.outline_size = 9
	lab.modulate = Catppuccin.YELLOW
	lab.outline_modulate = Catppuccin.CRUST
	lab.pixel_size = 0.008
	holder.add_child(lab)


func _spawn_pickup_beacon(x: int, y: int, px: int, py: int, label: String) -> void:
	if maxi(absi(x - px), absi(y - py)) > _entity_radius + 4:
		return
	var holder := Node3D.new()
	holder.position = Vector3(float(x) + 0.5, 0.0, float(y) + 0.5)
	landmark_root.add_child(holder)
	_add_mesh(holder, _meshes["sphere"], _mats["pickup"], Vector3(0, 0.55, 0), Vector3(0.7, 0.7, 0.7))
	_add_mesh(holder, _meshes["disc"], _mats["loot"], Vector3(0, 0.12, 0), Vector3(0.7, 0.7, 0.7))
	var lab := Label3D.new()
	lab.text = "*  %s" % label
	lab.position = Vector3(0, 1.35, 0)
	lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lab.font_size = 24
	lab.outline_size = 8
	lab.modulate = Catppuccin.YELLOW
	lab.outline_modulate = Catppuccin.CRUST
	lab.pixel_size = 0.008
	holder.add_child(lab)


func _ensure_objective_cue() -> void:
	## Subtle world marker + courier compass tick (#150). No dock chrome.
	if _objective_root == null:
		_objective_root = Node3D.new()
		_objective_root.name = "ObjectiveCue"
		add_child(_objective_root)
		_objective_beam = _add_mesh(_objective_root, _meshes["obj_beam"], _mats["obj_beam"], Vector3(0, 2.8, 0), Vector3(1.0, 5.5, 1.0))
		_objective_ring = _add_mesh(_objective_root, _meshes["ring"], _mats["obj_ring"], Vector3(0, 4.6, 0), Vector3(1.35, 0.55, 1.35))
		_objective_lab = Label3D.new()
		_objective_lab.name = "ObjectiveLab"
		_objective_lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		_objective_lab.font_size = 42
		_objective_lab.outline_size = 14
		_objective_lab.pixel_size = 0.009
		_objective_lab.outline_modulate = Catppuccin.CRUST
		_objective_lab.position = Vector3(0, 5.55, 0)
		_objective_root.add_child(_objective_lab)
		_objective_root.visible = false
	if _compass_tick == null and courier != null:
		_compass_tick = Node3D.new()
		_compass_tick.name = "CompassTick"
		courier.add_child(_compass_tick)
		_compass_tick.position = Vector3(0.0, 2.15, 0.0)
		_compass_wedge = MeshInstance3D.new()
		_compass_wedge.name = "Wedge"
		_compass_wedge.mesh = _meshes["facing"]
		_compass_wedge.material_override = _mats["compass"]
		_compass_wedge.position = Vector3(0.0, 0.0, -0.55)
		_compass_wedge.rotation_degrees = Vector3(90, 0, 0)
		_compass_wedge.scale = Vector3(1.35, 1.0, 1.55)
		_compass_tick.add_child(_compass_wedge)
		_compass_lab = Label3D.new()
		_compass_lab.name = "TickLab"
		_compass_lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		_compass_lab.font_size = 22
		_compass_lab.outline_size = 8
		_compass_lab.pixel_size = 0.007
		_compass_lab.modulate = Catppuccin.TEAL
		_compass_lab.outline_modulate = Catppuccin.CRUST
		_compass_lab.position = Vector3(0.0, 0.35, 0.0)
		_compass_tick.add_child(_compass_lab)
		_compass_tick.visible = false


func _parse_objective_target(state: Dictionary) -> Dictionary:
	## Snapshot objective from Payload-Zero / Signal Keys / pilgrimage / globe.
	var out := {"active": false, "id": "", "glyph": "", "x": 0, "y": 0, "compass": "", "dist": null, "text": ""}
	var obj = state.get("objective", null)
	if typeof(obj) != TYPE_DICTIONARY:
		return out
	var target = obj.get("target", null)
	var tx := -99999
	var ty := -99999
	if typeof(target) == TYPE_ARRAY and target.size() >= 2:
		tx = int(target[0])
		ty = int(target[1])
	elif typeof(target) == TYPE_DICTIONARY:
		tx = int(target.get("x", -99999))
		ty = int(target.get("y", -99999))
	var oid := str(obj.get("id", ""))
	if tx <= -99990:
		# Fallback: resolve Payload-Zero landmark ids from jackpoint / uplink arrays.
		if oid == "jackpoint":
			var jack = state.get("jackpoint", [])
			if typeof(jack) == TYPE_ARRAY and jack.size() >= 2:
				tx = int(jack[0])
				ty = int(jack[1])
		elif oid == "uplink":
			var uplink = state.get("uplink", [])
			if typeof(uplink) == TYPE_ARRAY and uplink.size() >= 2:
				tx = int(uplink[0])
				ty = int(uplink[1])
	if tx <= -99990:
		return out
	var glyph := "★"
	if oid == "jackpoint" or oid == "J":
		glyph = "J"
	elif oid == "uplink" or oid == "U":
		glyph = "U"
	elif oid.begins_with("vendor") or oid == "$":
		glyph = "$"
	elif "signal" in oid or oid == "loot":
		glyph = "*"
	out["active"] = true
	out["id"] = oid
	out["glyph"] = glyph
	out["x"] = tx
	out["y"] = ty
	out["compass"] = str(obj.get("compass", ""))
	out["dist"] = obj.get("dist", null)
	out["text"] = str(obj.get("text", ""))
	return out


func _update_objective_cue(state: Dictionary, px: int, py: int) -> void:
	_ensure_resources()
	_ensure_objective_cue()
	if _ice_mode:
		_obj_active = false
		if _objective_root:
			_objective_root.visible = false
		if _compass_tick:
			_compass_tick.visible = false
		return
	var info := _parse_objective_target(state)
	_obj_active = bool(info.get("active", false))
	_obj_id = str(info.get("id", ""))
	_obj_glyph = str(info.get("glyph", "★"))
	if not _obj_active:
		if _objective_root:
			_objective_root.visible = false
		if _compass_tick:
			_compass_tick.visible = false
		return
	_obj_target = Vector2i(int(info["x"]), int(info["y"]))
	# World marker at objective landmark (hidden when already on the tile).
	var here := (_obj_target.x == px and _obj_target.y == py)
	var far := maxi(absi(_obj_target.x - px), absi(_obj_target.y - py)) > _build_radius + 10
	if _objective_root:
		_objective_root.position = Vector3(float(_obj_target.x) + 0.5, 0.0, float(_obj_target.y) + 0.5)
		_objective_root.visible = (not here) and (not far)
		if _objective_lab:
			var bits: PackedStringArray = PackedStringArray()
			bits.append(_obj_glyph if not _obj_glyph.is_empty() else "★")
			var compass := str(info.get("compass", ""))
			if not compass.is_empty() and compass != "·":
				bits.append(compass)
			var dist = info.get("dist", null)
			if dist != null:
				bits.append("%sm" % str(dist))
			_objective_lab.text = " ".join(bits)
			_objective_lab.modulate = Catppuccin.SKY if _obj_glyph == "J" else (Catppuccin.PEACH if _obj_glyph == "U" else Catppuccin.YELLOW)
	if _compass_tick:
		_compass_tick.visible = not here
		if _compass_lab:
			var c := str(info.get("compass", "·"))
			var d = info.get("dist", null)
			if d != null:
				_compass_lab.text = "%s %s · %sm" % [_obj_glyph, c, str(d)]
			else:
				_compass_lab.text = "%s %s" % [_obj_glyph, c]
		_orient_compass_tick()


func _pulse_objective_cue(pulse: float) -> void:
	if not _obj_active or _objective_root == null or not _objective_root.visible:
		return
	if _objective_beam and _objective_beam.material_override is StandardMaterial3D:
		(_objective_beam.material_override as StandardMaterial3D).emission_energy_multiplier = 1.6 + 0.7 * sin(_pulse * 3.6)
	if _objective_ring:
		_objective_ring.rotation.y = _pulse * 1.4
		_objective_ring.position.y = 4.4 + 0.12 * sin(_pulse * 2.8)


func _orient_compass_tick() -> void:
	if _compass_tick == null or not _obj_active or not _compass_tick.visible:
		return
	# Point toward objective in XZ; keep tick upright relative to world yaw vs courier.
	var to := Vector3(float(_obj_target.x) + 0.5, 0.0, float(_obj_target.y) + 0.5)
	var from := courier.global_position if courier else Vector3.ZERO
	var flat := Vector3(to.x - from.x, 0.0, to.z - from.z)
	if flat.length_squared() < 0.0001:
		return
	var world_yaw := atan2(-flat.x, -flat.z)
	# CompassTick is a child of courier — compensate courier yaw so wedge faces target.
	_compass_tick.rotation.y = world_yaw - courier.rotation.y


func _paint_entities(state: Dictionary, px: int, py: int, you: String) -> void:
	# Street entities stay at parked-body coords — hide the pool while jacked.
	if _ice_mode:
		for node in _entity_pool:
			(node as Node3D).visible = false
		return
	var needed: Array = []
	var occupied: Dictionary = {}
	var players = state.get("players", [])
	if typeof(players) == TYPE_ARRAY:
		for p in players:
			if typeof(p) != TYPE_DICTIONARY:
				continue
			if str(p.get("id", "")) == you:
				continue
			if not bool(p.get("alive", true)):
				continue
			var ex := int(p.get("x", -999))
			var ey := int(p.get("y", -999))
			if maxi(absi(ex - px), absi(ey - py)) > _entity_radius:
				continue
			occupied["%d:%d" % [ex, ey]] = true
			needed.append({
				"x": ex, "y": ey,
				"role": "other",
				"label": str(p.get("name", p.get("glyph", "?"))),
				"yaw": FACING_YAW[int(p.get("facing", 0)) % 4],
				"facing": true,
			})
	var ents = state.get("entities", [])
	if typeof(ents) == TYPE_ARRAY:
		for e in ents:
			if typeof(e) != TYPE_DICTIONARY:
				continue
			var ex2 := int(e.get("x", -999))
			var ey2 := int(e.get("y", -999))
			if maxi(absi(ex2 - px), absi(ey2 - py)) > _entity_radius:
				continue
			var g := str(e.get("glyph", "?"))
			var role := str(GLYPH_ROLE.get(g, "prop"))
			if role in ["jackpoint", "uplink", "vendor", "self"]:
				continue
			# Kind hint from cameras / ICE
			if str(e.get("kind", "")) == "camera":
				role = "camera"
			occupied["%d:%d" % [ex2, ey2]] = true
			var yaw := 0.0
			var has_facing := false
			if e.has("facing"):
				yaw = FACING_YAW[int(e.get("facing", 0)) % 4]
				has_facing = role in ["npc", "other", "thug", "infected", "boss"]
			needed.append({
				"x": ex2, "y": ey2,
				"role": role,
				"label": str(e.get("name", g)),
				"yaw": yaw,
				"facing": has_facing,
			})

	# Map-glyph pickups (*) when snapshot overlays loot but landmarks omit it.
	var rows = state.get("map", [])
	if typeof(rows) == TYPE_ARRAY:
		var y0 := maxi(0, py - _entity_radius)
		var y1 := mini(rows.size(), py + _entity_radius + 1)
		for y in range(y0, y1):
			var row := str(rows[y])
			var x0 := maxi(0, px - _entity_radius)
			var x1 := mini(row.length(), px + _entity_radius + 1)
			for x in range(x0, x1):
				if row.substr(x, 1) != "*":
					continue
				var key := "%d:%d" % [x, y]
				if occupied.get(key, false):
					continue
				occupied[key] = true
				needed.append({
					"x": x, "y": y,
					"role": "pickup",
					"label": "Loot",
					"yaw": 0.0,
					"facing": false,
				})

	if needed.size() > _max_pooled:
		needed = needed.slice(0, _max_pooled)

	while _entity_pool.size() < needed.size():
		_entity_pool.append(_make_entity_node())
	for i in range(_entity_pool.size()):
		var node: Node3D = _entity_pool[i]
		if i >= needed.size():
			node.visible = false
			continue
		var spec: Dictionary = needed[i]
		node.visible = true
		node.position = Vector3(float(spec["x"]) + 0.5, 0.0, float(spec["y"]) + 0.5)
		node.rotation.y = float(spec["yaw"])
		_style_entity(node, str(spec["role"]), str(spec["label"]), bool(spec.get("facing", false)))


func _ensure_courier_parts() -> void:
	if courier == null:
		return
	if courier.get_node_or_null("Head") == null:
		var head := MeshInstance3D.new()
		head.name = "Head"
		head.mesh = _meshes["head"]
		head.material_override = _mats["other_hi"]
		head.position = Vector3(0, 1.55, 0)
		courier.add_child(head)
	if _courier_facing == null:
		_courier_facing = courier.get_node_or_null("Facing") as MeshInstance3D
	if _courier_facing == null:
		_courier_facing = MeshInstance3D.new()
		_courier_facing.name = "Facing"
		courier.add_child(_courier_facing)
	_courier_facing.mesh = _meshes["facing"]
	_courier_facing.material_override = _mats["facing"]
	# Prism points along local -Z (north when yaw=0).
	_courier_facing.position = Vector3(0, 0.95, -0.42)
	_courier_facing.rotation_degrees = Vector3(90, 0, 0)
	_courier_facing.scale = Vector3(1.1, 1.0, 1.0)


func _make_entity_node() -> Node3D:
	var n := Node3D.new()
	var body := MeshInstance3D.new()
	body.name = "Body"
	n.add_child(body)
	var head := MeshInstance3D.new()
	head.name = "Head"
	n.add_child(head)
	var accent := MeshInstance3D.new()
	accent.name = "Accent"
	n.add_child(accent)
	var facing := MeshInstance3D.new()
	facing.name = "Facing"
	n.add_child(facing)
	var lab := Label3D.new()
	lab.name = "Label"
	lab.position = Vector3(0, 1.95, 0)
	lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lab.font_size = 26
	lab.outline_size = 8
	lab.pixel_size = 0.008
	lab.outline_modulate = Catppuccin.CRUST
	n.add_child(lab)
	entity_root.add_child(n)
	return n


func _set_part(mi: MeshInstance3D, mesh: Mesh, mat: Material, pos: Vector3, scale: Vector3 = Vector3.ONE, visible: bool = true) -> void:
	if mi == null:
		return
	mi.visible = visible
	if not visible:
		return
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	mi.scale = scale
	mi.rotation = Vector3.ZERO


func _style_entity(node: Node3D, role: String, label: String, show_facing: bool = false) -> void:
	var body := node.get_node_or_null("Body") as MeshInstance3D
	var head := node.get_node_or_null("Head") as MeshInstance3D
	var accent := node.get_node_or_null("Accent") as MeshInstance3D
	var facing := node.get_node_or_null("Facing") as MeshInstance3D
	var lab := node.get_node_or_null("Label") as Label3D
	# Defaults — hide optional parts; Body always on.
	_set_part(head, _meshes["head"], _mats["prop"], Vector3.ZERO, Vector3.ONE, false)
	_set_part(accent, _meshes["box"], _mats["prop"], Vector3.ZERO, Vector3.ONE, false)
	_set_part(facing, _meshes["facing"], _mats["facing_other"], Vector3.ZERO, Vector3.ONE, false)
	var label_y := 1.95
	var label_color := Catppuccin.TEXT

	match role:
		"other":
			# Courier silhouette: tall capsule + head + sky facing chevron.
			_set_part(body, _meshes["capsule_tall"], _mats["other"], Vector3(0, 0.82, 0))
			_set_part(head, _meshes["head"], _mats["other_hi"], Vector3(0, 1.58, 0), Vector3(1.05, 1.05, 1.05), true)
			show_facing = true
			label_color = Catppuccin.BLUE
		"npc":
			_set_part(body, _meshes["capsule_short"], _mats["npc"], Vector3(0, 0.62, 0))
			_set_part(head, _meshes["head"], _mats["npc_head"], Vector3(0, 1.28, 0), Vector3(1.15, 1.0, 1.15), true)
			label_color = Catppuccin.LAVENDER
			label_y = 1.75
		"infected":
			# Hunched box torso + offset head — green silhouette vs boxes of slice 1.
			_set_part(body, _meshes["box"], _mats["infected"], Vector3(0, 0.48, 0.05), Vector3(0.58, 0.95, 0.42))
			_set_part(head, _meshes["sphere"], _mats["infected_head"], Vector3(0.08, 1.05, 0.05), Vector3(0.75, 0.7, 0.8), true)
			label_color = Catppuccin.GREEN
			label_y = 1.55
		"thug":
			# Wide peach slab + cylinder head — stockier than infected.
			_set_part(body, _meshes["box"], _mats["thug"], Vector3(0, 0.62, 0), Vector3(0.72, 1.2, 0.48))
			_set_part(head, _meshes["disc"], _mats["thug_head"], Vector3(0, 1.35, 0), Vector3(0.55, 0.9, 0.55), true)
			label_color = Catppuccin.PEACH
			label_y = 1.85
		"drone":
			_set_part(body, _meshes["sphere"], _mats["drone"], Vector3(0, 1.25, 0), Vector3(1.05, 0.85, 1.05))
			_set_part(accent, _meshes["ring"], _mats["drone"], Vector3(0, 1.25, 0), Vector3(1.15, 0.4, 1.15), true)
			label_color = Catppuccin.MAUVE
			label_y = 1.95
		"boss":
			_set_part(body, _meshes["capsule_tall"], _mats["boss"], Vector3(0, 0.95, 0), Vector3(1.25, 1.2, 1.25))
			_set_part(head, _meshes["sphere"], _mats["boss"], Vector3(0, 1.85, 0), Vector3(1.3, 1.1, 1.3), true)
			_set_part(accent, _meshes["ring"], _mats["boss"], Vector3(0, 1.35, 0), Vector3(1.4, 0.5, 1.4), true)
			show_facing = true
			label_color = Catppuccin.RED
			label_y = 2.35
		"camera":
			_set_part(body, _meshes["box"], _mats["camera"], Vector3(0, 1.55, 0), Vector3(0.28, 0.22, 0.38))
			_set_part(accent, _meshes["pillar"], _mats["prop"], Vector3(0, 0.75, 0), Vector3(0.35, 0.55, 0.35), true)
			label_color = Catppuccin.RED
			label_y = 2.05
		"ice":
			_set_part(body, _meshes["box"], _mats["ice"], Vector3(0, 0.9, 0), Vector3(0.48, 1.7, 0.48))
			label_color = Catppuccin.BLUE
			label_y = 2.1
		"core":
			_set_part(body, _meshes["sphere"], _mats["core"], Vector3(0, 1.05, 0), Vector3(1.2, 1.2, 1.2))
			label_color = Catppuccin.PINK
		"exit":
			_set_part(body, _meshes["box"], _mats["exit"], Vector3(0, 1.1, 0), Vector3(0.38, 2.1, 0.38))
			label_color = Catppuccin.GREEN
			label_y = 2.35
		"pickup":
			_set_part(body, _meshes["sphere"], _mats["pickup"], Vector3(0, 0.45, 0), Vector3(0.65, 0.65, 0.65))
			_set_part(accent, _meshes["disc"], _mats["loot"], Vector3(0, 0.1, 0), Vector3(0.65, 0.65, 0.65), true)
			label_color = Catppuccin.YELLOW
			label_y = 1.15
		"vendor":
			_set_part(body, _meshes["kiosk"], _mats["vendor"], Vector3(0, 0.85, 0))
			_set_part(accent, _meshes["canopy"], _mats["vendor_trim"], Vector3(0, 1.55, 0), Vector3.ONE, true)
			label_color = Catppuccin.YELLOW
			label_y = 2.2
		_:
			_set_part(body, _meshes["box"], _mats["prop"], Vector3(0, 0.4, 0), Vector3(0.45, 0.8, 0.45))
			label_y = 1.2

	if show_facing and facing:
		facing.visible = true
		facing.mesh = _meshes["facing"]
		facing.material_override = _mats["facing_other"] if role == "other" else _mats["facing"]
		facing.position = Vector3(0, 0.85, -0.4)
		facing.rotation_degrees = Vector3(90, 0, 0)
		facing.scale = Vector3(1.0, 1.0, 1.0)

	if lab:
		lab.text = label
		lab.modulate = label_color
		lab.position = Vector3(0, label_y, 0)


func _add_mesh(parent: Node3D, mesh: Mesh, mat: Material, pos: Vector3, scale: Vector3 = Vector3.ONE) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	mi.scale = scale
	parent.add_child(mi)
	return mi


func _begin_ice_transition(entering: bool) -> void:
	_trans_t = ICE_TRANS_SEC
	_trans_dir = 1 if entering else -1
	# Jack-in already emits snapshot sfx pulse (#47). Jack-out is click — extra pulse for 3D juice.
	if (not entering) and AudioManager:
		AudioManager.play_sfx("pulse")


func _apply_ice_environment(on: bool) -> void:
	_ice_mode = on  # ensure quality helpers see mode; apply_snapshot also sets this
	_apply_environment_quality()
	if moon:
		if on:
			moon.light_color = Color(0.55, 0.82, 1.0)
			moon.light_energy = 0.55 if (GraphicsSettings and GraphicsSettings.is_high()) else 0.4
		else:
			moon.light_color = Color(0.705882, 0.745098, 0.964706, 1)
			moon.light_energy = 0.32 if (GraphicsSettings and GraphicsSettings.is_high()) else 0.22
	if rim:
		if on:
			rim.light_color = Catppuccin.MAUVE
			rim.visible = GraphicsSettings.rim_enabled() if GraphicsSettings else true
			rim.light_energy = (0.55 if GraphicsSettings.is_high() else 0.0) if GraphicsSettings else 0.55
		else:
			rim.light_color = Catppuccin.SKY
			rim.visible = GraphicsSettings.rim_enabled() if GraphicsSettings else true
			rim.light_energy = GraphicsSettings.rim_energy() if GraphicsSettings else 0.42
	if eye_light:
		if on:
			eye_light.light_color = Catppuccin.SKY
			eye_light.light_energy = 2.15
			eye_light.omni_range = 10.5
		else:
			eye_light.light_color = Catppuccin.TEAL
			eye_light.light_energy = 1.75
			eye_light.omni_range = 9.5
	_sync_particles()


func _place_ice_tile(ch: String, origin: Vector3, alt: bool) -> void:
	# Abstract grid / node lattice — not street brick.
	if ch == " ":
		return
	_place_ice_floor(origin, alt)
	match ch:
		"#":
			_place_ice_lattice_wall(origin, alt)
		"I":
			_add_mesh(map_root, _meshes["box"], _mats["ice_barrier"], origin + Vector3(0, 1.25, 0), Vector3(0.82, 2.5, 0.82))
			_add_mesh(map_root, _meshes["sphere"], _mats["ice_node"], origin + Vector3(0, 2.65, 0), Vector3(0.45, 0.45, 0.45))
			_add_ice_label(origin + Vector3(0, 3.05, 0), "I  ICE", Catppuccin.BLUE)
		"%":
			_add_mesh(map_root, _meshes["sphere"], _mats["core"], origin + Vector3(0, 1.15, 0), Vector3(1.25, 1.25, 1.25))
			_add_mesh(map_root, _meshes["ring"], _mats["core"], origin + Vector3(0, 1.15, 0), Vector3(1.2, 0.45, 1.2))
			_add_ice_label(origin + Vector3(0, 2.15, 0), "%  CORE", Catppuccin.PINK)
		"X":
			_add_mesh(map_root, _meshes["box"], _mats["exit"], origin + Vector3(0, 1.25, 0), Vector3(0.22, 2.5, 0.22))
			_add_mesh(map_root, _meshes["ring"], _mats["ice_exit_ring"], origin + Vector3(0, 1.35, 0), Vector3(1.35, 0.55, 1.35))
			_add_ice_label(origin + Vector3(0, 2.85, 0), "X  EXIT", Catppuccin.GREEN)
		"*":
			_add_mesh(map_root, _meshes["sphere"], _mats["pickup"], origin + Vector3(0, 0.55, 0), Vector3(0.7, 0.7, 0.7))
			_add_mesh(map_root, _meshes["disc"], _mats["loot"], origin + Vector3(0, 0.12, 0), Vector3(0.7, 0.7, 0.7))
			_add_ice_label(origin + Vector3(0, 1.25, 0), "*  LOOT", Catppuccin.YELLOW)
		"A":
			_add_mesh(map_root, _meshes["capsule_tall"], _mats["boss"], origin + Vector3(0, 1.05, 0), Vector3(1.2, 1.15, 1.2))
			_add_mesh(map_root, _meshes["ring"], _mats["boss"], origin + Vector3(0, 1.45, 0), Vector3(1.5, 0.45, 1.5))
			_add_ice_label(origin + Vector3(0, 2.55, 0), "NULL CHOIR", Catppuccin.RED)
		"@", ".":
			pass
		_:
			pass


func _place_ice_floor(origin: Vector3, alt: bool) -> void:
	_add_mesh(map_root, _meshes["floor"], _mats["ice_floor"], origin + Vector3(0, 0.02, 0))
	# Neon grid ticks (cross) — lattice language vs street lane tick.
	_add_mesh(map_root, _meshes["box"], _mats["ice_grid"], origin + Vector3(0, 0.065, 0), Vector3(0.94, 0.012, 0.04))
	_add_mesh(map_root, _meshes["box"], _mats["ice_grid"], origin + Vector3(0, 0.065, 0), Vector3(0.04, 0.012, 0.94))
	if alt:
		_add_mesh(map_root, _meshes["sphere"], _mats["ice_node"], origin + Vector3(0, 0.16, 0), Vector3(0.22, 0.22, 0.22))


func _place_ice_lattice_wall(origin: Vector3, alt: bool) -> void:
	# Thin neon frame + translucent fill — not a brick corridor.
	var fill = _mats["ice_wall"]
	_add_mesh(map_root, _meshes["box"], fill, origin + Vector3(0, ICE_WALL_H * 0.5, 0), Vector3(0.62, ICE_WALL_H, 0.62))
	var s := 0.4
	for ox in [-s, s]:
		for oz in [-s, s]:
			_add_mesh(map_root, _meshes["box"], _mats["ice_frame"], origin + Vector3(ox, ICE_WALL_H * 0.5, oz), Vector3(0.07, ICE_WALL_H + 0.08, 0.07))
	_add_mesh(map_root, _meshes["box"], _mats["ice_frame"], origin + Vector3(0, ICE_WALL_H + 0.02, 0), Vector3(0.86, 0.055, 0.86))
	if alt:
		_add_mesh(map_root, _meshes["sphere"], _mats["ice_node"], origin + Vector3(0, ICE_WALL_H + 0.22, 0), Vector3(0.38, 0.38, 0.38))


func _paint_ice_layer_plate(state: Dictionary, px: int, py: int) -> void:
	var text := ice_banner_text(state)
	var cyber = state.get("cyberspace", {})
	var heist = state.get("ice_heist", {})
	var ice_n := ""
	var layer := 0
	if typeof(heist) == TYPE_DICTIONARY:
		ice_n = str(heist.get("ice_remaining", ""))
		layer = int(heist.get("layer", 0))
	if typeof(cyber) == TYPE_DICTIONARY and ice_n.is_empty():
		ice_n = str(cyber.get("ice_remaining", ""))
	var fp := "ice|%s|%s|%d" % [text, ice_n, layer]
	if fp == _last_landmark_fp and landmark_root.get_child_count() > 0:
		return
	_last_landmark_fp = fp
	for c in landmark_root.get_children():
		c.free()
	_jack_light = null
	_uplink_light = null
	var holder := Node3D.new()
	holder.position = Vector3(float(px) + 0.5, 0.0, float(py) + 0.5)
	landmark_root.add_child(holder)
	var lab := Label3D.new()
	lab.text = text
	lab.position = Vector3(0, 3.85, 0)
	lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lab.font_size = 36
	lab.outline_size = 12
	lab.modulate = Catppuccin.SKY if layer == 0 else Catppuccin.MAUVE
	lab.outline_modulate = Catppuccin.CRUST
	lab.pixel_size = 0.01
	holder.add_child(lab)
	# Small floating layer pips for heist L1/L2/L3.
	if layer >= 1:
		var layers := 3
		if typeof(heist) == TYPE_DICTIONARY:
			layers = int(heist.get("layers", 3))
		for i in range(layers):
			var pip_mat = _mats["core"] if (i + 1) == layer else _mats["ice_frame"]
			var ox := float(i - 1) * 0.42
			_add_mesh(holder, _meshes["sphere"], pip_mat, Vector3(ox, 3.35, 0), Vector3(0.28, 0.28, 0.28))


func _add_ice_label(pos: Vector3, text: String, color: Color) -> void:
	var lab := Label3D.new()
	lab.text = text
	lab.position = pos
	lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lab.font_size = 22
	lab.outline_size = 8
	lab.modulate = color
	lab.outline_modulate = Catppuccin.CRUST
	lab.pixel_size = 0.008
	map_root.add_child(lab)


func _apply_environment_quality() -> void:
	var env: Environment = world_env.environment if world_env else null
	if env == null:
		return
	var high := true if GraphicsSettings == null else GraphicsSettings.is_high()
	env.glow_enabled = high if GraphicsSettings == null else GraphicsSettings.glow_enabled()
	if _ice_mode:
		env.background_color = Color(0.02, 0.035, 0.07)
		env.ambient_light_color = Color(0.2, 0.45, 0.68)
		env.ambient_light_energy = GraphicsSettings.ambient_energy_ice() if GraphicsSettings else 0.68
		env.fog_light_color = Color(0.2, 0.55, 0.78)
		env.fog_density = GraphicsSettings.fog_density_ice() if GraphicsSettings else 0.045
		env.glow_intensity = GraphicsSettings.glow_intensity_ice() if GraphicsSettings else 0.88
		env.glow_bloom = GraphicsSettings.glow_bloom_ice() if GraphicsSettings else 0.22
	else:
		env.background_color = STREET_BG
		env.ambient_light_color = STREET_AMB
		env.ambient_light_energy = GraphicsSettings.ambient_energy_street() if GraphicsSettings else 0.48
		env.fog_light_color = STREET_FOG
		env.fog_density = GraphicsSettings.fog_density_street() if GraphicsSettings else 0.022
		env.glow_intensity = GraphicsSettings.glow_intensity_street() if GraphicsSettings else 0.55
		env.glow_bloom = GraphicsSettings.glow_bloom_street() if GraphicsSettings else 0.12


func _ensure_fx() -> void:
	if _fx_ready:
		return
	if fx_root == null:
		fx_root = Node3D.new()
		fx_root.name = "FxRoot"
		add_child(fx_root)
	_rain = _make_rain()
	_dust = _make_dust()
	_spark = _make_spark()
	fx_root.add_child(_rain)
	fx_root.add_child(_dust)
	fx_root.add_child(_spark)
	_fx_ready = true
	_sync_particles()


func _make_rain() -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "Rain"
	p.amount = 64
	p.lifetime = 0.85
	p.preprocess = 0.4
	p.visibility_aabb = AABB(Vector3(-12, -2, -12), Vector3(24, 16, 24))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := ParticleProcessMaterial.new()
	mat.direction = Vector3(0.08, -1.0, 0.04)
	mat.spread = 6.0
	mat.initial_velocity_min = 6.0
	mat.initial_velocity_max = 9.5
	mat.gravity = Vector3(0, -2.0, 0)
	mat.scale_min = 0.04
	mat.scale_max = 0.09
	mat.color = Color(0.55, 0.72, 0.95, 0.55)
	p.process_material = mat
	var dm := BoxMesh.new()
	dm.size = Vector3(0.02, 0.28, 0.02)
	var draw := StandardMaterial3D.new()
	draw.albedo_color = Color(0.55, 0.75, 1.0, 0.45)
	draw.emission_enabled = true
	draw.emission = Catppuccin.SKY
	draw.emission_energy_multiplier = 0.55
	draw.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	draw.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	p.draw_pass_1 = dm
	p.material_override = draw
	return p


func _make_dust() -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "NeonDust"
	p.amount = 28
	p.lifetime = 3.2
	p.preprocess = 1.0
	p.visibility_aabb = AABB(Vector3(-10, -1, -10), Vector3(20, 10, 20))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := ParticleProcessMaterial.new()
	mat.direction = Vector3(0.0, 1.0, 0.0)
	mat.spread = 55.0
	mat.initial_velocity_min = 0.15
	mat.initial_velocity_max = 0.55
	mat.gravity = Vector3(0, 0.05, 0)
	mat.scale_min = 0.03
	mat.scale_max = 0.08
	mat.color = Color(0.8, 0.55, 1.0, 0.5)
	p.process_material = mat
	var dm := SphereMesh.new()
	dm.radius = 0.04
	dm.height = 0.08
	var draw := StandardMaterial3D.new()
	draw.albedo_color = Color(0.8, 0.55, 1.0, 0.55)
	draw.emission_enabled = true
	draw.emission = Catppuccin.MAUVE
	draw.emission_energy_multiplier = 1.1
	draw.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	draw.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	p.draw_pass_1 = dm
	p.material_override = draw
	return p


func _make_spark() -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "UplinkSpark"
	p.amount = 18
	p.lifetime = 0.7
	p.emitting = false
	p.one_shot = false
	p.explosiveness = 0.35
	p.visibility_aabb = AABB(Vector3(-3, -1, -3), Vector3(6, 6, 6))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := ParticleProcessMaterial.new()
	mat.direction = Vector3(0.0, 1.0, 0.0)
	mat.spread = 40.0
	mat.initial_velocity_min = 1.2
	mat.initial_velocity_max = 2.8
	mat.gravity = Vector3(0, -1.5, 0)
	mat.scale_min = 0.04
	mat.scale_max = 0.1
	mat.color = Color(1.0, 0.72, 0.45, 0.85)
	p.process_material = mat
	var dm := SphereMesh.new()
	dm.radius = 0.05
	dm.height = 0.1
	var draw := StandardMaterial3D.new()
	draw.albedo_color = Catppuccin.PEACH
	draw.emission_enabled = true
	draw.emission = Catppuccin.PEACH
	draw.emission_energy_multiplier = 2.2
	draw.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	p.draw_pass_1 = dm
	p.material_override = draw
	return p


func _sync_particles() -> void:
	if not _fx_ready:
		return
	var on := true if GraphicsSettings == null else GraphicsSettings.particles_enabled()
	# Rain + dust on street High only; ice gets dust-only (lattice snow feel) on High.
	if _rain:
		_rain.emitting = on and not _ice_mode
		_rain.visible = _rain.emitting
		_rain.amount = 64 if on else 1
	if _dust:
		_dust.emitting = on
		_dust.visible = on
		_dust.amount = 36 if _ice_mode else 28
		if _dust.process_material is ParticleProcessMaterial:
			var pm := _dust.process_material as ParticleProcessMaterial
			pm.color = Color(0.45, 0.85, 1.0, 0.55) if _ice_mode else Color(0.8, 0.55, 1.0, 0.5)
	if _spark:
		var spark_on := on and (not _ice_mode) and _uplink_light != null
		_spark.emitting = spark_on
		_spark.visible = spark_on


func _follow_fx() -> void:
	if not _fx_ready or courier == null:
		return
	var base := courier.position
	if _rain:
		_rain.position = base + Vector3(0.0, 5.5, 0.0)
	if _dust:
		_dust.position = base + Vector3(0.0, 1.2, 0.0)
	if _spark and _uplink_light and is_instance_valid(_uplink_light):
		var holder := _uplink_light.get_parent() as Node3D
		if holder:
			_spark.global_position = holder.global_position + Vector3(0.0, 3.1, 0.0)
