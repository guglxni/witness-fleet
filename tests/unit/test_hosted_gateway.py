"""Public hosted gateway contract and browser security tests."""
import re

from fastapi.testclient import TestClient

from witness_fleet.hosting import create_hosted_app

ORIGIN = "https://demo.example.test"


class FakeController:
    manifest = {
        "release_id": "release-secret-owner-not-public",
        "task_plan": [{"task_id": f"task-{i}", "kind": kind} for i, kind in enumerate(
            ["inspect", "recover", "inspect", "inspect", "navigate", "navigate", "deliver"]
        )],
    }

    def __init__(self):
        self.phase = "recovery_and_verification"
        self.tick = 0

    def state(self):
        return {
            "mission_phase": self.phase,
            "world_tick": self.tick,
            "policy_epoch": 4,
            "local_owner_id": "owner-private",
            "tenant_id": "tenant-private",
            "sources": [{"text": "private source quote", "path": "/private/path"}],
            "tasks": [{"id": "task-0", "kind": "inspect", "state": "READY", "robot_id": "scout"}],
            "robots": [{"id": "scout", "pose": {"x": 1.25, "y": 2.5, "yaw": 0.4}}],
            "commands": [],
            "metrics": {"recovery_verified": 0, "delivery_completed": 0},
            "approval_required": False,
            "dispatch_ready": False,
            "held": False,
        }

    def run(self, event_id):
        self.tick += 1
        self.phase = "awaiting_owner_release"
        return self.state()

    def step(self, ticks, event_id):
        self.tick += 1
        return self.state()

    def approve_release(self, release_id, expected_policy_epoch, event_id):
        self.phase = "courier_delivery"
        return self.state()

    def close(self):
        pass


def _client(tmp_path, **kwargs):
    app = create_hosted_app(tmp_path, origin=ORIGIN,
        controller_factory=lambda root: FakeController(), **kwargs)
    return TestClient(app, base_url=ORIGIN)


def _csrf(client):
    response = client.get("/demo/v1/bootstrap")
    assert response.status_code == 200, response.text
    token = response.json()["csrf_token"]
    assert client.cookies.get("__Host-wf-csrf")
    return token


def _create(client, token, key="create-one"):
    return client.post("/demo/v1/sessions", json={"request_id": key},
        headers={"Origin": ORIGIN, "X-CSRF-Token": token})


def test_bootstrap_and_create_returns_capability_only_in_secure_cookie(tmp_path):
    with _client(tmp_path) as client:
        token = _csrf(client)
        response = _create(client, token)
        assert response.status_code == 201, response.text
        assert "capability" not in response.text.lower()
        cookie = response.headers.get("set-cookie", "")
        assert "__Host-wf-session=" in cookie
        assert "secure" in cookie.lower() and "httponly" in cookie.lower()
        assert "samesite=strict" in cookie.lower() and "path=/" in cookie.lower()
        assert response.json()["session"]["status"] == "active"
        assert not re.search(r"owner-private|tenant-private|private source|/private/path", response.text)


def test_missing_or_cross_origin_create_is_rejected_before_provisioning(tmp_path):
    calls = []
    app = create_hosted_app(tmp_path, origin=ORIGIN,
        controller_factory=lambda root: calls.append(root) or FakeController())
    with TestClient(app, base_url=ORIGIN) as client:
        token = _csrf(client)
        for headers in ({"X-CSRF-Token": token},
                        {"Origin": "null", "X-CSRF-Token": token},
                        {"Origin": "https://attacker.invalid", "X-CSRF-Token": token}):
            response = client.post("/demo/v1/sessions", json={"request_id": "x"}, headers=headers)
            assert response.status_code == 403
        assert calls == []


def test_every_session_action_requires_cookie_and_session_csrf(tmp_path):
    with _client(tmp_path) as client:
        token = _csrf(client)
        assert _create(client, token).status_code == 201
        csrf = client.cookies.get("__Host-wf-session-csrf")
        assert csrf
        assert client.get("/demo/v1/state").status_code == 200
        assert client.post("/demo/v1/run", json={"request_id": "run-1"},
                           headers={"Origin": ORIGIN}).status_code == 403
        response = client.post("/demo/v1/run", json={"request_id": "run-1"},
                               headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["mission_phase"] == "awaiting_owner_release"
        assert set(data) == {"mission_phase", "revision_tick", "tasks", "robots", "commands", "metrics", "expected_policy_epoch"}
        assert "private source" not in response.text and "tenant-private" not in response.text and "owner-private" not in response.text


def test_unknown_routes_and_openapi_are_absent(tmp_path):
    with _client(tmp_path) as client:
        for path in ("/api/state", "/api/run", "/api/sources/x", "/openapi.json", "/docs"):
            assert client.get(path).status_code == 404
            assert client.post(path, json={}).status_code == 404


def test_session_creation_has_capacity_limits(tmp_path):
    with _client(tmp_path, max_sessions=1, max_active=1) as client:
        token = _csrf(client)
        assert _create(client, token, "first").status_code == 201
        second_token = _csrf(client)
        response = _create(client, second_token, "second")
        assert response.status_code == 429
        assert "detail" in response.json() and response.json()["detail"] == "capacity_exhausted"
