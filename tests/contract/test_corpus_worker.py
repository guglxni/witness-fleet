from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sdk_adapter import CorpusSDKAdapter
from worker import create_app

from witness_fleet.ingestion import SourceStore


def test_worker_exposes_typed_local_ingest_search_and_health(tmp_path):
    adapter = CorpusSDKAdapter(SourceStore(tmp_path / "retained"), fixture_root=Path("fixtures/sources"))
    client = TestClient(create_app(adapter))

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


def test_worker_rejects_unknown_fields_and_non_allowlisted_source(tmp_path):
    client = TestClient(create_app(CorpusSDKAdapter(SourceStore(tmp_path / "retained"))))
    rejected = client.post("/ingest", json={"source_id": "../../secrets"})
    assert rejected.status_code == 422
    assert rejected.json() == {"detail": "ingest request rejected"}
    assert client.post("/search", json={"query": "x", "cypher": "MATCH (n) DELETE n"}).status_code == 422


def test_worker_does_not_disclose_fixture_path_on_ingest_failure(tmp_path):
    adapter = CorpusSDKAdapter(SourceStore(tmp_path / "retained"), fixture_root=tmp_path / "private-fixtures")
    response = TestClient(create_app(adapter)).post(
        "/ingest", json={"source_id": "restriction_decision_r1"})

    assert response.status_code == 422
    assert response.json() == {"detail": "ingest request rejected"}
    assert str(tmp_path) not in response.text


def test_worker_health_reports_unavailable_graph_with_sanitized_503(tmp_path):
    adapter = CorpusSDKAdapter(SourceStore(tmp_path / "retained"))
    adapter.graph_ready = AsyncMock(return_value=False)
    client = TestClient(create_app(adapter))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "corpus graph unavailable"}
