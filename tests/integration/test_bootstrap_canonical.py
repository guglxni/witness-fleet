from __future__ import annotations

import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.graph.governance import validate_governance
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.bootstrap import bootstrap


@pytest.mark.integration
def test_bootstrap_builds_inert_governance_and_tasks_idempotently(isolated_console_graph, tmp_path):  # noqa: F811
    graph = isolated_console_graph
    sources = SourceStore(tmp_path)
    prefix = "canonical-bootstrap-" + uuid.uuid4().hex
    before = graph.read_version_root()
    assert before is not None

    result = bootstrap(graph, sources, prefix=prefix, scenario="SC-001", seed=3)

    snapshot = graph.read_snapshot(node_ids=result["node_ids"])
    witnesses, errors = validate_governance(snapshot, sources)
    assert errors == ()
    assert {"scout", "recovery", "courier"}.issubset(set(result["robots"]))
    assert all(graph.get_node("Robot", robot_id) is not None
               for robot_id in ("scout", "recovery", "courier"))
    permissions = {(action, role) for witness in witnesses if witness.kind == "permission"
                   for action in witness.action_kinds for role in witness.robot_types}
    assert permissions == {
        (action, role)
        for action in ("travel", "recover", "deliver", "inspect", "verify", "hold", "wait")
        for role in ("scout", "recovery", "courier")
    }
    assert all(node.get("source_id", "").startswith(prefix)
               for node in snapshot["nodes"] if "Source" in node["labels"])
    assert len(result["task_ids"]) >= 5
    assert all(graph.get_node("Task", task_id)["state"] == "READY"
               for task_id in result["task_ids"])
    assert any(edge["relationship"] == "DEPENDS_ON" for edge in snapshot["edges"])
    assert any(w.kind == "restriction" and w.state == "active"
               and w.robot_types == ("courier",) for w in witnesses)
    assert any(w.kind == "release" and w.state == "staged" for w in witnesses)
    assert result["release_id"] in result["node_ids"]
    assert result["corridor_id"] == f"{prefix}-corridor-c"

    committed = graph.read_version_root()
    assert committed is not None
    assert bootstrap(graph, sources, prefix=prefix, scenario="SC-001", seed=3) == result
    assert graph.read_version_root()["graph_version"] == committed["graph_version"]

    with pytest.raises(ValueError, match="conflict"):
        bootstrap(graph, sources, prefix=prefix, scenario="SC-001", seed=4)
    assert graph.read_version_root()["graph_version"] == committed["graph_version"]
