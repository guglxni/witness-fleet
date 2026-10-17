from witness_fleet.domain import DispatchEvent, canonical_json_hash
from witness_fleet.simulation.protocol import preflight


def test_epoch_barrier_payload_identity_cannot_disagree_with_outer_epoch():
    payload = {'coordinator_epoch': 999}
    event = DispatchEvent(id='barrier', sequence=1, coordinator_epoch=1, kind='EPOCH_BARRIER',
                          effective_world_tick=0, payload=payload, payload_hash=canonical_json_hash(payload))
    result = preflight(event, last_sequence=0, coordinator_epoch=0, policy_epoch=0,
                       task_fences={}, resource_fences={}, current_tick=0)
    assert result['status'] == 'REJECTED'
    assert 'INVALID_EPOCH_BARRIER' in result['reason_codes']
