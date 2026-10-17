from __future__ import annotations

import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.graph import GraphStore

pytestmark = pytest.mark.integration


def _graph_version(graph: GraphStore) -> int:
    root = graph.read_version_root()
    assert root is not None
    return root["graph_version"]


def test_canonical_source_id_is_appendable_immutable_and_snapshot_visible(isolated_console_graph):  # noqa: F811
    graph = isolated_console_graph
    node_id = f"it-sourceidentity-{uuid.uuid4().hex}"
    attributes = {
        "source_id": "canonical-safe-source",
        "source_type": "synthetic",
        "display_name": "Synthetic fixture",
        "access_class": "synthetic",
    }
    before = graph.read_version_root()
    assert before is not None

    created = graph.append_node("Source", node_id, attributes)
    assert created["id"] == node_id
    assert created["source_id"] == "canonical-safe-source"
    assert _graph_version(graph) == before["graph_version"] + 1

    retried = graph.append_node("Source", node_id, attributes)
    assert retried == created
    assert _graph_version(graph) == before["graph_version"] + 1

    with pytest.raises(ValueError, match="immutable attributes"):
        graph.append_node("Source", node_id, {**attributes, "source_id": "changed-source"})
    assert graph.get_node("Source", node_id) == created
    snapshot = graph.read_snapshot(node_ids=[node_id])
    assert snapshot["nodes"] == [{"labels": ["Source"], **created}]
    assert _graph_version(graph) == before["graph_version"] + 1

    with pytest.raises(ValueError, match="attributes are not approved for Source"):
        graph.append_node("Source", f"{node_id}-unknown", {**attributes, "unapproved": "no"})
    assert graph.get_node("Source", f"{node_id}-unknown") is None
    assert _graph_version(graph) == before["graph_version"] + 1
