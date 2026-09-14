extends Node
## Optional GodotSteam bridge (#173). No-ops without SteamAPI / GDExtension.
## Never hard-depends on the Steam class — ClassDB / singleton reflection only so
## Godot 4.3 headless export and CI keep working without addons/godotsteam binaries.
## Deck / Big Picture → GraphicsSettings Low default hint (first-run only).
## Achievement / stat API is a placeholder until a real App ID + Steamworks defs land.
## Refs #141 · #132 · #130 · packaging #67. Do not close those epics from this file.

const PLACEHOLDER_APP_ID := 480  ## Valve SpaceWar — local Steam client testing only.
const CONFIG_PATH := "user://snowcrash_client.cfg"
const CONFIG_SECTION := "steam"

signal steam_ready(available: bool)
signal achievement_stub(api_name: String, ok: bool)

var _available: bool = false
var _initialized: bool = false
var _is_deck: bool = false
var _is_big_picture: bool = false
var _low_quality_hint: bool = false
var _app_id: int = PLACEHOLDER_APP_ID
var _last_init_status: int = -1
var _last_init_verbal: String = ""


func _ready() -> void:
	_load_app_id()
	_probe_env_hints()
	if _should_skip_steam_init():
		steam_ready.emit(false)
		return
	_try_init_steam()
	steam_ready.emit(_initialized)


func _process(_delta: float) -> void:
	if not _initialized:
		return
	_call_steam("run_callbacks", [])


func is_available() -> bool:
	return _available


func is_initialized() -> bool:
	return _initialized


func is_deck() -> bool:
	return _is_deck


func is_big_picture() -> bool:
	return _is_big_picture


func suggest_low_quality() -> bool:
	## Deck / Big Picture → prefer GraphicsSettings Low on first run (#173 / #148).
	return _low_quality_hint or _is_deck or _is_big_picture


func app_id() -> int:
	return _app_id


func last_init_status() -> int:
	return _last_init_status


func last_init_verbal() -> String:
	return _last_init_verbal


func set_achievement(api_name: String) -> bool:
	## Placeholder achievement path — no-ops without SteamAPI. Does not invent store defs.
	var name := str(api_name).strip_edges()
	if name.is_empty():
		achievement_stub.emit(name, false)
		return false
	if not _initialized:
		achievement_stub.emit(name, false)
		return false
	var ok_set: Variant = _call_steam("setAchievement", [name])
	var ok_store: Variant = _call_steam("storeStats", [])
	var ok: bool = bool(ok_set) and (ok_store == null or bool(ok_store) or ok_store == true)
	achievement_stub.emit(name, ok)
	return ok


func clear_achievement(api_name: String) -> bool:
	## Dev/test helper — no-ops without SteamAPI.
	if not _initialized:
		return false
	var ok: Variant = _call_steam("clearAchievement", [str(api_name)])
	_call_steam("storeStats", [])
	return bool(ok)


func _load_app_id() -> void:
	var env_id := OS.get_environment("SteamAppId")
	if env_id.is_empty():
		env_id = OS.get_environment("SteamGameId")
	if not env_id.is_empty() and env_id.is_valid_int():
		_app_id = int(env_id)
		return
	var cfg := ConfigFile.new()
	if cfg.load(CONFIG_PATH) == OK:
		var raw = cfg.get_value(CONFIG_SECTION, "app_id", PLACEHOLDER_APP_ID)
		if typeof(raw) == TYPE_INT or str(raw).is_valid_int():
			_app_id = int(raw)


func _probe_env_hints() -> void:
	## SteamOS / Deck sets SteamDeck=1 even before GodotSteam loads.
	if OS.get_environment("SteamDeck") == "1":
		_is_deck = true
		_low_quality_hint = true
	# Some Deck / BPM launches expose BigPicture via env; treat as Low hint.
	var bpm := OS.get_environment("SteamBigPicture").to_lower()
	if bpm == "1" or bpm == "true":
		_is_big_picture = true
		_low_quality_hint = true


func _should_skip_steam_init() -> bool:
	## Headless / CI / export smoke must not require Steam client or GDExtension.
	if DisplayServer.get_name() == "headless":
		return true
	if OS.has_feature("dedicated_server"):
		return true
	for arg in OS.get_cmdline_args():
		if str(arg) == "--headless" or str(arg).begins_with("--headless"):
			return true
	if OS.get_environment("SNOWCRASH_DISABLE_STEAM") == "1":
		return true
	return false


func _steam_present() -> bool:
	## GodotSteam GDExtension registers an Engine singleton named "Steam".
	## Godot 4.3-safe: singleton reflection only (no static ClassDB call helpers).
	return Engine.has_singleton("Steam")


func _try_init_steam() -> void:
	if not _steam_present():
		_available = false
		_initialized = false
		return
	_available = true
	# Ensure App ID env for steamInitEx variants that read env only.
	if OS.get_environment("SteamAppId").is_empty():
		OS.set_environment("SteamAppId", str(_app_id))
	if OS.get_environment("SteamGameId").is_empty():
		OS.set_environment("SteamGameId", str(_app_id))

	var resp: Variant = _call_steam("steamInitEx", [_app_id, true])
	if resp == null:
		# Older signatures / bool-only steamInit fallback.
		resp = _call_steam("steamInitEx", [])
	if resp == null:
		var ok_bool: Variant = _call_steam("steamInit", [_app_id, true])
		if ok_bool == null:
			ok_bool = _call_steam("steamInit", [])
		_initialized = bool(ok_bool)
		_last_init_status = 0 if _initialized else 1
		_last_init_verbal = "steamInit bool fallback"
	elif typeof(resp) == TYPE_DICTIONARY:
		var d: Dictionary = resp
		_last_init_status = int(d.get("status", 1))
		_last_init_verbal = str(d.get("verbal", ""))
		_initialized = _last_init_status == 0
	else:
		_initialized = bool(resp)
		_last_init_status = 0 if _initialized else 1

	if not _initialized:
		# Soft fail — keep playing without overlay / achievements (dev builds).
		return

	_refresh_device_flags()


func _refresh_device_flags() -> void:
	var deck_v: Variant = _call_steam("isSteamRunningOnSteamDeck", [])
	if deck_v != null:
		_is_deck = bool(deck_v)
	var bpm_v: Variant = _call_steam("isSteamInBigPictureMode", [])
	if bpm_v != null:
		_is_big_picture = bool(bpm_v)
	if _is_deck or _is_big_picture:
		_low_quality_hint = true


func _call_steam(method: String, args: Array) -> Variant:
	## Reflection-only Steam calls — never parse-time reference the Steam identifier.
	## Godot 4.3: Engine singleton only.
	if not Engine.has_singleton("Steam"):
		return null
	var s: Object = Engine.get_singleton("Steam")
	if s == null or not s.has_method(method):
		return null
	return s.callv(method, args)
