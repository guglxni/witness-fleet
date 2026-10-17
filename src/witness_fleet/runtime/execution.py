"""Trusted local graph-policy-native execution; no model output is authoritative."""
import json
import uuid
from datetime import UTC, datetime, timedelta

from witness_fleet.domain import (
    ActionProposal,
    Claim,
    CommandIntent,
    DispatchEvent,
    EvidenceBundle,
    VersionVector,
    canonical_json_hash,
)
from witness_fleet.graph.governance import validate_governance
from witness_fleet.policy.authorizer import authorize
from witness_fleet.runtime.command_effects import capture_command_effects
from witness_fleet.runtime.local_adapter import LocalSimulatorAdapter
from witness_fleet.runtime.observation_store import retain_observations
from witness_fleet.runtime.outcomes import OutcomeStore
from witness_fleet.runtime.storage import TransitionStore


class FleetExecution:
    """One explicit bounded execution owner around an otherwise inert console.

    Any uncertain dispatch or lost ownership latches HOLD, never retries motion.
    Callers cannot supply an ALLOW receipt or observation values.
    """
    def __init__(self, coordinator):
        self.owner = coordinator
        self.graph, self.service = coordinator.graph, coordinator.simulator
        self.transitions = TransitionStore(self.graph, holder_id=coordinator.holder_id)
        self.adapter = LocalSimulatorAdapter(self.service)

    def _hold(self, reason):
        self.service.journal.hold_admissions(reason)
        self.service._synchronize_journal_hold()
        self.service._save()

    def acquire(self):
        with self.owner._lock, self.service._lock:
            if self.owner.ready():
                return
            if self.service.status()['held'] or self.service.status()['started_commands']:
                raise ValueError('existing or held execution requires explicit reconciliation')
            root = self.graph.read_version_root()
            now = datetime.now(UTC)
            leased = self.transitions.acquire_coordinator(expected_epoch=root['coordinator_epoch'],
                holder_id=self.owner.holder_id, now_utc=now.isoformat(),
                lease_expires_at_utc=(now + timedelta(minutes=10)).isoformat(),
                event_id='barrier-' + uuid.uuid4().hex,
                effective_world_tick=self.service.status()['world_tick'])
            if leased is None:
                raise ValueError('coordinator lease unavailable')
            self._drain()
            if not self.owner.ready():
                raise ValueError('native and graph authority are not synchronized')

    def _authority(self):
        root, native = self.graph.read_version_root(), self.service.status()
        try:
            expiry = datetime.fromisoformat(root['coordinator_lease_expires_at_utc'].replace('Z', '+00:00'))
            valid = (root['coordinator_holder_id'] == self.owner.holder_id
                and root['coordinator_epoch'] == native['coordinator_epoch']
                and expiry.tzinfo is not None and expiry.utcoffset() == UTC.utcoffset(expiry)
                and expiry > datetime.now(UTC) and not native['held'])
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            self._hold('execution_authority_lost')
            raise ValueError('execution authority lost; native held')
        return root

    def _drain(self):
        for row in self.transitions.read_outbox(self.service.status()['last_sequence']):
            event = DispatchEvent.model_validate({key: row[key] for key in DispatchEvent.model_fields})
            if event.kind == 'COMMAND':
                self._authority()
                marked = self.graph.atomic_update(
                    expected_graph_version=self.graph.read_version_root()['graph_version'],
                    label='Command', node_id=event.id, attributes={'state': 'SENT'})
                if marked is None:
                    raise ValueError('dispatch CAS lost before transport')
            try:
                response = self.adapter.deliver(event)
                retained = self.adapter.event(event.id)
                wire = event.model_dump(mode='json')
                if (response['status'] != 'ACCEPTED' or retained is None
                        or any(retained[key] != wire[key] for key in wire if key != 'tenant_id')
                        or retained['status'] != 'APPLIED'):
                    raise ValueError('dispatch lacks exact applied receipt')
            except Exception:
                self._hold('dispatch_outcome_unknown')
                raise

    def _task(self, task_id):
        snapshot = self.graph.read_snapshot()
        nodes = self.owner._unique_nodes(snapshot)
        manifest = self.owner.manifest
        if task_id not in manifest['task_ids']:
            raise ValueError('task is outside active manifest')
        task = nodes[task_id]
        edges = snapshot['edges']
        if (task['labels'] != ['Task'] or task['state'] != 'READY'
                or [e['source_id'] for e in edges if e['relationship'] == 'CONTAINS'
                    and e['target_id'] == task_id] != [manifest['episode_id']]):
            raise ValueError('task is not a uniquely contained ready task')
        deps = [e['target_id'] for e in edges if e['source_id'] == task_id and e['relationship'] == 'DEPENDS_ON']
        if any(d not in manifest['task_ids'] or nodes[d]['labels'] != ['Task']
               or nodes[d]['state'] != 'VERIFIED' for d in deps):
            raise ValueError('task prerequisite is not verified')
        actors = [e['source_id'] for e in edges if e['target_id'] == task_id and e['relationship'] == 'ASSIGNED_TO']
        if len(actors) != 1 or actors[0] not in manifest['robots']:
            raise ValueError('unique native actor required')
        return task, actors[0]

    def execute_task(self, task_id, *, parameters, expected_effects, observations=()):
        with self.owner._lock, self.service._lock:
            if not self.owner.ready():
                raise ValueError('execution owner is not ready')
            task, robot = self._task(task_id)
            root = self._authority()
            now = datetime.now(UTC)
            claimed = self.graph.claim_task(task_id=task_id, robot_id=robot,
                expected_task_version=task['task_version'], coordinator_epoch=root['coordinator_epoch'],
                resource_ids=self.owner.manifest['resources'],
                lease_expires_at_utc=root['coordinator_lease_expires_at_utc'], now_utc=now.isoformat())
            if claimed is None:
                raise ValueError('task claim unavailable')
            claim_data = {key: claimed[key] for key in Claim.model_fields}
            claim_data['state'] = claim_data['state'].lower()
            claim = Claim.model_validate(claim_data)
            tick = self.service.status()['world_tick']
            payload = {'task_id': task_id, 'task_fence': claim.fence,
                       'resource_fences': dict(claim.resource_fences)}
            root = self.graph.read_version_root()
            control = self.transitions.append_control_event(event={
                'id': 'fence-' + uuid.uuid4().hex, 'kind': 'FENCE_INSTALL', 'payload': payload,
                'payload_hash': canonical_json_hash(payload), 'subject_ids': [task_id],
                'effective_world_tick': tick}, expected_graph_version=root['graph_version'])
            if control is None:
                raise ValueError('claim fence CAS lost')
            self._drain()
            if observations:
                retain_observations(self.graph, observations, episode_id=self.owner.manifest['episode_id'])
            snapshot = self.graph.read_snapshot()
            nodes = self.owner._unique_nodes(snapshot)
            root = self._authority()
            if any(root[key] != snapshot['versions'][key] for key in snapshot['versions']):
                raise ValueError('authorization snapshot changed')
            versions = VersionVector(graph_version=root['graph_version'], policy_epoch=root['policy_epoch'],
                coordinator_epoch=root['coordinator_epoch'], task_version=nodes[task_id]['task_version'],
                dependency_versions={rid: nodes[rid]['resource_version'] for rid in claim.resource_fences})
            proposal = ActionProposal(id='proposal-' + uuid.uuid4().hex, robot_id=robot,
                task_id=task_id, kind=task['kind'], parameters={**parameters, 'timeout_ticks': 2000,
                    'execution_until_tick': tick + 2000}, expected_versions=versions,
                required_predicates=tuple(json.loads(task['required_predicates'])),
                required_resource_ids=tuple(claim.resource_fences), expected_effects=expected_effects,
                corridor_id=self.owner.manifest['corridor_id'])
            witnesses, errors = validate_governance(snapshot, self.owner.sources)
            evidence = EvidenceBundle(observations=observations, planning_facts=(),
                governance_candidates=witnesses, integrity_errors=errors, versions=versions,
                completeness='complete')
            auth = authorize(proposal, evidence, claim, now_tick=tick,
                             now_utc=datetime.now(UTC), robot_type=robot)
            if auth.status != 'ALLOW':
                raise ValueError(f'policy refused task: {auth.status} {auth.reason_codes}')
            command = CommandIntent(command_id='command-' + uuid.uuid4().hex, proposal=proposal,
                payload_hash=canonical_json_hash(proposal), claim_id=claim.id, fence=claim.fence,
                resource_fences=claim.resource_fences, authorization_id=auth.authorization_id,
                policy_epoch=root['policy_epoch'], coordinator_epoch=root['coordinator_epoch'],
                dispatch_sequence=root['dispatch_sequence'] + 1, effective_world_tick=tick, authorization=auth)
            if self.transitions.prepare_command(command=command, authorization=auth,
                                                 expected_graph_version=root['graph_version']) is None:
                raise ValueError('command admission CAS lost')
            self._drain()
            while self.service.command(command.command_id)['state'] == 'RUNNING':
                self._authority()
                self.service.advance(1)
            receipt = self.service.command(command.command_id)
            if receipt['state'] != 'CONTROLLER_DONE':
                self._hold('native_command_failed')
                raise ValueError(f'native command did not complete: {receipt}')
            window = None
            if command.proposal.kind.value in {'travel', 'deliver'}:
                from services.simulator.stability import StabilityWindowCollector

                collector = StabilityWindowCollector(self.service, command)
                for _ in range(100):
                    self._authority()
                    window = collector.collect()
                    if window is not None:
                        break
                    if self.service.status()['world_tick'] >= command.proposal.parameters['execution_until_tick']:
                        break
                    self.service.advance(1)
                if window is None:
                    self._hold('native_stability_unverified')
                    raise ValueError('native arrival lacks bounded stability window')
            effects = capture_command_effects(self.service, command=command, now_utc=datetime.now(UTC),
                tenant_id=self.graph.tenant_id, stability_window=window)
            retain_observations(self.graph, effects, episode_id=self.owner.manifest['episode_id'])
            result = OutcomeStore(self.graph, self.owner.holder_id).finish(command.command_id,
                expected_graph_version=self.graph.read_version_root()['graph_version'], observations=effects,
                world_tick=self.service.status()['world_tick'])
            if result is None:
                self._hold('native_outcome_unverified')
                raise ValueError('native outcome lacks atomic retained verification')
            self.service.journal.transition_command(command.command_id, 'OUTCOME_VERIFIED')
            self.service._save()
            return result
