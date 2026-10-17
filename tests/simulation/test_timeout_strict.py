from services.simulator import FacilityWorld


def test_boolean_timeout_cannot_start_any_skill():
    with FacilityWorld() as world:
        result = world.start_skill('scout', 'travel', {'timeout_ticks': True})
        assert result['status'] == 'rejected'
        assert world.skill_status('scout')['status'] == 'idle'
