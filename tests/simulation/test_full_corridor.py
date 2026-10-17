from services.simulator import FacilityWorld


def test_post_recovery_clearance_is_ray_verified_not_missing_obstacle_guess():
    with FacilityWorld(seed=3) as world:
        world.start_skill('recovery', 'recover', {'timeout_ticks': 2000})
        for _ in range(2000):
            world.step()
            if world.skill_status('recovery')['status'] == 'done':
                break
        sample = world.inspect('scout')
        assert sample['obstruction']['state'] == 'absent', sample
        assert sample['gap']['fits']['courier'] is True
        assert sample['gap']['width_m'][0] >= .55
        assert sample['gap']['scope'] == 'corridor-c-gate-ray-coverage'


def test_restore_then_physical_crossing_delivers_payload_on_east_side():
    with FacilityWorld(seed=3, episode_id='crossing') as world:
        world.start_skill('recovery', 'recover', {'timeout_ticks': 2000})
        for _ in range(2000):
            world.step()
            if world.skill_status('recovery')['status'] == 'done':
                break
        world.start_skill('scout', 'travel', {'target_x': -4.0, 'target_y': -.55, 'timeout_ticks': 2000})
        for _ in range(2000):
            world.step()
            if world.skill_status('scout')['status'] == 'done':
                break
        assert world.skill_status('scout')['status'] == 'done'
        world.start_skill('scout', 'travel', {'target_x': -6.7, 'target_y': -.55, 'timeout_ticks': 2000})
        for _ in range(2000):
            world.step()
            if world.skill_status('scout')['status'] == 'done':
                break
        assert world.skill_status('scout')['status'] == 'done'
        assert world.load_payload('courier', 'parcel')['status'] == 'loaded'
        assert world.start_skill('courier', 'deliver', {'target_x': 4, 'target_y': 0, 'timeout_ticks': 2000})['status'] == 'accepted'
        saved = world.checkpoint()
    with FacilityWorld(seed=3, episode_id='crossing') as continuation:
        continuation.restore(saved)
        result = continuation.skill_status('courier')
        for _ in range(2000):
            continuation.step()
            result = continuation.skill_status('courier')
            if result['status'] in {'done', 'failed', 'timed_out'}:
                break
        assert result['status'] == 'done', result
        assert continuation.poses()['courier']['x'] > 3.8
        assert result['result']['postcondition']['payload_in_delivery_zone'] is True
        assert result['result']['postcondition']['zone_center'][0] == 4.0
