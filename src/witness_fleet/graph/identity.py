"""Snapshot-only compatibility for the writer's command/event ID namespace.

Never writes to storage or changes wire IDs. Invalid duplicate groups remain
unchanged so callers' global uniqueness checks reject them normally.
"""
import json
from collections import defaultdict
from copy import deepcopy

from witness_fleet.domain import CommandIntent, DispatchEvent, canonical_json_hash


def event_projection_id(tenant_id, event_id):
    return 'projection:DispatchEvent:' + canonical_json_hash([tenant_id, event_id])


def _pair_valid(command, event, edges, tenant_id):
    try:
        identifier = command['id']
        if (command['labels'] != ['Command'] or event['labels'] != ['DispatchEvent']
                or command.get('tenant_id') != tenant_id or event.get('tenant_id') != tenant_id
                or event.get('kind') != 'COMMAND'
                or command.get('command_id') != identifier or event.get('event_id') != identifier):
            return False
        raw = json.loads(command['payload_json'])
        intent = CommandIntent.model_validate(raw)
        event_payload = json.loads(event['payload_json'])
        validated_event = DispatchEvent.model_validate({
            key: event[key] for key in ('id', 'tenant_id', 'sequence', 'coordinator_epoch',
                                        'kind', 'payload_hash', 'effective_world_tick')
        } | {'payload': event_payload})
        digest = canonical_json_hash(raw)
        if (intent.command_id != identifier or event_payload != raw
                or intent.model_dump(mode='json') != raw
                or validated_event.id != identifier
                or command.get('payload_hash') != digest or event['payload_hash'] != digest
                or command.get('authorization_id') != intent.authorization_id
                or type(command.get('fence')) is not int or command['fence'] != intent.fence
                or type(command.get('dispatch_sequence')) is not int
                or command['dispatch_sequence'] != intent.dispatch_sequence
                or type(command.get('coordinator_epoch')) is not int
                or command['coordinator_epoch'] != intent.coordinator_epoch
                or validated_event.sequence != intent.dispatch_sequence
                or validated_event.coordinator_epoch != intent.coordinator_epoch
                or validated_event.effective_world_tick != intent.effective_world_tick
                or json.loads(event['subject_ids_json']) != [identifier, intent.proposal.task_id,
                    intent.proposal.robot_id, intent.claim_id, intent.authorization_id]):
            return False
        delivers = []
        for edge in edges:
            for end in ('source', 'target'):
                if edge.get(end + '_id') == identifier:
                    if edge.get(end + '_label') not in {'Command', 'DispatchEvent'}:
                        return False
            if (edge.get('relationship') == 'DELIVERS'
                    and identifier in (edge.get('source_id'), edge.get('target_id'))):
                if (edge.get('source_id') != identifier or edge.get('source_label') != 'DispatchEvent'
                        or edge.get('target_id') != identifier or edge.get('target_label') != 'Command'):
                    return False
                delivers.append(edge)
            elif ((edge.get('source_id') == identifier and edge.get('source_label') == 'DispatchEvent')
                  or (edge.get('target_id') == identifier and edge.get('target_label') == 'DispatchEvent')):
                return False
        return (len(delivers) == 1 and delivers[0].get('target_id') == identifier
                and delivers[0].get('target_label') == 'Command')
    except (KeyError, TypeError, ValueError):
        return False


def project_command_event_identities(snapshot, *, tenant_id):
    """Disambiguate exact complete COMMAND pairs; filtered singletons are unchanged."""
    groups = defaultdict(list)
    for node in snapshot['nodes']:
        if isinstance(node.get('id'), str):
            groups[node['id']].append(node)
    replacements = {}
    for identifier, group in groups.items():
        if len(group) != 2:
            continue
        commands = [n for n in group if n.get('labels') == ['Command']]
        events = [n for n in group if n.get('labels') == ['DispatchEvent']]
        if (len(commands) != 1 or len(events) != 1
                or not _pair_valid(commands[0], events[0], snapshot['edges'], tenant_id)):
            continue
        projected = event_projection_id(tenant_id, identifier)
        if projected in groups or projected in replacements.values():
            raise ValueError('projection identity collides with retained node identity')
        replacements[identifier] = projected
    if not replacements:
        return snapshot
    result = deepcopy(snapshot)
    for node in result['nodes']:
        if node['id'] in replacements and node['labels'] == ['DispatchEvent']:
            node['persisted_id'] = node['id']
            node['id'] = replacements[node['id']]
    for edge in result['edges']:
        for end in ('source', 'target'):
            if edge.get(end + '_label') == 'DispatchEvent' and edge.get(end + '_id') in replacements:
                edge[end + '_id'] = replacements[edge[end + '_id']]
    return result
