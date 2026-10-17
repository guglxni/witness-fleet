"""Native transport boundary tests use actual world/journal, not scenario telemetry."""
import pytest

from services.simulator.service import SimulatorService


def test_replayed_event_does_not_restart_native_skill(tmp_path):
    from witness_fleet.domain import DispatchEvent, canonical_json_hash
    service = SimulatorService(tmp_path)
    service.create_episode('service-test', 'SC-001', 3)
    payload = {'coordinator_epoch': 1, 'holder_id': 'local', 'lease_expires_at_utc': '2026-10-16T00:00:00Z'}
    barrier = DispatchEvent(id='barrier', sequence=1, coordinator_epoch=1, kind='EPOCH_BARRIER',
                            effective_world_tick=0, payload=payload, payload_hash=canonical_json_hash(payload))
    assert service.receive(barrier)['status'] == 'ACCEPTED'
    assert service.receive(barrier)['status'] == 'REPLAY'
    assert service.status()['last_sequence'] == 1
    assert service.status()['started_commands'] == 0
    service.close()


def test_episode_service_cannot_replace_retained_episode_with_same_id(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode('same', 'SC-001', 3)
    with pytest.raises(ValueError):
        service.create_episode('same', 'SC-003', 5)
    service.close()
