extends RefCounted
class_name DiegeticScreens
## In-world jack terminal + StreetNet / ad billboard (#160).
## Label3D + emissive quads only — no browser / SubViewport video.
## Display-only: never opens year docks or StreetNet (#133 gate).
## Omni budget unchanged (this class never creates lights).
## Original props — no third-party demo IP.

const AD_LOOP := [
	"NEON CREDITS · ZERO INTEREST*",
	"JACK SAFE · SPEND FOCUS WISELY",
	"STREETNET · KEEP PAYLOAD TALK IN-CHANNEL",
	"METAVERSE UPLINK · U BEACON AHEAD",
	"CATPPUCCIN NIGHTS · TEAL / SKY / PEACH",
]

const KIND_TERMINAL := "jack_terminal"
const KIND_BILLBOARD := "streetnet_board"


static func spawn_terminal(parent: Node3D, mats: Dictionary, offset: Vector3 = Vector3(0.85, 0.0, 0.55)) -> Node3D:
	## Prefab 1 — jackpoint kiosk screen (beside J landmark).
	var root := Node3D.new()
	root.name = "DiegeticTerminal"
	root.set_meta("diegetic_kind", KIND_TERMINAL)
	root.position = offset
	parent.add_child(root)
	_add_box(root, mats, Vector3(0, 0.55, 0), Vector3(0.55, 1.1, 0.35), "prop")
	_add_box(root, mats, Vector3(0, 1.25, 0.12), Vector3(0.48, 0.38, 0.04), "jack")
	var screen := _make_label(root, Vector3(0, 1.25, 0.16), "JACK TERMINAL", Catppuccin.SKY, 22)
	screen.name = "ScreenText"
	screen.pixel_size = 0.0055
	var sub := _make_label(root, Vector3(0, 1.02, 0.16), "awaiting snapshot…", Catppuccin.SUBTEXT0, 16)
	sub.name = "ScreenSub"
	sub.pixel_size = 0.0045
	return root


static func spawn_billboard(parent: Node3D, mats: Dictionary, offset: Vector3 = Vector3(-1.1, 0.0, 0.8)) -> Node3D:
	## Prefab 2 — StreetNet / cyber ad board (beside U or street landmark).
	var root := Node3D.new()
	root.name = "DiegeticBillboard"
	root.set_meta("diegetic_kind", KIND_BILLBOARD)
	root.position = offset
	parent.add_child(root)
	_add_box(root, mats, Vector3(0, 1.35, 0), Vector3(0.12, 2.5, 0.12), "prop")
	_add_box(root, mats, Vector3(0, 2.55, 0.08), Vector3(1.6, 0.95, 0.06), "vendor_trim")
	_add_box(root, mats, Vector3(0, 2.55, 0.12), Vector3(1.45, 0.8, 0.03), "vendor")
	var title := _make_label(root, Vector3(0, 2.85, 0.16), "STREETNET", Catppuccin.YELLOW, 28)
	title.name = "ScreenTitle"
	title.pixel_size = 0.006
	var body := _make_label(root, Vector3(0, 2.45, 0.16), "…", Catppuccin.TEXT, 18)
	body.name = "ScreenText"
	body.pixel_size = 0.0048
	var ad := _make_label(root, Vector3(0, 2.15, 0.16), AD_LOOP[0], Catppuccin.PEACH, 14)
	ad.name = "ScreenAd"
	ad.pixel_size = 0.0042
	return root


static func paint(screens: Array, state: Dictionary, ice_mode: bool, detailed: bool) -> void:
	## Update Label3D copy from snapshot. ICE → hide or simplify. Never touches docks.
	var lines := _streetnet_lines(state)
	var objective := _objective_line(state)
	var topic := _irc_topic(state)
	var ad := _ad_line(state)
	for node in screens:
		if node == null or not is_instance_valid(node):
			continue
		var kind := str(node.get_meta("diegetic_kind", ""))
		if ice_mode:
			_paint_ice(node, kind, detailed)
			continue
		node.visible = true
		if kind == KIND_TERMINAL:
			_set_label(node, "ScreenText", "JACK · READY" if detailed else "JACK")
			var sub := objective if not objective.is_empty() else "Press J at plinth"
			if not detailed and sub.length() > 28:
				sub = sub.substr(0, 26) + "…"
			_set_label(node, "ScreenSub", sub)
		elif kind == KIND_BILLBOARD:
			_set_label(node, "ScreenTitle", "STREETNET")
			var body := topic if not topic.is_empty() else (lines[0] if lines.size() else "channel #streets")
			if not detailed and body.length() > 36:
				body = body.substr(0, 34) + "…"
			_set_label(node, "ScreenText", body)
			_set_label(node, "ScreenAd", ad if detailed else "AD · CYBER")


