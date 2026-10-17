"""Process-restart regressions for graph-proven barrier HOLD/checkpoint boundaries."""
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.runtime.local_reconciliation import TrustedLocalReconciler
from witness_fleet.runtime.storage import TransitionStore

HOLDER = "crash-matrix-holder"


def _new_barrier(graph, service):
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=10)
    root = graph.read_version_root()
    transitions = TransitionStore(graph, holder_id=HOLDER)
    result = transitions.acquire_coordinator(
        expected_epoch=root["coordinator_epoch"], holder_id=HOLDER,
        now_utc=now.isoformat().replace("+00:00", "Z"),
        lease_expires_at_utc=expires.isoformat().replace("+00:00", "Z"),
        event_id="crash-matrix-barrier-" + service.root.name,
        effective_world_tick=service.world.world_tick,
    )
    assert result is not None
    from witness_fleet.domain import DispatchEvent

    row = transitions.read_outbox()[0]
    return DispatchEvent.model_validate({key: row[key] for key in DispatchEvent.model_fields})


def _setup(graph, tmp_path):
    service = SimulatorService(tmp_path / "simulator")
    service.create_episode("barrier-crash-matrix", "SC-001", 29)
    event = _new_barrier(graph, service)
    def clock():
        return datetime.now(UTC)
    TrustedLocalReconciler(graph, service, HOLDER, clock=clock).hold()
    return service, event, clock


def _assert_recovered(service, event):
    assert service.journal.applied_cursor == event.sequence
    assert service.journal.event(event.id)["status"] == "APPLIED"
    assert service.journal.identity()["held"] is False
    assert service.world.checkpoint()["held"] is False
    assert service.journal.checkpoint()["last_sequence"] == event.sequence
    assert service.status()["dispatch_ready"] is True


@pytest.mark.parametrize("fault_at", ["after_journal_commit", "before_native_release", "after_native_release"])
def test_resume_commit_and_native_release_faults_restart_into_explicit_recovery(
        isolated_console_graph, tmp_path, fault_at):  # noqa: F811
    from witness_fleet.runtime.barrier_resume import InjectedBarrierCrash, TrustedBarrierResumer

    service, event, clock = _setup(isolated_console_graph, tmp_path)
    try:
        with pytest.raises(InjectedBarrierCrash):
            TrustedBarrierResumer(isolated_console_graph, service, HOLDER, clock=clock).resume(
                event, fault_at=fault_at)
        assert service.journal.identity()["held"] is True
        if fault_at == "after_journal_commit":
            checkpoint = service.journal.checkpoint()
            assert checkpoint is not None
            assert checkpoint["last_sequence"] == event.sequence - 1
            assert service.world.checkpoint()["held"] is True
        elif fault_at == "before_native_release":
            checkpoint = service.journal.checkpoint()
            assert checkpoint is not None
            assert checkpoint["last_sequence"] == event.sequence - 1
            assert service.world.checkpoint()["held"] is True
        elif fault_at == 'after_native_release':
            checkpoint = service.journal.checkpoint()
            assert checkpoint is not None
            assert checkpoint["last_sequence"] == event.sequence - 1
            assert service.world.checkpoint()["held"] is False
            assert service.world.checkpoint()["hold_sources"] == {}
        else:
            checkpoint = service.journal.checkpoint()
            assert checkpoint is not None
            assert checkpoint["last_sequence"] == event.sequence
            native = json.loads(checkpoint["state_json"])["world"]
            assert native["held"] is False
            assert native["barrier_recovery"]["event_id"] == event.id
    finally:
        service.close()

    restarted = SimulatorService(tmp_path / "simulator")
    try:
        assert restarted.status()["held"] is True
        assert restarted.status()["dispatch_ready"] is False
        result = TrustedBarrierResumer(isolated_console_graph, restarted, HOLDER,
                                       clock=clock).recover(event)
        assert result == {"status": "RECOVERED", "event_id": event.id,
                          "cursor": event.sequence}
        _assert_recovered(restarted, event)
    finally:
        restarted.close()


def test_os_exit_at_journal_commit_reopens_held_without_python_cleanup(
        isolated_console_graph, tmp_path):  # noqa: F811
    from witness_fleet.runtime.barrier_resume import TrustedBarrierResumer
    service, event, clock = _setup(isolated_console_graph, tmp_path)
    graph_name = isolated_console_graph.graph_name
    graph_port = isolated_console_graph.port
    service_root = str(service.root)
    payload = event.model_dump(mode="json")
    service.close()

    script = r'''
import json, os
from datetime import UTC, datetime
from services.simulator.service import SimulatorService
from witness_fleet.domain import DispatchEvent
from witness_fleet.graph import GraphStore
from witness_fleet.runtime.barrier_resume import InjectedBarrierCrash, TrustedBarrierResumer
root, port, graph_name, raw, holder = __import__('sys').argv[1:]
graph = GraphStore(port=int(port), username='default')
graph.graph_name = graph_name
graph._graph = graph._client.select_graph(graph_name)
service = SimulatorService(root)
event = DispatchEvent.model_validate(json.loads(raw))
try:
    TrustedBarrierResumer(graph, service, holder, clock=lambda: datetime.now(UTC)).resume(
        event, fault_at='after_journal_commit')
except InjectedBarrierCrash:
    # Exit without service.close(), atexit handlers, or Python-level cleanup.
    os._exit(73)
os._exit(1)
'''
    child = subprocess.run(
        [sys.executable, "-c", script, service_root, str(graph_port), graph_name,
         json.dumps(payload), HOLDER], cwd=str(Path.cwd()),
        capture_output=True, text=True, timeout=60,
    )
    assert child.returncode == 73, child.stderr

    reopened = SimulatorService(service_root)
    try:
        assert reopened.status()["held"] is True
        assert reopened.status()["dispatch_ready"] is False
        result = TrustedBarrierResumer(isolated_console_graph, reopened, HOLDER,
                                       clock=clock).recover(event)
        assert result == {"status": "RECOVERED", "event_id": event.id,
                          "cursor": event.sequence}
        _assert_recovered(reopened, event)
    finally:
        reopened.close()


@pytest.mark.parametrize("fault_at", ["after_held_checkpoint", "after_release_checkpoint"])
def test_recovery_checkpoint_faults_restart_without_losing_hold_ownership(
        isolated_console_graph, tmp_path, fault_at):  # noqa: F811
    from witness_fleet.runtime.barrier_resume import InjectedBarrierCrash, TrustedBarrierResumer

    service, event, clock = _setup(isolated_console_graph, tmp_path)
    try:
        with pytest.raises(InjectedBarrierCrash, match="after journal commit"):
            TrustedBarrierResumer(isolated_console_graph, service, HOLDER, clock=clock).resume(
                event, fault_at="after_journal_commit")
    finally:
        service.close()

    committed = SimulatorService(tmp_path / "simulator")
    try:
        with pytest.raises(InjectedBarrierCrash):
            TrustedBarrierResumer(isolated_console_graph, committed, HOLDER, clock=clock).recover(
                event, fault_at=fault_at)
    finally:
        committed.close()

    restarted = SimulatorService(tmp_path / "simulator")
    try:
        assert restarted.status()["held"] is True
        assert restarted.status()["dispatch_ready"] is False
        result = TrustedBarrierResumer(isolated_console_graph, restarted, HOLDER,
                                       clock=clock).recover(event)
        assert result == {"status": "RECOVERED", "event_id": event.id,
                          "cursor": event.sequence}
        _assert_recovered(restarted, event)
    finally:
        restarted.close()
