"""Curses frontend for Snowcrash (SSH / TTY hardened)."""

from __future__ import annotations

import curses
import os
import sys
from typing import Optional

from ..engine import GameState, handle_action, new_game, snapshot
from .fpv import compass_line, render_fpv

# Minimum terminal size for playable TUI (cols x rows).
_MIN_COLS = 40
_MIN_ROWS = 12

# View modes: first-person ASCII vs classic overhead map.
_VIEW_FPV = "fpv"
_VIEW_MAP = "map"


def _safe_color_pair(n: int) -> int:
    """Return color_pair(n) or A_NORMAL if colors unavailable / pair invalid."""
    try:
        return curses.color_pair(n)
    except curses.error:
        return curses.A_NORMAL


def _safe_init_pair(n: int, fg: int, bg: int) -> None:
    try:
        curses.init_pair(n, fg, bg)
    except curses.error:
        pass


def _init_colors(no_color: bool = False) -> bool:
    """Initialize color pairs safely. Returns True if colors are usable."""
    if no_color or os.environ.get("SNOWCRASH_NO_COLOR", "").strip() in ("1", "true", "yes"):
        return False
    if not curses.has_colors():
        return False
    try:
        curses.start_color()
    except curses.error:
        return False
    try:
        curses.use_default_colors()
        default_bg = -1
    except curses.error:
        default_bg = curses.COLOR_BLACK
    _safe_init_pair(1, curses.COLOR_CYAN, default_bg)  # player / near walls
    _safe_init_pair(2, curses.COLOR_GREEN, default_bg)  # infected
    _safe_init_pair(3, curses.COLOR_YELLOW, default_bg)  # thug / door / item
    _safe_init_pair(4, curses.COLOR_MAGENTA, default_bg)  # drone
    _safe_init_pair(5, curses.COLOR_BLUE, default_bg)  # npc / ceiling
    _safe_init_pair(6, curses.COLOR_WHITE, default_bg)  # visible / floor
    _safe_init_pair(7, curses.COLOR_WHITE, default_bg)  # explored dim / far wall
    _safe_init_pair(8, curses.COLOR_RED, default_bg)
    _safe_init_pair(9, curses.COLOR_BLACK, curses.COLOR_WHITE)
    return True


def _default_view() -> str:
    pref = os.environ.get("SNOWCRASH_TUI_VIEW", "").strip().lower()
    if pref in (_VIEW_FPV, _VIEW_MAP):
        return pref
    return _VIEW_FPV


