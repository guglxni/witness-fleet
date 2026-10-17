"""One true vertical graph-policy-native-outcome tracer (no fabricated ALLOW)."""
import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.coordinator import Coordinator


@pytest.fixture
def execution_console(isolated_console_graph, tmp_path):  # noqa: F811
    service = SimulatorService(tmp_path / 'sim')
    coordinator = Coordinator(isolated_console_graph, SourceStore(tmp_path / 'sources'), service)
    coordinator.create_incident('SC-001', 3, 'tracer-' + uuid.uuid4().hex)
    try:
        yield coordinator
    finally:
        coordinator.close()


def test_real_inspect_command_completes_from_retained_native_frame(execution_console):
    from witness_fleet.runtime.execution import FleetExecution

    owner = execution_console
    runner = FleetExecution(owner)
    runner.acquire()
    assert owner.ready()
    task_id = owner.manifest['task_ids'][0]
    result = runner.execute_task(task_id, parameters={}, expected_effects=('inspected',))
    assert result['task']['state'] == 'VERIFIED'
    state = owner.state()
    assert len(state['commands']) == 1
    command_id = state['commands'][0]['command_id']
    receipt = owner.simulator.command(command_id)
    assert receipt['state'] == 'OUTCOME_VERIFIED'
    assert receipt['native']['result']['robot_id'] == 'scout'
    assert owner.graph.get_node('Task', task_id)['state'] == 'VERIFIED'
    assert owner.graph.get_node('Command', command_id)['state'] == 'OUTCOME_VERIFIED'
    assert owner.ready()
