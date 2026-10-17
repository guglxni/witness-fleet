from fastapi.testclient import TestClient

from services.simulator.http import create_app


def test_remote_host_rejected_and_invalid_request_does_not_echo_payload(tmp_path):
    app = create_app(root=tmp_path)
    with TestClient(app) as client:
        assert client.get('/state', headers={'host': 'untrusted.example'}).status_code == 400
        reply = client.post('/episodes', json={'episode_id':'x','scenario':'SC-001', 'seed':3, 'secret':'sensitive-marker'})
        assert reply.status_code == 422
        assert 'sensitive-marker' not in reply.text


def test_advance_without_episode_is_not_ready(tmp_path):
    with TestClient(create_app(root=tmp_path)) as client:
        assert client.post('/advance', json={'ticks':1}).status_code == 409
