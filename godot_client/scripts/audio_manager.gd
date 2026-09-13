extends Node
class_name AudioManagerAutoload
## Godot audio bus + juice for Steam first impressions (#134 · Refs #130 #118).
## Loads procedural WAVs from res://audio/ (PCM) without requiring editor .import.
## Persistence: ConfigFile user://snowcrash_client.cfg section [audio] (same file as onboarding).

const CONFIG_PATH := "user://snowcrash_client.cfg"
const CONFIG_SECTION := "audio"
const SFX_DIR := "res://audio/sfx/"
const MUSIC_DIR := "res://audio/music/"

const BUS_MASTER := "Master"
const BUS_SFX := "SFX"
const BUS_MUSIC := "Music"

## Snapshot / engine event_id → wav stem (matches snowcrash/static/sfx + streetnet_ping).
const SFX_MAP := {
	"step": "step",
	"bump": "bump",
	"melee": "melee",
	"hurt": "hurt",
	"kill": "kill",
	"pulse": "pulse",
	"pickup": "pickup",
	"use": "use",
	"talk": "talk",
	"door": "door",
	"win": "win",
	"death": "death",
	"click": "click",
	"streetnet_ping": "streetnet_ping",
	"confirm": "click",
	"uplink": "win",
}

const MUSIC_STREET := "street_ambient"
const MUSIC_ICE := "ice_jackin"

## Soften noisy cues so juice stays audible without spam.
const SFX_GAIN := {
	"step": 0.45,
	"bump": 0.55,
	"talk": 0.65,
	"streetnet_ping": 0.7,
	"click": 0.75,
	"confirm": 0.75,
}

var _cfg := ConfigFile.new()
var _streams: Dictionary = {}  # stem -> AudioStreamWAV
var _sfx_pool: Array = []  # AudioStreamPlayer
var _music_player: AudioStreamPlayer
var _pool_i: int = 0
var _muted: bool = false
var _master_lin: float = 1.0
var _sfx_lin: float = 1.0
var _music_lin: float = 0.7
var _current_bed: String = ""
var _chat_len: int = -1
var _last_ping_sfx_ms: int = 0
var _was_dead: bool = false
var _was_won: bool = false
var _had_uplink_flag: bool = false


func _ready() -> void:
	_ensure_buses()
	_music_player = AudioStreamPlayer.new()
	_music_player.name = "MusicPlayer"
	_music_player.bus = BUS_MUSIC
	add_child(_music_player)
	for i in range(8):
		var p := AudioStreamPlayer.new()
		p.name = "Sfx%d" % i
		p.bus = BUS_SFX
		add_child(p)
		_sfx_pool.append(p)
	_load_config()
	_apply_volumes()
	_preload_known()


func _ensure_buses() -> void:
	# Bus layout from project.godot; if missing, create SFX/Music under Master.
	if AudioServer.get_bus_index(BUS_SFX) < 0:
		AudioServer.add_bus()
		var idx := AudioServer.get_bus_count() - 1
		AudioServer.set_bus_name(idx, BUS_SFX)
		AudioServer.set_bus_send(idx, BUS_MASTER)
	if AudioServer.get_bus_index(BUS_MUSIC) < 0:
		AudioServer.add_bus()
		var idx2 := AudioServer.get_bus_count() - 1
		AudioServer.set_bus_name(idx2, BUS_MUSIC)
		AudioServer.set_bus_send(idx2, BUS_MASTER)


func _preload_known() -> void:
	for stem in SFX_MAP.values():
		_get_stream(SFX_DIR + stem + ".wav", false)
	_get_stream(MUSIC_DIR + MUSIC_STREET + ".wav", true)
	_get_stream(MUSIC_DIR + MUSIC_ICE + ".wav", true)


# ---- public API -------------------------------------------------------------

func play_sfx(event_id: String) -> void:
	if _muted or event_id.is_empty():
		return
	var stem := str(SFX_MAP.get(event_id, event_id))
	var stream := _get_stream(SFX_DIR + stem + ".wav", false)
	if stream == null:
		return
	var player: AudioStreamPlayer = _sfx_pool[_pool_i]
	_pool_i = (_pool_i + 1) % _sfx_pool.size()
	player.stream = stream
	var gain: float = float(SFX_GAIN.get(event_id, SFX_GAIN.get(stem, 1.0)))
	player.volume_db = linear_to_db(clampf(gain, 0.05, 1.0))
	player.play()


func play_list(events: Array) -> void:
	for e in events:
		play_sfx(str(e))


