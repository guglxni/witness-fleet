
import pytest
from test_protocol_commands import command_event
from test_service_admission import control

from services.simulator.service import SimulatorService


def test_journal_checkpoint_is_authoritative_if_file_is_missing(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode('crash-test', 'SC-001', 3)
    service.advance(3)
    service.close()
    (tmp_path / 'snapshot.json').unlink()
    resumed = SimulatorService(tmp_path)
    assert resumed.status()['world_tick'] == 3
    resumed.close()


def test_crash_after_admission_before_checkpoint_does_not_auto_resume_effect(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode('crash-test', 'SC-001', 3)
    service.receive(control('f1', 1, 'FENCE_INSTALL', {'task_id':'task','task_fence':1,'resource_fences':{'corridor':1}}))
    # Exercise actual admission, then simulate abrupt exit without service.close().
    service.journal.register(command_event(sequence=2, until=100).model_dump(mode='json'))
    service.journal.record_command('cmd', command_event(sequence=2, until=100).payload_hash, 'PREPARED', event_id='ce-2')
    service.journal.admit_next('ce-2', current_tick=0)
    service.journal.close()
    service.world.close()
    service._owner.close()
    resumed = SimulatorService(tmp_path)
    assert resumed.command('cmd')['state'] == 'UNKNOWN'
    assert resumed.status()['held'] is True
    assert resumed.status()['started_commands'] == 0
    resumed.close()


def test_two_service_owners_cannot_step_same_retained_root(tmp_path):
    service = SimulatorService(tmp_path)
    with pytest.raises(ValueError, match='owner'):
        SimulatorService(tmp_path)
    service.close()
