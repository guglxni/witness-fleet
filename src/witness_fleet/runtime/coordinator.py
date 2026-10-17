"""Single trusted local integration owner; FalkorDB remains workflow authority."""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import UTC, datetime

from witness_fleet.runtime.bootstrap import bootstrap


class Coordinator:
    """Coordinate retained graph state and an exclusively owned native simulator.

    Constructor is inert: it never assumes an unknown old command completed or
    takes over a live lease. Explicit operations acquire and validate authority.
    """

    def __init__(self, graph, sources, simulator):
        self.graph, self.sources, self.simulator = graph, sources, simulator
        self.holder_id = 'coordinator-' + uuid.uuid4().hex
        self._lock = threading.RLock()
        self.manifest = None
        native = simulator.status()
        if native['episode_id']:
            episode = graph.get_node('Episode', native['episode_id'])
            if episode is None:
                raise ValueError('native episode has no canonical graph manifest')
            self.manifest = json.loads(episode['payload_json'])['result']

    def ready(self):
        root = self.graph.read_version_root()
        native = self.simulator.status()
        if (not root or not self.manifest or native['held']
                or root.get('coordinator_holder_id') != self.holder_id
                or root['coordinator_epoch'] != native['coordinator_epoch']
                or root['policy_epoch'] != native['policy_epoch']
                or root['dispatch_sequence'] != native['last_sequence']):
            return False
        try:
            return datetime.fromisoformat(root['coordinator_lease_expires_at_utc'].replace('Z', '+00:00')) > datetime.now(UTC)
        except (KeyError, TypeError, ValueError):
            return False

    def create_incident(self, scenario, seed, event_id):
        with self._lock:
            if not isinstance(event_id, str) or not event_id or len(event_id) > 128:
                raise ValueError('bounded explicit event identity required')
            prefix = 'incident-' + hashlib.sha256(event_id.encode()).hexdigest()[:24]
            if self.manifest and (self.manifest['prefix'], self.manifest['scenario'], self.manifest['seed']) != (prefix, scenario, seed):
                raise ValueError('retained episode cannot be replaced; start a separate run directory')
            self.graph.initialize()
            self.manifest = bootstrap(self.graph, self.sources, prefix=prefix, scenario=scenario, seed=seed)
            self.simulator.create_episode(self.manifest['episode_id'], scenario, seed)
            self.simulator.load_payload('courier', prefix + '-parcel')
            return self.state()

    def _snapshot(self):
        return self.graph.read_snapshot()

    def state(self):
        with self._lock:
            root = self.graph.read_version_root() or {}
            native = self.simulator.status()
            snapshot = self._snapshot() if root else {'nodes': [], 'edges': [], 'versions': {}}
            nodes, edges = snapshot['nodes'], snapshot['edges']
            by_id = self._unique_nodes(snapshot)
            active_ids = self._active_manifest_ids(by_id)
            if self.manifest and native['episode_id'] != self.manifest['episode_id']:
                raise ValueError('native episode disagrees with active manifest')
            root = {**root, **snapshot['versions']}
            task_ids = set(self.manifest['task_ids']) if self.manifest else set()
            episode_id = self.manifest['episode_id'] if self.manifest else None
            for task_id in task_ids:
                task = by_id.get(task_id)
                owners = [e['source_id'] for e in edges if e['relationship'] == 'CONTAINS'
                          and e['target_id'] == task_id]
                if (task_id not in active_ids or task is None or task['labels'] != ['Task']
                        or task.get('tenant_id') != self.graph.tenant_id
                        or owners != [episode_id]):
                    raise ValueError('task is not uniquely contained by the active manifest episode')
            commands = []
            for node in nodes:
                if 'Command' not in node['labels'] or 'payload_json' not in node:
                    continue
                intent = json.loads(node['payload_json'])
                if intent['proposal']['task_id'] not in task_ids:
                    continue
                targets = [e['target_id'] for e in edges if e['relationship'] == 'FOR_TASK'
                           and e['source_id'] == node['id']]
                if (node['labels'] != ['Command'] or node.get('tenant_id') != self.graph.tenant_id
                        or targets != [intent['proposal']['task_id']]):
                    raise ValueError('command is not uniquely tied to an active task')
                receipt = self.simulator.command(node['id'])
                commands.append({'command_id': node['id'], 'robot_id': intent['proposal']['robot_id'],
                    'task_id': intent['proposal']['task_id'], 'kind': intent['proposal']['kind'],
                    'state': node['state'], 'last_known_state': receipt.get('last_known_state'),
                    'reconciliation_state': receipt.get('reconciliation_state') or 'known',
                    'world_tick': receipt.get('native', {}).get('world_tick', intent['effective_world_tick']),
                    'reason_codes': node.get('reason_codes', []), 'native': receipt.get('native')})
            tasks = []
            for node in nodes:
                if 'Task' not in node['labels'] or node['id'] not in task_ids:
                    continue
                matching = [c for c in commands if c['task_id'] == node['id']]
                robot = next((e['source_id'] for e in edges if e['relationship'] == 'ASSIGNED_TO'
                              and e['target_id'] == node['id']), None)
                tasks.append({'id': node['id'], 'kind': node['kind'], 'state': node['state'],
                    'robot_id': robot, 'depends_on': [e['target_id'] for e in edges
                        if e['source_id'] == node['id'] and e['relationship'] == 'DEPENDS_ON'],
                    'reason_codes': json.loads(node.get('reason_codes_json', '[]')),
                    'last_command_id': matching[-1]['command_id'] if matching else None})
            observations = []
            for node in nodes:
                if 'Observation' in node['labels'] and node.get('payload_json'):
                    value = json.loads(node['payload_json'])
                    if value['episode_id'] == native['episode_id']:
                        observations.append(value)
            robots = []
            for node in nodes:
                if 'Robot' in node['labels'] and node['id'] in native['poses']:
                    recent = [o['world_tick'] for o in observations if o['robot_id'] == node['id']]
                    active = next((c for c in reversed(commands) if c['robot_id'] == node['id']), None)
                    robots.append({'id': node['id'], 'role': node['robot_type'],
                        'pose': native['poses'][node['id']], 'state': active['state'] if active else 'IDLE',
                        'footprint_m': node['footprint_m'], 'last_observation_tick': max(recent) if recent else None})
            restrictions = [n for n in nodes if 'Restriction' in n['labels'] and n['id'] in active_ids]
            source_nodes = []
            for source in nodes:
                if 'Source' not in source['labels'] or source['id'] not in active_ids:
                    continue
                for edge in edges:
                    if (edge['relationship'] == 'REVISION_OF' and edge['target_id'] == source['id']
                            and edge['source_id'] in active_ids):
                        revision = by_id[edge['source_id']]
                        self._source_from_snapshot(revision['revision_id'], snapshot, by_id, active_ids)
                        source_nodes.append({**source, 'revision_id': revision['revision_id'],
                            'normalized_hash': revision['normalized_hash'],
                            'normalizer_version': revision['normalizer_version']})
            event_targets = {n['id'] for n in nodes if n['id'] in active_ids
                             and n['labels'] in [['Decision'], ['Release']]}
            event_targets.update(c['command_id'] for c in commands)
            events = []
            for node in nodes:
                if node['labels'] != ['DispatchEvent']:
                    continue
                targets = [e['target_id'] for e in edges if e['relationship'] == 'DELIVERS'
                           and e['source_id'] == node['id']]
                if (targets and set(targets) <= event_targets
                        and node.get('tenant_id') == self.graph.tenant_id):
                    events.append(node)
            events.sort(key=lambda n: (n.get('sequence', 0), n['id']))
            approval_required = any(t['state'] == 'NEEDS_APPROVAL' for t in tasks)
            recovery = any(t['kind'] == 'recover' and t['state'] == 'VERIFIED' for t in tasks)
            delivery = any(t['kind'] == 'deliver' and t['state'] == 'VERIFIED' for t in tasks)
            return {'schema_version': 1, 'revision': root.get('graph_version', 0) * 1000000000 + native['world_tick'],
                'episode_id': native['episode_id'], 'scenario': self.manifest['scenario'] if self.manifest else None,
                'world_tick': native['world_tick'], 'graph_version': root.get('graph_version', 0),
                'policy_epoch': root.get('policy_epoch', 0), 'coordinator_epoch': root.get('coordinator_epoch', 0),
                'dispatch_sequence': root.get('dispatch_sequence', 0), 'dispatch_ready': self.ready(),
                'hold_reason': native['hold_reason'] or 'RUNTIME_INTEGRATION_INCOMPLETE',
                'operator_mode': 'inspection_only', 'model_mode': 'disabled', 'sensor_mode': 'S0',
                'robots': robots, 'tasks': tasks, 'commands': commands, 'observations': observations,
                'restrictions': restrictions, 'sources': source_nodes, 'events': events,
                'approval_required': approval_required, 'release_id': self.manifest['release_id'] if self.manifest else None,
                'metrics': {'delivery_completed': int(delivery), 'recovery_verified': int(recovery),
                            'unauthorized_executed': None}}

    @staticmethod
    def _unique_nodes(snapshot):
        nodes = snapshot['nodes']
        identifiers = [node.get('id') for node in nodes]
        if (any(not isinstance(identifier, str) or not identifier for identifier in identifiers)
                or len(identifiers) != len(set(identifiers))):
            raise ValueError('ambiguous canonical node identity')
        return {node['id']: node for node in nodes}

    def source(self, revision_id):
        snapshot = self._snapshot()
        by_id = self._unique_nodes(snapshot)
        active_ids = self._active_manifest_ids(by_id)
        return self._source_from_snapshot(revision_id, snapshot, by_id, active_ids)

    def _active_manifest_ids(self, by_id):
        if self.manifest is None:
            return set()
        episode = by_id.get(self.manifest.get('episode_id'))
        if (episode is None or episode['labels'] != ['Episode']
                or episode.get('tenant_id') != self.graph.tenant_id):
            raise ValueError('active manifest episode is missing or ambiguous')
        try:
            retained = json.loads(episode['payload_json'])['result']
            node_ids, task_ids = retained['node_ids'], retained['task_ids']
            if retained != self.manifest:
                raise ValueError('active manifest disagrees with retained episode')
            for identifiers in (node_ids, task_ids):
                if (not isinstance(identifiers, list)
                        or any(not isinstance(i, str) or not i for i in identifiers)
                        or len(identifiers) != len(set(identifiers))):
                    raise ValueError('invalid active manifest identities')
            if (retained['episode_id'] not in node_ids or not set(task_ids) <= set(node_ids)
                    or not set(node_ids) <= by_id.keys()):
                raise ValueError('active manifest membership is incomplete')
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError('invalid retained active manifest') from exc
        return set(node_ids)

    def _source_from_snapshot(self, revision_id, snapshot, by_id, active_ids):
        revisions = [n for n in snapshot['nodes'] if n.get('revision_id') == revision_id]
        if not revisions:
            raise KeyError(revision_id)
        if len(revisions) != 1 or revisions[0]['labels'] != ['Revision']:
            raise ValueError('ambiguous source revision')
        revision = revisions[0]
        links = [e for e in snapshot['edges'] if e['source_id'] == revision['id']
                 and e['relationship'] == 'REVISION_OF']
        if len(links) != 1 or links[0]['target_id'] not in by_id:
            raise ValueError('source revision is unlinked or ambiguous')
        source = by_id[links[0]['target_id']]
        if (source['labels'] != ['Source']
                or any(n.get('tenant_id') != self.graph.tenant_id for n in (source, revision))):
            raise ValueError('invalid source graph chain')
        if source['id'] not in active_ids or revision['id'] not in active_ids:
            raise ValueError('source revision is outside the active manifest')
        spans = [by_id[e['source_id']] for e in snapshot['edges']
                 if e['relationship'] == 'IN_REVISION' and e['target_id'] == revision['id']
                 and e['source_id'] in active_ids]
        if not spans or any(n['labels'] != ['EvidenceSpan']
                            or n.get('tenant_id') != self.graph.tenant_id for n in spans):
            raise ValueError('source revision has no valid active manifest evidence chain')
        retained = self.sources.get(revision_id)
        for span in spans:
            span_links = [e for e in snapshot['edges'] if e['source_id'] == span['id']
                          and e['relationship'] == 'IN_REVISION']
            if len(span_links) != 1:
                raise ValueError('ambiguous active manifest evidence chain')
            self.sources.validate_span(revision_id, span['start_char'], span['end_char'], span['quote'])
        if (source.get('source_id') != retained.source_id
                or revision.get('content_hash') != retained.bytes_hash
                or revision.get('normalized_hash') != retained.normalized_hash
                or revision.get('normalizer_version') != retained.normalizer_version):
            raise ValueError('source graph and retained artifacts disagree')
        return {'revision_id': revision_id, 'source_id': retained.source_id,
                'text': retained.text, 'normalized_hash': retained.normalized_hash,
                'normalizer_version': retained.normalizer_version}

    def witness(self, decision_id):
        from witness_fleet.graph.governance import validate_governance

        snapshot = self._snapshot()
        by_id = self._unique_nodes(snapshot)
        if decision_id not in by_id:
            raise KeyError(decision_id)
        active_ids = self._active_manifest_ids(by_id)
        if decision_id not in active_ids:
            raise ValueError('witness is outside the active manifest')
        target = by_id[decision_id]
        if (target['labels'] not in [['Decision'], ['Restriction'], ['Permission'], ['Release']]
                or target.get('tenant_id') != self.graph.tenant_id):
            raise ValueError('witness root is not a canonical policy decision')
        witnesses, errors = validate_governance(snapshot, self.sources)
        # Traverse evidence dependencies in their stored direction. Reverse
        # only producer/approval edges; a shared owner/source is not a reason
        # to import every unrelated decision into the selected witness.
        forward = {'SUPPORTED_BY', 'IN_REVISION', 'REVISION_OF', 'OWNED_BY',
                   'IMPOSES', 'GRANTS', 'LIFTS', 'APPROVED_BY', 'AUTHORIZED_BY', 'WITNESSED'}
        reverse = {'IMPOSES', 'GRANTS', 'APPROVES', 'DELIVERS'}
        selected = {decision_id}
        for _ in range(12):
            expanded = selected | {edge['target_id'] for edge in snapshot['edges']
                if edge['relationship'] in forward and edge['source_id'] in selected}
            expanded |= {edge['source_id'] for edge in snapshot['edges']
                if edge['relationship'] in reverse and edge['target_id'] in selected}
            if expanded == selected:
                break
            selected = expanded
        if not selected <= active_ids:
            raise ValueError('witness evidence extends outside the active manifest')
        edges = [edge for edge in snapshot['edges'] if edge['source_id'] in selected
                 and edge['target_id'] in selected and edge['relationship'] in forward | reverse]
        spans = []
        for node_id in sorted(selected):
            node = by_id[node_id]
            if 'EvidenceSpan' not in node['labels']:
                continue
            revision_edge = next((edge for edge in edges if edge['source_id'] == node_id
                                  and edge['relationship'] == 'IN_REVISION'), None)
            if revision_edge:
                revision = by_id[revision_edge['target_id']]
                try:
                    self._source_from_snapshot(revision['revision_id'], snapshot, by_id, active_ids)
                    checked = self.sources.validate_span(revision['revision_id'], node['start_char'],
                                                         node['end_char'], node['quote'])
                    spans.append({'revision_id': revision['revision_id'], 'start': node['start_char'],
                                  'end': node['end_char'], 'quote': checked['quote']})
                except (KeyError, ValueError, OSError):
                    errors = (*errors, 'INVALID_SOURCE_SPAN:' + node_id)
        current = next((w for w in witnesses if w.id == decision_id or w.decision_id == decision_id), None)
        return {'decision_id': decision_id, 'status': current.state if current else 'recorded',
                'reason_codes': list(errors), 'nodes': [
                    {'id': key, 'type': by_id[key]['labels'][0],
                     'label': by_id[key].get('display_name', key),
                     'properties': {k: v for k, v in by_id[key].items() if k != 'labels'}}
                    for key in sorted(selected)],
                'edges': [{'source_id': e['source_id'], 'target_id': e['target_id'],
                           'relationship': e['relationship']} for e in edges],
                'spans': spans, 'completeness': 'invalid' if errors else 'complete'}

    def command(self, command_id):
        if not any(command['command_id'] == command_id for command in self.state()['commands']):
            raise KeyError(command_id)
        return self.simulator.command(command_id)

    def episode(self, episode_id):
        if not self.manifest or episode_id != self.manifest['episode_id']:
            raise KeyError(episode_id)
        return self.graph.get_node('Episode', episode_id)

    def close(self):
        self.simulator.close()
