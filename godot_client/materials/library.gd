extends RefCounted
class_name MaterialLibrary
## Shared Catppuccin trim / PBR factory (#156). Cheap enough for AOI pooling.
## Original shader + generated textures — no Abandoned Spaceship assets.
## Omni budget is unchanged (this class never creates lights).

const SHADER_PATH := "res://materials/recolor_trim.gdshader"
const TEX_TRIM := "res://materials/textures/trim_albedo.png"
const TEX_NORMAL := "res://materials/textures/trim_normal.png"
const TEX_ORM := "res://materials/textures/trim_orm.png"
const TEX_CONCRETE := "res://materials/textures/concrete_albedo.png"
const TEX_ICE := "res://materials/textures/ice_grid.png"

## Role → UV / trim / texture. Recolor + emission come from Catppuccin at make().
const ROLE_UV := {
	"wall": Vector2(1.6, 2.2),
	"wall_hi": Vector2(1.6, 2.2),
	"floor": Vector2(3.5, 3.5),
	"street": Vector2(2.8, 2.8),
	"grass": Vector2(4.0, 4.0),
	"water": Vector2(2.2, 2.2),
	"door": Vector2(1.2, 2.4),
	"void": Vector2(1.0, 1.0),
	"manhole": Vector2(2.0, 2.0),
	"stairs": Vector2(1.8, 1.8),
	"jack": Vector2(1.4, 2.6),
	"uplink": Vector2(1.4, 2.8),
	"vendor": Vector2(1.5, 1.8),
	"vendor_trim": Vector2(2.2, 2.2),
	"jack_shaft": Vector2(1.0, 3.0),
	"uplink_shaft": Vector2(1.0, 3.0),
	"vendor_shaft": Vector2(1.0, 3.0),
	"ice_wall": Vector2(2.4, 2.8),
	"ice_frame": Vector2(3.0, 3.0),
	"ice_floor": Vector2(3.2, 3.2),
	"ice_grid": Vector2(4.0, 4.0),
	"ice_barrier": Vector2(2.0, 2.6),
	"ice_node": Vector2(1.5, 1.5),
	"ice_void": Vector2(1.0, 1.0),
	"ice_exit_ring": Vector2(2.0, 2.0),
	"prop": Vector2(2.0, 2.0),
}

const ROLE_TRIM := {
	"wall": 0.72,
	"wall_hi": 0.7,
	"floor": 0.55,
	"street": 0.68,
	"grass": 0.4,
	"water": 0.35,
	"door": 0.58,
	"void": 0.15,
	"manhole": 0.5,
	"stairs": 0.55,
	"jack": 0.48,
	"uplink": 0.48,
	"vendor": 0.5,
	"vendor_trim": 0.62,
	"jack_shaft": 0.35,
	"uplink_shaft": 0.35,
	"vendor_shaft": 0.35,
	"ice_wall": 0.55,
	"ice_frame": 0.45,
	"ice_floor": 0.6,
	"ice_grid": 0.7,
	"ice_barrier": 0.5,
	"ice_node": 0.3,
	"ice_void": 0.1,
	"ice_exit_ring": 0.4,
	"prop": 0.5,
}

const ROLE_PANEL := {
	"wall": 3.0,
	"wall_hi": 3.0,
	"floor": 6.0,
	"street": 5.0,
	"grass": 7.0,
	"water": 4.0,
	"door": 2.4,
	"ice_wall": 3.4,
	"ice_floor": 5.5,
	"ice_grid": 8.0,
	"ice_barrier": 3.2,
}

static var _shader: Shader
static var _tex_trim: Texture2D
static var _tex_normal: Texture2D
static var _tex_orm: Texture2D
static var _tex_concrete: Texture2D
static var _tex_ice: Texture2D
static var _ready: bool = false


static func _ensure() -> void:
	if _ready:
		return
	_shader = load(SHADER_PATH) as Shader
	_tex_trim = _load_tex(TEX_TRIM)
	_tex_normal = _load_tex(TEX_NORMAL)
	_tex_orm = _load_tex(TEX_ORM)
	_tex_concrete = _load_tex(TEX_CONCRETE)
	_tex_ice = _load_tex(TEX_ICE)
	if _tex_trim == null:
		_tex_trim = _make_panel_tex()
	if _tex_concrete == null:
		_tex_concrete = _make_noise_tex()
	if _tex_ice == null:
		_tex_ice = _make_grid_tex()
	if _tex_normal == null:
		_tex_normal = _make_flat_normal()
	if _tex_orm == null:
		_tex_orm = _make_default_orm()
	_ready = true


static func _load_tex(path: String) -> Texture2D:
	if ResourceLoader.exists(path):
		var res: Resource = load(path)
		if res is Texture2D:
			return res as Texture2D
	return null


static func make(role: String, color: Color, emission_energy: float = 0.0, metallic: float = 0.15) -> ShaderMaterial:
	return _build(role, color, emission_energy, metallic, false, color.a)


