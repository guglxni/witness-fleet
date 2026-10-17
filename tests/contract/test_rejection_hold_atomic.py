"""Atomic failure holds preserve exact unadmitted identities for proof cancellation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from test_protocol_commands import command_event

from services.simulator.journal import Journal


def prepare_stale_command(journal):
    event = command_event(sequence=1, fence=1).model_dump(mode="json")
    journal.set_identity(
        coordinator_epoch=0,
        policy_epoch=0,
        task_fences={"task": 2},
        resource_fences={"corridor": 2},
    )
    assert journal.register(event)["status"] == "ACCEPTED"
    assert journal.record_command(
        "cmd", event["payload_hash"], "PREPARED", event_id=event["id"]
    )["status"] == "RECORDED"
    return event


def test_opt_in_rejection_atomically_holds_without_consuming_prepared_identity(tmp_path):
    journal = Journal(tmp_path / "atomic-rejection.sqlite")
    event = prepare_stale_command(journal)

    result = journal.admit_next(event["id"], current_tick=1, hold_on_rejection=True)

    assert result == {
        "status": "HOLD",
        "reason_codes": ["STALE_RESOURCE_FENCE", "STALE_TASK_FENCE"],
    }
    assert journal.identity()["held"] is True
    assert journal.identity()["coordinator_epoch"] == 0
    assert journal.applied_cursor == 0
    assert journal.event(event["id"])["status"] == "RECEIVED"
    assert journal.receipt("cmd")["state"] == "PREPARED"
    assert journal.hold_for_reconciliation(1, reason="trusted proof fence")["status"] == "HELD"
    assert journal.prove_never_admitted(event)["status"] == "NEVER_ADMITTED"
    journal.close()


def test_failed_admission_hold_blocks_an_independent_journal_connection(tmp_path):
    path = tmp_path / "two-connections.sqlite"
    first = Journal(path)
    second = Journal(path)
    event = prepare_stale_command(first)

    rejected = first.admit_next(event["id"], current_tick=1, hold_on_rejection=True)
    competing = second.admit_next(event["id"], current_tick=1, hold_on_rejection=True)

    assert rejected["status"] == "HOLD"
    assert competing == {"status": "HOLD", "reason_codes": ["INGRESS_HELD"]}
    assert second.applied_cursor == 0
    assert second.event(event["id"])["status"] == "RECEIVED"
    assert second.receipt("cmd")["state"] == "PREPARED"
    assert second.identity()["held"] is True
    first.close()
    second.close()


def test_rejected_admission_hold_excludes_a_concurrent_connection_before_commit(tmp_path, monkeypatch):
    """Exercise the production transaction with a competitor entering BEGIN before commit."""
    from witness_fleet.simulation import protocol

    path = tmp_path / "concurrent-rejection.sqlite"
    first = Journal(path)
    second = Journal(path)
    event = prepare_stale_command(first)
    preflight_entered = Event()
    competitor_entered = Event()
    release_preflight = Event()
    original = protocol.preflight

    def bounded_preflight(*args, **kwargs):
        preflight_entered.set()
        assert release_preflight.wait(5), "test did not release authoritative preflight"
        return original(*args, **kwargs)

    def trace_competitor(statement):
        if statement.strip().upper() == "BEGIN IMMEDIATE":
            competitor_entered.set()

    monkeypatch.setattr(protocol, "preflight", bounded_preflight)
    second._db.set_trace_callback(trace_competitor)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            rejected = executor.submit(
                first.admit_next, event["id"], current_tick=1, hold_on_rejection=True,
            )
            assert preflight_entered.wait(5), "authoritative admission did not enter preflight"
            assert first._db.in_transaction
            competing = executor.submit(
                second.admit_next, event["id"], current_tick=1, hold_on_rejection=True,
            )
            assert competitor_entered.wait(5), "competitor did not attempt BEGIN IMMEDIATE"
            release_preflight.set()
            assert rejected.result(timeout=5) == {
                "status": "HOLD",
                "reason_codes": ["STALE_RESOURCE_FENCE", "STALE_TASK_FENCE"],
            }
            assert competing.result(timeout=5) == {
                "status": "HOLD", "reason_codes": ["INGRESS_HELD"],
            }
        assert second.applied_cursor == 0
        assert second.identity()["held"] is True
        assert second.identity()["coordinator_epoch"] == 0
        retained_event = second.event(event["id"])
        retained_receipt = second.receipt("cmd")
        assert retained_event is not None and retained_event["status"] == "RECEIVED"
        assert retained_receipt["state"] == "PREPARED"
        history = second._db.execute(
            "SELECT state FROM command_history WHERE command_id=? ORDER BY id", ("cmd",),
        ).fetchall()
        assert [row["state"] for row in history] == ["PREPARED"]
    finally:
        release_preflight.set()
        second._db.set_trace_callback(None)
        first.close()
        second.close()


def test_invalid_prepared_receipt_rejection_holds_without_consuming_event(tmp_path):
    journal = Journal(tmp_path / "invalid-prepared.sqlite")
    event = command_event(sequence=1, fence=1).model_dump(mode="json")
    journal.set_identity(
        coordinator_epoch=0,
        policy_epoch=0,
        task_fences={"task": 1},
        resource_fences={"corridor": 1},
    )
    assert journal.register(event)["status"] == "ACCEPTED"
    assert journal.record_command(
        "cmd", event["payload_hash"], "PREPARED", event_id=event["id"]
    )["status"] == "RECORDED"
    assert journal.transition_command("cmd", "FAILED")["status"] == "RECORDED"

    result = journal.admit_next(event["id"], current_tick=1, hold_on_rejection=True)

    assert result == {"status": "HOLD", "reason_codes": ["INVALID_PREPARED_RECEIPT"]}
    assert journal.identity()["held"] is True
    assert journal.applied_cursor == 0
    assert journal.event(event["id"])["status"] == "RECEIVED"
    assert journal.receipt("cmd")["state"] == "FAILED"
    journal.close()


def test_rejection_hold_is_opt_in_and_flag_requires_exact_bool(tmp_path):
    journal = Journal(tmp_path / "legacy-default.sqlite")
    event = prepare_stale_command(journal)

    result = journal.admit_next(event["id"], current_tick=1)

    assert result == {
        "status": "REJECTED",
        "reason_codes": ["STALE_RESOURCE_FENCE", "STALE_TASK_FENCE"],
    }
    assert journal.identity()["held"] is False
    with pytest.raises(ValueError, match="exact bool"):
        journal.admit_next(event["id"], current_tick=1, hold_on_rejection=1)
    journal.close()


def test_hold_admissions_is_idempotent_at_the_current_identity(tmp_path):
    journal = Journal(tmp_path / "helper.sqlite")
    before = journal.identity()
    cursor = journal.applied_cursor

    first = journal.hold_admissions("legacy_unadmitted_replay")
    second = journal.hold_admissions("different_later_reason")

    assert first["status"] == second["status"] == "HELD"
    assert journal.identity()["held"] is True
    assert journal.identity()["coordinator_epoch"] == before["coordinator_epoch"]
    assert journal.identity()["hold_reason"] == "legacy_unadmitted_replay"
    assert journal.applied_cursor == cursor
    journal.close()


@pytest.mark.parametrize("reason", ["", "x" * 257, "bad\nreason", None])
def test_hold_admissions_rejects_unsafe_or_unbounded_reason(tmp_path, reason):
    journal = Journal(tmp_path / "invalid-reason.sqlite")
    with pytest.raises(ValueError, match="hold reason"):
        journal.hold_admissions(reason)
    assert journal.identity()["held"] is False
    journal.close()
