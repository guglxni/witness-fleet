"""Trusted graph-only barrier resume and explicit crash recovery contracts."""
from datetime import UTC, datetime, timedelta

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.runtime.local_reconciliation import TrustedLocalReconciler
from witness_fleet.runtime.storage import TransitionStore

HOLDER = "resume-holder"


def _make_barrier(graph, service, *, holder=HOLDER):
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=10)
    root = graph.read_version_root()
    result = TransitionStore(graph, holder_id=holder).acquire_coordinator(
        expected_epoch=root["coordinator_epoch"], holder_id=holder,
        now_utc=now.isoformat().replace("+00:00", "Z"),
        lease_expires_at_utc=expires.isoformat().replace("+00:00", "Z"),
        event_id="resume-barrier-" + service.root.name,
        effective_world_tick=service.world.world_tick,
    )
    assert result is not None
    from witness_fleet.domain import DispatchEvent

    row = TransitionStore(graph, holder_id=holder).read_outbox()[0]
    event = DispatchEvent.model_validate({
        key: row[key] for key in DispatchEvent.model_fields
    })
    return event


def _setup(graph, tmp_path):
    service = SimulatorService(tmp_path / "simulator")
    service.create_episode("barrier-resume", "SC-001", 19)
    event = _make_barrier(graph, service)
    def clock():
        return datetime.now(UTC)
    reconciler = TrustedLocalReconciler(graph, service, HOLDER, clock=clock)
    reconciler.hold()
    return service, event, clock


def test_exact_retained_graph_barrier_resumes_and_checkpoints_native_world(isolated_console_graph, tmp_path):  # noqa: F811
    from witness_fleet.runtime.barrier_resume import TrustedBarrierResumer

    service, event, clock = _setup(isolated_console_graph, tmp_path)
    try:
        result = TrustedBarrierResumer(isolated_console_graph, service, HOLDER, clock=clock).resume(event)

        assert result == {"status": "ACCEPTED", "event_id": event.id, "cursor": event.sequence}
        assert service.journal.applied_cursor == event.sequence
        assert service.journal.identity()["coordinator_epoch"] == event.coordinator_epoch
        assert service.journal.identity()["held"] is False
        assert service.world.checkpoint()["held"] is False
        assert service.journal.event(event.id)["status"] == "APPLIED"
        assert service.journal.checkpoint()["last_sequence"] == event.sequence
        assert service.status()["dispatch_ready"] is True
    finally:
        service.close()


def test_ordinary_receive_and_unrelated_native_hold_cannot_use_graph_equality(isolated_console_graph, tmp_path):  # noqa: F811
    from witness_fleet.runtime.barrier_resume import TrustedBarrierResumer

    service, event, clock = _setup(isolated_console_graph, tmp_path)
    try:
        service.world.hold("watchdog operator intervention", source_id="watchdog")
        before_cursor = service.journal.applied_cursor
        received = service.receive(event)

        assert received["status"] == "HOLD"
        assert service.journal.applied_cursor == before_cursor
        assert service.status()["held"] is True
        assert service.status()["dispatch_ready"] is False
        with pytest.raises(ValueError, match="hold|source|reconciliation"):
            TrustedBarrierResumer(isolated_console_graph, service, HOLDER, clock=clock).resume(event)
        sources = service.world.checkpoint()["hold_sources"]
        assert sources["watchdog"] == "watchdog operator intervention"
        assert sources["trusted_local_reconciliation"] == "trusted_local_reconciliation"
    finally:
        service.close()


def test_post_commit_fault_restarts_held_and_explicit_graph_recovery_finishes(isolated_console_graph, tmp_path):  # noqa: F811
    from witness_fleet.runtime.barrier_resume import InjectedBarrierCrash, TrustedBarrierResumer

    service, event, clock = _setup(isolated_console_graph, tmp_path)
    resumer = TrustedBarrierResumer(isolated_console_graph, service, HOLDER, clock=clock)
    try:
        with pytest.raises(InjectedBarrierCrash, match="injected.*after journal commit"):
            resumer.resume(event, fault_at="after_journal_commit")
        assert service.journal.applied_cursor == event.sequence
        assert service.status()["held"] is True
        assert service.journal.identity()["held"] is True
    finally:
        service.close()

    restarted = SimulatorService(tmp_path / "simulator")
    try:
        assert restarted.status()["held"] is True
        assert restarted.status()["dispatch_ready"] is False
        tick = restarted.world.world_tick
        assert restarted.advance(2)["held"] is True
        assert restarted.world.world_tick == tick

        recovered = TrustedBarrierResumer(isolated_console_graph, restarted, HOLDER,
                                          clock=clock).recover(event)

        assert recovered == {"status": "RECOVERED", "event_id": event.id,
                             "cursor": event.sequence}
        assert restarted.journal.applied_cursor == event.sequence
        assert restarted.journal.event(event.id)["status"] == "APPLIED"
        assert restarted.journal.identity()["held"] is False
        assert restarted.world.checkpoint()["held"] is False
        assert restarted.journal.checkpoint()["last_sequence"] == event.sequence
        assert restarted.status()["dispatch_ready"] is True
    finally:
        restarted.close()


def test_legacy_single_hold_restores_as_unknown_and_cannot_be_owner_cleared(tmp_path):
    from services.simulator.world import FacilityWorld

    world = FacilityWorld(seed=19, scenario="SC-001", episode_id="legacy-hold")
    try:
        checkpoint = world.checkpoint()
        checkpoint.pop("hold_sources", None)
        checkpoint["held"] = True
        checkpoint["hold_reason"] = "legacy unknown hold"
        world.restore(checkpoint)

        assert world.checkpoint()["held"] is True
        assert world.checkpoint()["hold_sources"] == {"legacy:unknown": "legacy unknown hold"}
        assert world.clear_hold_source("trusted_local_reconciliation",
                                       expected_reason="legacy unknown hold")["status"] == "held"
        assert world.checkpoint()["held"] is True
    finally:
        world.close()
