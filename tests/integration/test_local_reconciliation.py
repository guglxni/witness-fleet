import json
from datetime import UTC, datetime

import pytest
from test_protocol_commands import command_event

from services.simulator.service import SimulatorService
from witness_fleet.runtime.local_reconciliation import TrustedLocalReconciler


class BoundedLeaseGraph:
    def __init__(self, *, epoch=3, holder="trusted-holder", lease="2026-10-16T02:00:00Z"):
        self.root = {
            "coordinator_holder_id": holder,
            "coordinator_epoch": epoch,
            "coordinator_lease_expires_at_utc": lease,
        }
        self.reads = 0
        self.change_on_read = None

    def read_version_root(self):
        self.reads += 1
        if self.change_on_read == self.reads:
            self.root.update({"coordinator_holder_id": "new-holder", "coordinator_epoch": 4})
        return dict(self.root)


def reconciler(graph, service):
    return TrustedLocalReconciler(
        graph, service, "trusted-holder",
        clock=lambda: datetime(2026, 10, 16, 1, 0, tzinfo=UTC),
    )


def test_hold_fences_durable_journal_and_native_checkpoint(tmp_path):
    service = SimulatorService(tmp_path / "native")
    try:
        service.create_episode("trusted-hold", "SC-001", 7)
        graph = BoundedLeaseGraph()

        result = reconciler(graph, service).hold()

        assert result["status"] == "HELD"
        assert service.journal.identity()["coordinator_epoch"] == 3
        assert service.journal.identity()["held"] is True
        assert service.world.checkpoint()["held"] is True
        checkpoint = service.journal.checkpoint()
        assert checkpoint is not None
        assert json.loads(checkpoint["state_json"])["world"]["held"] is True
    finally:
        service.close()


def test_hold_rejects_foreign_or_expired_graph_lease_without_mutation(tmp_path):
    for graph in (BoundedLeaseGraph(holder="other"),
                  BoundedLeaseGraph(lease="2026-10-16T00:30:00Z")):
        service = SimulatorService(tmp_path / f"native-{graph.root['coordinator_holder_id']}-{graph.root['coordinator_lease_expires_at_utc'][-2:]}")
        try:
            service.create_episode("trusted-hold", "SC-001", 7)
            before = service.journal.identity()
            with pytest.raises(ValueError):
                reconciler(graph, service).hold()
            assert service.journal.identity() == before
            assert service.world.checkpoint()["held"] is False
        finally:
            service.close()


def test_hold_postcheck_takeover_rejects_but_keeps_native_and_durable_hold(tmp_path):
    service = SimulatorService(tmp_path / "native")
    try:
        service.create_episode("trusted-hold", "SC-001", 7)
        graph = BoundedLeaseGraph()
        graph.change_on_read = 2

        with pytest.raises(ValueError, match="lease|authority|changed|current"):
            reconciler(graph, service).hold()

        assert service.journal.identity()["held"] is True
        assert service.journal.identity()["coordinator_epoch"] == 3
        assert service.world.checkpoint()["held"] is True
    finally:
        service.close()


def _prepare_unadmitted_command(service):
    event = command_event()
    service.journal.register(event.model_dump(mode="json"))
    service.journal.record_command(
        "cmd", event.payload_hash, "PREPARED", event_id=event.id,
    )
    return event


def test_cancel_prepared_requires_durable_proof_and_retains_original_event(tmp_path):
    service = SimulatorService(tmp_path / "native")
    try:
        service.create_episode("trusted-cancel", "SC-001", 7)
        event = _prepare_unadmitted_command(service)
        graph = BoundedLeaseGraph()
        local = reconciler(graph, service)
        local.hold()

        result = local.cancel_prepared(event)

        assert result["status"] == "CANCELLED"
        assert service.journal.cancellation(event.id)["original_event_id"] == event.id
        retained = service.journal.event(event.id)
        assert retained["payload"] == event.model_dump(mode="json")["payload"]
        assert service.journal.applied_cursor == 0
        assert service.journal.identity()["held"] is True
    finally:
        service.close()


def test_cancel_prepared_rejects_absent_event_without_not_found_proof(tmp_path):
    service = SimulatorService(tmp_path / "native")
    try:
        service.create_episode("trusted-cancel", "SC-001", 7)
        event = command_event()
        graph = BoundedLeaseGraph()
        local = reconciler(graph, service)
        local.hold()

        with pytest.raises(ValueError):
            local.cancel_prepared(event)

        assert service.journal.cancellation(event.id) is None
        assert service.journal.identity()["held"] is True
    finally:
        service.close()


def test_cancel_postcheck_takeover_rejects_but_keeps_committed_disposition(tmp_path):
    service = SimulatorService(tmp_path / "native")
    try:
        service.create_episode("trusted-cancel", "SC-001", 7)
        event = _prepare_unadmitted_command(service)
        graph = BoundedLeaseGraph()
        local = reconciler(graph, service)
        local.hold()
        graph.reads = 0
        graph.change_on_read = 2

        with pytest.raises(ValueError, match="lease|authority|changed|current"):
            local.cancel_prepared(event)

        assert service.journal.cancellation(event.id)["status"] == "CANCELLED"
        assert service.journal.identity()["held"] is True
    finally:
        service.close()
