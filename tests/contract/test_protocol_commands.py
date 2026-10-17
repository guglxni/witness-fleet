from witness_fleet.domain import DispatchEvent, canonical_json_hash
from witness_fleet.simulation.protocol import preflight


def command_event(*, sequence=1, policy_epoch=0, fence=1, until=10, required_resources=('corridor',), resource_fences=None, effective_tick=0, outer_tick=0):
    from witness_fleet.domain import (
        ActionProposal,
        AuthorizationResult,
        CommandIntent,
        SkillKind,
        VersionVector,
        payload_hash,
    )
    versions=VersionVector(graph_version=1,policy_epoch=policy_epoch,coordinator_epoch=0)
    resource_fences = {'corridor':fence} if resource_fences is None else resource_fences
    proposal=ActionProposal(id='a',robot_id='scout',task_id='task',kind=SkillKind.INSPECT,parameters={},expected_versions=versions,required_predicates=(),required_resource_ids=required_resources,expected_effects=())
    auth=AuthorizationResult(authorization_id='auth',status='ALLOW',reason_codes=(),witness_ids=(),versions=versions,action_payload_hash=payload_hash(proposal),valid_until_tick=until,claim_id='claim',task_id='task',robot_id='scout',fence=fence,resource_fences=resource_fences,governance_integrity_version=1)
    cmd=CommandIntent(command_id='cmd',proposal=proposal,payload_hash=payload_hash(proposal),claim_id='claim',fence=fence,resource_fences=resource_fences,authorization_id='auth',policy_epoch=policy_epoch,coordinator_epoch=0,dispatch_sequence=sequence,effective_world_tick=effective_tick,authorization=auth)
    data=cmd.model_dump(mode='json')
    return DispatchEvent(id=f'ce-{sequence}',sequence=sequence,kind='COMMAND',coordinator_epoch=0,effective_world_tick=outer_tick,payload=data,payload_hash=canonical_json_hash(data))


def test_command_requires_exact_installed_fences_not_worker_larger_number():
    result=preflight(command_event(fence=9),last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={'task':1},resource_fences={'corridor':1},current_tick=0)
    assert result['status']=='REJECTED'
    assert set(result['reason_codes'])=={'STALE_TASK_FENCE','STALE_RESOURCE_FENCE'}


def test_changed_policy_cannot_admit_old_receipt():
    result=preflight(command_event(policy_epoch=0),last_sequence=0,coordinator_epoch=0,policy_epoch=1,task_fences={'task':1},resource_fences={'corridor':1},current_tick=0)
    assert result['status']=='REJECTED'
    assert 'STALE_POLICY_EPOCH' in result['reason_codes']


def test_expired_allow_receipt_cannot_execute():
    result=preflight(command_event(until=10),last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={'task':1},resource_fences={'corridor':1},current_tick=10)
    assert result['status']=='REJECTED'
    assert 'EXPIRED_OR_EARLY_AUTHORIZATION' in result['reason_codes']


def test_current_command_with_installed_fences_and_live_receipt_is_accepted():
    result=preflight(command_event(),last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={'task':1},resource_fences={'corridor':1},current_tick=1)
    assert result['status']=='ACCEPTED'


def test_command_outer_tick_must_match_intent_tick():
    result=preflight(command_event(effective_tick=1,outer_tick=0),last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={'task':1},resource_fences={'corridor':1},current_tick=1)
    assert result['status']=='REJECTED'
    assert 'COMMAND_ENVELOPE_MISMATCH' in result['reason_codes']


def test_command_requires_fence_for_every_proposal_resource():
    result=preflight(command_event(required_resources=('corridor','lift'),resource_fences={'corridor':1}),last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={'task':1},resource_fences={'corridor':1},current_tick=1)
    assert result['status']=='REJECTED'
    assert 'INCOMPLETE_RESOURCE_FENCES' in result['reason_codes']
