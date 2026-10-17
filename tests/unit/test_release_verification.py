import json
from datetime import UTC, datetime, timedelta

import pytest

from witness_fleet.domain import Observation, Pose, canonical_json_hash
from witness_fleet.graph.verification import validate_release_verification

APPROVED = datetime(2026, 1, 1, tzinfo=UTC)


def records():
    nodes, refs = [], []
    for predicate in ('recovery_verified', 'courier_fit'):
        obs = Observation(id=predicate, tenant_id='demo', episode_id='episode', robot_id='scout',
                          occurred_at=APPROVED, recorded_at=APPROVED, world_tick=10, expires_tick=60,
                          predicate=predicate, value=True, visibility='visible', pose=Pose(x=-3.5, y=-.55),
                          sensor_config_hash='sensor-config', subject_id='corridor',
                          scope={'corridor_id': 'corridor', 'release_id': 'release',
                                 'robot_type': 'courier', 'payload_class': 'loaded'})
        nodes.append({'id': obs.id, 'labels': ['Observation'], 'tenant_id': 'demo',
                      'predicate': predicate, 'value': True, 'payload_json': obs.model_dump_json()})
        refs.append({'observation_id': obs.id, 'payload_hash': canonical_json_hash(obs)})
    return nodes, refs


def verify(nodes, refs, **overrides):
    kwargs = dict(tenant_id='demo', corridor_id='corridor', release_id='release',
                  approved_at=APPROVED, effective_tick=20)
    kwargs.update(overrides)
    return validate_release_verification(nodes, json.dumps(refs), **kwargs)


def test_historical_references_validate_at_approval_not_current_wall_clock():
    nodes, refs = records()
    assert verify(nodes, refs) is True


def test_unreferenced_duplicate_retained_ids_also_fail_closed():
    nodes, refs = records()
    nodes.extend([{'id': 'unreferenced', 'labels': ['Observation']}] * 2)
    assert verify(nodes, refs) is False


@pytest.mark.parametrize('field,value', [
    ('tenant_id', 'other'), ('robot_id', 'courier'), ('visibility', 'insufficient'),
    ('expires_tick', 21), ('scope_json', '{}'),
])
def test_mirrored_graph_identity_cannot_disagree_with_payload(field, value):
    nodes, refs = records()
    nodes[0][field] = value
    assert verify(nodes, refs) is False


@pytest.mark.parametrize('field,value', [
    ('tenant_id', 'other'), ('episode_id', 'other'), ('value', False),
    ('world_tick', 30), ('expires_tick', 20), ('visibility', 'insufficient'),
    ('subject_id', 'other'), ('recorded_at', '2026-01-02T00:00:00Z'),
    ('scope', {'corridor_id': 'corridor', 'release_id': 'wrong',
               'robot_type': 'courier', 'payload_class': 'loaded'}),
])
def test_rehashed_but_unsafe_sample_is_rejected(field, value):
    nodes, refs = records()
    raw = json.loads(nodes[0]['payload_json'])
    raw[field] = value
    nodes[0]['payload_json'] = json.dumps(raw)
    refs[0]['payload_hash'] = canonical_json_hash(Observation.model_validate(raw))
    assert verify(nodes, refs) is False


@pytest.mark.parametrize('alteration', ['missing', 'duplicate_node', 'duplicate_ref', 'bad_hash', 'empty'])
def test_reference_set_must_be_complete_unique_and_exact(alteration):
    nodes, refs = records()
    if alteration == 'missing':
        nodes.pop()
    elif alteration == 'duplicate_node':
        nodes.append(dict(nodes[0]))
    elif alteration == 'duplicate_ref':
        refs.append(dict(refs[0]))
    elif alteration == 'bad_hash':
        refs[0]['payload_hash'] = 'wrong'
    else:
        refs.clear()
    assert verify(nodes, refs) is False


@pytest.mark.parametrize('tick', [True, '20', 9, 60])
def test_strict_original_approval_tick_bounds(tick):
    nodes, refs = records()
    assert verify(nodes, refs, effective_tick=tick) is False


def test_future_relative_to_original_approval_is_not_accepted():
    nodes, refs = records()
    assert verify(nodes, refs, approved_at=APPROVED - timedelta(seconds=1)) is False


@pytest.mark.parametrize('labels', ['Observation', 'notObservation', None, {'Observation': True}])
def test_malformed_graph_labels_fail_closed(labels):
    nodes, refs = records()
    nodes[0]['labels'] = labels
    assert verify(nodes, refs) is False
