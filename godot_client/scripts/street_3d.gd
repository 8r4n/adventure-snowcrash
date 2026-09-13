extends Node3D
class_name Street3D
## Snapshot map → neon 3D street (#141). Python /ws remains authority.
## Slice 2: distinct entity silhouettes, facing chevrons, vendor/J/U landmarks.
## Glyphs become PrimitiveMesh instances + Catppuccin emission materials.

const TILE := 1.0
const WALL_H := 2.55
const BUILD_RADIUS := 18
const ENTITY_RADIUS := 16
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

var cam_mode: int = CamMode.THIRD
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
## Deck: reuse shared PrimitiveMesh + materials; entity nodes are pooled (no free/alloc per snap).
const MAX_POOLED_ENTITIES := 48
const LANDMARK_VENDOR_RADIUS := 22


func _ready() -> void:
	_ensure_resources()
	_ensure_courier_parts()
	_apply_cam_rig()
	set_process(true)


func camera_mode_name() -> String:
	return "1st" if cam_mode == CamMode.FIRST else "3rd"


func toggle_camera() -> String:
	cam_mode = CamMode.THIRD if cam_mode == CamMode.FIRST else CamMode.FIRST
	_apply_cam_rig()
	return camera_mode_name()


func apply_snapshot(state: Dictionary) -> void:
	if state.is_empty():
		return
	var player: Dictionary = state.get("player", {})
	if typeof(player) != TYPE_DICTIONARY:
		player = {}
	var px := int(player.get("x", 0))
	var py := int(player.get("y", 0))
	var facing := FpvAscii.facing_index(player)
	_target_pos = Vector3(float(px) + 0.5, 0.0, float(py) + 0.5)
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
	_paint_entities(state, px, py, str(state.get("you", player.get("id", ""))))


func _process(delta: float) -> void:
	if not _have_pose:
		return
	courier.position = courier.position.lerp(_target_pos, clampf(LERP_POS * delta, 0.0, 1.0))
	courier.rotation.y = lerp_angle(courier.rotation.y, _target_yaw, clampf(LERP_YAW * delta, 0.0, 1.0))
	_pulse += delta
	var pulse := 1.0 + 0.35 * sin(_pulse * 3.2)
	if _jack_light:
		_jack_light.light_energy = 2.4 * pulse
	if _uplink_light:
		_uplink_light.light_energy = 2.6 * pulse


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
	_mats["wall"] = _mat(Catppuccin.TEAL.darkened(0.35), 0.55, 0.15)
	_mats["wall_hi"] = _mat(Catppuccin.SKY.darkened(0.2), 0.85, 0.2)
	_mats["floor"] = _mat(Catppuccin.SURFACE0, 0.0, 0.05)
	_mats["street"] = _mat(Catppuccin.MANTLE.lightened(0.08), 0.08, 0.25)
	_mats["grass"] = _mat(Catppuccin.GREEN.darkened(0.55), 0.05, 0.0)
	_mats["water"] = _mat(Color(0.29, 0.56, 0.85, 0.72), 0.35, 0.4)
	_mats["door"] = _mat(Catppuccin.YELLOW, 0.7, 0.2)
	_mats["void"] = _mat(Catppuccin.CRUST, 0.0, 0.0)
	_mats["manhole"] = _mat(Catppuccin.OVERLAY0, 0.15, 0.6)
	_mats["stairs"] = _mat(Catppuccin.LAVENDER.darkened(0.25), 0.25, 0.15)
	_mats["loot"] = _mat(Catppuccin.YELLOW, 1.1, 0.1)
	_mats["jack"] = _mat(Catppuccin.SKY, 1.8, 0.15)
	_mats["uplink"] = _mat(Catppuccin.PEACH, 1.9, 0.2)
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
	_mats["vendor"] = _mat(Catppuccin.YELLOW, 1.7, 0.25)
	_mats["vendor_trim"] = _mat(Catppuccin.PEACH, 1.2, 0.3)
	_mats["pickup"] = _mat(Catppuccin.YELLOW, 1.35, 0.1)
	_mats["boss"] = _mat(Catppuccin.RED, 1.15, 0.2)
	_mats["facing"] = _mat(Catppuccin.TEAL, 1.4, 0.15)
	_mats["facing_other"] = _mat(Catppuccin.SKY, 1.3, 0.15)
	_mats["prop"] = _mat(Catppuccin.SURFACE1, 0.2, 0.2)
	_mats["npc_head"] = _mat(Catppuccin.LAVENDER.lightened(0.12), 0.7, 0.1)
	_mats["infected_head"] = _mat(Catppuccin.GREEN.darkened(0.15), 0.85, 0.05)
	_mats["thug_head"] = _mat(Catppuccin.PEACH.darkened(0.1), 0.9, 0.15)
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
	var ring := TorusMesh.new()
	ring.inner_radius = 0.22
	ring.outer_radius = 0.38
	_meshes["ring"] = ring
	var plane := PlaneMesh.new()
	plane.size = Vector2(float(BUILD_RADIUS * 2 + 6), float(BUILD_RADIUS * 2 + 6))
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
	bits.append("%d:%d" % [int(px / REBUILD_STEP), int(py / REBUILD_STEP)])
	var y0 := maxi(0, py - BUILD_RADIUS)
	var y1 := mini(rows.size(), py + BUILD_RADIUS + 1)
	for y in range(y0, y1):
		var row := str(rows[y])
		var x0 := maxi(0, px - BUILD_RADIUS)
		var x1 := mini(row.length(), px + BUILD_RADIUS + 1)
		bits.append(row.substr(x0, x1 - x0))
	bits.append(str(state.get("jackpoint", [])))
	bits.append(str(state.get("uplink", [])))
	bits.append(str(state.get("plane", state.get("z", 0))))
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
	ground.material_override = _mats["void"]
	ground.position = Vector3(float(px) + 0.5, -0.05, float(py) + 0.5)
	map_root.add_child(ground)

	var y0 := maxi(0, py - BUILD_RADIUS)
	var y1 := mini(rows.size(), py + BUILD_RADIUS + 1)
	for y in range(y0, y1):
		var row := str(rows[y])
		var x0 := maxi(0, px - BUILD_RADIUS)
		var x1 := mini(row.length(), px + BUILD_RADIUS + 1)
		for x in range(x0, x1):
			var ch := row.substr(x, 1)
			if ch == " ":
				continue
			_place_tile(ch, x, y, (x + y) & 1 == 0)


