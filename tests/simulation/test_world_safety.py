import pytest

from services.simulator import FacilityWorld


def test_restore_keeps_simulator_time_and_loaded_payload_identity():
    with FacilityWorld(seed=1, episode_id='same') as original:
        original.load_payload('courier', 'parcel')
        original.step(4)
        saved = original.checkpoint()
        expected_time = float(original.data.time)
    with FacilityWorld(seed=1, episode_id='same') as restored:
        restored.restore(saved)
        assert restored.data.time == expected_time
        assert restored.inspect('courier')['payload']['payload_id'] == 'parcel'


def test_checkpoint_for_different_episode_is_not_a_continuation():
    with FacilityWorld(seed=1, episode_id='first') as original:
        saved = original.checkpoint()
    with FacilityWorld(seed=1, episode_id='second') as restored:
        with pytest.raises(ValueError):
            restored.restore(saved)


@pytest.mark.parametrize('kind,robot', [('recover', 'courier'), ('deliver', 'recovery')])
def test_recovery_and_delivery_roles_cannot_be_swapped(kind, robot):
    with FacilityWorld() as world:
        result = world.start_skill(robot, kind)
        assert result['status'] == 'rejected'
        assert result['reason'] == 'capability_mismatch'


def test_timeout_neutralizes_pending_motion_before_next_physics_tick():
    with FacilityWorld() as world:
        world.start_skill('scout', 'travel', {'target_x': -3.9, 'target_y': -.35, 'timeout_ticks': 1})
        world.step(2)
        assert world.skill_status('scout')['status'] == 'timed_out'
        pose = world.poses()['scout']
        controls = world.data.ctrl[list(world._robot_actuator_ids['scout'])]
        assert abs(controls[0] - pose['x']) < .001


def test_boolean_tick_is_not_an_integer_step():
    with FacilityWorld() as world:
        with pytest.raises(ValueError):
            world.step(True)
