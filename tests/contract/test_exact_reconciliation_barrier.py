from __future__ import annotations

import pytest

from services.simulator.journal import Journal
from witness_fleet.domain import DispatchEvent, canonical_json_hash
from witness_fleet.simulation.protocol import preflight


def barrier_event():
    payload = {"coordinator_epoch": 2}
    return {
        "id": "graph-barrier-2",
        "sequence": 1,
        "payload_hash": canonical_json_hash(payload),
        "kind": "EPOCH_BARRIER",
        "coordinator_epoch": 2,
        "effective_world_tick": 0,
        "payload": payload,
    }


def test_private_path_admits_exact_barrier_but_keeps_hold_until_matching_checkpoint(tmp_path):
    journal = Journal(tmp_path / "exact-resume.sqlite")
    journal.set_identity(coordinator_epoch=1, policy_epoch=0, task_fences={}, resource_fences={})
    journal.hold_for_reconciliation(2, reason="coordinator takeover")
    event = barrier_event()
    journal.register(event)
    identity_before = journal.identity()
    event_before = journal.event(event["id"])

    ordinary = journal.admit_next(event["id"], current_tick=0)
    assert ordinary["status"] == "REJECTED"
    assert "EPOCH_NOT_INCREASING" in ordinary["reason_codes"]
    assert journal.identity() == identity_before
    assert journal.event(event["id"]) == event_before

    result = journal._admit_reconciliation_barrier(event, current_tick=0)

    assert result == {"status": "ACCEPTED", "event_id": event["id"], "cursor": 1}
    assert journal.applied_cursor == 1
    assert journal.identity()["coordinator_epoch"] == 2
    assert journal.identity()["held"] is True
    assert journal.identity()["hold_reason"] == "coordinator takeover"
    assert journal.event(event["id"])["status"] == "APPLIED"
    marker = {"event_id": event["id"], "sequence": event["sequence"],
              "coordinator_epoch": event["coordinator_epoch"],
              "payload_hash": event["payload_hash"]}
    with pytest.raises(ValueError, match="HOLD"):
        journal._complete_reconciliation_barrier(event)
    stale = {"world": {"held": False, "hold_sources": {},
                       "barrier_recovery": {**marker, "payload_hash": "sha256:stale"}}}
    journal.record_checkpoint(stale, last_tick=0, last_sequence=1, last_hash="stale")
    with pytest.raises(ValueError, match="HOLD"):
        journal._complete_reconciliation_barrier(event)
    assert journal.identity()["held"] is True

    marker_checkpoint = {"world": {
        "held": False, "hold_sources": {}, "barrier_recovery": marker}}
    journal.record_checkpoint(marker_checkpoint, last_tick=0, last_sequence=1,
                              last_hash="native-release")
    completed = journal._complete_reconciliation_barrier(event)
    assert completed["held"] is False

    exact_replay = journal._admit_reconciliation_barrier(event, current_tick=0)
    assert exact_replay == {"status": "REPLAY", "event_id": event["id"], "cursor": 1}

    mismatched_replay = {**event, "payload_hash": "sha256:forged"}
    before = (journal.applied_cursor, journal.identity(), journal.event(event["id"]))
    assert journal._admit_reconciliation_barrier(mismatched_replay, current_tick=0) == {
        "status": "HOLD", "reason_codes": ["EVENT_IDENTITY_MISMATCH"]}
    assert (journal.applied_cursor, journal.identity(), journal.event(event["id"])) == before
    journal.close()


@pytest.mark.parametrize(
    "field,value",
    [("sequence", 2), ("payload_hash", "sha256:forged"), ("kind", "FENCE_INSTALL"),
     ("coordinator_epoch", 3), ("effective_world_tick", 1),
     ("payload", {"coordinator_epoch": 2, "holder_id": "other"})],
)
def test_private_path_rejects_any_changed_event_identity_without_mutation(tmp_path, field, value):
    journal = Journal(tmp_path / f"identity-{field}.sqlite")
    journal.set_identity(coordinator_epoch=1, policy_epoch=0, task_fences={}, resource_fences={})
    journal.hold_for_reconciliation(2, reason="coordinator takeover")
    event = barrier_event()
    journal.register(event)
    identity_before = journal.identity()
    event_before = journal.event(event["id"])

    forged = {**event, field: value}
    result = journal._admit_reconciliation_barrier(forged, current_tick=0)

    assert result == {"status": "HOLD", "reason_codes": ["EVENT_IDENTITY_MISMATCH"]}
    assert journal.applied_cursor == 0
    assert journal.identity() == identity_before
    assert journal.event(event["id"]) == event_before
    journal.close()


