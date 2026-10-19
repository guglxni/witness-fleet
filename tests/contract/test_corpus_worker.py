# pytest_plugins must precede imports so pytest owns the real ACL fixture.
# ruff: noqa: E402
pytest_plugins = ["isolated_acl_fixture"]

from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sdk_adapter import CorpusSDKAdapter
from worker import create_app

from witness_fleet.ingestion import SourceStore


def test_worker_exposes_typed_local_ingest_search_and_health(tmp_path, isolated_acl_server):
    adapter = CorpusSDKAdapter(SourceStore(tmp_path / "retained"), fixture_root=Path("fixtures/sources"),
                               host=isolated_acl_server.host, port=isolated_acl_server.port)
    client = TestClient(create_app(adapter))

    # A clean corpus fixture has no graph key until first ingestion. Bootstrap
    # through the real ingest endpoint before requiring graph-readiness health.
    first = client.post("/ingest", json={"source_id": "restriction_decision_r1"})
    assert first.status_code == 200
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    ingested = client.post("/ingest", json={"source_id": "restriction_decision_r1"})
    assert ingested.status_code == 200
    assert ingested.json()["rows"] == 1
    results = client.post("/search", json={"query": "paused", "limit": 10})
    assert results.status_code == 200
    assert results.json()["candidates"]
    for item in results.json()["candidates"]:
        assert item["quote"]
        assert item["start"] < item["end"]


def test_worker_rejects_unknown_fields_and_non_allowlisted_source(tmp_path, isolated_acl_server):
    adapter = CorpusSDKAdapter(SourceStore(tmp_path / "retained"), host=isolated_acl_server.host,
                               port=isolated_acl_server.port)
    client = TestClient(create_app(adapter))
    rejected = client.post("/ingest", json={"source_id": "../../secrets"})
    assert rejected.status_code == 422
    assert rejected.json() == {"detail": "ingest request rejected"}
    assert client.post("/search", json={"query": "x", "cypher": "MATCH (n) DELETE n"}).status_code == 422


def test_worker_does_not_disclose_fixture_path_on_ingest_failure(tmp_path, isolated_acl_server):
    adapter = CorpusSDKAdapter(
        SourceStore(tmp_path / "retained"), fixture_root=tmp_path / "private-fixtures",
        host=isolated_acl_server.host, port=isolated_acl_server.port,
    )
    response = TestClient(create_app(adapter)).post(
        "/ingest", json={"source_id": "restriction_decision_r1"})

    assert response.status_code == 422
    assert response.json() == {"detail": "ingest request rejected"}
    assert str(tmp_path) not in response.text


def test_worker_health_reports_unavailable_graph_with_sanitized_503(tmp_path, isolated_acl_server):
    adapter = CorpusSDKAdapter(SourceStore(tmp_path / "retained"), host=isolated_acl_server.host,
                               port=isolated_acl_server.port)
    adapter.graph_ready = AsyncMock(return_value=False)
    client = TestClient(create_app(adapter))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "corpus graph unavailable"}
