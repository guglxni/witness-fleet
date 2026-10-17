"""Real-graph provenance and release regressions for OutcomeStore."""
# pytest_plugins must precede imports so pytest owns fixture registration.
# ruff: noqa: E402, I001
pytest_plugins = ["isolated_runtime_fixture"]

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from test_runtime_outcomes import _prepared_command, _retain_observation

from witness_fleet.graph import GraphStore
from witness_fleet.runtime.outcomes import OutcomeStore


def _console_graph(runtime_graph):
    graph = GraphStore(host=runtime_graph.host, port=runtime_graph.port, username="default")
    graph.graph_name = "wf:demo:inspection-" + uuid.uuid4().hex
    graph._graph = graph._client.select_graph(graph.graph_name)
    graph.initialize()
    return graph



@pytest.mark.parametrize("predicate", ["arrived", "unrelated_fact"])
def test_verified_outcome_rejects_empty_effect_contract(isolated_runtime_graph, predicate):  # noqa: F811
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(
        isolated_runtime_graph, expected_effects=(),
    )
    observation = _retain_observation(
        graph, command, episode_id, corridor_id, predicate=predicate, value=True,
    )
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == before["graph_version"]
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"
    assert graph.get_node("Task", command.proposal.task_id)["state"] != "VERIFIED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "ACTIVE"


def test_verified_outcome_rejects_undeclared_extra_effect(isolated_runtime_graph):  # noqa: F811
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    expected = _retain_observation(graph, command, episode_id, corridor_id)
    unrelated = _retain_observation(
        graph, command, episode_id, corridor_id, predicate="unrelated_fact",
    )
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(expected, unrelated), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == before["graph_version"]
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"


def test_successful_outcome_rejects_an_unlinked_retained_observation(isolated_runtime_graph):  # noqa: F811
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(
        graph, command, episode_id, corridor_id, link_episode=False,
    )
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == before["graph_version"]
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"
    assert graph.get_node("Task", command.proposal.task_id)["state"] != "VERIFIED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "ACTIVE"


def test_finish_rejects_an_observation_with_an_additional_episode_owner(
    isolated_runtime_graph,
):  # noqa: F811
    console_db = _console_graph(isolated_runtime_graph)
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(console_db)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    other_episode_id = f"it-outcome-extra-owner-{uuid4().hex}"
    graph.append_node("Episode", other_episode_id, {
        "scenario_family": "SC-001", "outcome": "pending", "verification_state": "unverified",
        "configuration_hash": "c" * 64, "payload_json": f'{{"episode_id":"{other_episode_id}"}}',
    })
    graph.append_edge("CONTAINS", "Episode", other_episode_id, "Observation", observation.id)
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == before["graph_version"]
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"
    assert graph.get_node("Task", command.proposal.task_id)["state"] != "VERIFIED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "ACTIVE"


def test_replay_rejects_an_observation_with_an_additional_episode_owner(isolated_runtime_graph):
    console_db = _console_graph(isolated_runtime_graph)
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(console_db)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    before = graph.read_version_root()
    assert before is not None
    store = OutcomeStore(graph, holder)
    committed = store.finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )
    assert committed is not None

    other_episode_id = f"it-outcome-replay-owner-{uuid4().hex}"
    graph.append_node("Episode", other_episode_id, {
        "scenario_family": "SC-001", "outcome": "pending", "verification_state": "unverified",
        "configuration_hash": "d" * 64, "payload_json": f'{{"episode_id":"{other_episode_id}"}}',
    })
    graph.append_edge("CONTAINS", "Episode", other_episode_id, "Observation", observation.id)

    replay = store.finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert replay is None


