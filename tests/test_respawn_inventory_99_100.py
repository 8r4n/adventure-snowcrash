"""Regression tests for #99 (same-name respawn) and #100 (inventory select)."""

from snowcrash.items import make_stimpack, make_mono_knife
from snowcrash.mmorpg import GameWorld


def _kill(agent):
    agent.actor.hp = 0
    agent.actor.alive = False
    agent.lost = True
    agent.mode = "dead"
    agent.dead = True


def test_same_name_rejoin_after_death_respawns():
    w = GameWorld(99)
    a = w.join("Hiro")
    pid = a.id
    _kill(a)
    w._year_on_player_death(a, killer_name="Test")
    assert a.mode == "dead" and a.dead

    # Simulate disconnect then same-name rejoin (skip-intro / re-connect path)
    w.leave(pid)
    b = w.join("Hiro")
    assert b.id == pid
    assert b.actor.alive
    assert not b.dead
    assert b.mode == "play"
    assert not b.lost


def test_same_id_rejoin_after_win_respawns():
    w = GameWorld(100)
    a = w.join("YoursTruly")
    a.won = True
    a.mode = "won"
    b = w.join("YoursTruly", reconnect_id=a.id)
    assert b.id == a.id
    assert b.mode == "play"
    assert not b.won
    assert b.actor.alive


def test_explicit_r_respawns_without_new_name():
    w = GameWorld(101)
    a = w.join("Courier")
    _kill(a)
    w._year_on_player_death(a, killer_name="Thug")
    a.last_action_ts = 0
    w.handle_action(a, "r")
    assert a.actor.alive and a.mode == "play" and not a.dead


def test_inv_select_does_not_consume():
    w = GameWorld(102)
    a = w.join("Packrat")
    # Ensure stimpack at a known index
    a.actor.inventory = [make_stimpack(), make_mono_knife()]
    a.actor.inventory[1].equipped = True
    before_hp = a.actor.hp
    before_len = len(a.actor.inventory)
    a.last_action_ts = 0
    w.handle_action(a, "inv_select", "0")
    assert a.mode == "inventory"
    assert a.selected_inv == 0
    assert len(a.actor.inventory) == before_len
    assert a.actor.hp == before_hp  # stim not used


def test_inventory_multi_digit_and_arrows():
    w = GameWorld(103)
    a = w.join("DeepPockets")
    # Pad inventory past index 9
    a.actor.inventory = [make_stimpack() for _ in range(12)]
    a.mode = "inventory"
    a.selected_inv = 0
    a.last_action_ts = 0
    w.handle_action(a, "inv_select", "10")
    assert a.selected_inv == 10
    a.last_action_ts = 0
    w.handle_action(a, "s")  # move selection down
    assert a.selected_inv == 11
    a.last_action_ts = 0
    w.handle_action(a, "w")
    assert a.selected_inv == 10


def test_use_requires_explicit_u_after_select():
    w = GameWorld(104)
    a = w.join("Careful")
    a.actor.inventory = [make_stimpack()]
    a.actor.hp = 5
    a.actor.max_hp = 20
    a.last_action_ts = 0
    w.handle_action(a, "inv_select", "0")
    assert a.actor.hp == 5
    a.last_action_ts = 0
    w.handle_action(a, "u")
    assert a.actor.hp > 5
