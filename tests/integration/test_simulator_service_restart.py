
from services.simulator.service import SimulatorService
from witness_fleet.domain import DispatchEvent, canonical_json_hash


def test_receipt_and_world_survive_clean_service_restart_without_new_execution(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode('persistent', 'SC-001', 3)
    barrier_payload = {'coordinator_epoch': 1}
    service.receive(DispatchEvent(id='e1', sequence=1, coordinator_epoch=1, kind='EPOCH_BARRIER', effective_world_tick=0, payload=barrier_payload, payload_hash=canonical_json_hash(barrier_payload)))
    service.advance(10)
    service.close()
    restored = SimulatorService(tmp_path)
    assert restored.status()['episode_id'] == 'persistent'
    assert restored.status()['world_tick'] == 10
    assert restored.status()['last_sequence'] == 1
    assert restored.status()['started_commands'] == 0
    restored.close()
