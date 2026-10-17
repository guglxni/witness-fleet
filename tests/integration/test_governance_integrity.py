import json

from witness_fleet.graph.governance import validate_governance
from witness_fleet.ingestion.source_store import SourceStore


def valid_snapshot(tmp_path, kind='restriction'):
    sources=SourceStore(tmp_path/'sources')
    text='Maintenance owner prohibits loaded courier travel in corridor-c.'
    rev=sources.retain('maintenance',text.encode())
    span=sources.validate_span(rev.revision_id,0,len(text),text)
    scope={'corridor_id':'corridor-c','action_kinds':['travel','deliver'],'robot_types':['courier']}
    nodes=[{'labels':['Source'],'id':'source','source_id':'maintenance'},
      {'labels':['Revision'],'id':'rev','revision_id':rev.revision_id,'normalized_hash':rev.normalized_hash,'content_hash':rev.bytes_hash,'normalizer_version':rev.normalizer_version},
      {'labels':['EvidenceSpan'],'id':'span','start_char':0,'end_char':len(text),'quote':text,'quote_hash':span['quote_hash']},
      {'labels':['Owner'],'id':'owner','role':'maintenance_owner','authority_scope':'corridor-c'},
      {'labels':['Decision'],'id':'decision','kind':kind,'state':'active','effective_from_tick':0,'effective_to_tick':None,'scope_json':json.dumps(scope)},
      {'labels':['Restriction' if kind=='restriction' else 'Permission'],'id':'rule','state':'active'}]
    nodes.append({'labels':['ApprovalEvent'],'id':'decision-approval','actor_id':'owner',
                  'target_id':'decision','action':'approve','event_id':'decision-approval',
                  'expected_policy_epoch':0})
    edges=[{'source_id':a,'target_id':b,'relationship':r} for a,b,r in [
        ('rev','source','REVISION_OF'),('span','rev','IN_REVISION'),('decision','span','SUPPORTED_BY'),
        ('decision','owner','OWNED_BY'),('decision','rule','IMPOSES' if kind=='restriction' else 'GRANTS'),
        ('rule','corridor-c','APPLIES_TO'),('decision-approval','decision','APPROVES')]]
    nodes.append({'labels':['Corridor'],'id':'corridor-c'})
    snapshot = {'nodes': nodes, 'edges': edges}
    from test_governance_roster import bind_roster
    bind_roster(snapshot, sources)
    return snapshot, sources


def test_validator_returns_witnesses_and_errors_as_tuples(tmp_path):
    snapshot, sources = valid_snapshot(tmp_path)
    witnesses, errors = validate_governance(snapshot, sources)
    assert isinstance(witnesses, tuple)
    assert isinstance(errors, tuple)
    assert errors == ()


def test_complete_restriction_chain_validates_exact_retained_span_and_owner(tmp_path):
    snapshot,sources=valid_snapshot(tmp_path)
    witnesses, errors = validate_governance(snapshot,sources)
    assert errors == ()
    assert witnesses[0].kind=='restriction'
    assert witnesses[0].span_id=='span'


def test_misquoted_source_fails_closed_without_hiding_restriction(tmp_path):
    snapshot,sources=valid_snapshot(tmp_path)
    next(n for n in snapshot['nodes'] if n['id']=='span')['quote']='different'
    _, errors = validate_governance(snapshot,sources)
    assert 'INVALID_SOURCE_CHAIN:rule' in errors


def test_owner_outside_corridor_scope_fails_closed(tmp_path):
    snapshot,sources=valid_snapshot(tmp_path)
    next(n for n in snapshot['nodes'] if n['id']=='owner')['authority_scope']='corridor-d'
    _, errors = validate_governance(snapshot,sources)
    assert 'INVALID_OWNER_SCOPE:rule' in errors


def test_unknown_scope_never_becomes_empty_and_permissive(tmp_path):
    snapshot,sources=valid_snapshot(tmp_path)
    next(n for n in snapshot['nodes'] if n['id']=='decision')['scope_json']='{}'
    _, errors = validate_governance(snapshot,sources)
    assert 'INVALID_SCOPE:rule' in errors


def test_permission_without_exact_corridor_relation_is_invalid(tmp_path):
    snapshot, sources = valid_snapshot(tmp_path, kind='permission')
    snapshot['edges'] = [edge for edge in snapshot['edges']
                         if edge['relationship'] != 'APPLIES_TO']
    _, errors = validate_governance(snapshot, sources)
    assert 'INVALID_APPLIES_TO:rule' in errors


def test_active_decision_requires_exact_owner_approval_event(tmp_path):
    snapshot, sources = valid_snapshot(tmp_path)
    snapshot['nodes'] = [node for node in snapshot['nodes'] if node['id'] != 'decision-approval']
    snapshot['edges'] = [edge for edge in snapshot['edges']
                         if edge['relationship'] != 'APPROVES']
    _, errors = validate_governance(snapshot, sources)
    assert 'INVALID_APPROVAL:decision' in errors


def test_permission_positive_authority_rejects_wildcard_scope(tmp_path):
    snapshot, sources = valid_snapshot(tmp_path, kind='permission')
    decision = next(node for node in snapshot['nodes'] if node['id'] == 'decision')
    decision['scope_json'] = json.dumps({
        'corridor_id': '*', 'action_kinds': ['travel'], 'robot_types': ['*'],
    })
    _, errors = validate_governance(snapshot, sources)
    assert 'INVALID_SCOPE:rule' in errors