func play_confirm() -> void:
	play_sfx("confirm")


func play_streetnet_ping() -> void:
	var now := Time.get_ticks_msec()
	if now - _last_ping_sfx_ms < 400:
		return
	_last_ping_sfx_ms = now
	play_sfx("streetnet_ping")


func set_music_bed(bed: String) -> void:
	## bed: "street" | "ice" | "" (stop)
	if _muted:
		_current_bed = bed
		_music_player.stop()
		return
	var stem := ""
	match bed:
		"street":
			stem = MUSIC_STREET
		"ice":
			stem = MUSIC_ICE
		_:
			_current_bed = ""
			_music_player.stop()
			return
	if _current_bed == bed and _music_player.playing:
		return
	_current_bed = bed
	var stream := _get_stream(MUSIC_DIR + stem + ".wav", true)
	if stream == null:
		return
	_music_player.stream = stream
	_music_player.volume_db = 0.0
	_music_player.play()


func notify_snapshot(state: Dictionary) -> void:
	## Wire engine sfx[] + death / win / uplink / mode → music.
	var events = state.get("sfx", [])
	if typeof(events) == TYPE_ARRAY and not events.is_empty():
		play_list(events)

	var mode := str(state.get("mode", "play"))
	var cyber: Dictionary = state.get("cyberspace", {}) if typeof(state.get("cyberspace", {})) == TYPE_DICTIONARY else {}
	var heist: Dictionary = state.get("ice_heist", {}) if typeof(state.get("ice_heist", {})) == TYPE_DICTIONARY else {}
	var in_ice := mode == "cyberspace" or mode == "heist" or bool(cyber.get("active")) or bool(heist.get("active"))
	if in_ice:
		set_music_bed("ice")
	else:
		set_music_bed("street")

	var dead_now := bool(state.get("dead")) or mode == "dead" or bool(state.get("lost"))
	var won_now := bool(state.get("won")) or mode == "won"
	if dead_now and not _was_dead:
		# engine usually emits death in sfx[]; ensure juice if missing
		if typeof(events) != TYPE_ARRAY or not ("death" in events):
			play_sfx("death")
	if won_now and not _was_won:
		if typeof(events) != TYPE_ARRAY or not ("win" in events):
			play_sfx("win")
	_was_dead = dead_now
	_was_won = won_now

	# uplink deliver — Payload-Zero scrub / uplink flag edge
	var uplink = state.get("uplink", null)
	var quest = state.get("quest_flags", {})
	var delivered := false
	if typeof(uplink) == TYPE_DICTIONARY and bool(uplink.get("delivered", false)):
		delivered = true
	elif typeof(quest) == TYPE_DICTIONARY and (
		bool(quest.get("payload_delivered", false)) or bool(quest.get("uplink_done", false))
	):
		delivered = true
	elif won_now:
		delivered = true
	if delivered and not _had_uplink_flag and not won_now:
		play_sfx("uplink")
	_had_uplink_flag = delivered

	# StreetNet chat growth → soft ping
	var chat = state.get("chat", [])
	if typeof(chat) == TYPE_ARRAY:
		var n: int = chat.size()
		if _chat_len >= 0 and n > _chat_len:
			play_streetnet_ping()
		_chat_len = n


func notify_welcome(state: Dictionary) -> void:
	_was_dead = false
	_was_won = false
	_had_uplink_flag = false
	_chat_len = -1
	play_sfx("pulse")  # jack-in juice
	notify_snapshot(state)


func notify_rtt_ping(_rtt_ms: int) -> void:
	## Rare soft ping on WS RTT — chat growth is the primary StreetNet juice.
	var now := Time.get_ticks_msec()
	if now - _last_ping_sfx_ms < 12000:
		return
	play_streetnet_ping()


func is_muted() -> bool:
	return _muted


func set_muted(m: bool) -> void:
	_muted = m
	_apply_volumes()
	_save_config()
	if _muted:
		_music_player.stop()
	elif not _current_bed.is_empty():
		var bed := _current_bed
		_current_bed = ""
		set_music_bed(bed)


func toggle_mute() -> bool:
	set_muted(not _muted)
	if not _muted:
		play_confirm()
	return _muted


func master_linear() -> float:
	return _master_lin


func sfx_linear() -> float:
	return _sfx_lin


func music_linear() -> float:
	return _music_lin


func set_master_linear(v: float) -> void:
	_master_lin = clampf(v, 0.0, 1.0)
	_apply_volumes()
	_save_config()


func set_sfx_linear(v: float) -> void:
	_sfx_lin = clampf(v, 0.0, 1.0)
	_apply_volumes()
	_save_config()


