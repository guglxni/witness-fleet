"""Real graph and native read-only HTTP tracer, not motion acceptance."""
from fastapi.testclient import TestClient
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.api.app import create_app
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.coordinator import Coordinator


def test_real_incident_source_witness_and_unavailable_motion(isolated_runtime_graph, tmp_path):  # noqa: F811
    controller = Coordinator(isolated_runtime_graph, SourceStore(tmp_path / 'sources'),
                             SimulatorService(tmp_path / 'sim'))
    try:
        client = TestClient(create_app(controller), raise_server_exceptions=False)
        response = client.post('/api/incidents', json={
            'scenario': 'SC-001', 'seed': 3, 'event_id': 'live-console-tracer'})
        assert response.status_code == 200
        projection = response.json()
        assert len(projection['robots']) == 3
        assert projection['dispatch_ready'] is False
        assert projection['operator_mode'] == 'inspection_only'
        assert projection['hold_reason'] == 'RUNTIME_INTEGRATION_INCOMPLETE'
        source = projection['sources'][0]
        assert source['revision_id']
        fetched = client.get('/api/sources/' + source['revision_id'])
        assert fetched.status_code == 200
        assert fetched.json()['text']
        witness = client.get('/api/decisions/' + projection['restrictions'][0]['id'] + '/witness')
        assert witness.status_code == 200
        assert witness.json()['completeness'] == 'complete'
        assert client.get('/api/episodes/' + projection['episode_id']).json()['verification_state'] == 'unverified'
        assert client.get('/api/commands/missing').status_code == 404
        for route, payload in [('/api/run', {'event_id': 'run'}),
                               ('/api/step', {'event_id': 'step', 'ticks': 1}),
                               ('/api/releases/' + projection['release_id'] + '/approve',
                                {'event_id': 'approve', 'expected_policy_epoch': 0})]:
            blocked = client.post(route, json=payload)
            assert blocked.status_code == 503
            assert blocked.json()['detail']['code'] == 'RUNTIME_INTEGRATION_INCOMPLETE'
        assert controller.simulator.started_commands == 0
        assert client.get('/api/events?once=true').status_code == 200
    finally:
        controller.close()
