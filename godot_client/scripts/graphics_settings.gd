extends Node
## Low / High 3D quality preset (#141 slice 5). Persists in ConfigFile with onboarding/audio.
## Omni budget is documented in docs/godot-3d.md — this autoload never adds lights.
## #161 camera juice (look smooth / head bob) is cosmetic only — no client position authority.
## #157 High SSAO/SSIL/TAA/volumetric + probes — Low keeps these off (Deck / #148).
## #159 ground blend full path is High-only; Low keeps cheaper single-albedo ground.
## #160 diegetic screens: Low simplifies / hides in ICE.

const CONFIG_PATH := "user://snowcrash_client.cfg"
const CONFIG_SECTION := "graphics"

## High = desktop neon look; Low = Deck / weak GPU floor.
enum Quality { LOW = 0, HIGH = 1 }

signal quality_changed(level: int)

var _cfg := ConfigFile.new()
var _quality: int = Quality.HIGH
## #161 camera juice (cosmetic). Bob stays off on Low even if pref true.
var _look_smooth: bool = true
var _head_bob: bool = false


func _ready() -> void:
	_load()


func quality() -> int:
	return _quality


func is_high() -> bool:
	return _quality == Quality.HIGH


func is_low() -> bool:
	return _quality == Quality.LOW


func quality_name() -> String:
	return "High" if is_high() else "Low"


func set_quality(level: int) -> void:
	var q := Quality.HIGH if level == Quality.HIGH else Quality.LOW
	if q == _quality:
		return
	_quality = q
	_save()
	quality_changed.emit(_quality)


func toggle_quality() -> String:
	set_quality(Quality.LOW if is_high() else Quality.HIGH)
	return quality_name()


# ---- Knobs consumed by Street3D / Globe3D / main SubViewports ----------------

func build_radius() -> int:
	## Low tightened (#148) for Deck street-combat headroom vs prior 14.
	return 12 if is_low() else 18


func entity_radius() -> int:
	## Low tightened (#148) vs prior 12.
	return 10 if is_low() else 16


func max_pooled_entities() -> int:
	## Low tightened (#148) vs prior 28 — High stays 48.
	return 24 if is_low() else 48


func particles_enabled() -> bool:
	return is_high()


func glow_enabled() -> bool:
	return is_high()


func glow_intensity_street() -> float:
	return 0.28 if is_low() else 0.55


func glow_bloom_street() -> float:
	return 0.04 if is_low() else 0.12


func glow_intensity_ice() -> float:
	return 0.4 if is_low() else 0.88


func glow_bloom_ice() -> float:
	return 0.06 if is_low() else 0.22


func glow_intensity_globe() -> float:
	return 0.32 if is_low() else 0.62


func glow_bloom_globe() -> float:
	return 0.05 if is_low() else 0.14


func rim_enabled() -> bool:
	## Neon rim is a DirectionalLight3D — does NOT count against Omni budget.
	return is_high()


func rim_energy() -> float:
	return 0.0 if is_low() else 0.42


func msaa_3d() -> int:
	## Viewport.MSAA_DISABLED=0, MSAA_2X=1
	return 0 if is_low() else 1


func materials_use_orm() -> bool:
	## #156: Low drops ORM / normal maps (cheaper albedo + procedural trim).
	return is_high()


func materials_use_normal() -> bool:
	return is_high()


func kit_scatter() -> bool:
	## #158: Low skips debris / foliage / extra neon (AOI mesh count).
	return is_high()


func ground_blend_full() -> bool:
	## #159: High world-space multi-tex blend + normal; Low single tinted albedo.
	return is_high()


func ground_rubble_overlay() -> bool:
	## Sparse rubble chips on floor/street — High only (AOI mesh headroom).
	return is_high()


func diegetic_screens_detailed() -> bool:
	## #160: High full StreetNet/objective lines; Low short labels (and hide in ICE).
	return is_high()


## Camera juice (#161) — cosmetic only. /ws grid + intents stay authority.
func look_smoothing() -> bool:
	return _look_smooth


func set_look_smoothing(on: bool) -> void:
	var v := bool(on)
	if v == _look_smooth:
		return
	_look_smooth = v
	_save()


func toggle_look_smoothing() -> bool:
	set_look_smoothing(not _look_smooth)
	return _look_smooth


func head_bob() -> bool:
	## Deck / Low: off by default (never auto-on when quality is Low).
	if is_low():
		return false
	return _head_bob


func head_bob_user() -> bool:
	## Raw persisted preference (ignores Low override) — for HUD label.
	return _head_bob


func set_head_bob(on: bool) -> void:
	var v := bool(on)
	if v == _head_bob:
		return
	_head_bob = v
	_save()


func toggle_head_bob() -> bool:
	set_head_bob(not _head_bob)
	return _head_bob  # persisted pref; Low still forces bob off via head_bob()


func look_yaw_rate() -> float:
	## Higher = snappier turn follow. Smooth = softer cosmetic yaw.
	return 14.0 if not _look_smooth else 7.2


func look_pos_rate() -> float:
	## Cosmetic grid-cell mesh lerp (courier + entities). Not prediction.
	return 14.0 if not _look_smooth else 9.5



func ssao_enabled() -> bool:
	## #157 High only — Deck Low keeps AO off (#148).
	return is_high()


func ssil_enabled() -> bool:
	## #157 High only (affordable with Omni ≤3 + Forward+).
	return is_high()


func taa_enabled() -> bool:
	## #157 High SubViewport.use_taa — Low off.
	return is_high()


func volumetric_fog_enabled() -> bool:
	return is_high()


func volumetric_fog_density_street() -> float:
	## Denser neon shafts on High; Low unused (feature off).
	return 0.0 if is_low() else 0.028


func volumetric_fog_density_ice() -> float:
	return 0.0 if is_low() else 0.042


func volumetric_fog_density_globe() -> float:
	return 0.0 if is_low() else 0.018


func reflection_probes_enabled() -> bool:
	## Hotspots only (J / U / ICE core+exit) — not every tile.
	return is_high()


func fog_density_street() -> float:
	return 0.012 if is_low() else 0.022


func fog_density_ice() -> float:
	return 0.028 if is_low() else 0.045


func ambient_energy_street() -> float:
	return 0.38 if is_low() else 0.48


func ambient_energy_ice() -> float:
	return 0.5 if is_low() else 0.68


func _load() -> void:
	_cfg = ConfigFile.new()
	var err := _cfg.load(CONFIG_PATH)
	if err != OK and err != ERR_FILE_NOT_FOUND:
		push_warning("graphics_settings: load failed %s" % err)
	var raw := str(_cfg.get_value(CONFIG_SECTION, "quality", "high")).to_lower()
	_quality = Quality.LOW if raw == "low" or raw == "0" else Quality.HIGH
	_look_smooth = bool(_cfg.get_value(CONFIG_SECTION, "look_smooth", true))
	# Deck/Low: bob off by default — missing key ⇒ false.
	_head_bob = bool(_cfg.get_value(CONFIG_SECTION, "head_bob", false))


func _save() -> void:
	_cfg.set_value(CONFIG_SECTION, "quality", "low" if is_low() else "high")
	_cfg.set_value(CONFIG_SECTION, "look_smooth", _look_smooth)
	_cfg.set_value(CONFIG_SECTION, "head_bob", _head_bob)
	var err := _cfg.save(CONFIG_PATH)
	if err != OK:
		push_warning("graphics_settings: save failed %s" % err)
