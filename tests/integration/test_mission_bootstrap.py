"""Additive mission profile remains separate from the inert v1 manifest."""
import hashlib
import json

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.bootstrap import bootstrap

MISSION_TASKS = (
    ("scout-inspect", "scout", "inspect", {}, "inspected", []),
    ("recovery-recover", "recovery", "recover", {"target_displacement_m": 0.75},
     "obstruction_moved", ["obstacle_assessed"]),
    ("scout-park", "scout", "travel", {"target_x": -3.5, "target_y": -0.55}, "arrived", []),
    ("scout-verify", "scout", "verify", {}, "inspected", []),
    ("courier-approach", "courier", "travel", {"target_x": -3.5, "target_y": 0}, "arrived", []),
    ("courier-verify", "courier", "verify", {}, "inspected", []),
    ("courier-deliver", "courier", "deliver", {"target_x": 4, "target_y": 0},
     "delivered", ["recovery_verified", "courier_fit"]),
)


def test_default_profile_retains_the_exact_legacy_manifest_hash(isolated_runtime_graph, tmp_path):  # noqa: F811
    result = bootstrap(isolated_runtime_graph, SourceStore(tmp_path / "sources"),
                       prefix="legacy-golden-v1", scenario="SC-001", seed=3)
    episode = isolated_runtime_graph.get_node("Episode", result["episode_id"])
    payload = episode["payload_json"]

    assert hashlib.sha256(payload.encode("utf-8")).hexdigest() == (
        "6d14f8a7bcf8a776b29fdb2c965bac266f8e0e260050c532e437814098d91b27"
    )
    manifest = json.loads(payload)
    assert set(manifest["identity"]) == {
        "kind", "map_configuration", "prefix", "scenario", "seed", "version"
    }
    assert manifest["identity"]["version"] == 1
    assert "profile" not in result and "task_plan" not in result


def test_mission_v2_persists_the_exact_sc001_plan_and_graph_chain(isolated_console_graph, tmp_path):  # noqa: F811
    graph = isolated_console_graph
    sources = SourceStore(tmp_path / "sources")
    result = bootstrap(graph, sources, prefix="mission-v2-test", scenario="SC-001", seed=3,
                       profile="mission-v2")
    episode = graph.get_node("Episode", result["episode_id"])
    manifest = json.loads(episode["payload_json"])

    assert manifest["identity"]["version"] == 2
    assert manifest["identity"]["profile"] == "mission-v2"
    assert result["profile"] == "mission-v2"
    assert [task["key"] for task in result["task_plan"]] == [task[0] for task in MISSION_TASKS]
    expected_plan = []
    for key, robot_id, kind, parameters, effect, predicates in MISSION_TASKS:
        entry = {
            "key": key,
            "task_id": f"mission-v2-test-task-{key}",
            "robot_id": robot_id,
            "kind": kind,
            "parameters": parameters,
            "expected_effects": [effect],
            "required_predicates": predicates,
        }
        if key in {"courier-approach", "courier-deliver"}:
            entry["require_release"] = True
        expected_plan.append(entry)
    assert result["task_plan"] == expected_plan
    assert manifest["result"] == result

    snapshot = graph.read_snapshot(node_ids=result["node_ids"])
    tasks = {node["id"]: node for node in snapshot["nodes"] if node["labels"] == ["Task"]}
    assert set(tasks) == {entry["task_id"] for entry in expected_plan}
    assert {task["state"] for task in tasks.values()} == {"READY"}
    by_task = {entry["task_id"]: entry for entry in expected_plan}
    edges = snapshot["edges"]
    dependencies = {
        (edge["source_id"], edge["target_id"])
        for edge in edges if edge["relationship"] == "DEPENDS_ON"
    }
    assert dependencies == {
        (by_task[expected_plan[index]["task_id"]]["task_id"],
         expected_plan[index - 1]["task_id"])
        for index in range(1, len(expected_plan))
    }
    assert {
        (edge["source_id"], edge["target_id"])
        for edge in edges if edge["relationship"] == "ASSIGNED_TO"
    } == {(entry["robot_id"], entry["task_id"]) for entry in expected_plan}
    assert {
        edge["source_id"] for edge in edges if edge["relationship"] == "USES"
    } == {entry["task_id"] for entry in expected_plan}
    assert {
        edge["target_id"] for edge in edges if edge["relationship"] == "USES"
    } == {result["corridor_id"]}
    assert {
        edge["target_id"] for edge in edges if edge["relationship"] == "REQUIRES_RESOURCE"
    } == {result["resources"][0]}

    # v2 retains the exact courier-only travel/deliver restriction and staged release contract.
    restriction = graph.get_node("Restriction", result["restrictions"][0])
    release = graph.get_node("Release", result["release_id"])
    assert json.loads(restriction["subject_scope"]) == ["courier"]
    assert json.loads(restriction["condition_json"]) == {
        "corridor_id": result["corridor_id"], "action_kinds": ["travel", "deliver"]
    }
    assert release["state"] == "staged"
    release_source = graph.get_node("Source", "mission-v2-test-release-conditions-source")
    assert release_source["source_type"] == "synthetic"
    revision = next(node for node in snapshot["nodes"]
                    if node["labels"] == ["Revision"]
                    and node["id"] == "mission-v2-test-release-conditions-revision")
    release_text = sources.get(revision["revision_id"]).text
    assert json.loads(release_text)["required_predicates"] == ["recovery_verified", "courier_fit"]
    assert not any(node.get("kind") == "owner-release" for node in tasks.values())
    assert len(manifest["identity"]) == 7


def test_mission_v2_is_sc001_only_and_rejects_unknown_profile(isolated_console_graph, tmp_path):  # noqa: F811
    graph = isolated_console_graph
    sources = SourceStore(tmp_path / "sources")
    before = graph.read_snapshot()
    with pytest.raises(ValueError, match="SC-001"):
        bootstrap(graph, sources, prefix="wrong-scenario", scenario="SC-002", seed=3,
                  profile="mission-v2")
    with pytest.raises(ValueError, match="profile"):
        bootstrap(graph, sources, prefix="unknown-profile", scenario="SC-001", seed=3,
                  profile="mission-v3")
    assert graph.read_snapshot() == before


@pytest.mark.parametrize("first_profile", ["inspection-v1", "mission-v2"])
def test_same_prefix_cannot_be_reused_across_profiles(isolated_console_graph, tmp_path, first_profile):  # noqa: F811
    graph = isolated_console_graph
    sources = SourceStore(tmp_path / "sources")
    kwargs = {"profile": first_profile} if first_profile != "inspection-v1" else {}
    bootstrap(graph, sources, prefix="cross-profile-collision", scenario="SC-001", seed=3, **kwargs)
    before = graph.read_snapshot()
    other_profile = "inspection-v1" if first_profile == "mission-v2" else "mission-v2"

    with pytest.raises(ValueError, match="prefix conflict"):
        bootstrap(graph, sources, prefix="cross-profile-collision", scenario="SC-001", seed=3,
                  profile=other_profile)
    assert graph.read_snapshot() == before
