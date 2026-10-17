from __future__ import annotations

import pytest

from services.simulator.journal import Journal


def command_event() -> dict:
    return {
        "id": "cmd-event-1",
        "sequence": 1,
        "payload_hash": "sha256:original",
        "kind": "COMMAND",
        "coordinator_epoch": 2,
        "effective_world_tick": 0,
        "payload": {"command_id": "cmd-1", "target": "corridor-c"},
    }


def test_higher_epoch_hold_and_explicit_never_admitted_proof_precede_disposition(tmp_path):
    path = tmp_path / "cancel.sqlite"
    original = command_event()
    journal = Journal(path)
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="cmd-event-1")
    held = journal.hold_for_reconciliation(3, reason="restart barrier")
    assert held["coordinator_epoch"] == 3
    journal.close()

    journal = Journal(path)  # crash/reopen after hold fence
    with pytest.raises(ValueError):
        journal.record_cancellation_disposition(original, proof="NOT_FOUND")
    proof = journal.prove_never_admitted(original)
    assert proof["status"] == "NEVER_ADMITTED"
    journal.close()

    journal = Journal(path)  # crash/reopen after explicit proof
    disposition = journal.record_cancellation_disposition(original, proof=proof)
    assert disposition["status"] == "CANCELLED"
    assert disposition["original_event_id"] == "cmd-event-1"
    assert disposition["sequence"] == 1
    assert journal.event("cmd-event-1")["payload"] == original["payload"]
    journal.close()

    journal = Journal(path)  # crash/reopen before cursor consumption
    assert journal.cancellation("cmd-event-1")["status"] == "CANCELLED"
    assert journal.applied_cursor == 0
    assert journal.mark_applied("cmd-event-1")["cursor"] == 1
    journal.close()

    reopened = Journal(path)  # crash/reopen after cursor commit
    assert reopened.cancellation("cmd-event-1")["status"] == "CANCELLED"
    assert reopened.applied_cursor == 1
    assert reopened.receipt("cmd-1")["state"] == "CANCELLED"
    reopened.close()


def test_disposition_cannot_cancel_accepted_running_or_unknown_command(tmp_path):
    journal = Journal(tmp_path / "active.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:cmd", "ACCEPTED", event_id="cmd-event-1")
    journal.hold_for_reconciliation(3, reason="fence")
    proof = journal.prove_never_admitted(original)
    assert proof["status"] == "REJECTED"
    with pytest.raises(ValueError):
        journal.record_cancellation_disposition(original, proof=proof)
    journal.close()


def test_not_found_receipt_is_not_a_never_admitted_proof(tmp_path):
    journal = Journal(tmp_path / "missing.sqlite")
    assert journal.receipt("cmd-unknown")["status"] == "NOT_FOUND"
    with pytest.raises(ValueError):
        journal.prove_never_admitted(command_event())
    journal.close()


def test_never_admitted_proof_requires_contiguous_prior_identity(tmp_path):
    journal = Journal(tmp_path / "gap-proof.sqlite")
    original = command_event()
    original["sequence"] = 2
    original["id"] = "cmd-event-2"
    journal.register(original)
    journal.hold_for_reconciliation(3, reason="barrier")
    assert journal.prove_never_admitted(original)["status"] == "REJECTED"
    journal.close()


def test_hold_epoch_is_monotonic_and_identity_bound(tmp_path):
    journal = Journal(tmp_path / "epoch.sqlite")
    journal.hold_for_reconciliation(5, reason="barrier")
    with pytest.raises(ValueError):
        journal.hold_for_reconciliation(4, reason="rollback")
    assert journal.identity()["coordinator_epoch"] == 5
    journal.close()


