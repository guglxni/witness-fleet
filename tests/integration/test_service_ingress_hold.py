import pytest
from test_protocol_commands import command_event
from test_service_admission import control

from services.simulator.service import SimulatorService, _plain
from witness_fleet.domain import CommandIntent, DispatchEvent, canonical_json_hash, payload_hash


@pytest.mark.parametrize('timeout', ['bogus', True, 0, 1.5])
def test_malformed_timeout_is_durably_failed_after_ordered_admission(tmp_path, timeout):
    service=SimulatorService(tmp_path)
    service.create_episode('bad-timeout','SC-001',3)
    service.receive(control('f',1,'FENCE_INSTALL',{'task_id':'task','task_fence':1,'resource_fences':{'corridor':1}}))
    base=CommandIntent.model_validate(command_event(sequence=2,until=100).payload)
    proposal=base.proposal.model_copy(update={'parameters':{'timeout_ticks':timeout}})
    action_hash=payload_hash(proposal)
    auth=base.authorization.model_copy(update={'action_payload_hash':action_hash})
    intent=base.model_copy(update={'proposal':proposal,'payload_hash':action_hash,'authorization':auth})
    wire=intent.model_dump(mode='json')
    event=DispatchEvent(id='bad-timeout',sequence=2,coordinator_epoch=0,kind='COMMAND',effective_world_tick=0,
                        payload=wire,payload_hash=canonical_json_hash(wire))
    result=service.receive(event)
    assert result['command_state']=='FAILED'
    assert service.command('cmd')['state']=='FAILED'
    assert service.status()['last_sequence']==2
    assert service.status()['started_commands']==0
    assert service.world.skill_status('scout')['status']=='idle'
    assert service.receive(event)['status']=='REPLAY'
    service.close()
    resumed=SimulatorService(tmp_path)
    assert resumed.command('cmd')['state']=='FAILED'
    assert resumed.status()['started_commands']==0
    assert resumed.receive(event)['status']=='REPLAY'
    resumed.close()


def test_identity_collision_holds_actual_step_owner_not_only_journal(tmp_path):
    service=SimulatorService(tmp_path)
    service.create_episode('collision','SC-001',3)
    service.receive(control('f',1,'FENCE_INSTALL',{'task_id':'task','task_fence':1,'resource_fences':{'corridor':1}}))
    service.receive(command_event(sequence=2,until=100))
    original=service.world.world_tick
    collision=control('different',2,'FENCE_INSTALL',{'task_id':'task','task_fence':2,'resource_fences':{'corridor':2}})
    assert service.receive(collision)['status']=='CONFLICT'
    held_state = _plain(service.world.checkpoint())
    held_identity = service.journal.identity()
    held_receipt = service.command('cmd')
    service.advance(1)
    assert service.world._held is True
    assert service.command('cmd')['state'] != 'CONTROLLER_DONE'
    # Collision HOLD freezes advancement rather than consuming another tick.
    assert service.world.world_tick == original
    assert _plain(service.world.checkpoint()) == held_state
    assert service.journal.identity() == held_identity
    assert service.command('cmd') == held_receipt
    service.close()
