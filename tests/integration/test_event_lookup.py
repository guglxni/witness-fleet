"""Read-only event lookup traverses the real HTTP, service, journal, and native owner."""

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from services.simulator.http import create_app
from services.simulator.service import SimulatorService
from witness_fleet.domain import DispatchEvent, canonical_json_hash
from witness_fleet.simulation.client import SimulatorClient


class _TestClientAdapter:
    """Bridge the synchronous httpx client interface into FastAPI's real TestClient."""

    def __init__(self, test_client):
        self.test_client = test_client

    def request(self, method, url, *, json=None, timeout=None, follow_redirects=False):
        return self.test_client.request(method, url, json=json, follow_redirects=follow_redirects)

    def close(self):
        pass


def _event(identifier, sequence, kind, payload):
    return DispatchEvent(
        id=identifier,
        sequence=sequence,
        coordinator_epoch=1,
        kind=kind,
        effective_world_tick=0,
        payload=payload,
        payload_hash=canonical_json_hash(payload),
    )


def _read_only_state(service):
    return {
        "status": service.status(),
        "cursor": service.journal.applied_cursor,
        "identity": service.journal.identity(),
        "events": service.journal._db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "receipts": service.journal._db.execute("SELECT COUNT(*) FROM commands").fetchone()[0],
        "skills": {robot: service.world.skill_status(robot) for robot in service.world.ROBOT_IDS},
        "snapshot": (service.root / "snapshot.json").read_bytes(),
    }


def test_event_lookup_returns_exact_applied_and_unadmitted_journal_identities(tmp_path):
    identifier = "evt/% snow-λ"
    gap_identifier = "gap/% snow-λ"
    applied = _event(
        identifier,
        1,
        "EPOCH_BARRIER",
        {"coordinator_epoch": 1, "holder_id": "native", "lease_expires_at_utc": "2026-10-16T00:00:00Z"},
    )
    unadmitted = _event(
        gap_identifier,
        3,
        "FENCE_INSTALL",
        {"task_id": "task", "task_fence": 1, "resource_fences": {"corridor": 1}},
    )
    with TestClient(create_app(root=tmp_path)) as client:
        assert client.get("/events/not-created-yet").json() == {
            "status": "NOT_FOUND", "event_id": "not-created-yet"
        }
        assert client.post("/episodes", json={"episode_id": "lookup", "scenario": "SC-001", "seed": 3}).status_code == 201
        assert client.post("/events", json=applied.model_dump(mode="json")).json()["status"] == "ACCEPTED"
        assert client.post("/events", json=unadmitted.model_dump(mode="json")).json()["status"] == "HOLD"

        service = client.app.state.service
        applied_before = _read_only_state(service)
        response = client.get("/events/" + quote(identifier, safe=""))
        assert response.status_code == 200
        assert response.json() == {
            "status": "KNOWN",
            "event": {
                "id": identifier,
                "sequence": 1,
                "payload_hash": applied.payload_hash,
                "kind": "EPOCH_BARRIER",
                "coordinator_epoch": 1,
                "effective_world_tick": 0,
                "payload": applied.model_dump(mode="json")["payload"],
                "status": "APPLIED",
            },
        }
        assert _read_only_state(service) == applied_before
        simulator = SimulatorClient("http://localhost", client=_TestClientAdapter(client))
        assert simulator.query_event(identifier) == response.json()
        assert _read_only_state(service) == applied_before

        unadmitted_before = _read_only_state(service)
        response = client.get("/events/" + quote(gap_identifier, safe=""))
        assert response.status_code == 200
        assert response.json()["status"] == "KNOWN"
        assert response.json()["event"] == {
            "id": gap_identifier,
            "sequence": 3,
            "payload_hash": unadmitted.payload_hash,
            "kind": "FENCE_INSTALL",
            "coordinator_epoch": 1,
            "effective_world_tick": 0,
            "payload": unadmitted.model_dump(mode="json")["payload"],
            "status": "RECEIVED",
        }
        assert _read_only_state(service) == unadmitted_before
        assert simulator.query_event(gap_identifier) == response.json()
        assert _read_only_state(service) == unadmitted_before


@pytest.mark.parametrize("identifier", [
    "literal%2F", "literal%25", ".", "..", "../x", "a/../b",
    "evt/% snow-λ", "a//b", "/leading", "a?b#c", "%", "雪",
])
def test_event_lookup_roundtrips_exact_ids_without_journal_or_native_changes(tmp_path, identifier):
    with TestClient(create_app(root=tmp_path)) as http:
        assert http.post("/episodes", json={"episode_id": "exact-id", "scenario": "SC-001", "seed": 3}).status_code == 201
        service = http.app.state.service
        event = _event(identifier, 2, "FENCE_INSTALL", {
            "task_id": "task", "task_fence": 1, "resource_fences": {"corridor": 1},
        })
        service.journal.register(event.model_dump(mode="json"))
        expected = {"status": "KNOWN", "event": service.journal.event(identifier)}
        before = _read_only_state(service)
        encoded = quote(identifier, safe="").replace(".", "%2E")
        response = http.get("/events/" + encoded)
        assert response.status_code == 200
        assert response.json() == expected
        simulator = SimulatorClient("http://localhost", client=_TestClientAdapter(http))
        assert simulator.query_event(identifier) == expected
        assert _read_only_state(service) == before


@pytest.mark.parametrize("identifier", ["literal%2F", "literal%25", ".", "..", "雪/%"])
def test_missing_event_lookup_preserves_exact_id_and_state(tmp_path, identifier):
    with TestClient(create_app(root=tmp_path)) as http:
        service = http.app.state.service
        before = service.journal.identity(), service.journal.applied_cursor
        simulator = SimulatorClient("http://localhost", client=_TestClientAdapter(http))
        assert simulator.query_event(identifier) == {"status": "NOT_FOUND", "event_id": identifier}
        assert (service.journal.identity(), service.journal.applied_cursor) == before


def test_service_event_rejects_invalid_ids_without_touching_journal(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        before = service.journal._db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        for identifier in ("", None, 7, True):
            with pytest.raises(ValueError):
                service.event(identifier)
        assert service.journal._db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before
    finally:
        service.close()