def test_finish_cas_rejects_a_task_episode_owner_added_after_preflight(isolated_runtime_graph):
    console_db = _console_graph(isolated_runtime_graph)
    graph, holder, command, _, _, _ = _prepared_command(console_db)
    episode_ids = OutcomeStore(graph, holder)._episode_ids(command)
    assert len(episode_ids) == 1
    selected_episode_id = next(iter(episode_ids))
    observation = _retain_observation(
        graph, command, selected_episode_id, command.proposal.corridor_id,
    )
    baseline = graph.read_version_root()
    assert baseline is not None
    delegate = graph._graph

    class AddOwnerBeforeCas:
        def __getattr__(self, name):
            return getattr(delegate, name)

    wrapper = AddOwnerBeforeCas()
    store = OutcomeStore(graph, holder)
    original = graph._graph

    def query_before_cas(cypher, params):
        if "SET s.graph_version=s.graph_version+1, c.state=$terminal_command" in cypher:
            competing_id = f"it-outcome-task-owner-race-{uuid4().hex}"
            graph.append_node("Episode", competing_id, {
                "scenario_family": "SC-001", "outcome": "pending",
                "verification_state": "unverified", "configuration_hash": "e" * 64,
                "payload_json": f'{{"episode_id":"{competing_id}"}}',
            })
            graph.append_edge("CONTAINS", "Episode", competing_id,
                              "Task", command.proposal.task_id)
            graph.append_edge("OCCURRED_AT", "Episode", competing_id,
                              "Corridor", command.proposal.corridor_id)
        return original.query(cypher, params)

    graph._graph = wrapper
    wrapper.query = query_before_cas
    result = store.finish(
        command.command_id, expected_graph_version=baseline["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == baseline["graph_version"] + 3
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"
    assert graph.get_node("Task", command.proposal.task_id)["state"] != "VERIFIED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "ACTIVE"


def test_competing_finish_calls_have_one_cas_winner(isolated_runtime_graph):
    console_db = _console_graph(isolated_runtime_graph)
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(console_db)
    observations = (
        _retain_observation(graph, command, episode_id, corridor_id),
        _retain_observation(graph, command, episode_id, corridor_id),
    )
    before = graph.read_version_root()
    assert before is not None
    gate = Barrier(2)

    def finish_in_thread(observation):
        client = GraphStore(
            host=graph.host, port=graph.port, tenant_id=graph.tenant_id, username="default",
        )
        client.graph_name = graph.graph_name
        client._graph = client._client.select_graph(graph.graph_name)
        gate.wait(timeout=10)
        return OutcomeStore(client, holder).finish(
            command.command_id, expected_graph_version=before["graph_version"],
            observations=(observation,), world_tick=5,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(finish_in_thread, observation) for observation in observations]
        results = [future.result(timeout=30) for future in futures]

    assert sum(result is not None for result in results) == 1
    assert graph.read_version_root()["graph_version"] == before["graph_version"] + 1
    assert graph.get_node("Command", command.command_id)["state"] == "OUTCOME_VERIFIED"
    assert graph.get_node("Task", command.proposal.task_id)["state"] == "VERIFIED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "RELEASED"


def test_replay_fails_closed_when_verified_by_edges_disagree_with_committed_refs(isolated_runtime_graph):  # noqa: F811
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    before = graph.read_version_root()
    assert before is not None
    store = OutcomeStore(graph, holder)
    committed = store.finish(command.command_id, expected_graph_version=before["graph_version"],
                             observations=(observation,), world_tick=5)
    assert committed is not None
    extra = _retain_observation(
        graph, command, episode_id, corridor_id, predicate="arrived",
    )
    graph.append_edge("VERIFIED_BY", "Command", command.command_id,
                      "Observation", extra.id)

    replay = store.finish(command.command_id, expected_graph_version=before["graph_version"],
                          observations=(observation,), world_tick=5)

    assert replay is None


def test_verified_by_is_a_canonical_graph_relationship(isolated_runtime_graph):  # noqa: F811
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    before = graph.read_version_root()
    assert before is not None
    committed = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )
    assert committed is not None

    # The canonical writer accepts the relationship, and the graph snapshot
    # exposes the CAS-created edge as a normal first-class projection.
    graph.append_edge("VERIFIED_BY", "Command", command.command_id,
                      "Observation", observation.id)
    snapshot = graph.read_snapshot(labels=["Command", "Observation"])

    assert any(edge["relationship"] == "VERIFIED_BY"
               and edge["source_id"] == command.command_id
               and edge["target_id"] == observation.id for edge in snapshot["edges"])


def test_released_claim_allows_a_competing_task_to_reserve_shared_resource(isolated_runtime_graph):  # noqa: F811
    graph, holder, command, ids, episode_id, corridor_id = _prepared_command(
        isolated_runtime_graph, second_task=True,
    )
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    before = graph.read_version_root()
    assert before is not None
    committed = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )
    assert committed is not None
    assert committed["claim"]["state"] == "RELEASED"

    current = graph.read_version_root()
    assert current is not None
    now = datetime.now(UTC)
    competing = graph.claim_task(
        task_id=ids["task_2_id"], robot_id=ids["robot_1"], expected_task_version=0,
        coordinator_epoch=command.coordinator_epoch, resource_ids=[ids["resource_ids"][0]],
        lease_expires_at_utc=(now + timedelta(minutes=10)).isoformat(), now_utc=now.isoformat(),
    )

    assert competing is not None
    assert ids["resource_ids"][0] in competing["resource_fences"]
    assert competing["state"] == "ACTIVE"
