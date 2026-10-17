"""Adversarial graph evidence for the frozen OutcomeStore SPEC review."""
# pytest_plugins must precede imports so pytest owns fixture registration.
# ruff: noqa: E402, I001
pytest_plugins = ["isolated_runtime_fixture"]

from uuid import uuid4

from test_runtime_outcomes import _prepared_command, _retain_observation
from witness_fleet.runtime.outcomes import OutcomeStore


def test_finish_rejects_task_episode_owner_without_selected_corridor_edge(isolated_runtime_graph):
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    unrelated_episode_id = f"it-outcome-task-owner-no-corridor-{uuid4().hex}"
    graph.append_node("Episode", unrelated_episode_id, {
        "scenario_family": "SC-001", "outcome": "pending", "verification_state": "unverified",
        "configuration_hash": "f" * 64, "payload_json": f'{{"episode_id":"{unrelated_episode_id}"}}',
    })
    # This Episode owns the Task but is deliberately not linked to the command Corridor.
    graph.append_edge("CONTAINS", "Episode", unrelated_episode_id, "Task", command.proposal.task_id)
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"
    assert graph.get_node("Task", command.proposal.task_id)["state"] != "VERIFIED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "ACTIVE"


def test_replay_rejects_task_episode_owner_without_selected_corridor_edge(isolated_runtime_graph):
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    store = OutcomeStore(graph, holder)
    before = graph.read_version_root()
    assert before is not None
    committed = store.finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )
    assert committed is not None

    unrelated_episode_id = f"it-outcome-replay-task-owner-no-corridor-{uuid4().hex}"
    graph.append_node("Episode", unrelated_episode_id, {
        "scenario_family": "SC-001", "outcome": "pending", "verification_state": "unverified",
        "configuration_hash": "9" * 64, "payload_json": f'{{"episode_id":"{unrelated_episode_id}"}}',
    })
    graph.append_edge("CONTAINS", "Episode", unrelated_episode_id, "Task", command.proposal.task_id)

    replay = store.finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert replay is None


def test_cas_rejects_owner_added_after_preflight_without_version_bump(isolated_runtime_graph):
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    before = graph.read_version_root()
    delegate = graph._graph
    injected = []

    class AddOwnerAtWrite:
        def __getattr__(self, name):
            return getattr(delegate, name)

        def query(self, query, params=None, **kwargs):
            if 'SET s.graph_version=s.graph_version+1, c.state=$terminal_command' in query:
                # Additive external writer: no graph-version mutation, so only the
                # atomic ownership predicate, not a version mismatch, can reject it.
                delegate.query(
                    'MATCH (t:Task {id:$task,tenant_id:$tenant}) '
                    'CREATE (:Episode {id:$id,tenant_id:$tenant})-[:CONTAINS]->(t)',
                    {'task': command.proposal.task_id, 'tenant': graph.tenant_id,
                     'id': 'rogue-race-' + uuid4().hex},
                )
                injected.append(True)
            return delegate.query(query, params, **kwargs)

    graph._graph = AddOwnerAtWrite()
    try:
        result = OutcomeStore(graph, holder).finish(
            command.command_id, expected_graph_version=before['graph_version'],
            observations=(observation,), world_tick=5,
        )
    finally:
        graph._graph = delegate
    assert injected == [True]
    assert result is None
    assert graph.read_version_root()['graph_version'] == before['graph_version']
    assert graph.get_node('Command', command.command_id)['state'] == 'PREPARED'
    assert graph.get_node('Claim', command.claim_id)['state'] == 'ACTIVE'
