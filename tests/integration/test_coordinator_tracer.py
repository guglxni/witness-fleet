"""Tracer slice: canonical graph setup and truthful operator projection."""
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.coordinator import Coordinator


def test_create_incident_populates_graph_without_starting_motion(isolated_runtime_graph, tmp_path):  # noqa: F811
    simulator = SimulatorService(tmp_path / 'sim')
    controller = Coordinator(isolated_runtime_graph, SourceStore(tmp_path / 'sources'), simulator)
    try:
        before = controller.state()
        assert before['episode_id'] is None
        assert before['dispatch_ready'] is False
        created = controller.create_incident('SC-001', 3, 'create-tracer')
        assert created['episode_id']
        assert created['scenario'] == 'SC-001'
        assert {robot['id'] for robot in created['robots']} == {'scout', 'recovery', 'courier'}
        assert len(created['tasks']) == 5
        assert created['model_mode'] == 'disabled'
        assert created['metrics']['delivery_completed'] == 0
        assert simulator.started_commands == 0
        assert created['graph_version'] > 0
        witness = controller.witness(created['restrictions'][0]['id'])
        assert witness['completeness'] == 'complete'
        assert len(witness['nodes']) <= 15
        assert not any(node['type'] == 'Permission' for node in witness['nodes'])
        assert witness['spans']
        assert any(edge['relationship'] == 'OWNED_BY' for edge in witness['edges'])
        assert any(edge['relationship'] == 'SUPPORTED_BY' for edge in witness['edges'])
        span = witness['spans'][0]
        source = controller.source(span['revision_id'])
        assert source['text'][span['start']:span['end']] == span['quote']
        assert controller.create_incident('SC-001', 3, 'create-tracer')['episode_id'] == created['episode_id']
    finally:
        controller.close()