func _place_tile(ch: String, x: int, y: int, alt: bool) -> void:
	var origin := Vector3(float(x) + 0.5, 0.0, float(y) + 0.5)
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


func _spawn_jack_uplink(x: int, y: int, px: int, py: int, is_jack: bool) -> void:
	if maxi(absi(x - px), absi(y - py)) > BUILD_RADIUS + 8:
		return
	var origin := Vector3(float(x) + 0.5, 0.0, float(y) + 0.5)
	var holder := Node3D.new()
	holder.position = origin
	landmark_root.add_child(holder)
	var mat: Material = _mats["jack"] if is_jack else _mats["uplink"]
	# Tall silhouette: base plinth + pillar + crown sphere (readable at distance).
	_add_mesh(holder, _meshes["box"], mat, Vector3(0, 0.18, 0), Vector3(0.85, 0.36, 0.85))
	_add_mesh(holder, _meshes["pillar"], mat, Vector3(0, 1.45, 0), Vector3(1.05, 1.2, 1.05) if is_jack else Vector3(0.95, 1.35, 0.95))
	_add_mesh(holder, _meshes["sphere"], mat, Vector3(0, 2.95, 0), Vector3(0.95, 0.95, 0.95) if is_jack else Vector3(1.25, 1.25, 1.25))
	if not is_jack:
		_add_mesh(holder, _meshes["ring"], mat, Vector3(0, 2.55, 0), Vector3(1.0, 1.0, 1.0))
	var light := OmniLight3D.new()
	light.light_color = Catppuccin.SKY if is_jack else Catppuccin.PEACH
	light.light_energy = 2.4
	light.omni_range = 11.0
	light.omni_attenuation = 1.25
	light.shadow_enabled = false
	light.position = Vector3(0, 2.7, 0)
	holder.add_child(light)
	if is_jack:
		_jack_light = light
	else:
		_uplink_light = light
	var lab := Label3D.new()
	lab.text = "J  JACKPOINT" if is_jack else "U  UPLINK"
	lab.position = Vector3(0, 3.55, 0)
	lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lab.font_size = 38
	lab.outline_size = 12
	lab.modulate = Catppuccin.SKY if is_jack else Catppuccin.PEACH
	lab.outline_modulate = Catppuccin.CRUST
	lab.pixel_size = 0.008
	holder.add_child(lab)


func _spawn_vendor(x: int, y: int, px: int, py: int, label: String) -> void:
	if maxi(absi(x - px), absi(y - py)) > LANDMARK_VENDOR_RADIUS:
		return
	var holder := Node3D.new()
	holder.position = Vector3(float(x) + 0.5, 0.0, float(y) + 0.5)
	landmark_root.add_child(holder)
	# Emissive kiosk (no Omni — Deck light budget stays courier + J + U).
	_add_mesh(holder, _meshes["kiosk"], _mats["vendor"], Vector3(0, 0.85, 0))
	_add_mesh(holder, _meshes["canopy"], _mats["vendor_trim"], Vector3(0, 1.55, 0))
	_add_mesh(holder, _meshes["sphere"], _mats["vendor"], Vector3(0, 1.95, 0), Vector3(0.55, 0.55, 0.55))
	_add_mesh(holder, _meshes["box"], _mats["vendor_trim"], Vector3(0, 0.08, 0), Vector3(0.9, 0.1, 0.7))
	var lab := Label3D.new()
	lab.text = "$  %s" % (label if label else "VENDOR")
	lab.position = Vector3(0, 2.45, 0)
	lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lab.font_size = 32
	lab.outline_size = 10
	lab.modulate = Catppuccin.YELLOW
	lab.outline_modulate = Catppuccin.CRUST
	lab.pixel_size = 0.008
	holder.add_child(lab)


func _spawn_pickup_beacon(x: int, y: int, px: int, py: int, label: String) -> void:
	if maxi(absi(x - px), absi(y - py)) > ENTITY_RADIUS + 4:
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


func _paint_entities(state: Dictionary, px: int, py: int, you: String) -> void:
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
			if maxi(absi(ex - px), absi(ey - py)) > ENTITY_RADIUS:
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
			if maxi(absi(ex2 - px), absi(ey2 - py)) > ENTITY_RADIUS:
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
		var y0 := maxi(0, py - ENTITY_RADIUS)
		var y1 := mini(rows.size(), py + ENTITY_RADIUS + 1)
		for y in range(y0, y1):
			var row := str(rows[y])
			var x0 := maxi(0, px - ENTITY_RADIUS)
			var x1 := mini(row.length(), px + ENTITY_RADIUS + 1)
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

	if needed.size() > MAX_POOLED_ENTITIES:
		needed = needed.slice(0, MAX_POOLED_ENTITIES)

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
