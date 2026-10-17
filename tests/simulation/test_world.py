import numpy as np

from services.simulator import FacilityWorld


def test_one_mujoco_clock_advances_all_named_robots_and_checkpoint_replays():
    world = FacilityWorld(seed=7, scenario="SC-001", episode_id="episode-a")
    try:
        poses_before = world.poses()
        assert set(poses_before) == {"scout", "recovery", "courier"}
        tick_before = world.world_tick

        world.step(3)
        assert world.world_tick == tick_before + 3
        assert world.model.opt.timestep == 0.01

        checkpoint = world.checkpoint()
        world.step(2)
        first_future = world.poses()
        world.restore(checkpoint)
        world.step(2)
        replay_future = world.poses()
        for robot_id in first_future:
            assert np.allclose(
                [first_future[robot_id][key] for key in ("x", "y", "z", "yaw")],
                [replay_future[robot_id][key] for key in ("x", "y", "z", "yaw")],
            )
        assert world.world_tick == checkpoint["world_tick"] + 2
    finally:
        world.close()


def test_same_seed_and_scenario_have_identical_initial_poses():
    left = FacilityWorld(seed=11, scenario="SC-001")
    right = FacilityWorld(seed=11, scenario="SC-001")
    try:
        assert left.poses() == right.poses()
    finally:
        left.close()
        right.close()
