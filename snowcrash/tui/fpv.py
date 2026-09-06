"""ASCII first-person view for the curses TUI (raycast / column sample).

Pure stdlib — no heavy deps. Mirrors the web FpvEngine feel (facing + local
map walls/doors/entities) without a canvas or VideoAscii pipeline.
"""

from __future__ import annotations

from typing import List, Tuple

from .. import constants as C
from ..engine import GameState

# Wall / door / water block rays (match web isWall + door hit).
_BLOCKERS = frozenset({C.WALL, C.WATER, " ", C.DOOR})

# Distance bands → wall glyph (near → far). ASCII-safe for SSH / --no-color.
_WALL_NEAR = ("#", "H", "#", "H")
_WALL_MID = ("=", "|", "=", "|")
_WALL_FAR = (":", ";", ":", ";")
_DOOR_GLYPH = "+"
_WATER_GLYPH = "~"

# Entities drawn as billboards when in front of the camera.
_BILLBOARD = frozenset("itd&*!/[}%JU")

FACING_GLYPH = ("^", ">", "v", "<")


def _map_ch(gs: GameState, x: int, y: int) -> str:
    gmap = gs.gmap
    if not gmap.in_bounds(x, y):
        return C.WALL
    return gmap.tiles[y][x]


def _overlay_ch(gs: GameState, x: int, y: int) -> str:
    """Terrain + entity/item glyph at (x,y) when visible (else terrain)."""
    gmap = gs.gmap
    if not gmap.in_bounds(x, y):
        return C.WALL
    base = gmap.tiles[y][x]
    if not gmap.visible[y][x]:
        return base
    if gs.player.x == x and gs.player.y == y:
        return gs.player.glyph
    for a in gs.actors:
        if a.alive and a.x == x and a.y == y and not a.is_player():
            return a.glyph
    for fi in gs.floor_items:
        if fi.x == x and fi.y == y:
            return fi.item.glyph
    return base


def _wall_glyph(ch: str, dist: float, side: int) -> str:
    if ch == C.DOOR:
        return _DOOR_GLYPH
    if ch == C.WATER:
        return _WATER_GLYPH
    band = _WALL_NEAR if dist < 1.6 else _WALL_MID if dist < 3.5 else _WALL_FAR
    return band[side % 2]


def _shade_attr_pair(dist: float, side: int, is_door: bool = False) -> int:
    """Return preferred color pair id (1-9) for wall columns."""
    if is_door:
        return 3  # yellow
    if dist < 2.0:
        return 1 if side == 0 else 6  # cyan / white
    if dist < 4.0:
        return 6
    return 7


