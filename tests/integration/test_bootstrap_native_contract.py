from __future__ import annotations

import json
from pathlib import Path

from witness_fleet.runtime.bootstrap import bootstrap


class RecordingGraph:
    """Small graph contract recorder used to prove bootstrap payloads pre-write."""

    def __init__(self):
        self.nodes = {}
        self.edges = []

    def get_node(self, label, node_id):
        return self.nodes.get((label, node_id))

    def append_node(self, label, node_id, attributes):
        self.nodes[(label, node_id)] = {"labels": [label], **attributes}

    def append_edge(self, relationship, source_label, source_id, target_label, target_id):
        self.edges.append((relationship, source_label, source_id, target_label, target_id))


def test_bootstrap_payloads_match_native_simulation_contract(tmp_path: Path):
    graph = RecordingGraph()
    from witness_fleet.ingestion.source_store import SourceStore

    result = bootstrap(graph, SourceStore(tmp_path / "retained-sources"),
                       prefix="native-contract", scenario="SC-001", seed=3)

    assert {robot: graph.nodes[("Robot", robot)]["footprint_m"] for robot in result["robots"]} == {
        "scout": 0.22, "recovery": 0.38, "courier": 0.50,
    }
    assert {node["effective_clock_domain"] for (label, _), node in graph.nodes.items()
            if label in {"Decision", "Release"}} == {"simulation_tick_v1"}
    tasks = {node_id: node for (label, node_id), node in graph.nodes.items() if label == "Task"}
    assert tasks["native-contract-task-park-scout"]["kind"] == "travel"
    assert json.loads(tasks["native-contract-task-verify"]["required_predicates"]) == []
    assert json.loads(tasks["native-contract-task-deliver"]["required_predicates"]) == [
        "recovery_verified", "courier_fit",
    ]
