from snowcrash.mmorpg import GameWorld
from snowcrash.systems.aoi import interested_player_ids


def test_aoi_small_world_force_all():
    w = GameWorld(1)
    a = w.join("One")
    ids = interested_player_ids(w, a.id)
    assert a.id in ids
