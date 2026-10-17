from pathlib import Path

import pytest

from services.corpus.sdk_adapter import SDK_PIN, CorpusSDKAdapter
from witness_fleet.ingestion import SourceStore


def test_pinned_sdk_ingests_synthetic_source_as_real_queryable_span(tmp_path):
    source = Path("fixtures/sources/restriction_decision_r1.json").read_bytes()
    store = SourceStore(tmp_path / "retained")
    adapter = CorpusSDKAdapter(store)

    with pytest.raises(ValueError, match="allowlist"):
        adapter.ingest_source("test-restriction", source)
    with pytest.raises(ValueError, match="do not match"):
        adapter.ingest_source("restriction_decision_r1", b"untrusted payload")
    result = adapter.ingest_source("restriction_decision_r1", source)
    candidates = adapter.search("paused", limit=10)

    assert SDK_PIN == "35e67a0b27fdcc7f2c28508b09e86169851a8187"
    assert result["revision_id"]
    assert result["rows"] > 0
    assert candidates
    for candidate in candidates:
        validated = store.validate_span(candidate["revision_id"], candidate["start"], candidate["end"], candidate["quote"])
        assert validated["quote_hash"] == candidate["quote_hash"]
    assert any(item["source_id"] == "restriction_decision_r1" for item in candidates)


def test_sdk_adapter_has_no_delete_or_model_finalize_surface(tmp_path):
    adapter = CorpusSDKAdapter(SourceStore(tmp_path / "retained"))
    assert not hasattr(adapter, "delete_graph")
    assert not hasattr(adapter, "finalize")


def test_row_spans_locate_every_occurrence_without_reusing_first_offset():
    text = "alpha policy\nalpha policy"

    rows = CorpusSDKAdapter._rows(text, "facility_manual_r1", "facility_manual_r1:revision")

    assert [(int(row["start"]), int(row["end"])) for row in rows] == [(0, 12), (13, 25)]
    assert all(text[int(row["start"]):int(row["end"])] == row["quote"] for row in rows)


def test_adapter_rejects_non_corpus_graph(tmp_path):
    with pytest.raises(ValueError, match="synthetic tenant corpus graph"):
        CorpusSDKAdapter(SourceStore(tmp_path / "retained"), graph_name="wf:demo:ops")
    with pytest.raises(ValueError, match="least-privilege corpus role"):
        CorpusSDKAdapter(SourceStore(tmp_path / "retained"), username="admin")


def test_adapter_path_rejects_symlinked_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_bytes(b'{"quote": "untrusted"}')
    (fixtures / "restriction_decision_r1.json").symlink_to(outside)
    adapter = CorpusSDKAdapter(SourceStore(tmp_path / "retained"), fixture_root=fixtures)

    with pytest.raises(ValueError, match="beneath fixture root"):
        adapter.ingest_path("restriction_decision_r1")
