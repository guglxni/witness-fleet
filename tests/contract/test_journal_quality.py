from __future__ import annotations

import sqlite3

import pytest

from services.simulator.journal import Journal


def command_event() -> dict:
    return {
        "id": "event-1",
        "sequence": 1,
        "payload_hash": "sha256:original",
        "kind": "COMMAND",
        "coordinator_epoch": 2,
        "effective_world_tick": 0,
        "payload": {"command_id": "cmd-1", "target": "corridor-c"},
    }


@pytest.mark.parametrize("field,value", [
    ("last_tick", True), ("last_tick", 1.5), ("last_tick", -1),
    ("last_sequence", False), ("last_sequence", 0.5), ("last_sequence", -1),
])
def test_checkpoint_counters_require_exact_nonnegative_integers(tmp_path, field, value):
    journal = Journal(tmp_path / f"checkpoint-{field}-{value}.sqlite")
    counters = {"last_tick": 1, "last_sequence": 0}
    counters[field] = value
    with pytest.raises(ValueError, match="checkpoint tick/sequence"):
        journal.record_checkpoint(
            {"world_tick": 1}, **counters, last_hash="genesis"
        )
    journal.close()


@pytest.mark.parametrize("field,value", [
    ("policy_epoch", 1), ("resource_fences", {"corridor-c": 1}),
    ("task_fences", {"task-1": 1}),
])
def test_never_admitted_proof_is_bound_to_complete_identity_snapshot(tmp_path, field, value):
    journal = Journal(tmp_path / f"proof-identity-{field}.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="event-1")
    journal.hold_for_reconciliation(3, reason="barrier")
    proof = journal.prove_never_admitted(original)
    assert proof["status"] == "NEVER_ADMITTED"

    identity = {
        "coordinator_epoch": 3,
        "policy_epoch": 0,
        "resource_fences": {},
        "task_fences": {},
    }
    identity[field] = value
    journal.set_identity(**identity)

    with pytest.raises(ValueError, match="exact durable NEVER_ADMITTED proof"):
        journal.record_cancellation_disposition(original, proof=proof)
    assert journal.cancellation("event-1") is None
    journal.close()


def test_disposition_replay_survives_later_identity_snapshot_change(tmp_path):
    journal = Journal(tmp_path / "replay-after-identity-change.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="event-1")
    journal.hold_for_reconciliation(3, reason="barrier")
    proof = journal.prove_never_admitted(original)
    first = journal.record_cancellation_disposition(original, proof=proof)

    journal.set_identity(
        coordinator_epoch=3,
        policy_epoch=1,
        resource_fences={},
        task_fences={},
    )

    assert journal.record_cancellation_disposition(original, proof=proof) == first
    journal.close()


def test_existing_proofs_migrate_additively_and_legacy_missing_snapshot_fails_closed(tmp_path):
    path = tmp_path / "legacy-proof.sqlite"
    journal = Journal(path)
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="event-1")
    journal.hold_for_reconciliation(3, reason="barrier")
    proof = journal.prove_never_admitted(original)
    journal.close()

    # Simulate a database from before identity_json existed; keep the durable proof row intact.
    with sqlite3.connect(path) as db:
        db.execute("""
            CREATE TABLE cancellation_proofs_legacy (
                proof_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                payload_hash TEXT NOT NULL, hold_epoch INTEGER NOT NULL, result TEXT NOT NULL
            )
        """)
        db.execute("""
            INSERT INTO cancellation_proofs_legacy
            SELECT proof_id,event_id,sequence,payload_hash,hold_epoch,result FROM cancellation_proofs
        """)
        db.execute("DROP TABLE cancellation_proofs")
        db.execute("ALTER TABLE cancellation_proofs_legacy RENAME TO cancellation_proofs")

    reopened = Journal(path)
    columns = {row[1] for row in reopened._db.execute("PRAGMA table_info(cancellation_proofs)")}
    assert "identity_json" in columns
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM cancellation_proofs").fetchone()[0] == 1
        db.execute("UPDATE cancellation_proofs SET identity_json=NULL WHERE proof_id=?", (proof["proof_id"],))

    with pytest.raises(ValueError, match="exact durable NEVER_ADMITTED proof"):
        reopened.record_cancellation_disposition(original, proof=proof)
    assert reopened.cancellation("event-1") is None
    reopened.close()
