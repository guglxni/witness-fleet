import json

from test_governance_integrity import valid_snapshot

from witness_fleet.graph.governance import validate_governance


def release_snapshot(tmp_path):
    snapshot,sources=valid_snapshot(tmp_path)
    decision=next(n for n in snapshot['nodes'] if n['id']=='decision')
    release={'labels':['Release'],'id':'release','state':'staged','scope_json':decision['scope_json'],'effective_from_tick':1,'effective_to_tick':None}
    snapshot['nodes'].append(release)
    snapshot['edges'] += [{'source_id':a,'target_id':b,'relationship':r} for a,b,r in [
        ('release','rule','LIFTS'),('release','owner','APPROVED_BY'),('release','span','SUPPORTED_BY')]]
    return snapshot,sources,release


def test_staged_release_has_no_effective_authority(tmp_path):
    snapshot,sources,release=release_snapshot(tmp_path)
    witnesses, errors = validate_governance(snapshot,sources)
    witness=next(w for w in witnesses if w.id=='release')
    assert witness.state=='staged'
    assert witness.approved is False
    assert errors == ()


def test_released_state_without_named_owner_event_is_invalid(tmp_path):
    snapshot,sources,release=release_snapshot(tmp_path)
    release['state']='released'
    _, errors = validate_governance(snapshot,sources)
    assert 'INVALID_APPROVAL:release' in errors


def test_named_owner_approval_is_bound_to_exact_release(tmp_path):
    snapshot,sources,release=release_snapshot(tmp_path)
    release['state']='released'
    approval = {'labels':['ApprovalEvent'],'id':'approve','actor_id':'owner','target_id':'release','action':'approve','expected_policy_epoch':0}
    snapshot['nodes'].append(approval)
    snapshot['edges'].append({'source_id':'approve','target_id':'release','relationship':'APPROVES'})
    from test_governance_activation_provenance import bind_release_activation
    bind_release_activation(snapshot, release, snapshot['nodes'][-1])
    _, errors = validate_governance(snapshot,sources)
    assert errors == ()
    approval['actor_id']='different'
    _, errors = validate_governance(snapshot,sources)
    assert 'INVALID_APPROVAL:release' in errors


def test_release_may_not_broaden_original_restriction_scope(tmp_path):
    snapshot,sources,release=release_snapshot(tmp_path)
    original=next(n for n in snapshot['nodes'] if n['id']=='decision')
    original['scope_json']=json.dumps({'corridor_id':'corridor-c','action_kinds':['travel'],'robot_types':['courier']})
    _, errors = validate_governance(snapshot,sources)
    assert 'RELEASE_SCOPE_BROADENS:release' in errors
