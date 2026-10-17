"""The public host is a new explicit boundary, never the local owner API."""
from fastapi.testclient import TestClient

from witness_fleet.hosting import create_hosted_app

ORIGIN = 'https://demo.example.test'


def test_startup_is_inert_and_local_operator_routes_are_absent(tmp_path):
    calls = []
    app = create_hosted_app(tmp_path, origin=ORIGIN,
                           controller_factory=lambda root: calls.append(root))
    with TestClient(app, base_url=ORIGIN) as client:
        response = client.get('/healthz')
        assert response.status_code == 200
        assert response.json()['simulation_only'] is True
        assert response.json()['revision'] == 'development'
        assert client.post('/api/run', json={'event_id': 'bad'}).status_code == 404
        assert client.post('/api/releases/x/approve', json={}).status_code == 404
    assert calls == []