static func _paint_ice(node: Node3D, kind: String, detailed: bool) -> void:
	## Hidden or simplified while jacked — not a dock unlock path.
	if not detailed:
		node.visible = false
		return
	node.visible = true
	if kind == KIND_TERMINAL:
		_set_label(node, "ScreenText", "ICE LINK")
		_set_label(node, "ScreenSub", "lattice only")
	elif kind == KIND_BILLBOARD:
		_set_label(node, "ScreenTitle", "ICE")
		_set_label(node, "ScreenText", "StreetNet paused")
		_set_label(node, "ScreenAd", "—")


static func _streetnet_lines(state: Dictionary) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var chat = state.get("chat", [])
	if typeof(chat) == TYPE_ARRAY:
		for c in chat:
			if typeof(c) != TYPE_DICTIONARY:
				continue
			var text := str(c.get("text", "")).strip_edges()
			if text.is_empty():
				continue
			var nick := str(c.get("from", c.get("nick", "anon")))
			out.append("%s: %s" % [nick, text])
			if out.size() >= 3:
				break
	if out.is_empty():
		var msgs = state.get("messages", [])
		if typeof(msgs) == TYPE_ARRAY:
			for m in msgs:
				var t := str(m).strip_edges()
				if not t.is_empty():
					out.append(t)
				if out.size() >= 2:
					break
	return out


static func _objective_line(state: Dictionary) -> String:
	var obj = state.get("objective", "")
	if typeof(obj) == TYPE_DICTIONARY:
		return str(obj.get("text", "")).strip_edges()
	return str(obj).strip_edges()


static func _irc_topic(state: Dictionary) -> String:
	var irc = state.get("irc", {})
	if typeof(irc) != TYPE_DICTIONARY:
		return ""
	var ch := str(irc.get("channel", "#streets"))
	var topics = irc.get("topics", {})
	var topic := ""
	if typeof(topics) == TYPE_DICTIONARY:
		topic = str(topics.get(ch, ""))
	if topic.is_empty():
		topic = str(irc.get("topic", ""))
	if topic.is_empty():
		return "%s · live" % ch
	return "%s — %s" % [ch, topic]


static func _ad_line(state: Dictionary) -> String:
	var t := int(Time.get_ticks_msec() / 4000.0)
	var primer = state.get("primer", {})
	if typeof(primer) == TYPE_DICTIONARY and bool(primer.get("active", false)):
		var beat := str(primer.get("title", primer.get("beat", "PRIMER")))
		if not beat.is_empty():
			return "PRIMER · %s" % beat
	return AD_LOOP[t % AD_LOOP.size()]


static func _set_label(root: Node3D, name: String, text: String) -> void:
	var lab := root.get_node_or_null(name) as Label3D
	if lab:
		lab.text = text


static func _make_label(parent: Node3D, pos: Vector3, text: String, color: Color, font_size: int) -> Label3D:
	var lab := Label3D.new()
	lab.text = text
	lab.position = pos
	lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lab.font_size = font_size
	lab.outline_size = 8
	lab.modulate = color
	lab.outline_modulate = Catppuccin.CRUST
	lab.pixel_size = 0.005
	lab.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	parent.add_child(lab)
	return lab


static func _add_box(parent: Node3D, mats: Dictionary, pos: Vector3, scale: Vector3, mat_key: String) -> void:
	var mi := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3.ONE
	mi.mesh = box
	mi.position = pos
	mi.scale = scale
	if mats.has(mat_key):
		mi.material_override = mats[mat_key]
	elif mats.has("prop"):
		mi.material_override = mats["prop"]
	parent.add_child(mi)
