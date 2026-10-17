from __future__ import annotations

import json

import pytest

from services.simulator.journal import Journal


def event(sequence: int, *, event_id: str | None = None, payload: dict | None = None) -> dict:
    body = payload or {"command_id": f"cmd-{sequence}", "target": [sequence, 0]}
    return {
        "id": event_id or f"event-{sequence}",
        "sequence": sequence,
        "payload_hash": f"sha256:{sequence}",
        "kind": "COMMAND",
        "coordinator_epoch": 4,
        "effective_world_tick": sequence * 10,
        "payload": body,
    }


def test_register_is_durable_idempotent_and_rejects_identity_reuse(tmp_path):
    path = tmp_path / "receipts.sqlite"
    first = Journal(path)
    accepted = first.register(event(1))
    assert accepted["status"] == "ACCEPTED"
    assert first.register(event(1))["status"] == "REPLAY"
    assert first.receipt("cmd-1")["status"] == "NOT_FOUND"
    first.close()

    reopened = Journal(path)
    stored = reopened.event("event-1")
    assert stored["payload"] == event(1)["payload"]
    assert stored["status"] == "RECEIVED"
    assert reopened.register(event(1, payload={"command_id": "cmd-1", "target": [9, 9]}))["status"] == "CONFLICT"
    assert reopened.register(event(2, event_id="event-1"))["status"] == "CONFLICT"
    reopened.close()


def test_sequence_reuse_by_different_event_id_is_a_conflict(tmp_path):
    journal = Journal(tmp_path / "sequence-reuse.sqlite")
    assert journal.register(event(1))["status"] == "ACCEPTED"
    reused = event(1, event_id="event-impostor")
    assert journal.register(reused)["status"] == "CONFLICT"
    assert journal.event("event-impostor") is None
    journal.close()


def test_event_identity_conflict_persists_poison_and_global_hold(tmp_path):
    path = tmp_path / "identity-conflict.sqlite"
    journal = Journal(path)
    original = event(1, payload={"proposal": {"robot_id": "robot-poisoned"}})
    assert journal.register(original)["status"] == "ACCEPTED"
    conflicting = {**original, "payload": {"proposal": {"robot_id": "robot-other"}}}
    assert journal.register(conflicting)["status"] == "CONFLICT"
    journal.close()

    reopened = Journal(path)
    identity = reopened.identity()
    assert identity["identity_conflict"] is True
    assert identity["poisoned_robots"] == ["robot-other"]
    assert identity["held"] is True
    assert identity["hold_reason"] == "event_identity_conflict"
    reopened.close()


def test_command_receipt_collision_persists_global_hold(tmp_path):
    path = tmp_path / "command-conflict.sqlite"
    journal = Journal(path)
    assert journal.record_command("cmd-1", "sha256:first", "PREPARED")["status"] == "RECORDED"
    assert journal.record_command("cmd-1", "sha256:second", "PREPARED")["status"] == "CONFLICT"
    journal.close()

    reopened = Journal(path)
    identity = reopened.identity()
    assert identity["held"] is True
    assert identity["hold_reason"] == "command_receipt_conflict"
    reopened.close()


def test_command_receipt_state_collision_persists_global_hold(tmp_path):
    path = tmp_path / "command-state-conflict.sqlite"
    journal = Journal(path)
    journal.record_command("cmd-1", "sha256:same", "PREPARED", event_id="event-1")
    with pytest.raises(ValueError, match="different state"):
        journal.record_command("cmd-1", "sha256:same", "ACCEPTED", event_id="event-1")
    journal.close()

    reopened = Journal(path)
    identity = reopened.identity()
    assert identity["held"] is True
    assert identity["hold_reason"] == "command_receipt_state_conflict"
    reopened.close()


def test_gap_is_durable_but_does_not_advance_contiguous_applied_cursor(tmp_path):
    journal = Journal(tmp_path / "gap.sqlite")
    assert journal.register(event(2))["status"] == "GAP"
    assert journal.applied_cursor == 0
    assert journal.event("event-2")["status"] == "RECEIVED"
    assert journal.mark_applied("event-2")["status"] == "GAP"

    assert journal.register(event(1))["status"] == "ACCEPTED"
    assert journal.mark_applied("event-1") == {"status": "HELD", "cursor": 0}
    assert journal.applied_cursor == 0
    assert journal.mark_applied("event-2") == {"status": "GAP", "cursor": 0}
    assert journal.applied_cursor == 0
    journal.close()


def test_applying_contiguous_rows_does_not_clear_reconciliation_hold(tmp_path):
    path = tmp_path / "reconciliation-hold.sqlite"
    journal = Journal(path)
    assert journal.register(event(1))["status"] == "ACCEPTED"
    assert journal.register(event(2))["status"] == "GAP"
    journal.register(event(1))
    journal.hold_for_reconciliation(5, reason="proof required")
    assert journal.mark_applied("event-1") == {"status": "HELD", "cursor": 0}
    assert journal.identity()["held"] is True
    assert journal.identity()["hold_reason"] == "proof required"
    assert journal.mark_applied("event-2")["status"] == "GAP"
    assert journal.applied_cursor == 0
    journal.close()

    reopened = Journal(path)
    assert reopened.identity()["held"] is True
    assert reopened.identity()["hold_reason"] == "proof required"
    reopened.close()


