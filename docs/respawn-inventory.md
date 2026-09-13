# Respawn & inventory UX (#99 / #100)

## Respawn (same name)
After **death** or **win**, press **`r`** (or a respawn option button) to revive **in the current session**.

- Same courier name works — the live WebSocket session is reused.
- Reconnecting / skipping the intro after a terminal state also clears the stale dead/won slot and returns you to play under the same name.
- Replay intro (`Replay intro`) is optional flavor only; it is not required to respawn.

## Inventory
- **Click** an inventory row to **select** it (opens inventory mode). Consumables are **not** used on single click.
- **Double-click** or press **`u`** / **Enter** (while in inventory) to use the selection.
- Indices **10+**: type multi-digit (`1` then `0`), press letter keys (`a` = 10, `b` = 11, …), or move the selection with **arrows / WASD**.

Parent campaign: #42.
