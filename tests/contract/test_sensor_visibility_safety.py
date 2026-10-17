from datetime import UTC, datetime

from witness_fleet.simulation.observations import normalize_sensor_record


def test_low_visibility_is_unknown_even_if_producer_labels_visible():
    raw = {'robot_id': 'scout', 'world_tick': 10,
           'sensor': {'mode': 'S0', 'expires_tick': 60, 'config_hash': 'sensor-v1'},
           'pose': {'x': -2, 'y': 0, 'yaw': 0},
           'visibility': {'fraction': .1, 'state': 'visible'},
           'gap': {'visibility': 'visible', 'width_m': [1.0, 1.1],
                   'fits': {'scout': True, 'recovery': True, 'courier': True}},
           'obstruction': {'state': 'absent'}}
    result = normalize_sensor_record(raw, episode_id='e1', robot_type='scout',
                                    occurred_at=datetime.now(UTC), recorded_at=datetime.now(UTC))
    assert all(obs.value is None for obs in result)
