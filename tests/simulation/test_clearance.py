from services.simulator import FacilityWorld


def test_default_carton_sensor_local_clearance_excludes_blocked_agent_corridor():
    world = FacilityWorld(seed=2, scenario="SC-003")
    try:
        sample = world.inspect("scout")
        gap = sample["gap"]
        assert sample["obstruction"]["state"] == "observed"
        assert gap["visibility"] == "visible"
        assert gap["width_m"][0] > 0.22
        assert gap["width_m"][1] < 0.38
        assert gap["fits"]["scout"] is True
        assert gap["fits"]["recovery"] is False
        assert gap["fits"]["courier"] is False
    finally:
        world.close()


def test_recovery_clearance_requires_one_contiguous_side_opening():
    world = FacilityWorld(seed=2, scenario="SC-001")
    try:
        sample = world.inspect("scout")
        gap = sample["gap"]
        assert gap["fits"]["scout"] is True
        assert gap["fits"]["recovery"] is True
        assert gap["fits"]["courier"] is False
    finally:
        world.close()
