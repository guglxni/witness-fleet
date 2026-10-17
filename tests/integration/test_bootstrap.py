from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.graph.governance import validate_governance
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.bootstrap import bootstrap


def test_bootstrap_returns_canonical_retained_governance_and_task_dependencies(isolated_console_graph, tmp_path):  # noqa: F811
    graph = isolated_console_graph
    sources = SourceStore(tmp_path)
    import uuid
    prefix = 'boot-' + uuid.uuid4().hex
    result = bootstrap(graph, sources, prefix=prefix, scenario='SC-001', seed=3)
    snapshot = graph.read_snapshot(node_ids=result['node_ids'])
    witnesses, errors = validate_governance(snapshot, sources)
    assert errors == ()
    assert any(w.kind == 'permission' and 'courier' in w.robot_types for w in witnesses)
    assert any(w.kind == 'restriction' and w.state == 'active' for w in witnesses)
    assert any(w.kind == 'release' and w.state == 'staged' for w in witnesses)
    assert len(result['task_ids']) >= 5
    assert any(e['relationship'] == 'DEPENDS_ON' for e in snapshot['edges'])
    assert all(graph.get_node('Task', task)['state'] == 'READY' for task in result['task_ids'])
    again = bootstrap(graph, sources, prefix=prefix, scenario='SC-001', seed=3)
    assert again == result
