"""Soft hardcore opt-in death tax (#49)."""

from __future__ import annotations

from snowcrash.items import make_mono_knife, make_payload_zero, make_stimpack
from snowcrash.mmorpg import GameWorld
from snowcrash.systems.signal_keys import make_signal_key
from snowcrash.systems.soft_hardcore import HARDCORE_CREDIT_LOSS_PCT, is_hardcore_protected


def _join(w: GameWorld, name: str = "RiskCourier", soft_hardcore: bool = False):
    a = w.join(name, soft_hardcore=soft_hardcore)
    a.last_action_ts = 0
    return a


def _force_death(w: GameWorld, agent, killer_name: str = "Street Thug"):
    agent.actor.alive = False
    agent.actor.hp = 0
    agent.lost = True
    agent.mode = "dead"
    agent.sfx("death")
    w._year_on_player_death(agent, killer_name=killer_name)


def test_default_off_and_snapshot_fields():
    w = GameWorld(490)
    a = _join(w)
    s = w.snapshot(a)
    assert "soft_hardcore" in s
    assert s["soft_hardcore"]["enabled"] is False
    assert s["soft_hardcore"]["debt"] == 0
    assert s["soft_hardcore"]["last_penalty"] is None
    assert abs(s["soft_hardcore"]["credit_loss_pct"] - HARDCORE_CREDIT_LOSS_PCT) < 1e-9
    # Casual death: no credit burn
    a.credits = 100
    before_inv = len(a.actor.inventory)
    _force_death(w, a)
    assert a.credits == 100
    assert len(a.actor.inventory) == before_inv
    assert a.soft_hardcore["last_penalty"] is None or not a.soft_hardcore["last_penalty"].get("applied")
    s2 = w.snapshot(a)
    assert s2["dead"] is True
    assert s2["death_cause"]
    assert "Soft hardcore tax" not in (s2["death_cause"] or "")


def test_opt_in_action_and_join_flag():
    w = GameWorld(491)
    a = _join(w, "Toggle")
    assert w.handle_year_action(a, "hardcore_on", "")
    assert a.soft_hardcore["enabled"] is True
    assert w.handle_year_action(a, "hardcore", "off")
    assert a.soft_hardcore["enabled"] is False
    assert w.handle_year_action(a, "hardcore_status", "")
    b = _join(w, "JoinedHot", soft_hardcore=True)
    assert b.soft_hardcore["enabled"] is True
    s = w.snapshot(b)
    assert s["soft_hardcore"]["enabled"] is True


def test_death_burns_credits_and_drops_item_keeps_levels():
    w = GameWorld(492)
    a = _join(w, "Burner", soft_hardcore=True)
    a.credits = 100
    a.level = 4
    a.xp = 17
    # Ensure a droppable stim exists (join already gives stim + knife)
    if not any(i.id == "stimpack" for i in a.actor.inventory):
        a.actor.inventory.append(make_stimpack())
    inv_before = [i.id for i in a.actor.inventory]
    floor_before = len(w.floor_items)
    _force_death(w, a, killer_name="Infected Avatar")
    assert a.credits == 80  # 20% of 100
    assert a.level == 4
    assert a.xp == 17
    pen = a.soft_hardcore["last_penalty"]
    assert pen and pen["applied"]
    assert pen["credits_lost"] == 20
    assert pen["level_kept"] == 4
    assert pen["item_dropped"]
    assert len(a.actor.inventory) == len(inv_before) - 1
    assert len(w.floor_items) == floor_before + 1
    s = w.snapshot(a)
    assert "Soft hardcore" in (s["death_cause"] or "") or "credits" in (s["death_cause"] or "").lower()
    assert s["soft_hardcore"]["last_penalty"]["credits_lost"] == 20
    # Logs mention the tax
    assert any("Soft hardcore tax" in m for m in a.messages)


def test_quest_and_signal_keys_protected():
    w = GameWorld(493)
    a = _join(w, "CourierSafe", soft_hardcore=True)
    # Strip droppables so only protected remain
    a.actor.inventory = [
        make_payload_zero(),
        make_signal_key("signal_key_burbclave"),
    ]
    assert all(is_hardcore_protected(i) for i in a.actor.inventory)
    a.credits = 50
    floor_before = len(w.floor_items)
    _force_death(w, a)
    assert a.credits == 40  # 20% of 50
    assert len(a.actor.inventory) == 2
    assert any(i.id == "payload_zero" for i in a.actor.inventory)
    assert any(i.id == "signal_key_burbclave" for i in a.actor.inventory)
    assert len(w.floor_items) == floor_before
    pen = a.soft_hardcore["last_penalty"]
    assert pen["item_dropped"] is None
    assert "no droppable" in pen["summary"]


def test_empty_wallet_banks_debt_and_pay_clears():
    w = GameWorld(494)
    a = _join(w, "Broke", soft_hardcore=True)
    a.credits = 0
    a.actor.inventory = [make_payload_zero()]  # protected only
    _force_death(w, a)
    assert a.soft_hardcore["debt"] == 5
    a.credits = 10
    assert w.handle_year_action(a, "pay_hardcore_debt", "")
    assert a.soft_hardcore["debt"] == 0
    assert a.credits == 5


def test_year_snapshot_still_has_core_fields():
    w = GameWorld(495)
    a = _join(w)
    s = w.snapshot(a)
    for key in (
        "skills",
        "journal",
        "signal_keys",
        "neon_dash",
        "heat",
        "corp_patrol",
        "ice",
        "cyberspace",
        "soft_hardcore",
        "dead",
        "respawn_options",
    ):
        assert key in s
