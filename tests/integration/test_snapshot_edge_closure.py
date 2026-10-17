from __future__ import annotations

import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.graph import GraphStore

pytestmark = pytest.mark.integration


@pytest.fixture
def store(isolated_console_graph) -> GraphStore:  # noqa: F811
    return isolated_console_graph


def _same_graph_client(graph: GraphStore, *, max_edges: int | None = None) -> GraphStore:
    client = GraphStore(
        host=graph.host, port=graph.port, tenant_id=graph.tenant_id,
        username=graph.username, max_nodes=graph._snapshot_node_limit,
        max_edges=graph._snapshot_edge_limit if max_edges is None else max_edges,
        max_attempts=graph._snapshot_attempts,
    )
    client.graph_name = graph.graph_name
    client._graph = client._client.select_graph(client.graph_name)
    return client


def test_label_scoped_snapshot_excludes_edges_to_unselected_label(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    robot_id = f"it-snapshot-closure-{suffix}-robot"
    capability_id = f"it-snapshot-closure-{suffix}-capability"
    store.initialize()
    store.append_node("Robot", robot_id, {"robot_type": "courier"})
    store.append_node("Capability", capability_id, {"name": "inspect"})
    store.append_edge("HAS_CAPABILITY", "Robot", robot_id, "Capability", capability_id)

    snapshot = store.read_snapshot(labels=["Robot"], node_ids=[robot_id, capability_id])

    assert [node["id"] for node in snapshot["nodes"]] == [robot_id]
    assert snapshot["edges"] == []


def test_combined_label_scope_keeps_edge_with_both_returned_endpoints(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    robot_id = f"it-snapshot-closure-{suffix}-robot"
    capability_id = f"it-snapshot-closure-{suffix}-capability"
    store.initialize()
    store.append_node("Robot", robot_id, {"robot_type": "courier"})
    store.append_node("Capability", capability_id, {"name": "inspect"})
    store.append_edge("HAS_CAPABILITY", "Robot", robot_id, "Capability", capability_id)

    snapshot = store.read_snapshot(labels=["Robot", "Capability"], node_ids=[robot_id, capability_id])

    assert {node["id"] for node in snapshot["nodes"]} == {robot_id, capability_id}
    assert [
        (edge["source_label"], edge["source_id"], edge["target_label"], edge["target_id"])
        for edge in snapshot["edges"]
    ] == [("Robot", robot_id, "Capability", capability_id)]


def test_edge_cap_counts_only_edges_induced_by_selected_labels(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    robot_id = f"it-snapshot-closure-{suffix}-robot"
    task_id = f"it-snapshot-closure-{suffix}-task"
    resource_ids = [f"it-snapshot-closure-{suffix}-resource-{index}" for index in range(3)]
    store.initialize()
    store.append_node("Robot", robot_id, {"robot_type": "courier"})
    store.append_node("Task", task_id, {"kind": "inspect"})
    for resource_id in resource_ids:
        store.append_node("Resource", resource_id, {"kind": "corridor"})
        store.append_edge("REQUIRES_RESOURCE", "Task", task_id, "Resource", resource_id)

    capped = _same_graph_client(store, max_edges=1)
    snapshot = capped.read_snapshot(
        labels=["Robot"], node_ids=[robot_id, task_id, *resource_ids],
    )

    assert robot_id in {node["id"] for node in snapshot["nodes"]}
    assert all(node["labels"] == ["Robot"] for node in snapshot["nodes"])
    assert snapshot["edges"] == []
