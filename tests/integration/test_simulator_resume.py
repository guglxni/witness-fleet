from test_protocol_commands import command_event
from test_service_admission import control

from services.simulator.service import SimulatorService


def test_active_skill_resumes_only_from_exact_durable_checkpoint(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode('resume', 'SC-001', 3)
    service.receive(control('f', 1, 'FENCE_INSTALL', {'task_id':'task', 'task_fence':1, 'resource_fences':{'corridor':1}}))
    source = command_event(sequence=2, until=100)
    service.receive(source)
    # Inspect's native controller completes on its first physics step. Snapshot
    # the accepted/running command before stepping, then resume exactly once.
    assert service.command('cmd')['state'] == 'RUNNING'
    service.close()
    resumed = SimulatorService(tmp_path)
    resumed.advance(1)
    assert resumed.command('cmd')['state'] == 'CONTROLLER_DONE'
    assert resumed.status()['started_commands'] == 1
    assert resumed.receive(source)['status'] == 'REPLAY'
    resumed.close()
