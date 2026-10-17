from __future__ import annotations

import mujoco

from services.simulator import FacilityWorld


def test_scout_observes_box_only_when_return_is_within_range_and_not_occluded():
    world = FacilityWorld(seed=1, scenario="SC-001")
    try:
        # This test-only fixture setup places the known box within the scout sensor cone.
        adr = world._qpos_adr
        world.data.qpos[adr : adr + 3] = [-1.0, 0.0, 0.18]
        mujoco.mj_forward(world.model, world.data)
        sample = world.inspect("scout")
        assert sample["obstruction"]["state"] == "observed"
        assert sample["obstruction"]["observed_pose"]["x"] == -1.0
    finally:
        world.close()


def test_s0_returns_bounded_features_and_unknown_when_occluded():
    world = FacilityWorld(seed=0, scenario="SC-004")
    try:
        sample = world.inspect("scout")
        assert sample["sensor"]["mode"] == "S0"
        assert sample["sensor"]["max_range_m"] == 4.0
        assert sample["world_tick"] == world.world_tick
        assert sample["obstruction"]["state"] == "unknown"
        assert sample["obstruction"]["reason"] == "occluded"
        assert sample["visibility"]["fraction"] < 0.5
        assert max(sample["ranges_m"]) <= 4.0
        assert "obstruction_truth" not in sample
        assert "obstruction_truth" not in world.operator_projection()
    finally:
        world.close()


def test_sensor_config_hash_is_stable_and_observations_expire():
    world = FacilityWorld(seed=0)
    try:
        first = world.inspect("scout")
        second = world.inspect("scout")
        assert first["sensor"]["config_hash"] == second["sensor"]["config_hash"]
        assert first["sensor"]["expires_tick"] == first["world_tick"] + 50
    finally:
        world.close()
