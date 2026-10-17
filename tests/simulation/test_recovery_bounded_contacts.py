"""Native fixture acceptance: not a script-derived success or relaxed drift tolerance."""
import numpy as np

from services.simulator import FacilityWorld


def test_removal_is_bounded_contact_and_lateral_drift_not_a_launched_carton():
    with FacilityWorld(seed=3) as world:
        world.start_skill('recovery', 'recover', {'timeout_ticks': 2000, 'target_displacement_m': .75})
        initial = world._object_position().copy()
        for _ in range(2000):
            world.step()
            if world.skill_status('recovery')['status'] in {'done', 'failed', 'timed_out'}:
                break
        result = world.skill_status('recovery')
        final = world._object_position()
        assert result['status'] == 'done', result
        assert result['contact_count'] > 0
        assert abs(final[0] - initial[0]) <= .15, final
        assert 1.0 <= final[1] <= 1.5, final
        assert result['max_contact_force_n'] <= 120, result
        assert np.linalg.norm(final[:2] - initial[:2]) <= 1.6
