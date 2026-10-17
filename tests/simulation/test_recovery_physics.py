from services.simulator import FacilityWorld


def test_recovery_physically_pushes_then_parks_outside_courier_path():
    world = FacilityWorld(seed=3, scenario="SC-001")
    try:
        initial = world.inspect("scout")["obstruction"]["observed_pose"]
        accepted = world.start_skill(
            "recovery", "recover", {"target_displacement_m": 0.75, "timeout_ticks": 1200}
        )
        assert accepted["status"] == "accepted"
        result = _run_skill(world, 1300)
        assert result["status"] == "done"
        moved = world._object_position()
        recovery = world.poses()["recovery"]
        assert moved[1] > initial["y"] + 0.75
        assert abs(moved[0] - initial["x"]) < 3.1
        assert result["contact_count"] > 0
        assert result["measured_displacement_m"] >= 0.75
        assert result["phase"] == "parked"
        assert recovery["y"] > 1.0
    finally:
        world.close()
def test_short_staging_move_is_not_successful_east_side_delivery():
    world = FacilityWorld(seed=4, scenario="SC-001")
    try:
        loaded = world.load_payload("courier", "parcel")
        assert loaded["status"] == "loaded"
        assert loaded["payload_id"] == "parcel"
        assert world.inspect("courier")["payload"]["state"] == "observed"
        accepted = world.start_skill(
            "courier", "deliver", {"target_x": -5.7, "target_y": 0.0, "timeout_ticks": 1200}
        )
        assert accepted["status"] == "accepted"
        for _ in range(1300):
            world.step()
            result = world.skill_status("courier")
            if result["status"] in {"done", "failed", "timed_out"}:
                break
        assert result["status"] == "failed"
        assert result['reason'] == 'payload_delivery_postcondition_failed'
        arrival = world.inspect("courier")["payload"]
        assert arrival["state"] == "observed"
        assert arrival["payload_id"] == "parcel"
        assert arrival["delivery_zone"] is False
    finally:
        world.close()


def test_heavy_box_recovery_is_a_physical_failure_not_scripted_success():
    world = FacilityWorld(seed=3, scenario="SC-002")
    try:
        initial = world.inspect("scout")["obstruction"]["observed_pose"]
        accepted = world.start_skill(
            "recovery", "recover", {"target_displacement_m": 0.75, "timeout_ticks": 300}
        )
        assert accepted["status"] == "accepted"
        result = _run_skill(world, 400)
        assert result["status"] == "failed"
        final = world.inspect("scout")["obstruction"]["observed_pose"]
        assert abs(final["x"] - initial["x"]) < 0.15
        assert abs(final["y"] - initial["y"]) < 0.15
        assert result["measured_displacement_m"] < 0.15
    finally:
        world.close()


def _run_skill(world, ticks):
    for _ in range(ticks):
        world.step()
        status = world.skill_status("recovery")
        if status["status"] in {"done", "failed", "held", "timed_out"}:
            return status
    return world.skill_status("recovery")