def render_fpv(
    gs: GameState,
    width: int,
    height: int,
) -> Tuple[List[str], List[List[int]]]:
    """Raycast a first-person ASCII frame.

    Returns (rows, color_pair_ids) where color_pair_ids[y][x] is 0 for default
    or a pair number for optional curses coloring.
    """
    width = max(8, int(width))
    height = max(4, int(height))
    rows: List[List[str]] = [[" " for _ in range(width)] for _ in range(height)]
    attrs: List[List[int]] = [[0 for _ in range(width)] for _ in range(height)]

    px = gs.player.x + 0.5
    py = gs.player.y + 0.5
    facing = gs.player.facing % 4
    dir_x, dir_y = C.FACING_DIRS[facing]
    # Camera plane perpendicular to facing (FOV ~66° like web 0.66).
    plane_x = -dir_y * 0.66
    plane_y = dir_x * 0.66
    mid = height / 2.0
    depths = [1e9] * width

    # Sky / floor fill
    for y in range(height):
        if y < mid:
            # ceiling — slightly denser near horizon
            t = (mid - y) / max(1.0, mid)
            ch = "." if t < 0.15 else " "
            pair = 5 if ch == "." else 0
        else:
            t = (y - mid) / max(1.0, height - mid)
            if t < 0.2:
                ch = "."
            elif t < 0.45:
                ch = ":"
            elif t < 0.7:
                ch = "-"
            else:
                ch = "="
            pair = 6
        for x in range(width):
            rows[y][x] = ch
            attrs[y][x] = pair

    max_steps = 40
    for col in range(width):
        cam_x = (2 * col) / width - 1
        ray_dir_x = dir_x + plane_x * cam_x
        ray_dir_y = dir_y + plane_y * cam_x
        map_x = int(px)
        map_y = int(py)
        delta_dist_x = 1e30 if ray_dir_x == 0 else abs(1 / ray_dir_x)
        delta_dist_y = 1e30 if ray_dir_y == 0 else abs(1 / ray_dir_y)
        if ray_dir_x < 0:
            step_x = -1
            side_dist_x = (px - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - px) * delta_dist_x
        if ray_dir_y < 0:
            step_y = -1
            side_dist_y = (py - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - py) * delta_dist_y

        hit = False
        side = 0
        ch = C.WALL
        for _ in range(max_steps):
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1
            ch = _map_ch(gs, map_x, map_y)
            if ch in _BLOCKERS:
                hit = True
                break

        if side == 0:
            perp = (map_x - px + (1 - step_x) / 2) / ray_dir_x if ray_dir_x else 1e9
        else:
            perp = (map_y - py + (1 - step_y) / 2) / ray_dir_y if ray_dir_y else 1e9
        if not hit or perp != perp or perp < 0.05:  # NaN / too close
            perp = 0.05 if hit else 40.0
        depths[col] = perp

        if not hit:
            continue

        line_h = min(height, int(height / max(0.05, perp)))
        draw_start = max(0, int(mid - line_h / 2))
        draw_end = min(height - 1, int(mid + line_h / 2))
        glyph = _wall_glyph(ch, perp, side)
        pair = _shade_attr_pair(perp, side, is_door=(ch == C.DOOR))
        for y in range(draw_start, draw_end + 1):
            rows[y][col] = glyph
            attrs[y][col] = pair
        # Bright rim
        if draw_start < height:
            rows[draw_start][col] = glyph
            attrs[draw_start][col] = 1
        if draw_end >= 0:
            attrs[draw_end][col] = 1

    # Entity billboards in local FOV window
    pr = 10
    y_lo = max(0, gs.player.y - pr)
    y_hi = min(gs.gmap.height - 1, gs.player.y + pr)
    x_lo = max(0, gs.player.x - pr)
    x_hi = min(gs.gmap.width - 1, gs.player.x + pr)
    inv_det = 1.0 / (plane_x * dir_y - dir_x * plane_y) if (plane_x * dir_y - dir_x * plane_y) else 0.0

    sprites: List[Tuple[float, int, int, str]] = []
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            if x == gs.player.x and y == gs.player.y:
                continue
            if not gs.gmap.visible[y][x]:
                continue
            och = _overlay_ch(gs, x, y)
            if och not in _BILLBOARD:
                continue
            rel_x = x + 0.5 - px
            rel_y = y + 0.5 - py
            if inv_det == 0:
                continue
            transform_x = inv_det * (dir_y * rel_x - dir_x * rel_y)
            transform_y = inv_det * (-plane_y * rel_x + plane_x * rel_y)
            if transform_y <= 0.15:
                continue
            sprites.append((transform_y, x, y, och))

    sprites.sort(key=lambda t: -t[0])  # far → near so near overwrites

    for transform_y, _sx, _sy, och in sprites:
        # Recompute screen X (sorted by depth only)
        rel_x = _sx + 0.5 - px
        rel_y = _sy + 0.5 - py
        transform_x = inv_det * (dir_y * rel_x - dir_x * rel_y)
        screen_x = int((width / 2) * (1 + transform_x / transform_y))
        sprite_h = abs(int(height / transform_y))
        draw_start_y = max(0, int(mid - sprite_h / 2))
        draw_end_y = min(height - 1, int(mid + sprite_h / 2))
        sprite_w = max(1, int(sprite_h * 0.35))
        draw_start_x = max(0, screen_x - sprite_w // 2)
        draw_end_x = min(width - 1, screen_x + sprite_w // 2)
        pair = 2 if och == "i" else 3 if och == "t" else 4 if och == "d" else 5 if och == "&" else 3
        for sx in range(draw_start_x, draw_end_x + 1):
            if transform_y >= depths[sx]:
                continue
            for sy in range(draw_start_y, draw_end_y + 1):
                rows[sy][sx] = "|" if sx in (draw_start_x, draw_end_x) else " "
                attrs[sy][sx] = pair
            # Center glyph
            if sx == screen_x:
                cy = min(height - 1, max(0, int(mid)))
                rows[cy][sx] = och
                attrs[cy][sx] = pair
            depths[sx] = transform_y

    # Crosshair
    cx, cy = width // 2, height // 2
    if 0 <= cy < height:
        if cx - 2 >= 0:
            rows[cy][cx - 2] = "-"
            attrs[cy][cx - 2] = 1
        if cx + 2 < width:
            rows[cy][cx + 2] = "-"
            attrs[cy][cx + 2] = 1
    if 0 <= cx < width:
        if cy - 1 >= 0:
            rows[cy - 1][cx] = "|"
            attrs[cy - 1][cx] = 1
        if cy + 1 < height:
            rows[cy + 1][cx] = "|"
            attrs[cy + 1][cx] = 1
        rows[cy][cx] = "+"
        attrs[cy][cx] = 8

    return ["".join(r) for r in rows], attrs


def compass_line(facing: int) -> str:
    f = facing % 4
    return f"{FACING_GLYPH[f]} {C.FACING_NAMES[f]}"
