"""Single-owner native step service backed by authoritative durable journal receipts."""
from __future__ import annotations

import fcntl
import json
import os
import threading
import uuid
from pathlib import Path

from services.simulator.journal import Journal
from services.simulator.world import FacilityWorld
from witness_fleet.domain import CommandIntent, DispatchEvent


def _plain(value):
    """Detach native controller values into JSON-compatible receipt data."""
    if hasattr(value, 'tolist'):
        return _plain(value.tolist())
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


class SimulatorService:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._owner = (self.root / 'owner.lock').open('a+')
        try:
            fcntl.flock(self._owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._owner.close()
            raise ValueError('simulator step owner already running') from None
        self.journal = Journal(self.root / 'journal.sqlite')
        self.world = None
        self.active = {}
        self.native_results = {}
        self.started_commands = 0
        self._closed = False
        self._simulated_crash = False
        self._barrier_recovery = None
        checkpoint = self.journal.checkpoint()
        if checkpoint is not None:
            saved = json.loads(checkpoint['state_json'])
            native = saved['world']
            self.world = FacilityWorld(seed=native['seed'], scenario=native['scenario'],
                                       episode_id=native['episode_id'])
            self.world.restore(native)
            self.active = saved['active']
            self.native_results = saved.get('native_results', {})
            self.started_commands = saved['started_commands']
            if checkpoint['last_sequence'] != self.journal.applied_cursor:
                self.journal.recover_after_restart()
                if not self._restore_committed_barrier_recovery(checkpoint, native):
                    self.journal.recover_after_restart()
                    self.journal.hold_admissions('checkpoint does not cover latest admission')
                    self.world.hold('checkpoint does not cover latest admission',
                                    source_id='checkpoint:recovery')
                    self._save()
            elif not self._restore_committed_barrier_recovery(checkpoint, native):
                if self._synchronize_journal_hold():
                    self._save()

    @staticmethod
    def _is_committed_barrier_recovery(checkpoint, native):
        """Recognize the exact typed shape retained across a committed barrier crash."""
        marker = native.get('barrier_recovery') if isinstance(native, dict) else None
        return (isinstance(marker, dict) and set(marker) == {
                    'event_id', 'sequence', 'coordinator_epoch', 'payload_hash'}
                and isinstance(marker.get('event_id'), str) and bool(marker['event_id'])
                and type(marker.get('sequence')) is int and marker['sequence'] > 0
                and type(marker.get('coordinator_epoch')) is int and marker['coordinator_epoch'] >= 0
                and isinstance(marker.get('payload_hash'), str) and bool(marker['payload_hash'])
                and checkpoint.get('last_sequence') in {marker['sequence'] - 1, marker['sequence']})

    def _restore_committed_barrier_recovery(self, checkpoint, native):
        """Reinstall HOLD for one exact committed barrier, never release it at startup."""
        if not self._is_committed_barrier_recovery(checkpoint, native):
            return False
        marker = native['barrier_recovery']
        local = self.journal.event(marker['event_id'])
        identity = self.journal.identity()
        if (local is None or local['status'] != 'APPLIED'
                or local['sequence'] != marker['sequence']
                or local['payload_hash'] != marker['payload_hash']
                or local['coordinator_epoch'] != marker['coordinator_epoch']
                or local['kind'] != 'EPOCH_BARRIER'
                or self.journal.applied_cursor != marker['sequence']
                or identity['coordinator_epoch'] != marker['coordinator_epoch']
                or identity['identity_conflict']):
            return False

        # A checkpoint can precede the commit, capture the held commit, or capture
        # native release before the journal's final clear. Unknown native owners and
        # unrelated durable holds remain blockers.
        sources = native.get('hold_sources')
        allowed = {
            'trusted_local_reconciliation': 'trusted_local_reconciliation',
            'barrier:recovery': 'barrier commit requires explicit recovery',
            'journal:barrier commit requires explicit recovery':
                'barrier commit requires explicit recovery',
        }
        checkpoint_holds = (checkpoint['last_sequence'] != marker['sequence']
                            or 'barrier:recovery' in sources) if isinstance(sources, dict) else True
        if (not isinstance(sources, dict)
                or native.get('held') is not bool(sources)
                or any(key not in allowed or value != allowed[key] for key, value in sources.items())
                or (checkpoint_holds and not sources)
                or (not checkpoint_holds and sources
                    and ('barrier:recovery' not in sources
                         or 'trusted_local_reconciliation' in sources))):
            return False
        if identity['held']:
                journal_reconciliation = (
                    self.journal._meta('reconciliation_hold_epoch') == str(marker['coordinator_epoch'])
                    and not self.journal._meta('non_reconciliation_hold_reason'))
                journal_barrier = (
                    identity['hold_reason'] == 'barrier commit requires explicit recovery'
                    and self.journal._meta('non_reconciliation_hold_reason')
                        == 'barrier commit requires explicit recovery'
                    and self.journal._meta('reconciliation_hold_epoch') in (
                        '', str(marker['coordinator_epoch'])))
                if not (journal_reconciliation or journal_barrier):
                    return False
        else:
            checkpoint_row = self.journal.checkpoint()
            if not self._journal_checkpoint_matches_barrier(checkpoint_row, marker):
                return False
            if (self.journal._meta('reconciliation_hold_epoch')
                    or self.journal._meta('non_reconciliation_hold_reason')):
                return False
            self.journal.hold_admissions('barrier commit requires explicit recovery')

        self._barrier_recovery = {**marker, 'checkpoint_sequence': checkpoint['last_sequence']}
        self.world.hold('barrier commit requires explicit recovery', source_id='barrier:recovery')
        return True

    @staticmethod
    def _native_matches_active(active, native):
        """Accept a live status only when its saved skill identity belongs to this command."""
        identity = active.get('native_identity')
        return (isinstance(identity, dict)
                and isinstance(native, dict)
                and native.get('robot_id') == identity.get('robot_id')
                and native.get('kind') == identity.get('kind')
                and type(identity.get('accepted_tick')) is int
                and native.get('accepted_tick') == identity['accepted_tick'])

    def _synchronize_journal_hold(self):
        """Project journal HOLD without replacing or claiming independent native sources."""
        if self.world is None:
            return False
        identity = self.journal.identity()
        if not identity['held']:
            return False
        reason = identity['hold_reason'] or 'durable_journal_hold'
        native = self.world.checkpoint()
        recon_epoch = int(self.journal._meta('reconciliation_hold_epoch') or -1)
        source = ('trusted_local_reconciliation'
                  if reason == 'trusted_local_reconciliation'
                  and recon_epoch == identity.get('coordinator_epoch')
                  else 'journal:' + str(reason))
        if native['hold_sources'].get(source) == reason:
            return False
        self.world.hold(reason, source_id=source)
        return True

    def _save(self):
        if self.world is None:
            return
        checkpoint = _plain(self.world.checkpoint())
        saved = {'world': checkpoint, 'active': self.active,
                 'native_results': self.native_results, 'started_commands': self.started_commands}
        temporary = self.root / ('snapshot-' + uuid.uuid4().hex + '.tmp')
        with temporary.open('w') as handle:
            json.dump(saved, handle, allow_nan=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.root / 'snapshot.json')
        directory = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        from witness_fleet.domain import canonical_json_hash
        self.journal.record_checkpoint(saved, last_tick=self.world.world_tick,
            last_sequence=self.journal.applied_cursor, last_hash=canonical_json_hash(saved))

    def create_episode(self, episode_id, scenario, seed):
        with self._lock:
            if self.world is not None:
                if (self.world.episode_id, self.world.scenario, self.world.seed) != (episode_id, scenario, seed):
                    raise ValueError('retained episode cannot be replaced')
                return self.status()
            if not isinstance(episode_id, str) or not episode_id or type(seed) is not int:
                raise ValueError('explicit episode and integer seed required')
            self.world = FacilityWorld(seed=seed, scenario=scenario, episode_id=episode_id)
            self._synchronize_journal_hold()
            self._save()
            return self.status()

    def load_payload(self, robot_id, payload_id):
        """Explicit local fixture setup before motion; no caller-supplied physics."""
        with self._lock:
            if self.world is None:
                raise ValueError('episode required')
            native = self.world.checkpoint()
            if native['payload_loaded']:
                if robot_id != 'courier' or native['payload_id'] != payload_id:
                    raise ValueError('retained payload cannot be replaced')
                return {'status': 'loaded', 'payload_id': payload_id, 'robot_id': robot_id,
                        'world_tick': self.world.world_tick}
            if self.started_commands != 0 or self.world.world_tick != 0:
                raise ValueError('payload fixture must be loaded before execution')
            result = self.world.load_payload(robot_id, payload_id)
            if result['status'] != 'loaded':
                raise ValueError(result['reason'])
            self._save()
            return {**result, 'world_tick': self.world.world_tick}

    def _trusted_barrier_resume(self, event, *, provenance_identity, revalidate, fault_at=None):
        """Private trusted-only admission, native owner release, and checkpoint boundary."""
        from witness_fleet.domain import DispatchEvent
        from witness_fleet.runtime.barrier_resume import InjectedBarrierCrash

        if not isinstance(event, DispatchEvent):
            raise ValueError('typed immutable DispatchEvent required')
        if fault_at not in {None, 'before_admission', 'after_journal_commit',
                            'before_native_release', 'after_native_release'}:
            raise ValueError('unsupported barrier admission fault point')
        with self._lock:
            if self.world is None:
                raise ValueError('episode required')
            identity = self.journal.identity()
            world = self.world.checkpoint()
            sources = world['hold_sources']
            if (identity['held'] is not True or identity['identity_conflict']
                    or identity['hold_reason'] != 'trusted_local_reconciliation'
                    or self.journal._meta('non_reconciliation_hold_reason')
                    or world['held'] is not True
                    or sources.get('trusted_local_reconciliation') != 'trusted_local_reconciliation'
                    or set(sources) != {'trusted_local_reconciliation'}):
                raise ValueError('only the exact reconciliation-owned HOLD can resume')
            if (not isinstance(provenance_identity, tuple) or len(provenance_identity) != 4
                    or provenance_identity[0] != event.tenant_id
                    or not isinstance(provenance_identity[1], str) or not provenance_identity[1]
                    or provenance_identity[2] != event.coordinator_epoch
                    or provenance_identity[3] != event.payload.get('lease_expires_at_utc')):
                raise ValueError('graph barrier provenance identity does not match event')
            if (event.sequence != self.journal.applied_cursor + 1
                    or event.coordinator_epoch != identity['coordinator_epoch']
                    or self.journal._meta('reconciliation_hold_epoch') != str(event.coordinator_epoch)):
                return {'status': 'HOLD', 'reason_codes': ['BARRIER_NOT_NEXT_RECONCILIATION_CURSOR']}
            marker = {'event_id': event.id, 'sequence': event.sequence,
                      'coordinator_epoch': event.coordinator_epoch,
                      'payload_hash': event.payload_hash}
            if fault_at == 'before_admission':
                self._simulated_crash = True
                raise InjectedBarrierCrash('injected process stop before journal admission')
            if revalidate() != provenance_identity:
                raise ValueError('coordinator lease changed immediately before barrier admission')
            # Persist evidence before commit so a process stop in the SQLite/checkpoint gap
            # can be distinguished from arbitrary cursor drift without granting auto-resume.
            self.world.mark_barrier_recovery(marker)
            self._save()
            received = self.journal.register(event.model_dump(mode='json'))
            if received['status'] not in {'ACCEPTED', 'REPLAY'}:
                self.world.mark_barrier_recovery(None)
                self._save()
                return {'status': 'HOLD', 'reason_codes': ['BARRIER_NOT_NEXT_CURSOR']}
            admitted = self.journal._admit_reconciliation_barrier(
                event.model_dump(mode='json'), current_tick=self.world.world_tick)
            if admitted['status'] != 'ACCEPTED':
                self.world.mark_barrier_recovery(None)
                self._save()
                return admitted
            self._barrier_recovery = {**marker, 'checkpoint_sequence': event.sequence - 1}
            if fault_at == 'after_journal_commit':
                # Crash at the actual journal/checkpoint gap. Startup must reconstruct
                # an admission HOLD from the retained marker and applied receipt.
                self._simulated_crash = True
                raise InjectedBarrierCrash('injected process stop after journal commit before native release')
            try:
                current = revalidate()
                if current != provenance_identity:
                    raise ValueError('coordinator lease changed after barrier commit')
                if fault_at == 'before_native_release':
                    self._simulated_crash = True
                    raise InjectedBarrierCrash('injected process stop before native release')
                cleared = self.world.clear_hold_source(
                    'trusted_local_reconciliation', expected_reason='trusted_local_reconciliation')
                if cleared['status'] != 'ok':
                    raise ValueError('native reconciliation hold source could not be cleared')
                if fault_at == 'after_native_release':
                    self._simulated_crash = True
                    raise InjectedBarrierCrash('injected process stop after native release before checkpoint')
                current = revalidate()
                if current != provenance_identity:
                    raise ValueError('coordinator lease changed before native checkpoint')
                self._save()
                self.journal._complete_reconciliation_barrier(event.model_dump(mode='json'))
                self.world.mark_barrier_recovery(None)
                self._save()
                self._barrier_recovery = None
                return admitted
            except InjectedBarrierCrash:
                # Faults are modeled as process termination, not ordinary cleanup.
                self._simulated_crash = True
                raise
            except Exception:
                # A committed cursor is never rewound; detected failures latch both owners.
                self.journal.hold_admissions('barrier commit requires explicit recovery')
                self.world.hold('barrier commit requires explicit recovery', source_id='barrier:recovery')
                self.world.mark_barrier_recovery(marker)
                self._save()
                raise

    def _assert_no_command_history(self):
        if (self.journal._db.execute("SELECT 1 FROM commands LIMIT 1").fetchone()
                or self.journal._db.execute("SELECT 1 FROM command_history LIMIT 1").fetchone()):
            raise ValueError('prior command history blocks committed barrier recovery')

    def _recover_committed_barrier(self, event, *, provenance_identity, revalidate, fault_at=None):
        """Explicitly complete only the exact known committed barrier after restart."""
        from witness_fleet.domain import DispatchEvent
        from witness_fleet.runtime.barrier_resume import InjectedBarrierCrash

        if not isinstance(event, DispatchEvent):
            raise ValueError('typed immutable DispatchEvent required')
        if fault_at not in {None, 'after_held_checkpoint', 'after_release_checkpoint'}:
            raise ValueError('unsupported barrier recovery fault point')
        with self._lock:
            if self.world is None or self._barrier_recovery is None:
                raise ValueError('no exact committed barrier is available for explicit recovery')
            marker = {key: self._barrier_recovery[key] for key in
                      ('event_id', 'sequence', 'coordinator_epoch', 'payload_hash')}
            local = self.journal.event(event.id)
            checkpoint = self.journal.checkpoint()
            native = self.world.checkpoint()
            if checkpoint is None or local is None:
                raise ValueError('committed barrier recovery proof is unavailable')
            if (marker['event_id'] != event.id or marker['sequence'] != event.sequence
                    or marker['coordinator_epoch'] != event.coordinator_epoch
                    or marker['payload_hash'] != event.payload_hash
                    or local['status'] != 'APPLIED' or local['sequence'] != event.sequence
                    or local['payload_hash'] != event.payload_hash
                    or local['coordinator_epoch'] != event.coordinator_epoch
                    or local['kind'] != 'EPOCH_BARRIER'
                    or self.journal.applied_cursor != event.sequence
                    or self.journal.identity()['coordinator_epoch'] != event.coordinator_epoch
                    or checkpoint['last_sequence'] not in {event.sequence - 1, event.sequence}
                    or native['barrier_recovery'] != marker
                    or self.journal.identity()['identity_conflict']):
                raise ValueError('committed barrier recovery proof is incomplete or inconsistent')
            completed = (checkpoint['last_sequence'] == event.sequence
                         and not native['held'] and not native['hold_sources']
                         and not self.journal.identity()['held']
                         and self._journal_checkpoint_matches_barrier(checkpoint, marker))
            if completed:
                if native['barrier_recovery'] != marker:
                    raise ValueError('completed checkpoint lacks exact barrier recovery marker')
                if revalidate() != provenance_identity:
                    raise ValueError('coordinator lease changed during explicit recovery')
                self.world.mark_barrier_recovery(None)
                self._save()
                self._barrier_recovery = None
                return {'status': 'RECOVERED', 'event_id': event.id, 'cursor': event.sequence}
            if checkpoint['last_sequence'] != event.sequence:
                if (not native['held'] or set(native['hold_sources']) not in (
                        {'trusted_local_reconciliation', 'barrier:recovery'},
                        {'trusted_local_reconciliation', 'barrier:recovery',
                         'journal:barrier commit requires explicit recovery'})):
                    raise ValueError('held checkpoint recovery has unrelated hold sources')
            elif (native['held'] and set(native['hold_sources']) not in (
                    {'barrier:recovery'},
                    {'barrier:recovery', 'trusted_local_reconciliation'},
                    {'barrier:recovery', 'journal:barrier commit requires explicit recovery'},
                    {'barrier:recovery', 'trusted_local_reconciliation',
                     'journal:barrier commit requires explicit recovery'})):
                raise ValueError('released checkpoint recovery lacks exact barrier HOLD')
            elif not native['held'] and native['hold_sources']:
                raise ValueError('released checkpoint recovery has inconsistent hold sources')
            identity = self.journal.identity()
            journal_reconciliation_owned = (
                identity['held'] is True
                and self.journal._meta('reconciliation_hold_epoch') == str(event.coordinator_epoch)
                and not self.journal._meta('non_reconciliation_hold_reason')
            )
            journal_admission_committed = (
                identity['held'] is True
                and identity['hold_reason'] == 'barrier commit requires explicit recovery'
                and self.journal._meta('non_reconciliation_hold_reason') == 'barrier commit requires explicit recovery'
            )
            if (not (journal_reconciliation_owned or journal_admission_committed)
                    or identity['coordinator_epoch'] != event.coordinator_epoch
                    or identity['identity_conflict']):
                raise ValueError('unrelated journal HOLD blocks explicit recovery')
            if (self.journal._db.execute("SELECT 1 FROM commands LIMIT 1").fetchone()
                    or self.journal._db.execute("SELECT 1 FROM command_history LIMIT 1").fetchone()):
                raise ValueError('prior command history blocks committed barrier recovery')
            if (not isinstance(provenance_identity, tuple) or len(provenance_identity) != 4
                    or provenance_identity[0] != event.tenant_id
                    or provenance_identity[2] != event.coordinator_epoch
                    or provenance_identity[3] != event.payload.get('lease_expires_at_utc')):
                raise ValueError('graph barrier recovery provenance does not match event')
            if checkpoint['last_sequence'] != event.sequence:
                # The prior checkpoint is before the barrier commit. Persist a recovered
                # HOLD at the exact cursor, then release and checkpoint in phase two.
                self.world.hold('barrier commit requires explicit recovery', source_id='barrier:recovery')
                self._save()
                if fault_at == 'after_held_checkpoint':
                    self._simulated_crash = True
                    raise InjectedBarrierCrash('injected process stop after held recovery checkpoint')
                if revalidate() != provenance_identity:
                    raise ValueError('coordinator lease changed during explicit recovery')
                self.world.clear_hold_source(
                    'trusted_local_reconciliation', expected_reason='trusted_local_reconciliation')
                self.world.clear_hold_source(
                    'barrier:recovery', expected_reason='barrier commit requires explicit recovery')
                self.world.clear_hold_source(
                    'journal:barrier commit requires explicit recovery',
                    expected_reason='barrier commit requires explicit recovery')
                if self.world.checkpoint()['held']:
                    raise ValueError('unrelated native hold blocks release')
                self._save()
                if fault_at == 'after_release_checkpoint':
                    self._simulated_crash = True
                    raise InjectedBarrierCrash('injected process stop after release checkpoint')
                if revalidate() != provenance_identity:
                    self.journal.hold_admissions('barrier recovery lease changed')
                    self.world.hold('barrier recovery lease changed', source_id='barrier:recovery')
                    self._save()
                    raise ValueError('coordinator lease changed before recovery completion')
                self.journal._complete_reconciliation_barrier(event.model_dump(mode='json'))
                self.world.mark_barrier_recovery(None)
                self._save()
                self._barrier_recovery = None
                return {'status': 'RECOVERED', 'event_id': event.id, 'cursor': event.sequence}

            if (not native['held']
                    and not self._journal_checkpoint_matches_barrier(checkpoint, marker)):
                raise ValueError('released checkpoint does not retain exact barrier recovery marker')
            if native['held']:
                # Recovery may have crashed just after native release, before the
                # exact released checkpoint reached disk. Hold, then retry phase two.
                self.world.hold('barrier commit requires explicit recovery', source_id='barrier:recovery')
                self._save()
                if fault_at == 'after_held_checkpoint':
                    self._simulated_crash = True
                    raise InjectedBarrierCrash('injected process stop after held recovery checkpoint')
                if revalidate() != provenance_identity:
                    raise ValueError('coordinator lease changed during explicit recovery')
                self.world.clear_hold_source(
                    'trusted_local_reconciliation', expected_reason='trusted_local_reconciliation')
                self.world.clear_hold_source(
                    'barrier:recovery', expected_reason='barrier commit requires explicit recovery')
                self.world.clear_hold_source(
                    'journal:barrier commit requires explicit recovery',
                    expected_reason='barrier commit requires explicit recovery')
                if self.world.checkpoint()['held']:
                    raise ValueError('unrelated native hold blocks release')
                self._save()
                if fault_at == 'after_release_checkpoint':
                    self._simulated_crash = True
                    raise InjectedBarrierCrash('injected process stop after release checkpoint')
                if revalidate() != provenance_identity:
                    raise ValueError('coordinator lease changed before recovery completion')
                self.journal._complete_reconciliation_barrier(event.model_dump(mode='json'))
                self.world.mark_barrier_recovery(None)
                self._save()
                self._barrier_recovery = None
                return {'status': 'RECOVERED', 'event_id': event.id, 'cursor': event.sequence}

            # Native world is released and matching release checkpoint is durable.
            # The journal latch can now be cleared.
            if identity['held']:
                if revalidate() != provenance_identity:
                    raise ValueError('coordinator lease changed before recovery completion')
                self.journal._complete_reconciliation_barrier(event.model_dump(mode='json'))
            self.world.mark_barrier_recovery(None)
            self._save()
            self._barrier_recovery = None
            return {'status': 'RECOVERED', 'event_id': event.id, 'cursor': event.sequence}

    @staticmethod
    def _journal_checkpoint_matches_barrier(checkpoint, marker):
        """Prove the durable journal checkpoint contains exact native release state."""
        if checkpoint is None or checkpoint['last_sequence'] != marker['sequence']:
            return False
        try:
            state = json.loads(checkpoint['state_json'])
        except (TypeError, ValueError):
            return False
        native = state.get('world') if isinstance(state, dict) else None
        return (isinstance(native, dict)
                and native.get('held') is False
                and native.get('hold_sources') == {}
                and native.get('barrier_recovery') == marker)

    def receive(self, event):
        with self._lock:
            if self.world is None:
                raise ValueError('episode required')
            event = event if isinstance(event, DispatchEvent) else DispatchEvent.model_validate(event)
            if self.world.checkpoint()['held'] or self.journal.identity()['held']:
                return {'status': 'HOLD', 'reason_codes': ['INGRESS_HELD']}
            received = self.journal.register(event.model_dump(mode='json'))
            if received['status'] != 'ACCEPTED':
                durable_event = self.journal.event(event.id)
                if (received['status'] in {'REPLAY', 'GAP'} and durable_event is not None
                        and durable_event['status'] == 'RECEIVED'):
                    self.journal.hold_admissions('unadmitted_event_replay')
                    self._synchronize_journal_hold()
                    self._save()
                    return {'status': 'HOLD', 'reason_codes': ['UNADMITTED_EVENT_REPLAY']}
                if self._synchronize_journal_hold():
                    self._save()
                return received
            command = None
            if event.kind == 'COMMAND':
                command = CommandIntent.model_validate(event.payload)
                prepared = self.journal.record_command(command.command_id, event.payload_hash,
                                                       'PREPARED', event_id=event.id)
                if prepared['status'] == 'CONFLICT':
                    if self._synchronize_journal_hold():
                        self._save()
                    return prepared
            admitted = self.journal.admit_next(event.id, current_tick=self.world.world_tick,
                                               hold_on_rejection=True)
            if admitted['status'] != 'ACCEPTED':
                if self._synchronize_journal_hold():
                    self._save()
                return admitted
            if event.kind == 'REVOCATION':
                # Consume the ordered policy change, then halt under the same
                # step-owner lock before any subsequent physics tick can occur.
                self.journal.hold_admissions('policy_revoked')
                self._synchronize_journal_hold()
                for identifier, active in self.active.items():
                    if self.journal.receipt(identifier)['state'] == 'RUNNING':
                        native = self.world.skill_status(active['robot'])
                        if self._native_matches_active(active, native):
                            self.native_results[identifier] = _plain(native)
                        self.journal.transition_command(identifier, 'CANCELLED')
            if command is not None:
                robot = command.proposal.robot_id
                parameters = dict(command.proposal.parameters)
                timeout = parameters.get('timeout_ticks', 2000)
                deadline = parameters.get('execution_until_tick', command.authorization.valid_until_tick)
                if (type(timeout) is not int or timeout < 1
                        or type(deadline) is not int or deadline <= self.world.world_tick
                        or ('execution_until_tick' in parameters
                            and deadline > command.effective_world_tick + min(timeout, 2000))):
                    # The immutable ordered event stays consumed; a durable FAILED
                    # receipt removes ambiguity and makes replay harmless.
                    started = {'status':'rejected', 'reason':'invalid_native_parameters'}
                else:
                    parameters['timeout_ticks'] = min(timeout, 2000, deadline - self.world.world_tick)
                    try:
                        started = self.world.start_skill(robot, command.proposal.kind.value, parameters)
                    except (TypeError, ValueError):
                        # The immutable ordered event stays consumed; a durable FAILED
                        # receipt removes ambiguity and makes replay harmless.
                        started = {'status':'rejected', 'reason':'invalid_native_parameters'}
                active: dict = {'robot': robot, 'event_id': event.id,
                                'payload_hash': event.payload_hash}
                if started['status'] != 'rejected':
                    identity = dict(started)
                    identity['kind'] = command.proposal.kind.value
                    active['native_identity'] = identity
                self.active[command.command_id] = active
                if started['status'] == 'rejected':
                    self.native_results[command.command_id] = _plain(started)
                    self.journal.transition_command(command.command_id, 'FAILED')
                else:
                    self.native_results[command.command_id] = _plain(self.world.skill_status(robot))
                    self.started_commands += 1
                    self.journal.transition_command(command.command_id, 'RUNNING')
            if self._synchronize_journal_hold():
                self._save()
            self._save()
            if command is not None:
                admitted['command_state'] = self.journal.receipt(command.command_id)['state']
            return admitted

    def advance(self, ticks):
        if type(ticks) is not int or not 1 <= ticks <= FacilityWorld.MAX_STEP_BATCH:
            raise ValueError('bounded exact integer ticks required')
        with self._lock:
            if self.world is None:
                raise ValueError('episode required')
            if self._synchronize_journal_hold():
                self._save()
            if self.world.checkpoint()['held'] or self.journal.identity()['held']:
                return self.status()
            for _ in range(ticks):
                self.world.step()
                for identifier, active in self.active.items():
                    receipt = self.journal.receipt(identifier)
                    if receipt['state'] != 'RUNNING':
                        continue
                    native = self.world.skill_status(active['robot'])
                    if not self._native_matches_active(active, native):
                        continue
                    self.native_results[identifier] = _plain(native)
                    if native['status'] == 'done':
                        self.journal.transition_command(identifier, 'CONTROLLER_DONE')
                    elif native['status'] in {'failed', 'timed_out', 'cancelled'}:
                        state = 'CANCELLED' if native['status'] == 'cancelled' else 'FAILED'
                        self.journal.transition_command(identifier, state)
            self._save()
            return self.status()

    def command(self, identifier):
        with self._lock:
            receipt = self.journal.receipt(identifier)
            if identifier in self.native_results:
                receipt['native'] = _plain(self.native_results[identifier])
            elif (identifier in self.active and self.world is not None
                    and receipt.get('state') == 'RUNNING'):
                active = self.active[identifier]
                native = self.world.skill_status(active['robot'])
                if self._native_matches_active(active, native):
                    receipt['native'] = _plain(native)
            return receipt

    def event(self, event_id):
        """Read an original durable event identity and local disposition without side effects."""
        if not isinstance(event_id, str) or not event_id:
            raise ValueError('non-empty event identifier required')
        with self._lock:
            event = self.journal.event(event_id)
            if event is None:
                return {'status': 'NOT_FOUND', 'event_id': event_id}
            return {'status': 'KNOWN', 'event': event}

    def status(self):
        with self._lock:
            if self._synchronize_journal_hold():
                self._save()
            identity = self.journal.identity()
            native = self.world.checkpoint() if self.world else {}
            native_held = native.get('held', False)
            combined_held = identity['held'] or native_held
            return {**identity, 'held': combined_held,
                    'dispatch_ready': not combined_held,
                    'hold_reason': (native.get('hold_reason') if native_held
                                    else identity['hold_reason']),
                    'last_sequence': self.journal.applied_cursor,
                    'started_commands': self.started_commands,
                    'episode_id': self.world.episode_id if self.world else None,
                    'world_tick': self.world.world_tick if self.world else 0,
                    'poses': self.world.poses() if self.world else {},
                    'checkpoint_available': (self.root / 'snapshot.json').exists()}

    def scene_snapshot(self):
        """Return a detached, read-only scene DTO under the native owner lock."""
        with self._lock:
            if self.world is None:
                return {'status': 'unavailable'}
            from services.simulator.visualization import project_scene_snapshot
            return project_scene_snapshot(self.world)

    def observations(self):
        with self._lock:
            if self.world is None:
                raise ValueError('episode required')
            return {'robots': {robot: self.world.inspect(robot) for robot in self.world.ROBOT_IDS}}

    def close(self):
        with self._lock:
            if self._closed:
                return
            if not self._simulated_crash:
                self._save()
            if self.world is not None:
                self.world.close()
            self.journal.close()
            fcntl.flock(self._owner, fcntl.LOCK_UN)
            self._owner.close()
            self._closed = True