static func make_alpha(role: String, color: Color, emission_energy: float, metallic: float, alpha: float) -> ShaderMaterial:
	var c: Color = color
	c.a = alpha
	return _build(role, c, emission_energy, metallic, true, alpha)


static func make_tint(color: Color, emission_energy: float = 0.0, metallic: float = 0.15) -> ShaderMaterial:
	return make("generic", color, emission_energy, metallic)


static func _build(role: String, color: Color, emission_energy: float, metallic: float, use_alpha: bool, _alpha: float) -> ShaderMaterial:
	_ensure()
	var m: ShaderMaterial = ShaderMaterial.new()
	m.resource_name = "mat_%s" % role
	if _shader:
		m.shader = _shader
	m.set_shader_parameter("albedo_tint", color)
	m.set_shader_parameter("emission_color", color)
	m.set_shader_parameter("emission_energy", emission_energy)
	m.set_shader_parameter("metallic", metallic)
	m.set_shader_parameter("roughness", 0.42)
	var uv: Vector2 = ROLE_UV[role] if ROLE_UV.has(role) else Vector2(2.0, 2.0)
	m.set_shader_parameter("uv_scale", uv)
	var trim: float = float(ROLE_TRIM[role]) if ROLE_TRIM.has(role) else 0.45
	m.set_shader_parameter("trim_mix", trim)
	var panel: float = float(ROLE_PANEL[role]) if ROLE_PANEL.has(role) else 4.0
	m.set_shader_parameter("panel_freq", panel)
	m.set_shader_parameter("grout", 0.08)
	m.set_shader_parameter("use_alpha", use_alpha)
	m.set_shader_parameter("use_albedo_tex", true)
	var albedo: Texture2D = _tex_for_role(role)
	m.set_shader_parameter("albedo_tex", albedo)
	m.set_shader_parameter("normal_tex", _tex_normal)
	m.set_shader_parameter("orm_tex", _tex_orm)
	apply_quality(m)
	return m


static func _tex_for_role(role: String) -> Texture2D:
	if role.begins_with("ice"):
		return _tex_ice
	if role == "floor" or role == "street" or role == "grass" or role == "void":
		return _tex_concrete
	return _tex_trim


static func apply_quality(mat: Material) -> void:
	if not (mat is ShaderMaterial):
		return
	var use_maps: bool = true
	if GraphicsSettings:
		use_maps = GraphicsSettings.materials_use_orm()
	var sm: ShaderMaterial = mat as ShaderMaterial
	sm.set_shader_parameter("use_normal", use_maps)
	sm.set_shader_parameter("use_orm", use_maps)


static func set_emission(mat: Material, energy: float) -> void:
	if mat is ShaderMaterial:
		(mat as ShaderMaterial).set_shader_parameter("emission_energy", energy)
	elif mat is StandardMaterial3D:
		(mat as StandardMaterial3D).emission_energy_multiplier = energy


static func _make_panel_tex() -> ImageTexture:
	var img: Image = Image.create(32, 32, false, Image.FORMAT_RGBA8)
	for y in range(32):
		for x in range(32):
			var cx: float = float(x % 8) / 8.0
			var cy: float = float(y % 8) / 8.0
			var e: float = min(min(cx, 1.0 - cx), min(cy, 1.0 - cy))
			var v: float = 0.25 + smoothstep(0.0, 0.2, e) * 0.55
			img.set_pixel(x, y, Color(v, v, v, 1.0))
	return ImageTexture.create_from_image(img)


static func _make_noise_tex() -> ImageTexture:
	var img: Image = Image.create(32, 32, false, Image.FORMAT_RGBA8)
	for y in range(32):
		for x in range(32):
			var v: float = 0.22 + float((x * 13 + y * 7) % 17) / 68.0
			img.set_pixel(x, y, Color(v, v * 0.98, v * 0.94, 1.0))
	return ImageTexture.create_from_image(img)


static func _make_grid_tex() -> ImageTexture:
	var img: Image = Image.create(32, 32, false, Image.FORMAT_RGBA8)
	for y in range(32):
		for x in range(32):
			var line: bool = (x % 8) <= 1 or (y % 8) <= 1
			var v: float = 0.85 if line else 0.1
			img.set_pixel(x, y, Color(v * 0.55, v * 0.85, v, 1.0))
	return ImageTexture.create_from_image(img)


static func _make_flat_normal() -> ImageTexture:
	var img: Image = Image.create(4, 4, false, Image.FORMAT_RGBA8)
	img.fill(Color(0.5, 0.5, 1.0, 1.0))
	return ImageTexture.create_from_image(img)


static func _make_default_orm() -> ImageTexture:
	var img: Image = Image.create(4, 4, false, Image.FORMAT_RGBA8)
	img.fill(Color(0.85, 0.45, 0.65, 1.0))
	return ImageTexture.create_from_image(img)