def _wait_for_size(stdscr: "curses._CursesWindow") -> None:
    """Block until terminal is at least _MIN_COLS x _MIN_ROWS."""
    while True:
        max_y, max_x = stdscr.getmaxyx()
        if max_x >= _MIN_COLS and max_y >= _MIN_ROWS:
            return
        stdscr.erase()
        msg = f"Terminal too small ({max_x}x{max_y}). Resize to at least {_MIN_COLS}x{_MIN_ROWS}."
        try:
            y = max(0, max_y // 2)
            x = max(0, (max_x - len(msg)) // 2) if max_x > 0 else 0
            stdscr.addnstr(y, x, msg, max(0, max_x - 1))
        except curses.error:
            pass
        stdscr.refresh()
        ch = stdscr.getch()
        if ch in (ord("q"), 27):  # allow quit while waiting
            raise SystemExit(0)


def run_curses(seed: Optional[int] = None, no_color: bool = False) -> int:
    if not sys.stdin.isatty():
        print(
            "error: snowcrash TUI needs an interactive TTY "
            "(SSH session or local terminal). stdin is not a TTY.",
            file=sys.stderr,
        )
        return 1

    def _wrapped(stdscr: "curses._CursesWindow") -> int:
        return _game_loop(stdscr, seed, no_color=no_color)

    return curses.wrapper(_wrapped)


def _game_loop(
    stdscr: "curses._CursesWindow",
    seed: Optional[int],
    no_color: bool = False,
) -> int:
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)
    colors_ok = _init_colors(no_color=no_color)

    _wait_for_size(stdscr)

    gs = new_game(seed)
    view = _default_view()

    while True:
        max_y, max_x = stdscr.getmaxyx()
        if max_x < _MIN_COLS or max_y < _MIN_ROWS:
            _wait_for_size(stdscr)
            continue

        _draw(stdscr, gs, colors_ok=colors_ok, view=view)
        ch = stdscr.getch()
        if ch == curses.KEY_RESIZE:
            continue
        # Local TUI-only: toggle FPV ↔ overhead (does not consume a game turn).
        if ch in (ord("v"), ord("V")) and gs.mode == "play":
            view = _VIEW_MAP if view == _VIEW_FPV else _VIEW_FPV
            continue
        action = _key_to_action(ch, gs.mode)
        if action is None:
            continue
        result = handle_action(gs, action)
        if result.get("quit"):
            break
    return 0


def _key_to_action(ch: int, mode: str = "play") -> Optional[str]:
    """Map keypress → engine action.

    Play mode uses relative WASD + arrow turn/step so FPV updates with facing.
    ``q`` still quits in the TUI (web uses ``q`` for turn_left — use ``,`` / Left).
    """
    if ch == curses.KEY_RESIZE:
        return None
    if mode in ("help", "inventory"):
        if ch == curses.KEY_UP:
            return "k"
        if ch == curses.KEY_DOWN:
            return "j"
        if ch == 27:
            return "escape"
        if ch in (10, 13):
            return "enter"
        try:
            return chr(ch)
        except ValueError:
            return None

    # Play / dead / won — relative movement for FPV
    if ch == curses.KEY_UP:
        return "forward"
    if ch == curses.KEY_DOWN:
        return "back"
    if ch == curses.KEY_LEFT:
        return "turn_left"
    if ch == curses.KEY_RIGHT:
        return "turn_right"
    if ch == 27:  # ESC
        return "escape"
    if ch in (10, 13):
        return "enter"

    try:
        c = chr(ch)
    except ValueError:
        return None

    # Relative WASD (case-insensitive for movement)
    low = c.lower()
    if low == "w":
        return "forward"
    if low == "s":
        return "back"
    if low == "a":
        return "strafe_left"
    if low == "d":
        return "strafe_right"
    if low == "e":
        return "turn_right"
    if c == ",":
        return "turn_left"
    # Pass through letters (q quit, g get, f fire, i inv, ? help, hjkl abs, …)
    return c


def _status_budget(max_y: int) -> int:
    """Rows reserved for status + messages at the bottom."""
    return min(8, max(5, max_y // 4))


def _objective_hint(snap: dict) -> str:
    p = snap.get("player") or {}
    journal = snap.get("journal") or {}
    step = int(journal.get("step", 0) or 0)
    if snap.get("won"):
        return "Payload cleared"
    if p.get("has_payload"):
        return "Deliver to uplink U"
    if step >= 2:
        return "Recover Payload-Zero"
    if snap.get("quest_flags", {}).get("briefing"):
        return "Find jackpoint J"
    return "Talk to Relay Tran"


def _draw(
    stdscr: "curses._CursesWindow",
    gs: GameState,
    colors_ok: bool = True,
    view: str = _VIEW_FPV,
) -> None:
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    snap = snapshot(gs)

    if gs.mode == "help":
        _draw_help(stdscr, snap)
        stdscr.refresh()
        return

    if gs.mode == "inventory":
        _draw_inventory(stdscr, snap)
        stdscr.refresh()
        return

    budget = _status_budget(max_y)
    view_h = max(4, max_y - budget)

    if view == _VIEW_FPV:
        _draw_fpv(stdscr, gs, view_h, max_x, colors_ok=colors_ok)
    else:
        _draw_overhead(stdscr, gs, snap, view_h, max_x, colors_ok=colors_ok)

    # Status panel (always visible)
    p = snap["player"]
    status_y = view_h
    facing = p.get("facing", gs.player.facing) % 4
    view_tag = "FPV" if view == _VIEW_FPV else "MAP"
    line1 = (
        f"{p['name']}  HP {p['hp']}/{p['max_hp']}  Focus {p['focus']}/{p['max_focus']}  "
        f"{compass_line(facing)}  [{view_tag}]  Turn {snap['turn']}"
    )
    line2 = (
        f"Payload: {'YES' if p['has_payload'] else 'no'}  "
        f"Obj: {_objective_hint(snap)}  "
        f"[v view] [? help] [i inv] [g get] [f fire] [q quit]"
    )
    for i, line in enumerate((line1, line2)):
        if status_y + i < max_y:
            try:
                stdscr.addnstr(status_y + i, 0, line, max_x - 1, curses.A_BOLD)
            except curses.error:
                pass

    # Messages
    msgs = snap["messages"]
    msg_y = status_y + 2
    for i, m in enumerate(msgs[-(max_y - msg_y - 1) :]):
        if msg_y + i >= max_y:
            break
        try:
            stdscr.addnstr(msg_y + i, 0, m, max_x - 1)
        except curses.error:
            pass

    if gs.mode == "dead":
        _banner(stdscr, max_y, max_x, "YOU DIED — press r to restart, q to quit", 8, colors_ok)
    elif gs.mode == "won":
        _banner(stdscr, max_y, max_x, "YOU WIN — Payload cleared. r restart, q quit", 2, colors_ok)

    stdscr.refresh()


def _draw_fpv(
    stdscr: "curses._CursesWindow",
    gs: GameState,
    view_h: int,
    max_x: int,
    colors_ok: bool = True,
) -> None:
    cols = max(8, max_x - 1)
    rows, attrs = render_fpv(gs, cols, view_h)
    for y, row in enumerate(rows):
        if y >= view_h:
            break
        for x, ch in enumerate(row):
            if x >= max_x - 1:
                break
            attr = curses.A_NORMAL
            if colors_ok:
                pair = attrs[y][x] if y < len(attrs) and x < len(attrs[y]) else 0
                if pair:
                    attr = _safe_color_pair(pair)
                    if pair in (1, 8):
                        attr |= curses.A_BOLD
            try:
                stdscr.addch(y, x, ch, attr)
            except curses.error:
                pass


def _draw_overhead(
    stdscr: "curses._CursesWindow",
    gs: GameState,
    snap: dict,
    view_h: int,
    max_x: int,
    colors_ok: bool = True,
) -> None:
    """Draw a camera-centered overhead ASCII map (not world origin)."""
    rows = snap["map"]
    cam_w = max(8, max_x - 1)
    cam_h = max(4, view_h)
    px, py = gs.player.x, gs.player.y
    origin_x = max(0, min(gs.gmap.width - cam_w, px - cam_w // 2))
    origin_y = max(0, min(gs.gmap.height - cam_h, py - cam_h // 2))
    facing = gs.player.facing % 4
    player_glyph = compass_line(facing)[0]  # ^>v<

    for vy in range(cam_h):
        my = origin_y + vy
        if my < 0 or my >= len(rows):
            continue
        row = rows[my]
        for vx in range(cam_w):
            mx = origin_x + vx
            if mx < 0 or mx >= len(row):
                continue
            ch = row[mx]
            if mx == px and my == py:
                ch = player_glyph
            attr = curses.A_NORMAL
            if colors_ok:
                if not gs.gmap.visible[my][mx] and gs.gmap.explored[my][mx]:
                    attr = _safe_color_pair(6) | curses.A_DIM
                elif mx == px and my == py:
                    attr = _safe_color_pair(1) | curses.A_BOLD
                elif ch == "i":
                    attr = _safe_color_pair(2)
                elif ch == "t":
                    attr = _safe_color_pair(3)
                elif ch == "d":
                    attr = _safe_color_pair(4)
                elif ch == "&":
                    attr = _safe_color_pair(5) | curses.A_BOLD
                elif ch in ("*", "!", "/", "[", "}", "%"):
                    attr = _safe_color_pair(3) | curses.A_BOLD
                elif ch == "J":
                    attr = _safe_color_pair(1) | curses.A_BOLD
                elif ch == "U":
                    attr = _safe_color_pair(4) | curses.A_BOLD
                else:
                    attr = _safe_color_pair(6)
            try:
                stdscr.addch(vy, vx, ch, attr)
            except curses.error:
                pass


def _banner(stdscr, max_y, max_x, text, color_pair, colors_ok: bool = True):
    y = max_y // 2
    x = max(0, (max_x - len(text)) // 2)
    attr = curses.A_BOLD
    if colors_ok:
        attr |= _safe_color_pair(color_pair)
    try:
        stdscr.addnstr(y, x, text, max_x - 1, attr)
    except curses.error:
        pass


def _draw_help(stdscr, snap) -> None:
    stdscr.erase()
    for i, line in enumerate(snap["help"].splitlines()):
        try:
            stdscr.addstr(i + 1, 2, line)
        except curses.error:
            pass
    try:
        stdscr.addstr(0, 2, "HELP — any key to return", curses.A_BOLD)
    except curses.error:
        pass


def _draw_inventory(stdscr, snap) -> None:
    stdscr.erase()
    try:
        stdscr.addstr(0, 2, "INVENTORY — # select, e equip, u use, d drop, Esc back", curses.A_BOLD)
    except curses.error:
        pass
    inv = snap["inventory"]
    sel = snap["selected_inv"]
    if not inv:
        try:
            stdscr.addstr(2, 4, "(empty)")
        except curses.error:
            pass
    for i, it in enumerate(inv):
        mark = ">" if i == sel else " "
        eq = " [E]" if it["equipped"] else ""
        line = f"{mark} {i}: {it['glyph']} {it['name']} ({it['kind']}){eq}"
        attr = curses.A_REVERSE if i == sel else curses.A_NORMAL
        try:
            stdscr.addstr(2 + i, 2, line, attr)
        except curses.error:
            pass
        if i == sel:
            try:
                stdscr.addstr(3 + len(inv), 4, it["description"][:70])
            except curses.error:
                pass
