from witness_fleet.domain import DispatchEvent, canonical_json_hash
from witness_fleet.simulation.protocol import preflight


def event(sequence=1, kind='FENCE_INSTALL', epoch=0):
    payload={'task_id':'task','task_fence':1,'resource_fences':{'corridor':1}}
    return DispatchEvent(id=f'e-{sequence}',sequence=sequence,kind=kind,coordinator_epoch=epoch,effective_world_tick=0,payload=payload,payload_hash=canonical_json_hash(payload))


def test_gap_cannot_be_admitted_as_motion_or_fence_install():
    result=preflight(event(2),last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={},resource_fences={},current_tick=0)
    assert result['status']=='HOLD'
    assert 'SEQUENCE_GAP' in result['reason_codes']


def test_old_epoch_is_rejected_even_when_sequence_is_next():
    result=preflight(event(1,epoch=0),last_sequence=0,coordinator_epoch=1,policy_epoch=0,task_fences={},resource_fences={},current_tick=0)
    assert result['status']=='REJECTED'
    assert 'STALE_COORDINATOR_EPOCH' in result['reason_codes']


def test_worker_cannot_install_lower_resource_fence():
    result=preflight(event(),last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={'task':2},resource_fences={'corridor':2},current_tick=0)
    assert result['status']=='REJECTED'
    assert 'FENCE_ROLLBACK' in result['reason_codes']


def test_next_current_epoch_installed_fence_is_accepted():
    result=preflight(event(),last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={},resource_fences={},current_tick=0)
    assert result['status']=='ACCEPTED'


def test_future_outer_tick_holds_even_when_event_sequence_is_next():
    future = DispatchEvent(id='future',sequence=1,kind='FENCE_INSTALL',coordinator_epoch=0,
                           effective_world_tick=1,payload={'task_id':'task','task_fence':1,'resource_fences':{'corridor':1}},
                           payload_hash=canonical_json_hash({'task_id':'task','task_fence':1,'resource_fences':{'corridor':1}}))
    result=preflight(future,last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={},resource_fences={},current_tick=0)
    assert result['status']=='HOLD'
    assert 'EVENT_NOT_YET_EFFECTIVE' in result['reason_codes']


def test_malformed_fence_payload_returns_safe_rejection():
    malformed = DispatchEvent(id='bad-fence',sequence=1,kind='FENCE_INSTALL',coordinator_epoch=0,
                              effective_world_tick=0,payload={'task_id':'task','task_fence':1,'resource_fences':'corridor'},
                              payload_hash=canonical_json_hash({'task_id':'task','task_fence':1,'resource_fences':'corridor'}))
    result=preflight(malformed,last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={},resource_fences={},current_tick=0)
    assert result['status']=='REJECTED'
    assert 'INVALID_FENCE_INSTALL' in result['reason_codes']


def test_duplicate_sequence_requires_journal_identity_check():
    result=preflight(event(1),last_sequence=1,coordinator_epoch=0,policy_epoch=0,task_fences={},resource_fences={},current_tick=0)
    assert result['status']=='HOLD'
    assert result['reason_codes']==['JOURNAL_IDENTITY_CHECK_REQUIRED']


def test_policy_transition_requires_incremental_current_coordinator_proof():
    payload={'expected_previous_policy_epoch':0,'policy_epoch':1,
             'policy_proof':{'coordinator_epoch':0,'proof_id':'proof-1'}}
    policy_event=DispatchEvent(id='policy',sequence=1,kind='POLICY_ACTIVATION',coordinator_epoch=0,
                               effective_world_tick=0,payload=payload,payload_hash=canonical_json_hash(payload))
    result=preflight(policy_event,last_sequence=0,coordinator_epoch=0,policy_epoch=0,task_fences={},resource_fences={},current_tick=0)
    assert result['status']=='ACCEPTED'


def test_policy_transition_rejects_rollback_or_untrusted_epoch_proof():
    payload={'expected_previous_policy_epoch':2,'policy_epoch':1,
             'policy_proof':{'coordinator_epoch':3,'proof_id':'proof-1'}}
    policy_event=DispatchEvent(id='policy',sequence=1,kind='REVOCATION',coordinator_epoch=0,
                               effective_world_tick=0,payload=payload,payload_hash=canonical_json_hash(payload))
    result=preflight(policy_event,last_sequence=0,coordinator_epoch=0,policy_epoch=2,task_fences={},resource_fences={},current_tick=0)
    assert result['status']=='REJECTED'
    assert {'INVALID_POLICY_TRANSITION','UNTRUSTED_POLICY_PROOF'} <= set(result['reason_codes'])
