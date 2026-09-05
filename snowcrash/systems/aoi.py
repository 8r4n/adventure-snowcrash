"""Area-of-interest / interest management for snapshot broadcasts (#18)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from ..mmorpg import GameWorld, PlayerAgent

# Manhattan AOI radius for "nearby" interest (entities already FOV-culled)
AOI_RADIUS = 28
# Always include party / crew members regardless of distance
SOCIAL_ALWAYS = True


def interested_player_ids(
    world: "GameWorld",
    actor_id: str,
    *,
    radius: int = AOI_RADIUS,
    force_all: bool = False,
) -> Set[str]:
    """Return player ids that should receive a broadcast after actor_id acts.

    Reduces O(n²) full-fanout: action snapshots go to self + nearby + social.
    Tick broadcasts may still use full set when force_all=True (or small worlds).
    """
    if force_all or len(world.players) <= 8:
        return {pid for pid, p in world.players.items() if p.connected}

    agent = world.players.get(actor_id)
    if not agent or not agent.connected:
        return {pid for pid, p in world.players.items() if p.connected}

    out: Set[str] = {actor_id}
    ax, ay = agent.actor.x, agent.actor.y
    az = int(getattr(agent.actor, "z", 0) or 0)
    party_id = getattr(agent, "party_id", None)
    crew_id = getattr(agent, "crew_id", None)

    for pid, other in world.players.items():
        if not other.connected or pid == actor_id:
            continue
        if SOCIAL_ALWAYS:
            if party_id and getattr(other, "party_id", None) == party_id:
                out.add(pid)
                continue
            if crew_id and getattr(other, "crew_id", None) == crew_id:
                out.add(pid)
                continue
        oz = int(getattr(other.actor, "z", 0) or 0)
        if oz != az:
            continue
        if other.actor.x < 0:
            continue
        if abs(other.actor.x - ax) + abs(other.actor.y - ay) <= radius:
            out.add(pid)
    return out


def aoi_docs() -> str:
    return (
        "Interest management (#18): WebSocket action broadcasts use "
        "interested_player_ids() (self + Manhattan AOI=%d + party/crew). "
        "Entity lists in snapshot remain FOV-culled. Tick loop uses AOI when "
        "online_count > 8; else full fanout. See docs/staging.md."
    ) % AOI_RADIUS