def test_command_receipts_transition_monotonically_and_survive_reopen(tmp_path):
    path = tmp_path / "commands.sqlite"
    journal = Journal(path)
    journal.register(event(1))
    journal.record_command("cmd-1", "sha256:command", "ACCEPTED", event_id="event-1")
    journal.transition_command("cmd-1", "RUNNING")
    with pytest.raises(ValueError):
        journal.transition_command("cmd-1", "ACCEPTED")
    journal.close()

    reopened = Journal(path)
    assert reopened.receipt("cmd-1")["state"] == "RUNNING"
    assert reopened.receipt("missing")["status"] == "NOT_FOUND"
    reopened.close()


def test_checkpoint_and_identity_metadata_are_durable(tmp_path):
    path = tmp_path / "checkpoint.sqlite"
    journal = Journal(path)
    journal.set_identity(
        coordinator_epoch=4,
        policy_epoch=8,
        resource_fences={"corridor-c": 3},
        task_fences={"task-7": 2},
    )
    checkpoint = journal.record_checkpoint(
        {"robots": {"scout": {"x": 1.0}}, "world_tick": 12},
        last_tick=12,
        last_sequence=0,
        last_hash="genesis",
    )
    journal.close()

    reopened = Journal(path)
    assert reopened.identity() == {
        "coordinator_epoch": 4,
        "policy_epoch": 8,
        "resource_fences": {"corridor-c": 3},
        "task_fences": {"task-7": 2},
        "identity_conflict": False,
        "poisoned_robots": [],
        "held": False,
        "hold_reason": None,
    }
    restored = reopened.checkpoint()
    assert restored["id"] == checkpoint["id"]
    assert json.loads(restored["state_json"])["world_tick"] == 12
    assert restored["last_tick"] == 12
    reopened.close()


def test_identity_fence_snapshots_retain_omitted_fence_identities(tmp_path):
    journal = Journal(tmp_path / "fences.sqlite")
    journal.set_identity(
        coordinator_epoch=4,
        policy_epoch=8,
        resource_fences={"corridor-c": 3},
        task_fences={"task-7": 2},
    )
    identity = journal.set_identity(
        coordinator_epoch=5,
        policy_epoch=9,
        resource_fences={},
        task_fences={},
    )
    assert identity["resource_fences"] == {"corridor-c": 3}
    assert identity["task_fences"] == {"task-7": 2}
    journal.close()


@pytest.mark.parametrize("field,value", [
    ("coordinator_epoch", True), ("coordinator_epoch", 4.0),
    ("policy_epoch", False), ("policy_epoch", 8.0),
])
def test_identity_epochs_reject_bool_and_float_values(tmp_path, field, value):
    journal = Journal(tmp_path / f"strict-{field}-{value}.sqlite")
    identity = {"coordinator_epoch": 4, "policy_epoch": 8,
                "resource_fences": {}, "task_fences": {}}
    identity[field] = value
    with pytest.raises(ValueError, match="non-negative integers"):
        journal.set_identity(**identity)
    journal.close()


@pytest.mark.parametrize("fence_value", [True, 1.0])
@pytest.mark.parametrize("fence_kind", ["resource_fences", "task_fences"])
def test_identity_fences_reject_bool_and_float_values(tmp_path, fence_kind, fence_value):
    journal = Journal(tmp_path / f"strict-{fence_kind}-{fence_value}.sqlite")
    identity = {"coordinator_epoch": 4, "policy_epoch": 8,
                "resource_fences": {}, "task_fences": {}}
    identity[fence_kind] = {"fence": fence_value}
    with pytest.raises(ValueError, match="non-negative integers"):
        journal.set_identity(**identity)
    journal.close()


def test_uncertain_restart_marks_active_command_unknown_unless_checkpoint_postcondition_matches(tmp_path):
    path = tmp_path / "restart.sqlite"
    journal = Journal(path)
    journal.register(event(1))
    journal.record_command("cmd-1", "sha256:command", "RUNNING", event_id="event-1", postcondition={"x": 2})
    journal.record_checkpoint(
        {"world_tick": 4}, last_tick=4, last_sequence=0, last_hash="genesis", postconditions={}
    )
    journal.close()

    reopened = Journal(path)
    changed = reopened.recover_after_restart()
    assert changed == ["cmd-1"]
    assert reopened.receipt("cmd-1")["state"] == "UNKNOWN"
    reopened.close()

    exact = Journal(path)
    exact.transition_command("cmd-1", "RECONCILED")
    exact.close()


def test_identical_checkpoint_postcondition_preserves_durable_command_state(tmp_path):
    path = tmp_path / "exact-checkpoint.sqlite"
    journal = Journal(path)
    journal.register(event(1))
    expected = {"x": 2}
    journal.mark_applied("event-1")
    journal.record_command("cmd-1", "sha256:command", "RUNNING", event_id="event-1", postcondition=expected)
    journal.record_checkpoint(
        {"world_tick": 5},
        last_tick=5,
        last_sequence=1,
        last_hash="sha256:1",
        postconditions={"cmd-1": expected},
    )
    journal.close()

    reopened = Journal(path)
    assert reopened.recover_after_restart() == []
    assert reopened.receipt("cmd-1")["state"] == "RUNNING"
    reopened.close()
