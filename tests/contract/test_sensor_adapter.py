from datetime import UTC, datetime

import pytest

from witness_fleet.simulation.observations import normalize_sensor_record

NOW = datetime(2026, 10, 15, tzinfo=UTC)


def record():
    return {'robot_id': 'scout', 'world_tick': 10,
            'sensor': {'mode': 'S0', 'expires_tick': 60, 'config_hash': 'sensor-v1'},
            'pose': {'x': -2, 'y': 0, 'yaw': 0},
            'visibility': {'state': 'visible', 'fraction': 1},
            'gap': {'visibility': 'visible', 'width_m': [.43, .43],
                    'fits': {'scout': True, 'recovery': True, 'courier': False}},
            'obstruction': {'state': 'observed', 'observed_pose': {'x': 0, 'y': 0}}}


def test_visible_gap_preserves_role_scoped_clearance_and_expiry():
    observations = normalize_sensor_record(record(), episode_id='e1', robot_type='scout', occurred_at=NOW, recorded_at=NOW)
    clearance = next(o for o in observations if o.predicate == 'clearance')
    assert clearance.value is True
    assert clearance.scope['robot_type'] == 'scout'
    assert clearance.expires_tick == 60
    assert clearance.subject_id == 'corridor-c'
    assert clearance.quality['width_interval_m'] == (.43, .43)
    assert next(o for o in observations if o.predicate == 'obstruction').value is True


def test_unknown_gap_is_not_clear_or_absent_obstruction():
    raw = record()
    raw['gap'] = None
    raw['obstruction'] = {'state': 'unknown', 'reason': 'occluded'}
    raw['visibility'] = {'state': 'insufficient', 'fraction': .1}
    observations = normalize_sensor_record(raw, episode_id='e1', robot_type='courier', occurred_at=NOW, recorded_at=NOW)
    assert all(o.value is None for o in observations)
    assert all(o.visibility == 'insufficient' for o in observations)


def test_observation_identity_is_stable_and_sensor_payload_changes_identity():
    kwargs = {'episode_id': 'e1', 'robot_type': 'courier', 'occurred_at': NOW, 'recorded_at': NOW}
    a = normalize_sensor_record(record(), **kwargs)
    assert a == normalize_sensor_record(record(), **kwargs)
    raw = record()
    raw['gap']['fits']['courier'] = True
    b = normalize_sensor_record(raw, **kwargs)
    assert a[0].id != b[0].id


def test_clearance_cannot_exceed_measured_conservative_width():
    raw = record()
    raw['gap']['fits']['courier'] = True
    observations = normalize_sensor_record(raw, episode_id='e1', robot_type='courier', occurred_at=NOW, recorded_at=NOW)
    assert next(o for o in observations if o.predicate == 'clearance').value is False


def test_adapter_rejects_nonfinite_and_unbounded_sensor_fields():
    for mutate in (lambda r: r.update(world_tick=True), lambda r: r['sensor'].update(expires_tick=10),
                   lambda r: r['pose'].update(x=float('nan')), lambda r: r['gap']['fits'].update(scout='yes'),
                   lambda r: r['gap'].update(width_m=[.2, -.1])):
        raw = record()
        mutate(raw)
        with pytest.raises(ValueError):
            normalize_sensor_record(raw, episode_id='e1', robot_type='scout', occurred_at=NOW, recorded_at=NOW)
