extends RefCounted
class_name FpvAscii
## TUI-style column raycast → ASCII rows from a snapshot map (#118 / #78).
## Operates on snapshot `map` row strings + player x/y/facing — no GameState.

const BLOCKERS := {"#": true, "~": true, " ": true, "+": true}
const BILLBOARD := "itd&*!/[}%JU@"
const WALL_NEAR := ["#", "H", "#", "H"]
const WALL_MID := ["=", "|", "=", "|"]
const WALL_FAR := [":", ";", ":", ";"]
const FACING_DIRS := [Vector2(0, -1), Vector2(1, 0), Vector2(0, 1), Vector2(-1, 0)]
const FACING_GLYPH := ["^", ">", "v", "<"]
const FACING_NAMES := ["N", "E", "S", "W"]


static func facing_index(player: Dictionary) -> int:
	if player.has("facing"):
		return int(player.get("facing", 0)) % 4
	var name := str(player.get("facing_name", "N")).to_upper()
	var i := FACING_NAMES.find(name)
	return i if i >= 0 else 0


static func compass_line(player: Dictionary) -> String:
	var f := facing_index(player)
	return "%s %s" % [FACING_GLYPH[f], FACING_NAMES[f]]


static func map_at(rows: Array, x: int, y: int) -> String:
	if y < 0 or y >= rows.size():
		return "#"
	var row := str(rows[y])
	if x < 0 or x >= row.length():
		return "#"
	return row.substr(x, 1)


static func render(state: Dictionary, width: int = 56, height: int = 18) -> String:
	width = maxi(8, width)
	height = maxi(4, height)
	var rows_src = state.get("map", [])
	if typeof(rows_src) != TYPE_ARRAY or rows_src.is_empty():
		return "(no map in snapshot)"
	var player: Dictionary = state.get("player", {})
	if typeof(player) != TYPE_DICTIONARY:
		player = {}
	var px := float(player.get("x", 0)) + 0.5
	var py := float(player.get("y", 0)) + 0.5
	var facing := facing_index(player)
	var dir: Vector2 = FACING_DIRS[facing]
	var plane := Vector2(-dir.y * 0.66, dir.x * 0.66)
	var mid := height / 2.0

	var grid: Array = []
	for y in range(height):
		var line: Array = []
		line.resize(width)
		var ch := " "
		if y < mid:
			var t := (mid - y) / maxf(1.0, mid)
			ch = "." if t < 0.15 else " "
		else:
			var t2 := (y - mid) / maxf(1.0, height - mid)
			if t2 < 0.2:
				ch = "."
			elif t2 < 0.45:
				ch = ":"
			elif t2 < 0.7:
				ch = "-"
			else:
				ch = "="
		for x in range(width):
			line[x] = ch
		grid.append(line)

	var depths: PackedFloat32Array = PackedFloat32Array()
	depths.resize(width)
	for i in range(width):
		depths[i] = 1e9

	var max_steps := 40
	for col in range(width):
		var cam_x := (2.0 * col) / float(width) - 1.0
		var ray_dir := dir + plane * cam_x
		var map_x := int(px)
		var map_y := int(py)
		var delta_x := 1e30 if absf(ray_dir.x) < 1e-12 else absf(1.0 / ray_dir.x)
		var delta_y := 1e30 if absf(ray_dir.y) < 1e-12 else absf(1.0 / ray_dir.y)
		var step_x := -1 if ray_dir.x < 0.0 else 1
		var step_y := -1 if ray_dir.y < 0.0 else 1
		var side_dist_x: float
		var side_dist_y: float
		if ray_dir.x < 0.0:
			side_dist_x = (px - map_x) * delta_x
		else:
			side_dist_x = (map_x + 1.0 - px) * delta_x
		if ray_dir.y < 0.0:
			side_dist_y = (py - map_y) * delta_y
		else:
			side_dist_y = (map_y + 1.0 - py) * delta_y

		var hit := false
		var side := 0
		var ch_hit := "#"
		for _s in range(max_steps):
			if side_dist_x < side_dist_y:
				side_dist_x += delta_x
				map_x += step_x
				side = 0
			else:
				side_dist_y += delta_y
				map_y += step_y
				side = 1
			ch_hit = map_at(rows_src, map_x, map_y)
			if BLOCKERS.has(ch_hit):
				hit = true
				break

		var perp: float
		if side == 0:
			perp = (map_x - px + (1 - step_x) / 2.0) / ray_dir.x if absf(ray_dir.x) > 1e-12 else 1e9
		else:
			perp = (map_y - py + (1 - step_y) / 2.0) / ray_dir.y if absf(ray_dir.y) > 1e-12 else 1e9
		if not hit or is_nan(perp) or perp < 0.05:
			perp = 0.05 if hit else 40.0
		depths[col] = perp
		if not hit:
			continue

		var line_h := mini(height, int(height / maxf(0.05, perp)))
		var draw_start := maxi(0, int(mid - line_h / 2.0))
		var draw_end := mini(height - 1, int(mid + line_h / 2.0))
		var glyph := _wall_glyph(ch_hit, perp, side)
		for y in range(draw_start, draw_end + 1):
			grid[y][col] = glyph

	# Entity billboards from overlay glyphs already baked into map rows
	var pr := 10
	var pxi := int(player.get("x", 0))
	var pyi := int(player.get("y", 0))
	var det := plane.x * dir.y - dir.x * plane.y
	var inv_det := 0.0 if absf(det) < 1e-12 else 1.0 / det
	var sprites: Array = []
	if inv_det != 0.0:
		var y_lo := maxi(0, pyi - pr)
		var y_hi := mini(rows_src.size() - 1, pyi + pr)
		for y in range(y_lo, y_hi + 1):
			var row := str(rows_src[y])
			var x_lo := maxi(0, pxi - pr)
			var x_hi := mini(row.length() - 1, pxi + pr)
			for x in range(x_lo, x_hi + 1):
				if x == pxi and y == pyi:
					continue
				var och := row.substr(x, 1)
				if BILLBOARD.find(och) < 0:
					continue
				var rel := Vector2(x + 0.5 - px, y + 0.5 - py)
				var transform_x := inv_det * (dir.y * rel.x - dir.x * rel.y)
				var transform_y := inv_det * (-plane.y * rel.x + plane.x * rel.y)
				if transform_y <= 0.15:
					continue
				sprites.append({"ty": transform_y, "tx": transform_x, "ch": och})

	sprites.sort_custom(func(a, b): return a["ty"] > b["ty"])
	for spr in sprites:
		var transform_y: float = spr["ty"]
		var transform_x: float = spr["tx"]
		var och: String = spr["ch"]
		var screen_x := int((width / 2.0) * (1.0 + transform_x / transform_y))
		var sprite_h := absi(int(height / transform_y))
		var draw_start_y := maxi(0, int(mid - sprite_h / 2.0))
		var draw_end_y := mini(height - 1, int(mid + sprite_h / 2.0))
		var sprite_w := maxi(1, int(sprite_h * 0.35))
		var draw_start_x := maxi(0, screen_x - sprite_w / 2)
		var draw_end_x := mini(width - 1, screen_x + sprite_w / 2)
		for sx in range(draw_start_x, draw_end_x + 1):
			if transform_y >= depths[sx]:
				continue
			for sy in range(draw_start_y, draw_end_y + 1):
				grid[sy][sx] = "|" if sx == draw_start_x or sx == draw_end_x else " "
			if sx == screen_x:
				var cy := clampi(int(mid), 0, height - 1)
				grid[cy][sx] = och
			depths[sx] = transform_y

	# Crosshair
	var cx := width / 2
	var cy2 := height / 2
	if cy2 >= 0 and cy2 < height:
		if cx - 2 >= 0:
			grid[cy2][cx - 2] = "-"
		if cx + 2 < width:
			grid[cy2][cx + 2] = "-"
	if cx >= 0 and cx < width:
		if cy2 - 1 >= 0:
			grid[cy2 - 1][cx] = "|"
		if cy2 + 1 < height:
			grid[cy2 + 1][cx] = "|"
		grid[cy2][cx] = "+"

	var out: PackedStringArray = PackedStringArray()
	for y in range(height):
		var parts: PackedStringArray = PackedStringArray()
		for x in range(width):
			parts.append(str(grid[y][x]))
		out.append("".join(parts))
	return "\n".join(out)


