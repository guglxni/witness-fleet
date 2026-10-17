"""Explicit local SC-001 mission; no automatic owner release or restart takeover."""
import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime

from witness_fleet.runtime.approval import ApprovalCommand, TrustedLocalPrincipal
from witness_fleet.runtime.approval_writer import ApprovalWriter
from witness_fleet.runtime.coordinator import Coordinator
from witness_fleet.runtime.effects import capture_recovery_verification
from witness_fleet.runtime.execution import FleetExecution
from witness_fleet.runtime.observation_store import retain_observations
from witness_fleet.runtime.sensing import capture_evidence


class MissionController(Coordinator):
    """Opt-in simulation demo with a configured synthetic maintenance owner.

    HTTP callers cannot supply an actor, evidence values, task targets or ALLOW.
    The local UI represents the demo owner, not production authentication.
    """
    def __init__(self, graph, sources, simulator):
        super().__init__(graph, sources, simulator)
        if not self.manifest or self.manifest.get('profile') != 'mission-v2':
            raise ValueError('mission-v2 manifest required for local mission')
        self._operation = threading.Lock()
        self.runner = FleetExecution(self)
        self.principal = TrustedLocalPrincipal(actor_id=self.manifest['owners'][0],
            tenant_id=graph.tenant_id, role='maintenance_owner', trust_mode='configured_local')

    @staticmethod
    def _event(value):
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise ValueError('bounded explicit event identity required')
        return value

    def _recovery_command(self):
        for command in super().state()['commands']:
            if command['kind'] == 'recover' and command['state'] == 'OUTCOME_VERIFIED':
                return command['command_id']
        raise ValueError('verified recovery prerequisite required')

    def _observe(self, actor, *, recovery=False):
        args = dict(tenant_id=self.graph.tenant_id,
            corridor_id=self.manifest['corridor_id'], release_id=self.manifest['release_id'],
            now_utc=datetime.now(UTC), observer_ids=(actor,))
        observations = capture_evidence(self.simulator, **args)
        if recovery:
            observations += capture_recovery_verification(self.simulator,
                command_id=self._recovery_command(), **args)
        return observations

    def _phase(self, state):
        tasks = {t['id']: t for t in state['tasks']}
        plan = self.manifest['task_plan']
        if all(tasks[p['task_id']]['state'] == 'VERIFIED' for p in plan):
            return 'complete'
        if self.simulator.status()['held']:
            return 'held'
        first_done = all(tasks[p['task_id']]['state'] == 'VERIFIED' for p in plan[:4])
        released = self.graph.get_node('Release', self.manifest['release_id'])['state'] == 'released'
        if first_done and not released:
            return 'awaiting_owner_release'
        return 'courier_delivery' if released else 'recovery_and_verification'

    def state(self):
        state = super().state()
        phase = self._phase(state)
        state.update(operator_mode='local_mission', mission_phase=phase,
            approval_required=phase == 'awaiting_owner_release',
            hold_reason=self.simulator.status()['hold_reason'],
            local_owner_id=self.principal.actor_id)
        return state

    def _next(self):
        state = self.state()
        if state['mission_phase'] in {'complete', 'awaiting_owner_release'}:
            return False
        if state['mission_phase'] == 'held':
            raise ValueError('mission held; explicit reconciliation required')
        self.runner.acquire()
        states = {t['id']: t['state'] for t in state['tasks']}
        for entry in self.manifest['task_plan']:
            if states[entry['task_id']] == 'VERIFIED':
                continue
            observations = ()
            if entry['kind'] == 'recover':
                observations = self._observe('recovery')
            elif entry['kind'] == 'deliver':
                observations = self._observe('courier', recovery=True)
            self.runner.execute_task(entry['task_id'], parameters=entry['parameters'],
                expected_effects=tuple(entry['expected_effects']), observations=observations)
            return True
        return False

    def _request(self, event_id, intent, execute):
        """Durable at-most-once admission, not a replacement for graph authority.

        Reserve BEFORE any native work. A crash/exception leaves a durable PENDING
        record, so an unknown outcome never re-executes. The simulator's owner
        lock excludes another process; SQLite also arbitrates concurrent callers.
        """
        payload = json.dumps({'episode_id': self.manifest['episode_id'], **intent},
                             sort_keys=True, separators=(',', ':'))
        with closing(sqlite3.connect(self.simulator.root / 'mission-requests.sqlite')) as db, db:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS requests ('
                       'event_id TEXT PRIMARY KEY, intent TEXT NOT NULL, result TEXT)')
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT intent,result FROM requests WHERE event_id=?',
                             (event_id,)).fetchone()
            if row:
                if row[0] != payload:
                    raise ValueError('mission request identity conflict')
                if row[1] is None:
                    self.runner._hold('mission_request_outcome_unknown')
                    raise ValueError('mission request outcome unknown; explicit reconciliation required')
                return json.loads(row[1])
            if db.execute('SELECT 1 FROM requests WHERE result IS NULL LIMIT 1').fetchone():
                self.runner._hold('mission_request_outcome_unknown')
                raise ValueError('unresolved mission request; explicit reconciliation required')
            db.execute('INSERT INTO requests(event_id,intent) VALUES (?,?)',
                       (event_id, payload))
            db.commit()
        try:
            result = execute()
            encoded = json.dumps(result, sort_keys=True, separators=(',', ':'))
            with closing(sqlite3.connect(self.simulator.root / 'mission-requests.sqlite')) as db, db:
                db.execute('PRAGMA synchronous=FULL')
                db.execute('UPDATE requests SET result=? WHERE event_id=? AND intent=? AND result IS NULL',
                           (encoded, event_id, payload))
        except BaseException:
            self.runner._hold('mission_request_outcome_unknown')
            raise
        return json.loads(encoded)

    def _run_tasks(self):
        for _ in self.manifest['task_plan']:
            if not self._next():
                break
        return self.state()

    def _step_task(self):
        self._next()
        return self.state()

    def run(self, event_id):
        self._event(event_id)
        with self._operation:
            return self._request(event_id, {'kind': 'run'}, self._run_tasks)

    def step(self, ticks, event_id):
        # Operator step means one graph-authorized task, never naked physics.
        self._event(event_id)
        if type(ticks) is not int or not 1 <= ticks <= 100000:
            raise ValueError('invalid step bound')
        with self._operation:
            return self._request(event_id, {'kind': 'step', 'ticks': ticks}, self._step_task)

    def approve_release(self, release_id, expected_policy_epoch, event_id):
        self._event(event_id)
        with self._operation, self._lock:
            state = self.state()
            if release_id != self.manifest['release_id']:
                raise ValueError('release is outside active mission')
            approval_id = 'approval-' + hashlib.sha256(event_id.encode()).hexdigest()
            existing = self.graph.get_node('ApprovalEvent', approval_id)
            if existing:
                if (existing.get('target_id') != release_id
                        or existing.get('expected_policy_epoch') != expected_policy_epoch):
                    raise ValueError('approval identity conflict')
                return state
            if type(expected_policy_epoch) is not int or expected_policy_epoch != state['policy_epoch']:
                raise ValueError('approval expected policy epoch is stale')
            if state['mission_phase'] != 'awaiting_owner_release':
                raise ValueError('recovery and scout verification prerequisites required')
            self.runner._authority()
            proof = self._observe('scout', recovery=True)
            retain_observations(self.graph, proof, episode_id=self.manifest['episode_id'])
            intent = ApprovalCommand(event_id=event_id, target_id=release_id,
                actor_id=self.principal.actor_id, tenant_id=self.graph.tenant_id,
                expected_policy_epoch=expected_policy_epoch,
                notes='Explicit local demo-owner release after retained native verification')
            ApprovalWriter(self.graph, self.sources, self.principal,
                holder_id=self.holder_id).approve_release(intent,
                    effective_world_tick=self.simulator.status()['world_tick'])
            self.runner._drain()
            return self.state()

    def hold(self, reason, event_id):
        self._event(event_id)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 512:
            raise ValueError('bounded HOLD reason required')
        with self.simulator._lock:
            self.runner._hold('operator_hold:' + reason)
        return self.state()
