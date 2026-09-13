extends Node
## Low / High 3D quality preset (#141 slice 5). Persists in ConfigFile with onboarding/audio.
## Omni budget is documented in docs/godot-3d.md — this autoload never adds lights.

const CONFIG_PATH := "user://snowcrash_client.cfg"
const CONFIG_SECTION := "graphics"

## High = desktop neon look; Low = Deck / weak GPU floor.
enum Quality { LOW = 0, HIGH = 1 }

signal quality_changed(level: int)

var _cfg := ConfigFile.new()
var _quality: int = Quality.HIGH


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


func _save() -> void:
	_cfg.set_value(CONFIG_SECTION, "quality", "low" if is_low() else "high")
	var err := _cfg.save(CONFIG_PATH)
	if err != OK:
		push_warning("graphics_settings: save failed %s" % err)
