extends RefCounted
class_name MeshKit
## Original modular corridor / prop kit (#158). Snapshot-placed; Python /ws stays authority.
## OBJ sources live under res://models/. Parsed to ArrayMesh so editor import is not required.
## Not Abandoned Spaceship IP. Omni budget unchanged (this class never creates lights).

const MODEL_DIR := "res://models/"
const NAMES := [
	"wall_panel",
	"floor_tile",
	"door_frame",
	"crate",
	"pipe",
	"neon_strip",
	"foliage",
	"vent",
]

## TERRAIN / GLYPH role → kit mesh name (street_3d catalog).
const ROLE_MESH := {
	"wall": "wall_panel",
	"floor": "floor_tile",
	"street": "floor_tile",
	"grass": "floor_tile",
	"water": "floor_tile",
	"door": "door_frame",
	"manhole": "floor_tile",
	"stairs_up": "floor_tile",
	"stairs_down": "floor_tile",
}

static var _cache: Dictionary = {}
static var _ready: bool = false


static func ensure() -> void:
	if _ready:
		return
	for n in NAMES:
		_cache[n] = _load_obj(n)
	_ready = true


static func get_mesh(name: String) -> Mesh:
	ensure()
	if _cache.has(name) and _cache[name] != null:
		return _cache[name] as Mesh
	return null


static func mesh_for_role(role: String) -> Mesh:
	var key: String = str(ROLE_MESH[role]) if ROLE_MESH.has(role) else ""
	if key == "":
		return null
	return get_mesh(key)


static func _load_obj(name: String) -> Mesh:
	var path: String = "%s%s.obj" % [MODEL_DIR, name]
	if ResourceLoader.exists(path):
		var imported: Resource = load(path)
		if imported is Mesh:
			return imported as Mesh
	var txt: String = ""
	if FileAccess.file_exists(path):
		var f: FileAccess = FileAccess.open(path, FileAccess.READ)
		if f:
			txt = f.get_as_text()
			f.close()
	if txt == "":
		return _fallback_box(name)
	return _parse_obj(txt, name)


static func _parse_obj(txt: String, name: String) -> Mesh:
	var raw_v: Array = []
	var raw_vn: Array = []
	var raw_vt: Array = []
	var verts: PackedVector3Array = PackedVector3Array()
	var norms: PackedVector3Array = PackedVector3Array()
	var uvs: PackedVector2Array = PackedVector2Array()
	for line in txt.split("\n"):
		var s: String = line.strip_edges()
		if s.begins_with("v "):
			var p: PackedStringArray = s.split(" ", false)
			if p.size() >= 4:
				raw_v.append(Vector3(float(p[1]), float(p[2]), float(p[3])))
		elif s.begins_with("vn "):
			var p2: PackedStringArray = s.split(" ", false)
			if p2.size() >= 4:
				raw_vn.append(Vector3(float(p2[1]), float(p2[2]), float(p2[3])))
		elif s.begins_with("vt "):
			var p3: PackedStringArray = s.split(" ", false)
			if p3.size() >= 3:
				raw_vt.append(Vector2(float(p3[1]), float(p3[2])))
		elif s.begins_with("f "):
			var bits: PackedStringArray = s.split(" ", false)
			if bits.size() < 4:
				continue
			for i in range(1, 4):
				var tok: PackedStringArray = bits[i].split("/")
				var vi: int = int(tok[0]) - 1
				var vti: int = int(tok[1]) - 1 if tok.size() > 1 and tok[1] != "" else -1
				var vni: int = int(tok[2]) - 1 if tok.size() > 2 and tok[2] != "" else -1
				if vi >= 0 and vi < raw_v.size():
					verts.append(raw_v[vi])
				else:
					verts.append(Vector3.ZERO)
				if vni >= 0 and vni < raw_vn.size():
					norms.append(raw_vn[vni])
				else:
					norms.append(Vector3.UP)
				if vti >= 0 and vti < raw_vt.size():
					uvs.append(raw_vt[vti])
				else:
					uvs.append(Vector2.ZERO)
	if verts.is_empty():
		return _fallback_box(name)
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = norms
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	var am: ArrayMesh = ArrayMesh.new()
	am.resource_name = name
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return am


static func _fallback_box(name: String) -> Mesh:
	var b: BoxMesh = BoxMesh.new()
	b.size = Vector3.ONE
	b.resource_name = name
	return b