def test_private_path_requires_exact_next_contiguous_cursor(tmp_path):
    journal = Journal(tmp_path / "cursor-gap.sqlite")
    journal.set_identity(coordinator_epoch=1, policy_epoch=0, task_fences={}, resource_fences={})
    journal.hold_for_reconciliation(2, reason="coordinator takeover")
    event = barrier_event()
    event["sequence"] = 2
    journal.register(event)
    identity_before = journal.identity()
    event_before = journal.event(event["id"])

    result = journal._admit_reconciliation_barrier(event, current_tick=0)

    assert result == {"status": "HOLD", "reason_codes": ["SEQUENCE_GAP"]}
    assert journal.applied_cursor == 0
    assert journal.identity() == identity_before
    assert journal.event(event["id"]) == event_before
    journal.close()


def test_private_preflight_equality_capability_is_default_false():
    payload = {"coordinator_epoch": 2}
    event = DispatchEvent(id="barrier", sequence=1, coordinator_epoch=2, kind="EPOCH_BARRIER",
                          effective_world_tick=0, payload=payload,
                          payload_hash=canonical_json_hash(payload))
    ordinary = preflight(event, last_sequence=0, coordinator_epoch=2, policy_epoch=0,
                         task_fences={}, resource_fences={}, current_tick=0)
    opted_in = preflight(event, last_sequence=0, coordinator_epoch=2, policy_epoch=0,
                         task_fences={}, resource_fences={}, current_tick=0,
                         allow_reconciliation_equal_epoch=True)

    assert "EPOCH_NOT_INCREASING" in ordinary["reason_codes"]
    assert opted_in["status"] == "ACCEPTED"
    non_barrier_payload = {"task_id": "task", "task_fence": 1, "resource_fences": {}}
    non_barrier = DispatchEvent(id="fence", sequence=1, coordinator_epoch=2, kind="FENCE_INSTALL",
                                effective_world_tick=0, payload=non_barrier_payload,
                                payload_hash=canonical_json_hash(non_barrier_payload))
    assert preflight(non_barrier, last_sequence=0, coordinator_epoch=2, policy_epoch=0,
                     task_fences={}, resource_fences={}, current_tick=0,
                     allow_reconciliation_equal_epoch=True)["reason_codes"] == ["EPOCH_BARRIER_REQUIRED"]


def test_private_path_rejects_identity_mismatch_without_mutation(tmp_path):
    journal = Journal(tmp_path / "identity-mismatch.sqlite")
    journal.set_identity(coordinator_epoch=1, policy_epoch=0, task_fences={}, resource_fences={})
    journal.hold_for_reconciliation(2, reason="coordinator takeover")
    event = barrier_event()
    journal.register(event)
    identity_before = journal.identity()
    event_before = journal.event(event["id"])

    forged = {**event, "payload": {"coordinator_epoch": 2, "holder_id": "other"}}
    result = journal._admit_reconciliation_barrier(forged, current_tick=0)

    assert result == {"status": "HOLD", "reason_codes": ["EVENT_IDENTITY_MISMATCH"]}
    assert journal.applied_cursor == 0
    assert journal.identity() == identity_before
    assert journal.event(event["id"]) == event_before
    journal.close()


def test_private_path_refuses_a_non_reconciliation_hold_without_relabeling_it(tmp_path):
    journal = Journal(tmp_path / "wrong-hold.sqlite")
    journal.set_identity(coordinator_epoch=1, policy_epoch=0, task_fences={}, resource_fences={})
    journal.hold_admissions("operator hold")
    journal.hold_for_reconciliation(2, reason="coordinator takeover")
    event = barrier_event()
    journal.register(event)
    identity_before = journal.identity()
    event_before = journal.event(event["id"])

    result = journal._admit_reconciliation_barrier(event, current_tick=0)

    assert result == {"status": "HOLD", "reason_codes": ["RECONCILIATION_HOLD_REQUIRED"]}
    assert journal.applied_cursor == 0
    assert journal.identity() == identity_before
    assert journal.identity()["hold_reason"] == "operator hold"
    assert journal.event(event["id"]) == event_before
    journal.close()


def test_generic_barrier_recovery_reason_does_not_grant_reconciliation_ownership(tmp_path):
    journal = Journal(tmp_path / "generic-recovery-latch.sqlite")
    journal.set_identity(coordinator_epoch=1, policy_epoch=0, task_fences={}, resource_fences={})
    journal.hold_admissions("barrier commit requires explicit recovery")
    event = barrier_event()
    journal.register(event)

    before = (journal.applied_cursor, journal.identity(), journal.event(event["id"]))
    result = journal._admit_reconciliation_barrier(event, current_tick=0)

    assert result == {"status": "HOLD", "reason_codes": ["RECONCILIATION_HOLD_REQUIRED"]}
    assert (journal.applied_cursor, journal.identity(), journal.event(event["id"])) == before
    journal.close()


