from fastapi.testclient import TestClient

from services.simulator.http import create_app


def test_http_episode_and_state_return_declared_sensor_records(tmp_path):
    app = create_app(root=tmp_path)
    with TestClient(app) as client:
        assert client.post('/episodes', json={'episode_id': 'http-test', 'scenario': 'SC-001', 'seed': 3}).status_code == 201
        response = client.get('/observations')
        assert response.status_code == 200
        assert set(response.json()['robots']) == {'scout', 'recovery', 'courier'}
        assert 'model' not in response.json()
        assert client.post('/advance', json={'ticks': True}).status_code == 422
        assert client.post('/advance', json={'ticks': 2}).json()['world_tick'] == 2
