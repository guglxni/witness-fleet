from test_protocol_commands import command_event
from test_service_admission import control

from services.simulator.service import SimulatorService
from witness_fleet.domain import (
    CommandIntent,
    DispatchEvent,
    SkillKind,
    canonical_json_hash,
    payload_hash,
)


def test_invalid_native_parameters_leave_durable_failed_receipt_not_accepted_limbo(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode('invalid-start', 'SC-001', 3)
    service.receive(control('f', 1, 'FENCE_INSTALL', {'task_id':'task','task_fence':1,'resource_fences':{'corridor':1}}))
    template = CommandIntent.model_validate(command_event(sequence=2, until=100).payload)
    proposal = template.proposal.model_copy(update={'kind':SkillKind.TRAVEL,'parameters':{'target_x':99}})
    action_hash = payload_hash(proposal)
    authorization = template.authorization.model_copy(update={'action_payload_hash':action_hash})
    command = template.model_copy(update={'proposal':proposal,'payload_hash':action_hash,'authorization':authorization})
    wire = command.model_dump(mode='json')
    event = DispatchEvent(id='invalid',sequence=2,coordinator_epoch=0,kind='COMMAND',
        effective_world_tick=0,payload=wire,payload_hash=canonical_json_hash(wire))
    reply = service.receive(event)
    assert reply['status']=='ACCEPTED'  # Ordered event is durably consumed, never ambiguous 409.
    assert reply['command_state']=='FAILED'
    assert service.command('cmd')['state']=='FAILED'
    assert service.status()['last_sequence']==2
    assert service.status()['started_commands']==0
    assert service.receive(event)['status']=='REPLAY'
    service.close()
    resumed = SimulatorService(tmp_path)
    assert resumed.command('cmd')['state']=='FAILED'
    resumed.close()