def test_proof_becomes_stale_if_original_event_is_applied_before_disposition(tmp_path):
    journal = Journal(tmp_path / "stale-proof.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="cmd-event-1")
    journal.hold_for_reconciliation(3, reason="barrier")

    proof = journal.prove_never_admitted(original)
    assert proof["status"] == "NEVER_ADMITTED"
    assert journal.mark_applied("cmd-event-1") == {"status": "HELD", "cursor": 0}
    assert journal.record_cancellation_disposition(original, proof=proof)["status"] == "CANCELLED"
    assert journal.applied_cursor == 0
    assert journal.mark_applied("cmd-event-1")["status"] == "CANCELLED"
    assert journal.applied_cursor == 1
    journal.close()


def test_epoch_barrier_can_advance_cursor_while_held_without_releasing_hold(tmp_path):
    journal = Journal(tmp_path / "held-barrier.sqlite")
    barrier = {**command_event(), "id": "barrier-1", "kind": "EPOCH_BARRIER",
               "payload": {"barrier_id": "barrier-1"}}
    journal.register(barrier)
    journal.hold_for_reconciliation(3, reason="barrier reconciliation")

    assert journal.mark_applied("barrier-1") == {"status": "APPLIED", "cursor": 1}
    assert journal.identity()["held"] is True
    assert journal.identity()["hold_reason"] == "barrier reconciliation"
    journal.close()


def test_proof_becomes_stale_if_command_state_changes_before_disposition(tmp_path):
    journal = Journal(tmp_path / "stale-command.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="cmd-event-1")
    journal.hold_for_reconciliation(3, reason="barrier")

    proof = journal.prove_never_admitted(original)
    assert proof["status"] == "NEVER_ADMITTED"
    journal.transition_command("cmd-1", "SENT")
    with pytest.raises(ValueError, match="exact durable NEVER_ADMITTED proof"):
        journal.record_cancellation_disposition(original, proof=proof)
    assert journal.cancellation("cmd-event-1") is None
    journal.close()


def test_second_command_cannot_claim_event_after_never_admitted_proof(tmp_path):
    journal = Journal(tmp_path / "second-admission.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="cmd-event-1")
    journal.hold_for_reconciliation(3, reason="barrier")
    proof = journal.prove_never_admitted(original)
    assert proof["status"] == "NEVER_ADMITTED"

    assert journal.record_command("cmd-alias", "sha256:original", "PREPARED", event_id="cmd-event-1")["status"] == "CONFLICT"
    assert journal.identity()["held"] is True
    assert journal.record_cancellation_disposition(original, proof=proof)["status"] == "CANCELLED"
    journal.close()


def test_proof_becomes_stale_if_coordinator_epoch_changes(tmp_path):
    journal = Journal(tmp_path / "stale-epoch.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="cmd-event-1")
    journal.hold_for_reconciliation(3, reason="barrier")

    proof = journal.prove_never_admitted(original)
    assert proof["status"] == "NEVER_ADMITTED"
    journal.set_identity(coordinator_epoch=4, policy_epoch=0, resource_fences={}, task_fences={})
    with pytest.raises(ValueError, match="exact durable NEVER_ADMITTED proof"):
        journal.record_cancellation_disposition(original, proof=proof)
    assert journal.cancellation("cmd-event-1") is None
    journal.close()


@pytest.mark.parametrize("field,value", [
    ("id", "other-event"), ("sequence", 2), ("payload_hash", "sha256:forged"),
    ("kind", "OTHER"), ("coordinator_epoch", 1), ("effective_world_tick", 99),
    ("payload", {"command_id": "cmd-1", "target": "different"}),
])
def test_disposition_requires_complete_original_event_identity(tmp_path, field, value):
    journal = Journal(tmp_path / f"event-identity-{field}.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="cmd-event-1")
    journal.hold_for_reconciliation(3, reason="barrier")
    proof = journal.prove_never_admitted(original)

    changed = {**original, field: value}
    with pytest.raises(ValueError):
        journal.record_cancellation_disposition(changed, proof=proof)
    assert journal.cancellation("cmd-event-1") is None
    journal.close()


@pytest.mark.parametrize("field,value", [
    ("proof_id", "missing-proof"), ("sequence", True), ("sequence", 1.0),
    ("payload_hash", "sha256:forged"), ("hold_epoch", 99), ("hold_epoch", True),
    ("event_id", "other-event"), ("status", "REJECTED"),
])
def test_disposition_requires_complete_unmodified_proof_identity(tmp_path, field, value):
    journal = Journal(tmp_path / f"proof-identity-{field}-{value}.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="cmd-event-1")
    journal.hold_for_reconciliation(3, reason="barrier")
    proof = journal.prove_never_admitted(original)
    forged = {**proof, field: value}

    with pytest.raises(ValueError):
        journal.record_cancellation_disposition(original, proof=forged)
    assert journal.cancellation("cmd-event-1") is None
    journal.close()


def test_disposition_replay_is_immutable_and_idempotent(tmp_path):
    journal = Journal(tmp_path / "disposition-replay.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="cmd-event-1")
    journal.hold_for_reconciliation(3, reason="barrier")
    proof = journal.prove_never_admitted(original)

    first = journal.record_cancellation_disposition(original, proof=proof)
    assert journal.record_command("cmd-alias", "sha256:original", "PREPARED", event_id="cmd-event-1")["status"] == "CONFLICT"
    assert journal.record_cancellation_disposition(original, proof=proof) == first
    assert journal.mark_applied("cmd-event-1")["status"] == "CANCELLED"
    assert journal.identity()["held"] is True
    stored = journal.cancellation("cmd-event-1")
    assert stored is not None
    assert stored["disposition"] == first["disposition"]
    journal.close()


def test_disposition_rejects_proof_with_extra_fields(tmp_path):
    journal = Journal(tmp_path / "extra-proof-field.sqlite")
    original = command_event()
    journal.register(original)
    journal.record_command("cmd-1", "sha256:original", "PREPARED", event_id="cmd-event-1")
    journal.hold_for_reconciliation(3, reason="barrier")
    proof = {**journal.prove_never_admitted(original), "comment": "caller text"}
    with pytest.raises(ValueError):
        journal.record_cancellation_disposition(original, proof=proof)
    journal.close()