func set_music_linear(v: float) -> void:
	_music_lin = clampf(v, 0.0, 1.0)
	_apply_volumes()
	_save_config()


func stop_all() -> void:
	_music_player.stop()
	_current_bed = ""
	for p in _sfx_pool:
		(p as AudioStreamPlayer).stop()


# ---- WAV load / volume / config --------------------------------------------

func _get_stream(path: String, loop: bool) -> AudioStreamWAV:
	var key := "%s|%s" % [path, "1" if loop else "0"]
	if _streams.has(key):
		return _streams[key]
	var stream := _load_wav(path, loop)
	if stream:
		_streams[key] = stream
	return stream


func _load_wav(path: String, loop: bool) -> AudioStreamWAV:
	if not FileAccess.file_exists(path):
		push_warning("AudioManager: missing %s" % path)
		return null
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_warning("AudioManager: cannot open %s" % path)
		return null
	var bytes := f.get_buffer(f.get_length())
	if bytes.size() < 44:
		return null
	# RIFF/WAVE PCM parse
	if bytes.slice(0, 4).get_string_from_ascii() != "RIFF":
		return null
	if bytes.slice(8, 12).get_string_from_ascii() != "WAVE":
		return null
	var offset := 12
	var channels := 1
	var rate := 22050
	var bits := 16
	var data := PackedByteArray()
	while offset + 8 <= bytes.size():
		var chunk_id := bytes.slice(offset, offset + 4).get_string_from_ascii()
		var chunk_size := bytes.decode_u32(offset + 4)
		var payload := offset + 8
		if chunk_id == "fmt ":
			channels = bytes.decode_u16(payload + 2)
			rate = bytes.decode_u32(payload + 4)
			bits = bytes.decode_u16(payload + 14)
		elif chunk_id == "data":
			data = bytes.slice(payload, payload + chunk_size)
			break
		offset = payload + chunk_size
		if chunk_size % 2 == 1:
			offset += 1
	if data.is_empty():
		return null
	var stream := AudioStreamWAV.new()
	if bits == 8:
		stream.format = AudioStreamWAV.FORMAT_8_BITS
	else:
		stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = rate
	stream.stereo = channels > 1
	stream.data = data
	if loop:
		stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
		var frame_bytes := channels * (bits / 8)
		var frames := int(data.size() / max(1, frame_bytes))
		stream.loop_begin = 0
		stream.loop_end = frames
	else:
		stream.loop_mode = AudioStreamWAV.LOOP_DISABLED
	return stream


func _lin_to_bus_db(lin: float) -> float:
	if lin <= 0.001:
		return -80.0
	return linear_to_db(lin)


func _apply_volumes() -> void:
	var master_idx := AudioServer.get_bus_index(BUS_MASTER)
	var sfx_idx := AudioServer.get_bus_index(BUS_SFX)
	var music_idx := AudioServer.get_bus_index(BUS_MUSIC)
	if master_idx >= 0:
		AudioServer.set_bus_volume_db(master_idx, _lin_to_bus_db(0.0 if _muted else _master_lin))
		AudioServer.set_bus_mute(master_idx, _muted)
	if sfx_idx >= 0:
		AudioServer.set_bus_volume_db(sfx_idx, _lin_to_bus_db(_sfx_lin))
	if music_idx >= 0:
		AudioServer.set_bus_volume_db(music_idx, _lin_to_bus_db(_music_lin))


func _load_config() -> void:
	_cfg = ConfigFile.new()
	var err := _cfg.load(CONFIG_PATH)
	if err != OK:
		return
	_muted = bool(_cfg.get_value(CONFIG_SECTION, "muted", false))
	_master_lin = float(_cfg.get_value(CONFIG_SECTION, "master", 1.0))
	_sfx_lin = float(_cfg.get_value(CONFIG_SECTION, "sfx", 1.0))
	_music_lin = float(_cfg.get_value(CONFIG_SECTION, "music", 0.7))


func _save_config() -> void:
	_cfg.set_value(CONFIG_SECTION, "muted", _muted)
	_cfg.set_value(CONFIG_SECTION, "master", _master_lin)
	_cfg.set_value(CONFIG_SECTION, "sfx", _sfx_lin)
	_cfg.set_value(CONFIG_SECTION, "music", _music_lin)
	var err := _cfg.save(CONFIG_PATH)
	if err != OK:
		push_warning("AudioManager: could not save %s (%s)" % [CONFIG_PATH, error_string(err)])