static func _wall_glyph(ch: String, dist: float, side: int) -> String:
	if ch == "+":
		return "+"
	if ch == "~":
		return "~"
	var band: Array = WALL_NEAR if dist < 1.6 else WALL_MID if dist < 3.5 else WALL_FAR
	return str(band[side % 2])


static func map_crop(state: Dictionary, radius: int = 14) -> String:
	var rows = state.get("map", [])
	if typeof(rows) != TYPE_ARRAY or rows.is_empty():
		return "(no map in snapshot)"
	var player: Dictionary = state.get("player", {})
	if typeof(player) != TYPE_DICTIONARY:
		player = {}
	var px := int(player.get("x", 0))
	var py := int(player.get("y", 0))
	var facing := facing_index(player)
	var y0: int = maxi(0, py - radius)
	var y1: int = mini(rows.size(), py + radius + 1)
	var lines: PackedStringArray = PackedStringArray()
	lines.append("overhead · %s · (%d,%d)" % [compass_line(player), px, py])
	for yi in range(y0, y1):
		var row := str(rows[yi])
		var x0: int = maxi(0, px - radius * 2)
		var x1: int = mini(row.length(), px + radius * 2 + 1)
		var slice := row.substr(x0, x1 - x0)
		# Mark player with facing glyph when this is their row
		if yi == py:
			var local := px - x0
			if local >= 0 and local < slice.length():
				slice = slice.substr(0, local) + FACING_GLYPH[facing] + slice.substr(local + 1)
		lines.append(slice)
	return "\n".join(lines)
