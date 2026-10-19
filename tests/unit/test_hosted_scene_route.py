"""New scene assets are read-only, authenticated, and never mount local APIs."""
from fastapi.testclient import TestClient

from witness_fleet.hosting import create_hosted_app

ORIGIN = 'https://demo.example.test'


class SceneController:
    manifest = {'release_id': 'private-release'}

    def __init__(self):
        self.simulator = self
        self.reads = 0

    def state(self):
        return {'mission_phase': 'recovery_and_verification', 'revision': 2,
                'policy_epoch': 1, 'tasks': [], 'robots': [], 'commands': [], 'metrics': {}}

    def scene_snapshot(self):
        self.reads += 1
        return {'schema_version': 1, 'source': 'mujoco_snapshot', 'world_tick': 0,
                'model_sha256': 'a' * 64, 'units': 'm', 'up_axis': 'z',
                'geometries': [], 'sites': []}

    def close(self):
        pass


def test_scene_requires_existing_session_without_starting_or_stepping(tmp_path):
    calls = []
    controller = SceneController()
    app = create_hosted_app(tmp_path, origin=ORIGIN,
                            controller_factory=lambda root: calls.append(root) or controller)
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get('/demo/v1/scene').status_code == 401
        assert calls == []
        csrf = client.get('/demo/v1/bootstrap').json()['csrf_token']
        created = client.post('/demo/v1/sessions', json={'request_id': 'scene-read'},
                              headers={'Origin': ORIGIN, 'X-CSRF-Token': csrf})
        assert created.status_code == 201
        response = client.get('/demo/v1/scene')
        assert response.status_code == 200
        assert response.json()['source'] == 'mujoco_snapshot'
        assert response.json()['world_tick'] == 0
        assert controller.reads == 1
        assert len(calls) == 1
        assert client.post('/demo/v1/scene', json={}).status_code == 405
        assert client.get('/api/state').status_code == 404
        assert response.headers['cache-control'] == 'no-store'
