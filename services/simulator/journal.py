"""Durable simulator-side receipt/outbox identity journal.

This module is intentionally independent of coordinator/domain DTOs. Events are mappings with
``id``, ``sequence``, ``payload_hash``, ``kind``, ``coordinator_epoch``,
``effective_world_tick`` and a JSON-compatible ``payload``. JSON is canonicalized (sorted keys,
compact separators) before persistence, making replay identity deterministic. A successful write
is committed under SQLite WAL + synchronous=FULL before its result is returned.

The journal records/reconciles identities; it cannot prove exactly-once physical effects or act as
planner truth. Callers must hold on uncertain recovery and inspect the simulated world as needed.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_STATES = {
    "PREPARED", "SENT", "ACCEPTED", "RUNNING", "CONTROLLER_DONE", "OUTCOME_VERIFIED",
    "FAILED", "CANCELLED", "UNKNOWN", "RECONCILED",
}
_NEXT = {
    "PREPARED": {"SENT", "ACCEPTED", "FAILED", "CANCELLED", "UNKNOWN"},
    "SENT": {"ACCEPTED", "FAILED", "CANCELLED", "UNKNOWN"},
    "ACCEPTED": {"RUNNING", "FAILED", "CANCELLED", "UNKNOWN"},
    "RUNNING": {"CONTROLLER_DONE", "FAILED", "CANCELLED", "UNKNOWN"},
    "CONTROLLER_DONE": {"OUTCOME_VERIFIED", "FAILED", "UNKNOWN"},
    "OUTCOME_VERIFIED": set(), "FAILED": set(), "CANCELLED": set(),
    "UNKNOWN": {"RECONCILED"}, "RECONCILED": set(),
}
_EVENT_FIELDS = ("id", "sequence", "payload_hash", "kind", "coordinator_epoch", "effective_world_tick", "payload")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _is_nonnegative_int(value: Any) -> bool:
    """Identity counters are JSON integer identities; bool and float aliases are invalid."""
    return type(value) is int and value >= 0


def _event_identity(event: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(event, Mapping) or any(field not in event for field in _EVENT_FIELDS):
        raise ValueError("complete original event identity required")
    identity = {field: event[field] for field in _EVENT_FIELDS}
    if (not _is_nonnegative_int(identity["sequence"]) or identity["sequence"] < 1
            or not _is_nonnegative_int(identity["coordinator_epoch"])
            or not _is_nonnegative_int(identity["effective_world_tick"])
            or not all(isinstance(identity[key], str) and identity[key] for key in ("id", "payload_hash", "kind"))):
        raise ValueError("invalid event identity")
    try:
        _json(identity)
    except (TypeError, OverflowError, ValueError) as exc:
        raise ValueError("event must be JSON serializable") from exc
    return identity


class Journal:
    """SQLite durable journal for simulator receipts, checkpoints, and cancellation disposition."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, timeout=10, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE, payload_hash TEXT NOT NULL,
                kind TEXT NOT NULL, coordinator_epoch INTEGER NOT NULL, effective_world_tick INTEGER NOT NULL,
                event_json TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS commands (
                command_id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, state TEXT NOT NULL,
                event_id TEXT, postcondition_json TEXT, last_known_state TEXT NOT NULL,
                reconciliation_state TEXT, checkpoint_id TEXT
            );
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, command_id TEXT NOT NULL,
                state TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY, state_json TEXT NOT NULL, last_tick INTEGER NOT NULL,
                last_sequence INTEGER NOT NULL, last_hash TEXT NOT NULL, postconditions_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS cancellation_proofs (
                proof_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                payload_hash TEXT NOT NULL, hold_epoch INTEGER NOT NULL, result TEXT NOT NULL,
                identity_json TEXT
            );
            CREATE TABLE IF NOT EXISTS cancellations (
                event_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE, payload_hash TEXT NOT NULL,
                hold_epoch INTEGER NOT NULL, proof_id TEXT NOT NULL UNIQUE, disposition_json TEXT NOT NULL
            );
            INSERT OR IGNORE INTO metadata(key,value) VALUES
                ('applied_cursor','0'), ('coordinator_epoch','0'), ('policy_epoch','0'),
                ('resource_fences','{}'), ('task_fences','{}'), ('held','false'),
                ('identity_conflict','false'), ('poisoned_robots','[]');
        """)
        # Additive metadata/schema migrations keep existing durable journals readable.
        self._db.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES('hold_reason','')")
        self._db.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES('reconciliation_hold_epoch','')")
        self._db.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES('non_reconciliation_hold_reason','')")
        if self._meta("held") == "true" and not self._meta("reconciliation_hold_epoch"):
            self._set_meta("non_reconciliation_hold_reason", self._meta("hold_reason"))
        proof_columns = {row[1] for row in self._db.execute("PRAGMA table_info(cancellation_proofs)")}
        if "identity_json" not in proof_columns:
            self._db.execute("ALTER TABLE cancellation_proofs ADD COLUMN identity_json TEXT")

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _transaction(self):
        self._db.execute("BEGIN IMMEDIATE")

    def _meta(self, key: str) -> str:
        row = self._db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return str(row[0])

    def _set_meta(self, key: str, value: str) -> None:
        self._db.execute("INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def _hold(self, reason: str, *, replace: bool = False,
              reconciliation_epoch: int | None = None) -> None:
        """Persist a global admission hold without allowing incidental code to release it."""
        if reason == "event_identity_conflict":
            self._set_meta("identity_conflict", "true")
        already_held = self._meta("held") == "true"
        self._set_meta("held", "true")
        if replace or not already_held or not self._meta("hold_reason"):
            self._set_meta("hold_reason", reason)
        if reconciliation_epoch is not None:
            self._set_meta("reconciliation_hold_epoch", str(reconciliation_epoch))
            self._set_meta("non_reconciliation_hold_reason", "")
        else:
            self._set_meta("reconciliation_hold_epoch", "")
            self._set_meta("non_reconciliation_hold_reason", reason)

    def _persist_identity_conflict(self, payload: Any) -> None:
        """Persist collision evidence and poison the robot named by the rejected payload."""
        robots = set(json.loads(self._meta("poisoned_robots")))
        proposal = payload.get("proposal") if isinstance(payload, Mapping) else None
        robot_id = proposal.get("robot_id") if isinstance(proposal, Mapping) else None
        if isinstance(robot_id, str) and robot_id:
            robots.add(robot_id)
        self._set_meta("identity_conflict", "true")
        self._set_meta("poisoned_robots", _json(sorted(robots)))
        self._hold("event_identity_conflict", replace=True)

    @property
    def applied_cursor(self) -> int:
        with self._lock:
            return int(self._meta("applied_cursor"))

    def register(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Durably store immutable event identity before acknowledging; gaps are retained but held."""
        if any(field not in event for field in _EVENT_FIELDS):
            raise ValueError(f"event requires fields: {_EVENT_FIELDS}")
        try:
            identity = {field: event[field] for field in _EVENT_FIELDS}
            seq = identity["sequence"]
            epoch = identity["coordinator_epoch"]
            tick = identity["effective_world_tick"]
            if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
                raise ValueError("sequence must be a positive integer")
            if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
                raise ValueError("coordinator_epoch must be a non-negative integer")
            if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
                raise ValueError("effective_world_tick must be a non-negative integer")
            if not all(isinstance(identity[k], str) and identity[k] for k in ("id", "payload_hash", "kind")):
                raise ValueError("event id, payload_hash, and kind must be non-empty strings")
            event_json, payload_json = _json(identity), _json(identity["payload"])
        except (TypeError, OverflowError) as exc:
            raise ValueError("event must be JSON serializable") from exc
        with self._lock:
            self._transaction()
            try:
                by_id = self._db.execute("SELECT event_json,sequence FROM events WHERE event_id=?", (identity["id"],)).fetchone()
                by_seq = self._db.execute("SELECT event_json,event_id,sequence FROM events WHERE sequence=?", (seq,)).fetchone()
                if by_id or by_seq:
                    existing = by_id or by_seq
                    if existing["event_json"] == event_json and existing["sequence"] == seq:
                        status = "REPLAY"
                    else:
                        status = "CONFLICT"
                        self._persist_identity_conflict(identity["payload"])
                    self._db.execute("COMMIT")
                    return {"status": status, "event_id": identity["id"], "sequence": seq}
                cursor = int(self._meta("applied_cursor"))
                gap = seq != cursor + 1
                self._db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)", (
                    identity["id"], seq, identity["payload_hash"], identity["kind"], epoch,
                    tick, event_json, payload_json, "RECEIVED",
                ))
                if gap:
                    self._hold("sequence_gap")
                self._db.execute("COMMIT")
                return {"status": "GAP" if gap else "ACCEPTED", "event_id": identity["id"], "sequence": seq}
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def event(self, event_id: str) -> dict[str, Any] | None:
        """Return an event by ID, including the original decoded payload and local receipt status."""
        with self._lock:
            row = self._db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
            if not row:
                return None
            return {"id": row["event_id"], "sequence": row["sequence"], "payload_hash": row["payload_hash"],
                    "kind": row["kind"], "coordinator_epoch": row["coordinator_epoch"],
                    "effective_world_tick": row["effective_world_tick"], "payload": json.loads(row["payload_json"]),
                    "status": row["status"]}

    def mark_applied(self, event_id: str) -> dict[str, Any]:
        """Consume only the next contiguous sequence; a disposition can consume the original as cancelled."""
        with self._lock:
            self._transaction()
            try:
                row = self._db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
                if row is None:
                    self._db.execute("COMMIT")
                    return {"status": "NOT_FOUND", "event_id": event_id}
                cursor = int(self._meta("applied_cursor"))
                if row["sequence"] != cursor + 1:
                    self._db.execute("COMMIT")
                    return {"status": "GAP", "cursor": cursor}
                cancelled = self._db.execute("SELECT * FROM cancellations WHERE event_id=?", (event_id,)).fetchone()
                if self._meta("held") == "true" and cancelled is None and row["kind"] != "EPOCH_BARRIER":
                    self._db.execute("COMMIT")
                    return {"status": "HELD", "cursor": cursor}
                applied_status = "CANCELLED" if cancelled else "APPLIED"
                self._db.execute("UPDATE events SET status=? WHERE event_id=?", (applied_status, event_id))
                if cancelled:
                    command_id = json.loads(row["payload_json"]).get("command_id")
                    if command_id:
                        command = self._db.execute("SELECT state FROM commands WHERE command_id=?", (command_id,)).fetchone()
                        if command and command["state"] in {"PREPARED", "SENT"}:
                            self._db.execute("UPDATE commands SET state='CANCELLED',last_known_state='CANCELLED',reconciliation_state=NULL WHERE command_id=?", (command_id,))
                            self._db.execute("INSERT INTO command_history(command_id,state) VALUES(?, 'CANCELLED')", (command_id,))
                self._set_meta("applied_cursor", str(row["sequence"]))
                self._db.execute("COMMIT")
                return {"status": "CANCELLED" if cancelled else "APPLIED", "cursor": row["sequence"]}
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def admit_next(self, event_id: str, *, current_tick: int, hold_on_rejection: bool = False) -> dict[str, Any]:
        """Linearize built-in bounded preflight, receipt admission and cursor.

        No arbitrary callback can run inside SQL. Replay never restarts a skill;
        only the returned ACCEPTED permission may be consumed by the step owner.
        """
        if type(hold_on_rejection) is not bool:
            raise ValueError('hold_on_rejection must be an exact bool')
        from witness_fleet.domain import DispatchEvent
        from witness_fleet.simulation.protocol import preflight

        with self._lock:
            self._transaction()
            try:
                row = self._db.execute('SELECT * FROM events WHERE event_id=?', (event_id,)).fetchone()
                if row is None:
                    self._db.execute('COMMIT')
                    return {'status': 'NOT_FOUND'}
                if row['status'] != 'RECEIVED':
                    self._db.execute('COMMIT')
                    return {'status': 'REPLAY', 'event_id': event_id, 'cursor': self.applied_cursor}
                cursor = int(self._meta('applied_cursor'))
                installed = self.identity()
                if row['sequence'] != cursor + 1:
                    self._hold('sequence_gap')
                    self._db.execute('COMMIT')
                    return {'status': 'HOLD', 'reason_codes': ['SEQUENCE_GAP']}
                if installed['held'] and row['kind'] != 'EPOCH_BARRIER':
                    self._db.execute('COMMIT')
                    return {'status': 'HOLD', 'reason_codes': ['INGRESS_HELD']}
                if installed['identity_conflict']:
                    self._db.execute('COMMIT')
                    return {'status': 'HOLD', 'reason_codes': ['IDENTITY_CONFLICT']}
                event = self.event(event_id)
                if event is None:
                    raise ValueError('event disappeared inside authoritative admission transaction')
                typed = DispatchEvent.model_validate({key: event[key] for key in _EVENT_FIELDS})
                outcome = preflight(typed, last_sequence=cursor, current_tick=current_tick,
                                    coordinator_epoch=installed['coordinator_epoch'],
                                    policy_epoch=installed['policy_epoch'],
                                    task_fences=installed['task_fences'], resource_fences=installed['resource_fences'])
                if outcome.get('status') != 'ACCEPTED':
                    if hold_on_rejection and outcome.get('status') == 'REJECTED':
                        self._hold('admission_rejected')
                        outcome = {'status': 'HOLD', 'reason_codes': outcome.get('reason_codes', [])}
                    self._db.execute('COMMIT')
                    return outcome
                if row['kind'] == 'COMMAND':
                    payload = event['payload']
                    command = self._db.execute('SELECT * FROM commands WHERE command_id=?',
                                               (payload['command_id'],)).fetchone()
                    if (command is None or command['state'] != 'PREPARED'
                            or command['event_id'] != event_id or command['payload_hash'] != row['payload_hash']
                            or self._db.execute('SELECT 1 FROM cancellations WHERE event_id=?', (event_id,)).fetchone()):
                        if hold_on_rejection:
                            self._hold('admission_rejected')
                        self._db.execute('COMMIT')
                        return {'status': 'HOLD' if hold_on_rejection else 'REJECTED',
                                'reason_codes': ['INVALID_PREPARED_RECEIPT']}
                    self._db.execute("UPDATE commands SET state='ACCEPTED',last_known_state='ACCEPTED' WHERE command_id=?",
                                     (payload['command_id'],))
                    self._db.execute("INSERT INTO command_history(command_id,state) VALUES(?, 'ACCEPTED')",
                                     (payload['command_id'],))
                elif row['kind'] == 'FENCE_INSTALL':
                    payload = event['payload']
                    self._set_meta('task_fences', _json({**installed['task_fences'], payload['task_id']: payload['task_fence']}))
                    self._set_meta('resource_fences', _json({**installed['resource_fences'], **payload['resource_fences']}))
                elif row['kind'] in {'POLICY_ACTIVATION', 'REVOCATION'}:
                    self._set_meta('policy_epoch', str(event['payload']['policy_epoch']))
                elif row['kind'] == 'EPOCH_BARRIER':
                    unresolved = self._db.execute("SELECT 1 FROM commands WHERE state IN ('SENT','UNKNOWN','ACCEPTED','RUNNING','CONTROLLER_DONE') LIMIT 1").fetchone()
                    if unresolved:
                        self._db.execute('COMMIT')
                        return {'status': 'HOLD', 'reason_codes': ['UNRESOLVED_COMMANDS']}
                    self._set_meta('coordinator_epoch', str(row['coordinator_epoch']))
                    self._set_meta('held', 'false')
                    self._set_meta('hold_reason', '')
                self._db.execute("UPDATE events SET status='APPLIED' WHERE event_id=?", (event_id,))
                self._set_meta('applied_cursor', str(row['sequence']))
                self._db.execute('COMMIT')
                return {'status': 'ACCEPTED', 'event_id': event_id, 'cursor': row['sequence']}
            except Exception:
                if self._db.in_transaction:
                    self._db.execute('ROLLBACK')
                raise

    def _admit_reconciliation_barrier(self, event_identity: Mapping[str, Any], *, current_tick: int) -> dict[str, Any]:
        """Admit only the exact next retained barrier under its owned reconciliation hold.

        This private entry point is reserved for the trusted graph adapter. The caller's
        in-process boundary, not SQLite, attests graph provenance; SQLite rechecks all local
        identity, hold, cursor, and receipt constraints atomically.
        """
        identity = _event_identity(event_identity)
        from witness_fleet.domain import DispatchEvent
        from witness_fleet.simulation.protocol import preflight

        with self._lock:
            self._transaction()
            try:
                row = self._db.execute("SELECT * FROM events WHERE event_id=?", (identity["id"],)).fetchone()
                if row is None:
                    self._db.execute("COMMIT")
                    return {"status": "NOT_FOUND"}
                if row["event_json"] != _json(identity):
                    self._db.execute("COMMIT")
                    return {"status": "HOLD", "reason_codes": ["EVENT_IDENTITY_MISMATCH"]}
                if row["status"] != "RECEIVED":
                    self._db.execute("COMMIT")
                    return {"status": "REPLAY", "event_id": identity["id"],
                            "cursor": int(self._meta("applied_cursor"))}

                cursor = int(self._meta("applied_cursor"))
                epoch = int(self._meta("coordinator_epoch"))
                if row["sequence"] != cursor + 1:
                    self._db.execute("COMMIT")
                    return {"status": "HOLD", "reason_codes": ["SEQUENCE_GAP"]}
                reconciliation_owned = (
                    self._meta('held') == 'true'
                    and self._meta('reconciliation_hold_epoch') == str(epoch)
                    and not self._meta('non_reconciliation_hold_reason'))
                if (row['kind'] != 'EPOCH_BARRIER' or row['coordinator_epoch'] != epoch
                        or not reconciliation_owned
                        or self._meta('identity_conflict') == 'true'):
                    self._db.execute("COMMIT")
                    return {"status": "HOLD", "reason_codes": ["RECONCILIATION_HOLD_REQUIRED"]}

                # Do not trust a terminal-looking enum: every prior command must have an
                # immutable NEVER_ADMITTED proof and consumed cancellation disposition.
                commands = self._db.execute("SELECT * FROM commands").fetchall()
                for command in commands:
                    if command["state"] != "CANCELLED" or not command["event_id"]:
                        self._db.execute("COMMIT")
                        return {"status": "HOLD", "reason_codes": ["UNRESOLVED_COMMANDS"]}
                    original = self._db.execute(
                        "SELECT * FROM events WHERE event_id=?", (command["event_id"],)
                    ).fetchone()
                    cancellation = self._db.execute(
                        "SELECT * FROM cancellations WHERE event_id=?", (command["event_id"],)
                    ).fetchone()
                    if original is None or cancellation is None or original["status"] != "CANCELLED":
                        self._db.execute("COMMIT")
                        return {"status": "HOLD", "reason_codes": ["UNRESOLVED_COMMANDS"]}
                    proof = self._db.execute(
                        "SELECT * FROM cancellation_proofs WHERE proof_id=?", (cancellation["proof_id"],)
                    ).fetchone()
                    original_event = json.loads(original["event_json"])
                    original_payload = original_event.get("payload")
                    if (proof is None or proof["result"] != "NEVER_ADMITTED"
                            or proof["identity_json"] is None
                            or proof["event_id"] != original["event_id"]
                            or proof["sequence"] != original["sequence"]
                            or proof["payload_hash"] != original["payload_hash"]
                            or proof["hold_epoch"] != cancellation["hold_epoch"]
                            or cancellation["sequence"] != original["sequence"]
                            or cancellation["payload_hash"] != original["payload_hash"]
                            or original_event["kind"] != "COMMAND"
                            or not isinstance(original_payload, Mapping)
                            or original_payload.get("command_id") != command["command_id"]
                            or command["payload_hash"] != original["payload_hash"]
                            or original["sequence"] > cursor):
                        self._db.execute("COMMIT")
                        return {"status": "HOLD", "reason_codes": ["UNRESOLVED_COMMANDS"]}
                # Historical rows without an associated command row are also fail-closed.
                if self._db.execute(
                        "SELECT 1 FROM command_history h LEFT JOIN commands c "
                        "ON c.command_id=h.command_id WHERE c.command_id IS NULL LIMIT 1").fetchone():
                    self._db.execute("COMMIT")
                    return {"status": "HOLD", "reason_codes": ["UNRESOLVED_COMMANDS"]}

                typed = DispatchEvent.model_validate(identity)
                outcome = preflight(
                    typed, last_sequence=cursor, current_tick=current_tick,
                    coordinator_epoch=epoch, policy_epoch=int(self._meta("policy_epoch")),
                    task_fences=json.loads(self._meta("task_fences")),
                    resource_fences=json.loads(self._meta("resource_fences")),
                    allow_reconciliation_equal_epoch=True,
                )
                if outcome.get("status") != "ACCEPTED":
                    self._db.execute("COMMIT")
                    return outcome

                self._set_meta("coordinator_epoch", str(row["coordinator_epoch"]))
                # Preserve the reconciliation owner's visible reason, while retaining
                # its epoch ownership as the exact admission latch across this commit.
                self._db.execute("UPDATE events SET status='APPLIED' WHERE event_id=?", (identity["id"],))
                self._set_meta("applied_cursor", str(row["sequence"]))
                self._db.execute("COMMIT")
                return {"status": "ACCEPTED", "event_id": identity["id"], "cursor": row["sequence"]}
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def _complete_reconciliation_barrier(self, event_identity: Mapping[str, Any]) -> dict[str, Any]:
        """Clear only the durable admission latch for one exactly applied barrier."""
        identity = _event_identity(event_identity)
        with self._lock:
            self._transaction()
            try:
                row = self._db.execute('SELECT * FROM events WHERE event_id=?',
                                       (identity['id'],)).fetchone()
                if row is None:
                    raise ValueError('exact committed barrier HOLD is required for release')
                held_for_reconciliation = (
                    self._meta('reconciliation_hold_epoch') == str(row['coordinator_epoch'])
                    and not self._meta('non_reconciliation_hold_reason'))
                held_for_recovery = (
                    self._meta('non_reconciliation_hold_reason')
                        == 'barrier commit requires explicit recovery'
                    and self._meta('reconciliation_hold_epoch') in (
                        '', str(row['coordinator_epoch'])))
                checkpoint_row = self.checkpoint()
                checkpoint_state = (json.loads(checkpoint_row['state_json'])
                                    if checkpoint_row is not None else None)
                native = checkpoint_state.get('world') if isinstance(checkpoint_state, Mapping) else None
                marker = native.get('barrier_recovery') if isinstance(native, Mapping) else None
                matching_checkpoint = (
                    checkpoint_row is not None
                    and checkpoint_row['last_sequence'] == identity['sequence']
                    and checkpoint_row['last_tick'] == row['effective_world_tick']
                    and isinstance(native, Mapping)
                    and marker == {
                        'event_id': identity['id'], 'sequence': identity['sequence'],
                        'coordinator_epoch': identity['coordinator_epoch'],
                        'payload_hash': identity['payload_hash']}
                    and native.get('held') is False and native.get('hold_sources') == {})
                if (row is None or row['event_json'] != _json(identity)
                        or row['kind'] != 'EPOCH_BARRIER' or row['status'] != 'APPLIED'
                        or row['sequence'] != int(self._meta('applied_cursor'))
                        or row['coordinator_epoch'] != int(self._meta('coordinator_epoch'))
                        or self._meta('held') != 'true'
                        or self._meta('identity_conflict') == 'true'
                        or not (held_for_reconciliation or held_for_recovery)
                        or not matching_checkpoint):
                    raise ValueError('exact committed barrier HOLD is required for release')
                self._set_meta('held', 'false')
                self._set_meta('hold_reason', '')
                self._set_meta('reconciliation_hold_epoch', '')
                self._set_meta('non_reconciliation_hold_reason', '')
                self._db.execute('COMMIT')
                return self.identity()
            except Exception:
                if self._db.in_transaction:
                    self._db.execute('ROLLBACK')
                raise

    def record_command(self, command_id: str, payload_hash: str, state: str, *, event_id: str | None = None, postcondition: Any = None) -> dict[str, Any]:
        """Commit a command receipt/history state before returning it."""
        self._validate_state(state)
        post_json = None if postcondition is None else _json(postcondition)
        with self._lock:
            self._transaction()
            try:
                row = self._db.execute("SELECT * FROM commands WHERE command_id=?", (command_id,)).fetchone()
                if row:
                    if row["payload_hash"] != payload_hash or row["event_id"] != event_id:
                        self._hold("command_receipt_conflict")
                        self._db.execute("COMMIT")
                        return {"status": "CONFLICT", "command_id": command_id}
                    if row["state"] != state:
                        self._hold("command_receipt_state_conflict")
                        self._db.execute("COMMIT")
                        raise ValueError("command already has a different state; use transition_command")
                else:
                    existing_event_command = None
                    if event_id:
                        existing_event_command = self._db.execute(
                            "SELECT command_id FROM commands WHERE event_id=?", (event_id,)
                        ).fetchone()
                    if existing_event_command is not None:
                        self._hold("command_event_identity_conflict")
                        self._db.execute("COMMIT")
                        return {"status": "CONFLICT", "command_id": command_id}
                    if event_id and self._db.execute(
                            "SELECT 1 FROM cancellations WHERE event_id=?", (event_id,)).fetchone():
                        self._hold("command_after_cancellation_conflict")
                        self._db.execute("COMMIT")
                        return {"status": "CONFLICT", "command_id": command_id}
                    self._db.execute("INSERT INTO commands VALUES(?,?,?,?,?,?,?,?)",
                                     (command_id, payload_hash, state, event_id, post_json, state, None, None))
                    self._db.execute("INSERT INTO command_history(command_id,state) VALUES(?,?)", (command_id, state))
                self._db.execute("COMMIT")
                return {"status": "RECORDED", "command_id": command_id, "state": state}
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    @staticmethod
    def _validate_state(state: str) -> None:
        if state not in _STATES:
            raise ValueError(f"unsupported command state: {state}")

    def transition_command(self, command_id: str, state: str) -> dict[str, Any]:
        """Append one legal forward state transition; UNKNOWN is resolved only as RECONCILED."""
        self._validate_state(state)
        with self._lock:
            self._transaction()
            try:
                row = self._db.execute("SELECT state,event_id FROM commands WHERE command_id=?", (command_id,)).fetchone()
                if not row:
                    self._db.execute("COMMIT")
                    return {"status": "NOT_FOUND", "command_id": command_id}
                if row["event_id"] and self._db.execute(
                        "SELECT 1 FROM cancellations WHERE event_id=?", (row["event_id"],)).fetchone():
                    self._db.execute("COMMIT")
                    raise ValueError("command cannot transition after cancellation disposition")
                if state not in _NEXT[row["state"]]:
                    self._db.execute("COMMIT")
                    raise ValueError(f"illegal command transition {row['state']} -> {state}")
                self._db.execute("UPDATE commands SET state=?,last_known_state=?,reconciliation_state=? WHERE command_id=?",
                                 (state, state if state != "UNKNOWN" else row["state"], "UNKNOWN" if state == "UNKNOWN" else None, command_id))
                self._db.execute("INSERT INTO command_history(command_id,state) VALUES(?,?)", (command_id, state))
                self._db.execute("COMMIT")
                return {"status": "RECORDED", "command_id": command_id, "state": state}
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def receipt(self, command_id: str) -> dict[str, Any]:
        """Look up local receipt; NOT_FOUND deliberately does not mean NEVER_ADMITTED."""
        with self._lock:
            row = self._db.execute("SELECT * FROM commands WHERE command_id=?", (command_id,)).fetchone()
            if not row:
                return {"status": "NOT_FOUND", "command_id": command_id}
            return {"status": "KNOWN", "command_id": command_id, "payload_hash": row["payload_hash"],
                    "state": row["state"], "event_id": row["event_id"],
                    "last_known_state": row["last_known_state"],
                    "reconciliation_state": row["reconciliation_state"], "checkpoint_id": row["checkpoint_id"]}

    def set_identity(self, *, coordinator_epoch: int, policy_epoch: int, resource_fences: Mapping[str, int], task_fences: Mapping[str, int]) -> dict[str, Any]:
        """Persist epoch and fence snapshots as simulator identity metadata."""
        if (not _is_nonnegative_int(coordinator_epoch) or not _is_nonnegative_int(policy_epoch)
                or not isinstance(resource_fences, Mapping) or not isinstance(task_fences, Mapping)
                or any(not isinstance(k, str) or not k for k in (*resource_fences.keys(), *task_fences.keys()))
                or any(not _is_nonnegative_int(v) for v in (*resource_fences.values(), *task_fences.values()))):
            raise ValueError("epochs and fences must be non-negative integers")
        with self._lock:
            self._transaction()
            try:
                old = int(self._meta("coordinator_epoch"))
                if coordinator_epoch < old:
                    raise ValueError("coordinator epoch cannot move backwards")
                if policy_epoch < int(self._meta("policy_epoch")):
                    raise ValueError("policy epoch cannot move backwards")
                prior_resources = json.loads(self._meta("resource_fences"))
                prior_tasks = json.loads(self._meta("task_fences"))
                if any(resource_fences.get(key, value) < value for key, value in prior_resources.items()):
                    raise ValueError("resource fences cannot move backwards")
                if any(task_fences.get(key, value) < value for key, value in prior_tasks.items()):
                    raise ValueError("task fences cannot move backwards")
                self._set_meta("coordinator_epoch", str(coordinator_epoch))
                self._set_meta("policy_epoch", str(policy_epoch))
                self._set_meta("resource_fences", _json({**prior_resources, **dict(resource_fences)}))
                self._set_meta("task_fences", _json({**prior_tasks, **dict(task_fences)}))
                self._db.execute("COMMIT")
                return self.identity()
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def identity(self) -> dict[str, Any]:
        with self._lock:
            return {"coordinator_epoch": int(self._meta("coordinator_epoch")),
                    "policy_epoch": int(self._meta("policy_epoch")),
                    "resource_fences": json.loads(self._meta("resource_fences")),
                    "task_fences": json.loads(self._meta("task_fences")),
                    "identity_conflict": self._meta("identity_conflict") == "true",
                    "poisoned_robots": json.loads(self._meta("poisoned_robots")),
                    "held": self._meta("held") == "true",
                    "hold_reason": self._meta("hold_reason") or None}

    def hold_admissions(self, reason: str) -> dict[str, Any]:
        """Persist a same-epoch, same-cursor admission hold without changing receipts."""
        if (not isinstance(reason, str) or not reason or len(reason) > 256
                or any(ord(character) < 32 or ord(character) == 127 for character in reason)):
            raise ValueError('hold reason must be a bounded printable string')
        with self._lock:
            self._transaction()
            try:
                identity = self.identity()
                if identity['identity_conflict']:
                    self._hold('event_identity_conflict', replace=True)
                    reason = 'event_identity_conflict'
                else:
                    self._hold(reason)
                cursor = int(self._meta('applied_cursor'))
                self._db.execute('COMMIT')
                return {'status': 'HELD', 'coordinator_epoch': identity['coordinator_epoch'],
                        'cursor': cursor, 'reason': self._meta('hold_reason')}
            except Exception:
                if self._db.in_transaction:
                    self._db.execute('ROLLBACK')
                raise

    def hold_for_reconciliation(self, higher_epoch: int, *, reason: str) -> dict[str, Any]:
        """Durably hold admission at a monotonic higher coordinator epoch before proof/disposition."""
        if not _is_nonnegative_int(higher_epoch):
            raise ValueError("higher coordinator epoch must be a non-negative integer")
        if not reason:
            raise ValueError("hold reason is required")
        with self._lock:
            self._transaction()
            try:
                current = int(self._meta("coordinator_epoch"))
                if higher_epoch <= current:
                    raise ValueError("hold must install a higher coordinator epoch")
                already_held = self._meta("held") == "true"
                prior_reconciliation_epoch = self._meta("reconciliation_hold_epoch")
                identity_conflict = self._meta("identity_conflict") == "true"
                self._set_meta("coordinator_epoch", str(higher_epoch))
                if identity_conflict:
                    self._hold("event_identity_conflict", replace=True)
                elif not already_held:
                    self._hold(reason, replace=True, reconciliation_epoch=higher_epoch)
                elif prior_reconciliation_epoch == str(current):
                    self._hold(reason, replace=True, reconciliation_epoch=higher_epoch)
                elif self._meta("hold_reason") == "sequence_gap":
                    # Keep the coordinator reason visible without erasing the independent gap source.
                    self._set_meta("hold_reason", reason)
                    self._set_meta("reconciliation_hold_epoch", str(higher_epoch))
                    self._set_meta("non_reconciliation_hold_reason", "sequence_gap")
                else:
                    # Existing rejection/operator holds retain their owner and block resume.
                    self._set_meta("non_reconciliation_hold_reason", self._meta("hold_reason"))
                self._db.execute("COMMIT")
                return {"status": "HELD", "coordinator_epoch": higher_epoch, "reason": reason}
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def prove_never_admitted(self, original_event: Mapping[str, Any]) -> dict[str, Any]:
        """Create a durable exact-identity proof only while held, fenced and before sequence apply."""
        identity = _event_identity(original_event)
        event_json = _json(identity)
        with self._lock:
            self._transaction()
            try:
                row = self._db.execute("SELECT * FROM events WHERE event_id=?", (identity["id"],)).fetchone()
                if row is None:
                    raise ValueError("NOT_FOUND is not proof; original event identity is not journaled")
                epoch, cursor = int(self._meta("coordinator_epoch")), int(self._meta("applied_cursor"))
                identity_snapshot = {
                    "coordinator_epoch": epoch,
                    "policy_epoch": int(self._meta("policy_epoch")),
                    "resource_fences": json.loads(self._meta("resource_fences")),
                    "task_fences": json.loads(self._meta("task_fences")),
                }
                command_id = identity["payload"].get("command_id") if isinstance(identity["payload"], Mapping) else None
                command = self._db.execute("SELECT state,event_id,payload_hash FROM commands WHERE command_id=?", (command_id,)).fetchone() if command_id else None
                valid = (row["event_json"] == event_json
                         and identity["kind"] == "COMMAND"
                         and epoch > identity["coordinator_epoch"]
                         and self._meta("held") == "true" and identity["sequence"] == cursor + 1
                         and row["status"] == "RECEIVED"
                         and self._db.execute("SELECT 1 FROM cancellations WHERE event_id=?", (identity["id"],)).fetchone() is None
                         and command is not None and command["state"] == "PREPARED"
                         and command["event_id"] == identity["id"]
                         and command["payload_hash"] == identity["payload_hash"])
                proof_id = uuid.uuid4().hex
                result = "NEVER_ADMITTED" if valid else "REJECTED"
                self._db.execute("INSERT INTO cancellation_proofs VALUES(?,?,?,?,?,?,?)", (
                    proof_id, identity["id"], identity["sequence"], identity["payload_hash"], epoch, result,
                    _json(identity_snapshot)))
                self._db.execute("COMMIT")
                return {"status": result, "proof_id": proof_id, "event_id": identity["id"],
                        "sequence": identity["sequence"], "payload_hash": identity["payload_hash"],
                        "hold_epoch": epoch}
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def record_cancellation_disposition(self, original_event: Mapping[str, Any], *, proof: Mapping[str, Any]) -> dict[str, Any]:
        """Store a separate immutable cancellation referencing, never replacing, the original event."""
        identity = _event_identity(original_event)
        proof_fields = {"status", "proof_id", "event_id", "sequence", "payload_hash", "hold_epoch"}
        if not isinstance(proof, Mapping) or set(proof) != proof_fields:
            raise ValueError("an explicit durable NEVER_ADMITTED proof is required")
        if (not isinstance(proof["proof_id"], str) or not proof["proof_id"]
                or not isinstance(proof["event_id"], str) or not proof["event_id"]
                or not _is_nonnegative_int(proof["sequence"]) or proof["sequence"] < 1
                or not isinstance(proof["payload_hash"], str) or not proof["payload_hash"]
                or not _is_nonnegative_int(proof["hold_epoch"])):
            raise ValueError("invalid durable NEVER_ADMITTED proof identity")
        with self._lock:
            self._transaction()
            try:
                row = self._db.execute("SELECT * FROM events WHERE event_id=?", (identity["id"],)).fetchone()
                proof_row = self._db.execute("SELECT * FROM cancellation_proofs WHERE proof_id=?", (proof["proof_id"],)).fetchone()
                event_json = _json(identity)
                if row is None or row["event_json"] != event_json or self._meta("held") != "true":
                    raise ValueError("cancellation requires held ingress and exact durable NEVER_ADMITTED proof")
                current_identity = {
                    "coordinator_epoch": int(self._meta("coordinator_epoch")),
                    "policy_epoch": int(self._meta("policy_epoch")),
                    "resource_fences": json.loads(self._meta("resource_fences")),
                    "task_fences": json.loads(self._meta("task_fences")),
                }
                if (proof_row is None
                        or proof_row["identity_json"] is None
                        or proof_row["result"] != "NEVER_ADMITTED"
                        or proof_row["event_id"] != identity["id"]
                        or proof_row["sequence"] != identity["sequence"]
                        or proof_row["payload_hash"] != identity["payload_hash"]
                        or proof_row["hold_epoch"] != proof["hold_epoch"]
                        or proof["status"] != "NEVER_ADMITTED"
                        or proof["event_id"] != identity["id"]
                        or proof["sequence"] != identity["sequence"]
                        or proof["payload_hash"] != identity["payload_hash"]):
                    raise ValueError("cancellation requires held ingress and exact durable NEVER_ADMITTED proof")

                existing = self._db.execute("SELECT * FROM cancellations WHERE event_id=?", (identity["id"],)).fetchone()
                if existing is not None:
                    if (proof_row is not None and proof_row["result"] == "NEVER_ADMITTED"
                            and existing["sequence"] == identity["sequence"]
                            and existing["payload_hash"] == identity["payload_hash"]
                            and existing["hold_epoch"] == proof_row["hold_epoch"]
                            and existing["proof_id"] == proof_row["proof_id"]):
                        self._db.execute("COMMIT")
                        disposition = self.cancellation(identity["id"])
                        assert disposition is not None
                        return disposition
                    raise ValueError("cancellation disposition is immutable")

                cursor = int(self._meta("applied_cursor"))
                if proof_row["identity_json"] != _json(current_identity):
                    raise ValueError("cancellation requires held ingress and exact durable NEVER_ADMITTED proof")
                command_id = identity["payload"].get("command_id") if isinstance(identity["payload"], Mapping) else None
                command = self._db.execute(
                    "SELECT state,event_id,payload_hash FROM commands WHERE command_id=?", (command_id,)
                ).fetchone() if command_id else None
                if (int(self._meta("coordinator_epoch")) != proof_row["hold_epoch"]
                        or cursor + 1 != identity["sequence"]
                        or row["status"] != "RECEIVED"
                        or command is None or command["state"] != "PREPARED"
                        or command["event_id"] != identity["id"]
                        or command["payload_hash"] != identity["payload_hash"]):
                    raise ValueError("cancellation requires held ingress and exact durable NEVER_ADMITTED proof")
                self._db.execute("INSERT INTO cancellations VALUES(?,?,?,?,?,?)", (
                    row["event_id"], row["sequence"], row["payload_hash"], proof_row["hold_epoch"],
                    proof_row["proof_id"], _json({"kind": "CANCELLATION_DISPOSITION", "original_event_id": row["event_id"],
                    "sequence": row["sequence"], "payload_hash": row["payload_hash"], "hold_epoch": proof_row["hold_epoch"]})))
                self._db.execute("COMMIT")
                disposition = self.cancellation(row["event_id"])
                assert disposition is not None
                return disposition
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def cancellation(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM cancellations WHERE event_id=?", (event_id,)).fetchone()
            if not row:
                return None
            return {"status": "CANCELLED", "original_event_id": row["event_id"], "sequence": row["sequence"],
                    "payload_hash": row["payload_hash"], "hold_epoch": row["hold_epoch"],
                    "disposition": json.loads(row["disposition_json"])}

    def record_checkpoint(self, state: Any, *, last_tick: int, last_sequence: int, last_hash: str,
                          postconditions: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Atomically commit serialized world snapshot, durable cursor/hash, and checkpoint identity."""
        if (type(last_tick) is not int or last_tick < 0
                or type(last_sequence) is not int or last_sequence < 0 or not last_hash):
            raise ValueError("checkpoint tick/sequence must be non-negative integers and hash non-empty")
        state_json, post_json = _json(state), _json(dict(postconditions or {}))
        checkpoint_id = hashlib.sha256((state_json + f"|{last_tick}|{last_sequence}|{last_hash}|{post_json}").encode()).hexdigest()
        with self._lock:
            self._transaction()
            try:
                if last_sequence != int(self._meta("applied_cursor")):
                    raise ValueError("checkpoint sequence must match applied cursor")
                self._db.execute("INSERT OR REPLACE INTO checkpoints VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                                 (checkpoint_id, state_json, last_tick, last_sequence, last_hash, post_json))
                self._set_meta("latest_checkpoint_id", checkpoint_id)
                self._db.execute("UPDATE commands SET checkpoint_id=? WHERE command_id IN (SELECT command_id FROM commands)", (checkpoint_id,))
                self._db.execute("COMMIT")
                return {"id": checkpoint_id, "last_tick": last_tick, "last_sequence": last_sequence, "last_hash": last_hash}
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def checkpoint(self) -> dict[str, Any] | None:
        with self._lock:
            checkpoint_id = self._meta("latest_checkpoint_id") if self._db.execute("SELECT 1 FROM metadata WHERE key='latest_checkpoint_id'").fetchone() else None
            row = self._db.execute("SELECT * FROM checkpoints WHERE checkpoint_id=?", (checkpoint_id,)).fetchone() if checkpoint_id else None
            if not row:
                return None
            return {"id": row["checkpoint_id"], "state_json": row["state_json"], "last_tick": row["last_tick"],
                    "last_sequence": row["last_sequence"], "last_hash": row["last_hash"],
                    "postconditions": json.loads(row["postconditions_json"])}

    def recover_after_restart(self) -> list[str]:
        """Mark active effects UNKNOWN unless the latest checkpoint records their exact postcondition."""
        with self._lock:
            checkpoint = self.checkpoint()
            posts = checkpoint["postconditions"] if checkpoint else {}
            self._transaction()
            try:
                rows = self._db.execute("SELECT * FROM commands WHERE state IN ('PREPARED','SENT','ACCEPTED','RUNNING','CONTROLLER_DONE')").fetchall()
                changed = []
                for row in rows:
                    expected = json.loads(row["postcondition_json"]) if row["postcondition_json"] is not None else None
                    if expected is not None and posts.get(row["command_id"], object()) == expected:
                        continue
                    self._db.execute("UPDATE commands SET last_known_state=state,reconciliation_state='UNKNOWN',state='UNKNOWN' WHERE command_id=?", (row["command_id"],))
                    self._db.execute("INSERT INTO command_history(command_id,state) VALUES(?, 'UNKNOWN')", (row["command_id"],))
                    changed.append(row["command_id"])
                if changed:
                    self._hold("uncertain simulator state after restart")
                self._db.execute("COMMIT")
                return changed
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise
