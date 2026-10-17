"""Approval authority must re-read the exact retained sensor proof historically."""

import json
from datetime import UTC, datetime

import pytest
from test_governance_activation_provenance import approved_release, bind_release_activation

from witness_fleet.domain import Observation, Pose, canonical_json_hash
from witness_fleet.graph.governance import validate_governance


def historical_release(tmp_path):
    snapshot, sources, release, approval = approved_release(tmp_path)
    bind_release_activation(snapshot, release, approval)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    approval['created_at'] = now.isoformat()
    references = []
    for predicate in ('recovery_verified', 'courier_fit'):
        obs = Observation(id=predicate, tenant_id='demo', episode_id='episode', robot_id='scout',
            occurred_at=now, recorded_at=now, world_tick=1, expires_tick=51,
            predicate=predicate, value=True, pose=Pose(x=-3.5, y=-.55), visibility='visible',
            scope={'corridor_id': 'corridor-c', 'release_id': release['id'],
                   'robot_type': 'courier', 'payload_class': 'loaded'},
            sensor_config_hash='sensor-v1', subject_id='corridor-c')
        snapshot['nodes'].append({'id': obs.id, 'labels': ['Observation'], 'tenant_id': 'demo',
            'predicate': predicate, 'value': True, 'payload_json': obs.model_dump_json()})
        references.append({'observation_id': obs.id, 'payload_hash': canonical_json_hash(obs)})
    approval['verification_json'] = json.dumps(references)
    return snapshot, sources, release, approval


def test_valid_historical_reference_is_not_expired_by_present_wall_clock(tmp_path):
    snapshot, sources, release, _ = historical_release(tmp_path)
    witnesses, errors = validate_governance(snapshot, sources)
    assert errors == ()
    assert next(w for w in witnesses if w.id == release['id']).approved


@pytest.mark.parametrize('timestamp', [None, 17, True, {}, 'not-a-time'])
def test_malformed_approval_timestamp_returns_invalid_provenance(tmp_path, timestamp):
    snapshot, sources, release, approval = historical_release(tmp_path)
    approval['created_at'] = timestamp
    witnesses, errors = validate_governance(snapshot, sources)
    assert 'INVALID_ACTIVATION_PROVENANCE:release' in errors
    assert next(w for w in witnesses if w.id == release['id']).approved is False


@pytest.mark.parametrize('mutation', ['missing_refs', 'missing_observation', 'forged_hash',
                                      'tampered_observation', 'stale_at_approval'])
def test_missing_or_tampered_historical_verification_never_approves(tmp_path, mutation):
    snapshot, sources, release, approval = historical_release(tmp_path)
    if mutation == 'missing_refs':
        approval.pop('verification_json')
    elif mutation == 'missing_observation':
        snapshot['nodes'] = [n for n in snapshot['nodes'] if n['id'] != 'courier_fit']
    elif mutation == 'forged_hash':
        references = json.loads(approval['verification_json'])
        references[0]['payload_hash'] = 'wrong'
        approval['verification_json'] = json.dumps(references)
    else:
        node = next(n for n in snapshot['nodes'] if n['id'] == 'courier_fit')
        payload = json.loads(node['payload_json'])
        payload['value' if mutation == 'tampered_observation' else 'expires_tick'] = False if mutation == 'tampered_observation' else 1
        node['payload_json'] = json.dumps(payload)
    witnesses, errors = validate_governance(snapshot, sources)
    assert 'INVALID_ACTIVATION_PROVENANCE:release' in errors
    assert next(w for w in witnesses if w.id == release['id']).approved is False
