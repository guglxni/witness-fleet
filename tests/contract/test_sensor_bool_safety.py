from datetime import UTC, datetime

import pytest

from witness_fleet.simulation.observations import normalize_sensor_record


@pytest.mark.parametrize('field', ['fraction', 'x', 'y', 'yaw'])
def test_sensor_boolean_is_not_a_number(field):
    raw = {'robot_id': 'scout', 'world_tick': 10,
           'sensor': {'mode': 'S0', 'expires_tick': 60, 'config_hash': 'sensor-v1'},
           'pose': {'x': -2, 'y': 0, 'yaw': 0},
           'visibility': {'fraction': 1.0, 'state': 'visible'},
           'gap': None, 'obstruction': {'state': 'unknown'}}
    if field == 'fraction':
        raw['visibility']['fraction'] = True
    else:
        raw['pose'][field] = True
    with pytest.raises(ValueError):
        normalize_sensor_record(raw, episode_id='e1', robot_type='scout',
                                occurred_at=datetime.now(UTC), recorded_at=datetime.now(UTC))
