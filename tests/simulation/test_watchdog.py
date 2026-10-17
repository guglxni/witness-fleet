import pytest

from services.simulator import FacilityWorld


def test_watchdog_holds_motion_and_rejects_new_motion_after_deadline():
    world = FacilityWorld(seed=0, scenario="SC-001")
    try:
        started = world.start_skill("scout", "travel", {"target_x": -1.0, "target_y": -1.0})
        assert started["status"] == "accepted"
        world.step(5)
        before = world.poses()["scout"]
        held = world.heartbeat(now_s=10.0, allowed=False)
        assert held["status"] == "held"
        world.step(20)
        after = world.poses()["scout"]
        assert abs(after["x"] - before["x"]) <= 0.01
        assert abs(after["y"] - before["y"]) <= 0.01
        assert abs(after["yaw"] - before["yaw"]) <= 0.01
        rejected = world.start_skill("courier", "travel", {"target_x": 2.0, "target_y": 0.0})
        assert rejected["status"] == "rejected"
    finally:
        world.close()


def test_travel_controller_respects_bounded_timeout():
    world = FacilityWorld(seed=0, scenario="SC-001")
    try:
        with pytest.raises(ValueError, match="outside bounds"):
            world.start_skill(
                "courier", "travel", {"target_x": 8.0, "target_y": 0.0, "timeout_ticks": 3}
            )
        started = world.start_skill(
            "courier", "travel", {"target_x": 6.5, "target_y": 0.0, "timeout_ticks": 3}
        )
        assert started["status"] == "accepted"
        world.step(5)
        assert world.skill_status("courier")["status"] == "timed_out"
    finally:
        world.close()
