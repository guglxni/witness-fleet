from test_protocol_commands import command_event

from services.simulator.service import SimulatorService
from witness_fleet.domain import DispatchEvent, canonical_json_hash


def control(identifier, sequence, kind, payload):
    return DispatchEvent(id=identifier, sequence=sequence, coordinator_epoch=0, kind=kind,
                         effective_world_tick=0, payload=payload, payload_hash=canonical_json_hash(payload))


def test_current_fenced_command_starts_once_and_persists_sensor_completion(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode('command-test', 'SC-001', 3)
    fence = control('f1', 1, 'FENCE_INSTALL', {'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1}})
    assert service.receive(fence)['status'] == 'ACCEPTED'
    command = command_event(sequence=2, until=100)
    assert service.receive(command)['status'] == 'ACCEPTED'
    assert service.receive(command)['status'] == 'REPLAY'
    assert service.status()['started_commands'] == 1
    service.advance(2)
    receipt = service.command('cmd')
    assert receipt['state'] == 'CONTROLLER_DONE'
    assert service.observations()['robots']['scout']['world_tick'] == 2
    service.close()


def test_stale_fence_cannot_start_physical_effect(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode('stale-test', 'SC-001', 3)
    service.receive(control('f1', 1, 'FENCE_INSTALL', {'task_id': 'task', 'task_fence': 9, 'resource_fences': {'corridor': 9}}))
    result = service.receive(command_event(sequence=2))
    assert result['status'] == 'HOLD'
    assert set(result['reason_codes']) == {'STALE_TASK_FENCE', 'STALE_RESOURCE_FENCE'}
    assert service.status()['held'] is True
    assert service.status()['coordinator_epoch'] == 0
    assert service.status()['last_sequence'] == 1
    assert service.status()['started_commands'] == 0
    service.close()
