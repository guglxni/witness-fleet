"""Mission factory opts in explicitly and never dispatches during startup."""
from fastapi.testclient import TestClient
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401


def test_mission_factory_bootstraps_without_command_or_tick(isolated_console_graph, tmp_path):  # noqa: F811
    from witness_fleet.api.mission import create_mission_app
    graph = isolated_console_graph
    app = create_mission_app(tmp_path, graph=graph, port=8095)
    with TestClient(app) as client:
        state = client.get('/api/state').json()
        assert state['operator_mode'] == 'local_mission'
        assert state['mission_phase'] == 'recovery_and_verification'
        assert len(state['tasks']) == 7
        assert state['world_tick'] == 0
        assert not state['commands']
        assert not state['dispatch_ready']
        assert client.post('/api/releases/'+state['release_id']+'/approve', json={
            'event_id': 'premature', 'expected_policy_epoch': state['policy_epoch']}).status_code == 409
        assert client.post('/api/run', headers={'Origin':'https://evil.example'},
                           json={'event_id':'evil'}).status_code == 403
        assert client.get('/api/state').json()['world_tick'] == 0