def test_identity_conflict_hold_cannot_become_reconciliation_owned(tmp_path):
    journal = Journal(tmp_path / "identity-conflict-hold.sqlite")
    journal.set_identity(coordinator_epoch=1, policy_epoch=0, task_fences={}, resource_fences={})
    journal.hold_for_reconciliation(2, reason="coordinator takeover")
    event = barrier_event()
    journal.register(event)
    conflicting = {**event, "id": "conflicting-event"}
    result = journal.register(conflicting)
    assert result["status"] == "CONFLICT"
    identity_before = journal.identity()
    event_before = journal.event(event["id"])

    admission = journal._admit_reconciliation_barrier(event, current_tick=0)

    assert admission == {"status": "HOLD", "reason_codes": ["RECONCILIATION_HOLD_REQUIRED"]}
    assert journal.identity() == identity_before
    assert journal.applied_cursor == 0
    assert journal.event(event["id"]) == event_before
    journal.close()


@pytest.mark.parametrize(
    "state",
    ["PREPARED", "SENT", "UNKNOWN", "ACCEPTED", "RUNNING", "CONTROLLER_DONE",
     "FAILED", "CANCELLED", "RECONCILED"],
)
def test_private_path_refuses_any_prior_command_receipt_state_without_mutation(tmp_path, state):
    journal = Journal(tmp_path / f"receipt-{state}.sqlite")
    journal.set_identity(coordinator_epoch=1, policy_epoch=0, task_fences={}, resource_fences={})
    journal.hold_for_reconciliation(2, reason="coordinator takeover")
    event = barrier_event()
    journal.register(event)
    journal.record_command("receipt", "sha256:prior", state)
    identity_before = journal.identity()
    event_before = journal.event(event["id"])
    receipt_before = journal.receipt("receipt")

    result = journal._admit_reconciliation_barrier(event, current_tick=0)

    assert result == {"status": "HOLD", "reason_codes": ["UNRESOLVED_COMMANDS"]}
    assert journal.applied_cursor == 0
    assert journal.identity() == identity_before
    assert journal.event(event["id"]) == event_before
    assert journal.receipt("receipt") == receipt_before
    journal.close()


@pytest.mark.parametrize(("initial", "terminal"), [("SENT", "FAILED"), ("UNKNOWN", "RECONCILED")])
def test_private_path_rejects_terminal_enum_after_unresolved_command_history(tmp_path, initial, terminal):
    journal = Journal(tmp_path / f"spoof-{initial}-{terminal}.sqlite")
    journal.set_identity(coordinator_epoch=1, policy_epoch=0, task_fences={}, resource_fences={})
    journal.hold_for_reconciliation(2, reason="coordinator takeover")
    event = barrier_event()
    journal.register(event)
    journal.record_command("receipt", "sha256:prior", initial)
    journal.transition_command("receipt", terminal)
    identity_before = journal.identity()
    event_before = journal.event(event["id"])
    receipt_before = journal.receipt("receipt")

    result = journal._admit_reconciliation_barrier(event, current_tick=0)

    assert result == {"status": "HOLD", "reason_codes": ["UNRESOLVED_COMMANDS"]}
    assert journal.applied_cursor == 0
    assert journal.identity() == identity_before
    assert journal.event(event["id"]) == event_before
    assert journal.receipt("receipt") == receipt_before
    journal.close()


def test_private_path_accepts_receipt_with_durable_never_admitted_cancellation_proof(tmp_path):
    journal = Journal(tmp_path / "proved-cancellation.sqlite")
    original_payload = {"command_id": "never-admitted-command"}
    original = {
        "id": "never-admitted-event",
        "sequence": 1,
        "payload_hash": canonical_json_hash(original_payload),
        "kind": "COMMAND",
        "coordinator_epoch": 1,
        "effective_world_tick": 0,
        "payload": original_payload,
    }
    journal.set_identity(coordinator_epoch=1, policy_epoch=0, task_fences={}, resource_fences={})
    journal.register(original)
    journal.record_command("never-admitted-command", original["payload_hash"], "PREPARED",
                           event_id=original["id"])
    journal.hold_for_reconciliation(2, reason="coordinator takeover")
    proof = journal.prove_never_admitted(original)
    assert proof["status"] == "NEVER_ADMITTED"
    journal.record_cancellation_disposition(original, proof=proof)
    assert journal.mark_applied(original["id"])["status"] == "CANCELLED"

    event = barrier_event()
    event["id"] = "graph-barrier-after-cancel"
    event["sequence"] = 2
    journal.register(event)

    result = journal._admit_reconciliation_barrier(event, current_tick=0)

    assert result == {"status": "ACCEPTED", "event_id": event["id"], "cursor": 2}
    assert journal.applied_cursor == 2
    assert journal.identity()["held"] is True
    journal.close()
