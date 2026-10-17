"""Pure corrupt-snapshot negatives; no graph records are deleted or rewritten."""
import copy
import json

import pytest
from test_protocol_commands import command_event

from witness_fleet.graph.identity import event_projection_id, project_command_event_identities
from witness_fleet.runtime.coordinator import Coordinator


def pair():
    event = command_event()
    raw = event.model_dump(mode='json')
    command = raw['payload']
    identifier = command['command_id']
    envelope = {k: v for k, v in raw.items() if k != 'payload'}
    envelope.update(id=identifier, labels=['DispatchEvent'], event_id=identifier,
        payload_json=json.dumps(command), subject_ids_json=json.dumps([
            identifier, command['proposal']['task_id'], command['proposal']['robot_id'],
            command['claim_id'], command['authorization_id']]))
    node = {k: command[k] for k in ('command_id', 'fence', 'authorization_id',
                                     'dispatch_sequence', 'coordinator_epoch')}
    node.update(id=identifier, labels=['Command'], tenant_id='demo',
                payload_json=json.dumps(command), payload_hash=event.payload_hash)
    return {'nodes': [node, envelope], 'edges': [{'source_id': identifier, 'source_label': 'DispatchEvent',
        'target_id': identifier, 'target_label': 'Command', 'relationship': 'DELIVERS', 'properties': {}}]}


def test_projection_is_pure_idempotent_and_keeps_command_endpoints():
    snapshot = pair()
    snapshot['nodes'].append({'id': 'task', 'labels': ['Task'], 'tenant_id': 'demo'})
    snapshot['edges'].append({'source_id': 'cmd', 'source_label': 'Command', 'target_id': 'task',
        'target_label': 'Task', 'relationship': 'FOR_TASK', 'properties': {}})
    before = copy.deepcopy(snapshot)
    projected = project_command_event_identities(snapshot, tenant_id='demo')
    assert snapshot == before
    assert len(Coordinator._unique_nodes(projected)) == 3
    assert projected['edges'][0]['source_id'] == event_projection_id('demo', 'cmd')
    assert projected['edges'][0]['target_id'] == 'cmd'
    assert projected['edges'][1] == snapshot['edges'][1]
    assert projected['nodes'][1]['persisted_id'] == projected['nodes'][1]['event_id'] == 'cmd'
    assert project_command_event_identities(projected, tenant_id='demo') == projected


@pytest.mark.parametrize('mutation', ['wrong_direction', 'wrong_type', 'untyped', 'tenant',
    'multi_label', 'duplicate_event', 'duplicate_command', 'extra_delivers', 'reverse_extra',
    'incoming_extra', 'governance_collision'])
def test_only_exact_writer_pair_is_normalized(mutation):
    snapshot = pair()
    edge = snapshot['edges'][0]
    if mutation == 'wrong_direction':
        edge.update(source_label='Command', target_label='DispatchEvent')
    elif mutation == 'wrong_type':
        edge['target_label'] = 'Release'
    elif mutation == 'untyped':
        del edge['source_label']
    elif mutation == 'tenant':
        snapshot['nodes'][1]['tenant_id'] = 'other'
    elif mutation == 'multi_label':
        snapshot['nodes'][0]['labels'].append('Task')
    elif mutation == 'duplicate_event':
        snapshot['nodes'].append(copy.deepcopy(snapshot['nodes'][1]))
    elif mutation == 'duplicate_command':
        snapshot['nodes'].append(copy.deepcopy(snapshot['nodes'][0]))
    elif mutation == 'extra_delivers':
        snapshot['edges'].append(copy.deepcopy(edge))
    elif mutation == 'reverse_extra':
        snapshot['edges'].append({**edge, 'source_label': 'Command', 'target_label': 'DispatchEvent'})
    elif mutation == 'incoming_extra':
        snapshot['edges'].append({**edge, 'source_id': 'other-event'})
    elif mutation == 'governance_collision':
        snapshot['nodes'].append({'id': 'cmd', 'labels': ['Release']})
    assert project_command_event_identities(snapshot, tenant_id='demo') == snapshot
    with pytest.raises(ValueError, match='ambiguous'):
        Coordinator._unique_nodes(project_command_event_identities(snapshot, tenant_id='demo'))
