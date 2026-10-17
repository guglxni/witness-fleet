from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.graph import GraphStore
from witness_fleet.graph.store import OversizeSnapshot, StaleSnapshot

pytestmark = pytest.mark.integration


@pytest.fixture
def store(isolated_console_graph) -> GraphStore:  # noqa: F811
    return isolated_console_graph


def _same_graph_client(graph: GraphStore, **limits: int) -> GraphStore:
    """Open an independent client connection to this test's retained namespace."""
    client = GraphStore(
        host=graph.host, port=graph.port, tenant_id=graph.tenant_id,
        username=graph.username,
        max_nodes=limits.get("max_nodes", graph._snapshot_node_limit),
        max_edges=limits.get("max_edges", graph._snapshot_edge_limit),
        max_attempts=limits.get("max_attempts", graph._snapshot_attempts),
    )
    client.graph_name = graph.graph_name
    client._graph = client._client.select_graph(client.graph_name)
    return client


def test_migration_and_health_use_real_graph(store: GraphStore) -> None:
    assert store.health() is True
    before = store.read_version_root()
    state = store.initialize()
    assert state["id"] == "fleet"
    assert state["tenant_id"] == "demo"
    assert state["schema_version"] == 1
    if before is not None:
        assert state == before
    assert store.read_version_root()["id"] == "fleet"


def test_append_event_is_idempotent_and_rejects_hash_conflicts(store: GraphStore) -> None:
    store.initialize()
    version_before = store.read_version_root()["graph_version"]
    event_id = f"it-event-{uuid.uuid4().hex}"
    event = {
        "kind": "OBSERVATION",
        "payload_hash": "sha256:abc",
        "subject_ids_json": '["robot-test"]',
        "effective_world_tick": 1,
    }
    first = store.append_event(event_id=event_id, **event)
    second = store.append_event(event_id=event_id, **event)
    assert {key: value for key, value in first.items() if key != "created"} == {
        key: value for key, value in second.items() if key != "created"
    }
    assert first["created"] is True
    assert second["created"] is False
    assert store.read_version_root()["graph_version"] == version_before + 1
    with pytest.raises(ValueError, match="payload hash"):
        store.append_event(event_id=event_id, **{**event, "payload_hash": "sha256:different"})
    assert store.query_count >= 3


