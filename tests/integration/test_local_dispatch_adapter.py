"""Local transport preserves the graph event identity and receiver receipts."""

import pytest

from services.simulator.service import SimulatorService
from witness_fleet.domain import DispatchEvent, canonical_json_hash
from witness_fleet.runtime.local_adapter import LocalSimulatorAdapter


def test_local_adapter_delivers_exact_barrier_and_reads_exact_event(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('local-transport', 'SC-001', 3)
        payload = {'coordinator_epoch': 1, 'holder_id': 'configured-local',
                   'lease_expires_at_utc': '2026-10-16T00:00:00Z'}
        event = DispatchEvent(id='exact/barrier%identity', sequence=1, coordinator_epoch=1,
                              kind='EPOCH_BARRIER', effective_world_tick=0, payload=payload,
                              payload_hash=canonical_json_hash(payload))
        adapter = LocalSimulatorAdapter(service)
        assert adapter.deliver(event)['status'] == 'ACCEPTED'
        assert adapter.deliver(event)['status'] == 'REPLAY'
        retained = adapter.event(event.id)
        assert retained['id'] == event.id
        assert retained['payload_hash'] == event.payload_hash
        assert retained['payload'] == payload
        assert adapter.event('missing') is None
        assert adapter.receipt('missing') == {'status': 'NOT_FOUND', 'command_id': 'missing'}
        assert adapter.status()['started_commands'] == 0
    finally:
        service.close()


def test_local_adapter_requires_typed_hash_bound_event_before_service_access():
    adapter = LocalSimulatorAdapter(None)
    with pytest.raises(ValueError, match='typed'):
        adapter.deliver({'id': 'untrusted'})
