"""Safety boundaries in the graph/native mission executor."""
from datetime import UTC, datetime

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401
from test_mission_execution import mission_console  # noqa: F401

from witness_fleet.runtime.execution import FleetExecution
from witness_fleet.runtime.sensing import capture_evidence


def test_out_of_order_task_does_not_claim_or_dispatch(mission_console):  # noqa: F811
    owner = mission_console
    runner = FleetExecution(owner)
    runner.acquire()
    task = owner.manifest['task_plan'][1]
    before = owner.graph.read_version_root()
    with pytest.raises(ValueError, match='prerequisite'):
        runner.execute_task(task['task_id'], parameters=task['parameters'],
                            expected_effects=tuple(task['expected_effects']))
    assert owner.graph.read_version_root() == before
    assert not owner.simulator.status()['started_commands']


def test_foreign_actor_sensing_cannot_authorize_recovery(mission_console):  # noqa: F811
    owner = mission_console
    runner = FleetExecution(owner)
    runner.acquire()
    inspect, recovery = owner.manifest['task_plan'][:2]
    runner.execute_task(inspect['task_id'], parameters={}, expected_effects=('inspected',))
    observations = capture_evidence(owner.simulator, tenant_id=owner.graph.tenant_id,
        corridor_id=owner.manifest['corridor_id'], release_id=owner.manifest['release_id'],
        now_utc=datetime.now(UTC), observer_ids=('scout',))
    with pytest.raises(ValueError, match='NEEDS_EVIDENCE'):
        runner.execute_task(recovery['task_id'], parameters=recovery['parameters'],
                            expected_effects=('obstruction_moved',), observations=observations)
    assert owner.simulator.status()['started_commands'] == 1
    assert not any(c['kind'] == 'recover' for c in owner.state()['commands'])


def test_unknown_transport_latches_hold_and_does_not_retry(mission_console, monkeypatch):  # noqa: F811
    owner = mission_console
    runner = FleetExecution(owner)
    runner.acquire()
    calls = []
    original = runner.adapter.deliver

    def uncertain(event):
        if event.kind == 'COMMAND':
            calls.append(event.id)
            raise ConnectionError('no authoritative receipt')
        return original(event)

    monkeypatch.setattr(runner.adapter, 'deliver', uncertain)
    task = owner.manifest['task_plan'][0]
    with pytest.raises(ConnectionError):
        runner.execute_task(task['task_id'], parameters={}, expected_effects=('inspected',))
    assert len(calls) == 1
    assert owner.simulator.status()['held'] is True
    command = owner.graph.get_node('Command', calls[0])
    assert command['state'] == 'SENT'
    with pytest.raises(ValueError, match='reconciliation'):
        runner.acquire()
    assert len(calls) == 1
    assert owner.simulator.status()['started_commands'] == 0
