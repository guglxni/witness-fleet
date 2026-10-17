from test_protocol_commands import command_event
from test_service_admission import control

from services.simulator.service import SimulatorService


def test_durable_journal_hold_is_applied_to_native_world_after_restart(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode('held-restart', 'SC-001', 3)
    service.receive(control('fence', 1, 'FENCE_INSTALL', {
        'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1},
    }))
    service.receive(command_event(sequence=2, until=100))
    assert service.world.checkpoint()['held'] is False

    collision = control('collision', 2, 'FENCE_INSTALL', {
        'task_id': 'other', 'task_fence': 2, 'resource_fences': {'corridor': 2},
    })
    assert service.journal.register(collision.model_dump(mode='json'))['status'] == 'CONFLICT'
    assert service.journal.identity()['held'] is True

    # Simulate process death after the journal commit but before native hold/checkpoint.
    service.journal.close()
    service.world.close()
    service._owner.close()

    resumed = SimulatorService(tmp_path)
    assert resumed.journal.identity()['held'] is True
    assert resumed.world.checkpoint()['held'] is True
    resumed.advance(1)
    assert resumed.command('cmd')['state'] != 'CONTROLLER_DONE'
    assert resumed.world.checkpoint()['held'] is True
    resumed.close()
