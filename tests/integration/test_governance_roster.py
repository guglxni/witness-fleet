import json

from test_governance_integrity import valid_snapshot

from witness_fleet.graph.governance import validate_governance


def bind_roster(snapshot, sources, *, actions=('travel', 'deliver')):
    snapshot['nodes'] = [node for node in snapshot['nodes'] if not node['id'].startswith('roster-')]
    snapshot['edges'] = [edge for edge in snapshot['edges']
                         if not edge['source_id'].startswith('roster-') and not edge['target_id'].startswith('roster-')]
    text = json.dumps({'owners': [{'owner_id': 'owner', 'role': 'maintenance_owner',
                                 'scope': ['corridor-c'], 'actions': list(actions)}]})
    revision = sources.retain('owner-roster', text.encode())
    span = sources.validate_span(revision.revision_id, 0, len(text), text)
    snapshot['nodes'].extend([
        {'labels': ['Source'], 'id': 'roster-source', 'source_id': 'owner-roster'},
        {'labels': ['Revision'], 'id': 'roster-rev', 'revision_id': revision.revision_id,
         'content_hash': revision.bytes_hash, 'normalized_hash': revision.normalized_hash,
         'normalizer_version': revision.normalizer_version},
        {'labels': ['EvidenceSpan'], 'id': 'roster-span', 'start_char': 0, 'end_char': len(text),
         'quote': text, 'quote_hash': span['quote_hash']},
    ])
    snapshot['edges'].extend([
        {'source_id': 'owner', 'target_id': 'roster-span', 'relationship': 'SUPPORTED_BY'},
        {'source_id': 'roster-span', 'target_id': 'roster-rev', 'relationship': 'IN_REVISION'},
        {'source_id': 'roster-rev', 'target_id': 'roster-source', 'relationship': 'REVISION_OF'},
    ])
    rule = next(n for n in snapshot['nodes'] if n['id'] == 'rule')
    rule.update({'rule_type': 'prohibit', 'subject_scope': json.dumps(['courier']),
                 'condition_json': json.dumps({'corridor_id': 'corridor-c', 'action_kinds': ['travel', 'deliver']})})
    if 'Permission' in rule['labels']:
        rule['action_kind'] = 'travel'
    return snapshot


def test_owner_properties_without_retained_roster_cannot_authorize(tmp_path):
    snapshot, sources = valid_snapshot(tmp_path)
    snapshot['edges'] = [edge for edge in snapshot['edges']
                         if not (edge['source_id'] == 'owner' and edge['relationship'] == 'SUPPORTED_BY')]
    _, errors = validate_governance(snapshot, sources)
    assert any(error.startswith('INVALID_OWNER_ROSTER') for error in errors)


def test_roster_action_scope_cannot_be_broadened_by_graph_owner_properties(tmp_path):
    snapshot, sources = valid_snapshot(tmp_path)
    bind_roster(snapshot, sources, actions=('inspect', 'recover'))
    _, errors = validate_governance(snapshot, sources)
    assert any(error.startswith('INVALID_OWNER_ROSTER') for error in errors)


def test_valid_retained_roster_and_typed_scope_are_required_together(tmp_path):
    snapshot, sources = valid_snapshot(tmp_path)
    bind_roster(snapshot, sources)
    _, errors = validate_governance(snapshot, sources)
    assert errors == ()


def test_conflicting_typed_policy_scope_is_not_authority(tmp_path):
    snapshot, sources = valid_snapshot(tmp_path)
    bind_roster(snapshot, sources)
    next(n for n in snapshot['nodes'] if n['id'] == 'rule')['condition_json'] = json.dumps({'corridor_id': 'corridor-d', 'action_kinds': ['travel']})
    _, errors = validate_governance(snapshot, sources)
    assert any(error.startswith('INVALID_TYPED_POLICY') for error in errors)