def test_append_node_is_immutable_and_advances_version_once(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    store.initialize()
    before = store.read_version_root()["graph_version"]
    robot_id = f"it-robot-{suffix}"
    attrs = {"robot_type": "courier", "footprint_m": 0.5, "payload_kg": 2.0,
             "capability_version": 1, "available": True}
    created = store.append_node("Robot", robot_id, attrs)
    assert created["robot_type"] == "courier"
    assert store.read_version_root()["graph_version"] == before + 1
    assert store.append_node("Robot", robot_id, attrs) == created
    assert store.read_version_root()["graph_version"] == before + 1
    with pytest.raises(ValueError, match="immutable attributes"):
        store.append_node("Robot", robot_id, {**attrs, "robot_type": "forklift"})
    assert store.get_node("Robot", robot_id)["robot_type"] == "courier"


def test_append_edge_is_immutable_and_advances_version_once(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    store.initialize()
    source_id, target_id = f"it-robot-{suffix}", f"it-capability-{suffix}"
    store.append_node("Robot", source_id, {"robot_type": "courier"})
    store.append_node("Capability", target_id, {"name": "inspect", "limits_json": "{}"})
    before = store.read_version_root()["graph_version"]
    store.append_edge("HAS_CAPABILITY", "Robot", source_id, "Capability", target_id, {"rank": 1})
    after_create = store.read_version_root()["graph_version"]
    assert after_create == before + 1
    store.append_edge("HAS_CAPABILITY", "Robot", source_id, "Capability", target_id, {"rank": 1})
    assert store.read_version_root()["graph_version"] == after_create
    with pytest.raises(ValueError, match="immutable attributes"):
        store.append_edge("HAS_CAPABILITY", "Robot", source_id, "Capability", target_id, {"rank": 2})
    edge = next(edge for edge in store.read_snapshot(node_ids=[source_id, target_id])["edges"]
                if edge["source_id"] == source_id and edge["target_id"] == target_id)
    assert edge["properties"]["rank"] == 1


def test_atomic_update_guards_graph_version_and_appends_dispatch_event(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    expected = store.initialize()["graph_version"]
    result = store.atomic_update(
        expected_graph_version=expected,
        label="Command",
        node_id=f"it-command-{suffix}",
        attributes={
            "command_id": f"it-command-{suffix}",
            "payload_hash": "sha256:command",
            "fence": 1,
            "state": "PENDING",
            "authorization_id": f"it-auth-{suffix}",
            "dispatch_sequence": 1,
            "coordinator_epoch": 0,
        },
        event={
            "event_id": f"it-dispatch-{suffix}",
            "kind": "COMMAND",
            "payload_hash": "sha256:command",
            "subject_ids_json": f'["it-robot-{suffix}"]',
            "effective_world_tick": 1,
        },
    )
    assert result is not None
    assert result["graph_version"] == expected + 1
    assert store.get_node("Command", f"it-command-{suffix}")["command_id"] == f"it-command-{suffix}"
    assert store.get_node("DispatchEvent", f"it-dispatch-{suffix}")["sequence"] > 0
    stale = store.atomic_update(
        expected_graph_version=expected,
        label="Robot",
        node_id=f"it-stale-{suffix}",
        attributes={"robot_type": "courier"},
    )
    assert stale is None
    assert store.get_node("Robot", f"it-stale-{suffix}") is None


def test_atomic_update_rejects_event_for_non_deliverable_label(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    store.initialize()
    before = store.read_version_root()["graph_version"]

    with pytest.raises(ValueError, match="DELIVERS"):
        store.atomic_update(
            expected_graph_version=before,
            label="Robot",
            node_id=f"it-robot-event-{suffix}",
            attributes={"robot_type": "courier"},
            event={
                "event_id": f"it-event-invalid-target-{suffix}",
                "kind": "COMMAND",
                "payload_hash": "sha256:command",
                "subject_ids_json": f'["it-robot-event-{suffix}"]',
                "effective_world_tick": 1,
            },
        )

    assert store.get_node("Robot", f"it-robot-event-{suffix}") is None
    assert store.get_node("DispatchEvent", f"it-event-invalid-target-{suffix}") is None
    assert store.read_version_root()["graph_version"] == before


def test_atomic_update_cannot_overwrite_existing_immutable_robot_identity(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    robot_id = f"it-atomic-immutable-{suffix}"
    store.initialize()
    store.append_node("Robot", robot_id, {
        "robot_type": "courier", "footprint_m": 0.5, "payload_kg": 2.0,
        "capability_version": 1, "available": True,
    })
    before = store.read_version_root()["graph_version"]

    result = store.atomic_update(
        expected_graph_version=before,
        label="Robot",
        node_id=robot_id,
        attributes={"robot_type": "forklift", "available": False},
    )

    assert result is None
    assert store.get_node("Robot", robot_id)["robot_type"] == "courier"
    assert store.get_node("Robot", robot_id)["available"] is True
    assert store.read_version_root()["graph_version"] == before


def test_atomic_update_changes_only_declared_mutable_field(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    robot_id = f"it-atomic-mutable-{suffix}"
    store.initialize()
    store.append_node("Robot", robot_id, {
        "robot_type": "courier", "footprint_m": 0.5, "payload_kg": 2.0,
        "capability_version": 1, "available": True,
    })
    before = store.read_version_root()["graph_version"]

    result = store.atomic_update(
        expected_graph_version=before, label="Robot", node_id=robot_id,
        attributes={"available": False},
    )

    assert result is not None
    assert result["graph_version"] == before + 1
    assert store.get_node("Robot", robot_id)["robot_type"] == "courier"
    assert store.get_node("Robot", robot_id)["available"] is False


def test_read_snapshot_returns_raw_canonical_records(store: GraphStore) -> None:
    snapshot = store.read_snapshot(labels=["Task", "Resource"])
    assert set(snapshot) == {"nodes", "edges", "versions"}
    assert isinstance(snapshot["nodes"], list)
    assert isinstance(snapshot["edges"], list)
    assert snapshot["versions"]["graph_version"] >= 0


def test_read_snapshot_can_scope_nodes_and_induced_edges(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    store.initialize()
    robot_id, capability_id, outside_id = (
        f"it-snapshot-scope-{suffix}-{part}" for part in ("robot", "capability", "outside")
    )
    store.append_node("Robot", robot_id, {"robot_type": "courier"})
    store.append_node("Capability", capability_id, {"name": "inspect"})
    store.append_node("Capability", outside_id, {"name": "outside"})
    store.append_edge("HAS_CAPABILITY", "Robot", robot_id, "Capability", capability_id)
    store.append_edge("HAS_CAPABILITY", "Robot", robot_id, "Capability", outside_id)

    snapshot = store.read_snapshot(node_ids=[robot_id, capability_id])

    assert {node["id"] for node in snapshot["nodes"]} == {robot_id, capability_id}
    assert [(edge["source_id"], edge["target_id"]) for edge in snapshot["edges"]] == [
        (robot_id, capability_id),
    ]


def test_normative_governance_relationship_variants_are_appendable(store: GraphStore) -> None:
    suffix = uuid.uuid4().hex
    store.initialize()
    entities = {
        "corridor": ("Corridor", {}), "map": ("Map", {}),
        "permission": ("Permission", {}), "decision": ("Decision", {}),
        "release": ("Release", {}), "span": ("EvidenceSpan", {}),
        "claim": ("Claim", {}), "authorization": ("AuthorizationReceipt", {}),
        "dispatch": ("DispatchEvent", {}),
        "fact": ("PlanningFact", {}), "observation": ("Observation", {}),
        "task": ("Task", {}), "command": ("Command", {}),
        "episode": ("Episode", {}), "revision": ("Revision", {}),
        "source": ("Source", {}), "restriction": ("Restriction", {}),
        "approval": ("ApprovalEvent", {}), "assessment": ("Assessment", {}),
    }
    ids = {name: f"it-rel-{suffix}-{name}" for name in entities}
    for name, (label, attributes) in entities.items():
        store.append_node(label, ids[name], attributes)
    cases = [
        ("IN_MAP", "Corridor", "corridor", "Map", "map"),
        ("APPLIES_TO", "Permission", "permission", "Corridor", "corridor"),
        ("SUPPORTED_BY", "Decision", "decision", "EvidenceSpan", "span"),
        ("SUPPORTED_BY", "Release", "release", "EvidenceSpan", "span"),
        ("UNDER_CLAIM", "AuthorizationReceipt", "authorization", "Claim", "claim"),
        ("DELIVERS", "DispatchEvent", "dispatch", "Command", "command"),
        ("DELIVERS", "DispatchEvent", "dispatch", "Decision", "decision"),
        ("DELIVERS", "DispatchEvent", "dispatch", "Release", "release"),
        ("DELIVERS", "DispatchEvent", "dispatch", "Claim", "claim"),
        ("WITNESSED", "AuthorizationReceipt", "authorization", "PlanningFact", "fact"),
        ("WITNESSED", "AuthorizationReceipt", "authorization", "Decision", "decision"),
        ("WITNESSED", "AuthorizationReceipt", "authorization", "Restriction", "restriction"),
        ("WITNESSED", "AuthorizationReceipt", "authorization", "Release", "release"),
        ("WITNESSED", "AuthorizationReceipt", "authorization", "Permission", "permission"),
        ("WITNESSED", "AuthorizationReceipt", "authorization", "EvidenceSpan", "span"),
        ("CONTAINS", "Episode", "episode", "Command", "command"),
        ("CONTAINS", "Episode", "episode", "Task", "task"),
        ("APPROVES", "ApprovalEvent", "approval", "Decision", "decision"),
        ("CONSIDERED", "Assessment", "assessment", "Observation", "observation"),
        ("CONSIDERED", "Assessment", "assessment", "Episode", "episode"),
    ]

    for relationship, source_label, source_name, target_label, target_name in cases:
        store.append_edge(relationship, source_label, ids[source_name], target_label, ids[target_name])

    snapshot = store.read_snapshot(node_ids=list(ids.values()))
    observed = {(edge["relationship"], edge["source_id"], edge["target_id"])
                for edge in snapshot["edges"]}
    assert observed == {
        (relationship, ids[source_name], ids[target_name])
        for relationship, _, source_name, _, target_name in cases
    }


def test_read_snapshot_retries_when_graph_changes_between_queries(store: GraphStore, monkeypatch: pytest.MonkeyPatch) -> None:
    store.initialize()
    suffix = uuid.uuid4().hex
    anchor_id = f"it-snapshot-anchor-{suffix}"
    robot_id = f"it-snapshot-interleave-{suffix}"
    store.append_node("Robot", anchor_id, {"robot_type": "courier"})
    writer = _same_graph_client(store)
    original_query = store._query
    injected = False

    def query_with_real_interleaving(cypher: str, params: dict | None = None, *, write: bool = False):
        nonlocal injected
        if "RETURN labels(n) AS labels" in cypher and not injected:
            injected = True
            result = original_query(cypher, params, write=write)
            writer.append_node("Robot", robot_id, {"robot_type": "courier"})
            return result
        return original_query(cypher, params, write=write)

    monkeypatch.setattr(store, "_query", query_with_real_interleaving)
    snapshot = store.read_snapshot(node_ids=[anchor_id, robot_id])

    assert injected
    assert any(node.get("id") == robot_id for node in snapshot["nodes"])
    assert snapshot["versions"]["graph_version"] == writer.read_version_root()["graph_version"]


def test_read_snapshot_raises_after_three_real_interleavings(store: GraphStore, monkeypatch: pytest.MonkeyPatch) -> None:
    store.initialize()
    anchor_id = f"it-snapshot-retry-anchor-{uuid.uuid4().hex}"
    store.append_node("Robot", anchor_id, {"robot_type": "courier"})
    writer = _same_graph_client(store)
    original_query = store._query
    writes = 0

    def query_with_persistent_interleaving(cypher: str, params: dict | None = None, *, write: bool = False):
        nonlocal writes
        result = original_query(cypher, params, write=write)
        if "RETURN labels(n) AS labels" in cypher:
            writes += 1
            writer.append_node("Robot", f"it-snapshot-retry-{uuid.uuid4().hex}", {"robot_type": "courier"})
        return result

    monkeypatch.setattr(store, "_query", query_with_persistent_interleaving)
    with pytest.raises(StaleSnapshot, match="3 snapshot attempts"):
        store.read_snapshot(node_ids=[anchor_id])
    assert writes == 3


def test_read_snapshot_rejects_oversize_with_small_configured_caps(store: GraphStore) -> None:
    store.initialize()
    suffix = uuid.uuid4().hex
    node_ids = [f"it-snapshot-small-cap-{suffix}-{i}" for i in range(2)]
    for node_id in node_ids:
        store.append_node("Robot", node_id, {"robot_type": "test"})
    node_capped = _same_graph_client(store, max_nodes=1)
    with pytest.raises(OversizeSnapshot, match="nodes"):
        node_capped.read_snapshot(node_ids=node_ids)

    edge_ids = [f"it-snapshot-small-edge-{suffix}-{i}" for i in range(3)]
    store.append_node("Robot", edge_ids[0], {"robot_type": "test"})
    for node_id in edge_ids[1:]:
        store.append_node("Capability", node_id, {"name": "inspect"})
    store.append_edge("HAS_CAPABILITY", "Robot", edge_ids[0], "Capability", edge_ids[1])
    store.append_edge("HAS_CAPABILITY", "Robot", edge_ids[0], "Capability", edge_ids[2])
    edge_capped = _same_graph_client(store, max_edges=1)
    with pytest.raises(OversizeSnapshot, match="edges"):
        edge_capped.read_snapshot(node_ids=edge_ids)


def test_read_snapshot_raises_for_oversize_unscoped_isolated_graph(store: GraphStore) -> None:
    # A named additive row makes the isolated namespace exceed the one-node cap.
    store.append_node("DispatchEvent", f"it-snapshot-oversize-{uuid.uuid4().hex}", {})
    capped = _same_graph_client(store, max_nodes=1)
    with pytest.raises(OversizeSnapshot, match="nodes"):
        capped.read_snapshot(labels=["FleetState", "DispatchEvent"])


def test_empty_test_record_delete_does_not_advance_graph_version_offline() -> None:
    # Record the destructive query instead of sending it to any graph server.
    store = GraphStore.__new__(GraphStore)
    store.tenant_id = "demo"
    calls = []

    def record_query(cypher, params=None, *, write=False):
        calls.append((cypher, params, write))
        return SimpleNamespace(result_set=[[0]])

    store._query = record_query
    prefix = f"it-no-record-{uuid.uuid4().hex}-"

    assert store.delete_test_records(prefix) == 0
    assert len(calls) == 1
    cypher, params, write = calls[0]
    assert params == {"tenant_id": "demo", "prefix": prefix}
    assert write is True
    assert "FOREACH (node IN nodes | DETACH DELETE node)" in cypher
    assert "s.graph_version=s.graph_version+CASE WHEN deleted>0 THEN 1 ELSE 0 END" in cypher
    assert "SET s.graph_version=s.graph_version+1" not in cypher
    assert "RETURN deleted" in cypher
