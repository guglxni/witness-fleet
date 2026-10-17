"""Native travel and delivery complete only after physically settled arrival."""

import math

from services.simulator import FacilityWorld

ARRIVAL_TOLERANCE_M = 0.035


def _finish(world, robot, budget=2000):
    for _ in range(budget):
        world.step()
        result = world.skill_status(robot)
        if result["status"] in {"done", "failed", "timed_out"}:
            return result
    return world.skill_status(robot)


def _assert_stable_arrival(world, robot, target, *, extra_ticks=500):
    result = world.skill_status(robot)
    pose = world.poses()[robot]
    distance = math.hypot(pose["x"] - target[0], pose["y"] - target[1])
    qvel_adr = world._robot_joint_adr[robot][:2]
    speed = math.hypot(*(float(world.data.qvel[adr]) for adr in qvel_adr))
    assert result["status"] == "done", result
    assert distance < ARRIVAL_TOLERANCE_M, (distance, pose)
    assert speed <= 0.01, (speed, pose)

    max_distance = distance
    for _ in range(extra_ticks):
        world.step()
        pose = world.poses()[robot]
        distance = math.hypot(pose["x"] - target[0], pose["y"] - target[1])
        max_distance = max(max_distance, distance)
    speed = math.hypot(*(float(world.data.qvel[adr]) for adr in qvel_adr))
    assert max_distance < ARRIVAL_TOLERANCE_M, (max_distance, pose)
    assert speed <= 0.02, (speed, pose)


def test_travel_done_waits_for_low_speed_and_stays_within_arrival_tolerance():
    target = (-3.5, -0.55)
    with FacilityWorld(seed=3, scenario="SC-001") as world:
        accepted = world.start_skill("scout", "travel", {
            "target_x": target[0], "target_y": target[1], "timeout_ticks": 2000,
        })
        assert accepted["status"] == "accepted"
        result = _finish(world, "scout")
        assert result["status"] == "done", result
        _assert_stable_arrival(world, "scout", target)


def test_delivery_done_waits_for_low_speed_and_stays_within_arrival_tolerance():
    target = (4.0, 0.0)
    with FacilityWorld(seed=3, scenario="SC-001") as world:
        assert world.start_skill("recovery", "recover", {
            "target_displacement_m": 0.75, "timeout_ticks": 2000,
        })["status"] == "accepted"
        assert _finish(world, "recovery")["status"] == "done"

        for x in (-4.0, -6.7):
            accepted = world.start_skill("scout", "travel", {
                "target_x": x, "target_y": -0.55, "timeout_ticks": 2000,
            })
            assert accepted["status"] == "accepted"
            assert _finish(world, "scout")["status"] == "done"

        assert world.load_payload("courier", "terminal-stability-payload")["status"] == "loaded"
        accepted = world.start_skill("courier", "deliver", {
            "target_x": target[0], "target_y": target[1], "timeout_ticks": 2000,
        })
        assert accepted["status"] == "accepted"
        result = _finish(world, "courier")
        assert result["status"] == "done", result
        assert result["result"]["postcondition"]["payload_in_delivery_zone"] is True
        _assert_stable_arrival(world, "courier", target)
