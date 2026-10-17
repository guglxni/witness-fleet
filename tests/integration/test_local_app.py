"""A runnable inspection server constructs real graph/native dependencies."""
from fastapi.testclient import TestClient
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.api.local import create_local_app


def test_local_app_serves_real_graph_and_never_pretends_motion_is_ready(isolated_runtime_graph, tmp_path):  # noqa: F811
    ui_dir = tmp_path / 'ui'
    ui_dir.mkdir()
    (ui_dir / 'index.html').write_text('<html>inspection-ui-test</html>')
    app = create_local_app(tmp_path, graph_port=isolated_runtime_graph.port, graph_user='default',
                           ui_dir=ui_dir, port=8094)
    with TestClient(app) as client:
        assert 'inspection-ui-test' in client.get('/').text
        assert client.post('/api/run', json={'event_id': 'origin'},
                           headers={'origin': 'http://127.0.0.1:8094'}).status_code == 503
        assert client.post('/api/run', json={'event_id': 'bad-origin'},
                           headers={'origin': 'http://evil.example:8094'}).status_code == 403
        assert client.get('/api/state').json()['episode_id'] is None
        created = client.post('/api/incidents', json={
            'scenario': 'SC-001', 'seed': 3, 'event_id': 'local-app-incident'})
        assert created.status_code == 200
        state = created.json()
        assert len(state['robots']) == 3
        assert state['operator_mode'] == 'inspection_only'
        assert state['dispatch_ready'] is False
        assert client.post('/api/hold', json={'event_id': 'hold', 'reason': 'test'}).status_code == 503
        assert client.post('/api/incidents', json={
            'scenario': 'SC-002', 'seed': 3, 'event_id': 'different'}).status_code == 409
        assert client.get('/api/state').json()['episode_id'] == state['episode_id']
    # Construct a NEW service process boundary on the exact retained checkpoint.
    with TestClient(create_local_app(tmp_path, graph_port=isolated_runtime_graph.port,
                                    graph_user='default')) as restarted:
        replay = restarted.get('/api/state').json()
        assert replay['episode_id'] == state['episode_id']
        assert replay['world_tick'] == state['world_tick'] == 0
        assert replay['dispatch_ready'] is False
