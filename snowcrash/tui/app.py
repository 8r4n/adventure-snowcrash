"""Curses frontend for Snowcrash."""

from __future__ import annotations

import curses
from typing import Optional

from .. import constants as C
from ..engine import GameState, handle_action, new_game, snapshot


def run_curses(seed: Optional[int] = None) -> int:
    def _wrapped(stdscr: "curses._CursesWindow") -> int:
        return _game_loop(stdscr, seed)

    return curses.wrapper(_wrapped)


def _game_loop(stdscr: "curses._CursesWindow", seed: Optional[int]) -> int:
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)  # player
        curses.init_pair(2, curses.COLOR_GREEN, -1)  # infected
        curses.init_pair(3, curses.COLOR_YELLOW, -1)  # thug
        curses.init_pair(4, curses.COLOR_MAGENTA, -1)  # drone
        curses.init_pair(5, curses.COLOR_BLUE, -1)  # npc
        curses.init_pair(6, curses.COLOR_WHITE, -1)  # visible
        curses.init_pair(7, curses.COLOR_BLACK, -1)  # explored dim — may fail
        try:
            curses.init_pair(7, curses.COLOR_WHITE, -1)
        except curses.error:
            pass
        curses.init_pair(8, curses.COLOR_RED, -1)
        curses.init_pair(9, curses.COLOR_BLACK, curses.COLOR_WHITE)

    gs = new_game(seed)

    while True:
        _draw(stdscr, gs)
        ch = stdscr.getch()
        action = _key_to_action(ch)
        if action is None:
            continue
        result = handle_action(gs, action)
        if result.get("quit"):
            break
    return 0


def _key_to_action(ch: int) -> Optional[str]:
    if ch == curses.KEY_UP:
        return "up"
    if ch == curses.KEY_DOWN:
        return "down"
    if ch == curses.KEY_LEFT:
        return "left"
    if ch == curses.KEY_RIGHT:
        return "right"
    if ch == 27:  # ESC
        return "escape"
    if ch in (10, 13):
        return "enter"
    try:
        return chr(ch)
    except ValueError:
        return None


def _draw(stdscr: "curses._CursesWindow", gs: GameState) -> None:
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

    # Map
    rows = snap["map"]
    for y, row in enumerate(rows):
        if y >= max_y - 8:
            break
        for x, ch in enumerate(row):
            if x >= max_x - 1:
                break
            attr = curses.A_NORMAL
            if curses.has_colors():
                if not gs.gmap.visible[y][x] and gs.gmap.explored[y][x]:
                    attr = curses.color_pair(6) | curses.A_DIM
                elif ch == "@":
                    attr = curses.color_pair(1) | curses.A_BOLD
                elif ch == "i":
                    attr = curses.color_pair(2)
                elif ch == "t":
                    attr = curses.color_pair(3)
                elif ch == "d":
                    attr = curses.color_pair(4)
                elif ch == "&":
                    attr = curses.color_pair(5) | curses.A_BOLD
                elif ch in ("*", "!", "/", "[", "}", "%"):
                    attr = curses.color_pair(3) | curses.A_BOLD
                else:
                    attr = curses.color_pair(6)
            try:
                stdscr.addch(y, x, ch, attr)
            except curses.error:
                pass

    # Status panel
    p = snap["player"]
    status_y = min(len(rows), max_y - 8)
    line1 = (
        f"{p['name']}  HP {p['hp']}/{p['max_hp']}  Focus {p['focus']}/{p['max_focus']}  "
        f"Atk {p['attack']} Def {p['defense']} Hack {p['hack']}  Turn {snap['turn']}"
    )
    line2 = f"Seed {snap['seed']}  Payload: {'YES' if p['has_payload'] else 'no'}  [? help] [i inv] [g get] [f fire/hack] [q quit]"
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
        _banner(stdscr, max_y, max_x, "YOU DIED — press r to restart, q to quit", 8)
    elif gs.mode == "won":
        _banner(stdscr, max_y, max_x, "YOU WIN — Payload cleared. r restart, q quit", 2)

    stdscr.refresh()


def _banner(stdscr, max_y, max_x, text, color_pair):
    y = max_y // 2
    x = max(0, (max_x - len(text)) // 2)
    attr = curses.A_BOLD
    if curses.has_colors():
        attr |= curses.color_pair(color_pair)
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
