"""HTTP adapter tests use an explicit stub, not fleet acceptance evidence."""
from fastapi.testclient import TestClient

from witness_fleet.api.app import create_app


class BoundaryController:
    def ready(self):
        return False

    def state(self):
        return {"revision": 1, "dispatch_ready": False}

    def source(self, revision_id):
        if revision_id == "missing":
            raise KeyError(revision_id)
        return {"revision_id": revision_id, "normalized_text": "Exact retained bytes."}

    def witness(self, decision_id):
        return {"decision_id": decision_id, "nodes": [], "edges": []}

    def command(self, command_id):
        return {"command_id": command_id, "state": "UNKNOWN"}

    def episode(self, episode_id):
        return {"id": episode_id, "state": "unverified"}

    def hold(self, reason, event_id):
        return {"reason": reason, "event_id": event_id, "dispatch_ready": False}

    def step(self, ticks, event_id):
        return {"ticks": ticks, "event_id": event_id}

    def run(self, event_id):
        return {"event_id": event_id}

    def approve_release(self, release_id, expected_policy_epoch, event_id):
        return {"release_id": release_id, "expected_policy_epoch": expected_policy_epoch, "event_id": event_id}


def test_read_boundary_preserves_unknown_outcome_and_retained_source():
    client = TestClient(create_app(BoundaryController()))
    assert client.get('/api/sources/revision-1').json()['normalized_text'] == 'Exact retained bytes.'
    assert client.get('/api/commands/c1').json()['state'] == 'UNKNOWN'
    assert client.get('/api/decisions/d1/witness').json()['decision_id'] == 'd1'
    assert client.get('/api/episodes/e1').json()['state'] == 'unverified'
    assert client.get('/api/sources/missing').status_code == 404


def test_hold_operator_endpoint_has_strict_reason_and_id():
    client = TestClient(create_app(BoundaryController()))
    result = client.post('/api/hold', json={'reason': 'operator stop', 'event_id': 'stop-1'})
    assert result.status_code == 200
    assert result.json()['dispatch_ready'] is False
    assert client.post('/api/hold', json={'reason': 'x', 'event_id': 'y', 'approved': True}).status_code == 422
    assert client.post('/api/hold', json={'reason': '', 'event_id': 'y'}).status_code == 422


def test_step_requires_bounded_strict_integer_and_event_id():
    client = TestClient(create_app(BoundaryController()))
    assert client.post('/api/step', json={'ticks': 10, 'event_id': 'step-1'}).json()['ticks'] == 10
    for ticks in (True, 0, -1, 100001, 1.5):
        assert client.post('/api/step', json={'ticks': ticks, 'event_id': 'step-x'}).status_code == 422


def test_release_actor_authority_cannot_be_set_by_json():
    client = TestClient(create_app(BoundaryController()))
    body = {'expected_policy_epoch': 3, 'notes': 'after reinspection', 'event_id': 'approve-1'}
    assert client.post('/api/releases/r1/approve', json=body).status_code == 200
    for field in ('actor', 'approved', 'scope', 'owner_id'):
        assert client.post('/api/releases/r1/approve', json={**body, field: 'maintenance_owner'}).status_code == 422


def test_cross_site_requests_cannot_run_or_approve():
    client = TestClient(create_app(BoundaryController()))
    assert client.post('/api/run', json={'event_id': 'run1'}, headers={'origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/hold', json={'event_id': 's', 'reason': 's'}, headers={'sec-fetch-site': 'cross-site'}).status_code == 403


def test_stream_snapshot_can_be_rehydrated_without_consumer_truth():
    controller = BoundaryController()
    controller.sse_snapshot = lambda: controller.state()
    client = TestClient(create_app(controller))
    response = client.get('/api/events?once=true')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/event-stream')
    assert 'id: 1\n' in response.text
    assert 'event: snapshot\n' in response.text
    assert '"dispatch_ready":false' in response.text


def test_validation_rejection_never_echoes_sensitive_request_values():
    client = TestClient(create_app(BoundaryController()))
    response = client.post('/api/run', json={'event_id': 'run-1', 'unexpected': 'private-marker'})
    assert response.status_code == 422
    assert 'private-marker' not in response.text
    assert response.json()['detail']['code'] == 'INVALID_INPUT'


def test_absent_controller_read_and_write_return_not_ready():
    client = TestClient(create_app())
    assert client.get('/api/sources/r1').status_code == 503
    assert client.post('/api/run', json={'event_id': 'r1'}).status_code == 503
