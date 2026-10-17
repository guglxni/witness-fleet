"""Native shoulder staging: physical-only evidence, not graph authorization."""

from services.simulator import FacilityWorld


def _finish(world, robot, budget):
    for _ in range(budget):
        world.step()
        result = world.skill_status(robot)
        if result["status"] in {"done", "failed", "rejected"}:
            return result
    return world.skill_status(robot)


def test_current_courier_fit_and_safe_shoulder_staging_use_real_physics():
    with FacilityWorld(seed=3, scenario="SC-001") as world:
        world.start_skill("recovery", "recover", {
            "target_displacement_m": 0.75, "timeout_ticks": 2000,
        })
        recovered = _finish(world, "recovery", 2000)
        assert recovered["status"] == "done"
        assert recovered["contact_count"] > 0
        assert recovered["max_contact_force_n"] <= 120

        world.start_skill("scout", "travel", {
            "target_x": -3.5, "target_y": -0.55, "timeout_ticks": 2000,
        })
        assert _finish(world, "scout", 2000)["status"] == "done"
        sample = world.inspect("scout")
        assert sample["world_tick"] == world.world_tick
        assert sample["visibility"]["state"] == "visible"
        assert sample["gap"]["fits"]["courier"] is True
        assert world.world_tick < sample["sensor"]["expires_tick"]

        world.load_payload("courier", "shoulder-staging-payload")
        accepted = world.start_skill("courier", "deliver", {
            "target_x": 4.0, "target_y": 0.0, "timeout_ticks": 2000,
        })
        assert accepted["status"] == "accepted"
        assert world.world_tick == sample["world_tick"]  # Fresh at admission, not at completion.
        delivered = _finish(world, "courier", 2000)
        assert delivered["status"] == "done"
        assert delivered["reason"] is None
        assert delivered["result"]["postcondition"]["payload_in_delivery_zone"] is True
        assert world.poses()["courier"]["x"] > 3.8
