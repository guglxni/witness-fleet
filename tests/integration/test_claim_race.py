from __future__ import annotations

import threading
import uuid
from typing import Any

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.graph import GraphStore

pytestmark = pytest.mark.integration


def _same_graph_client(graph: GraphStore) -> GraphStore:
    """Open an independent client connection to this test's retained namespace."""
    client = GraphStore(
        host=graph.host, port=graph.port, tenant_id=graph.tenant_id,
        username=graph.username, max_nodes=graph._snapshot_node_limit,
        max_edges=graph._snapshot_edge_limit, max_attempts=graph._snapshot_attempts,
    )
    client.graph_name = graph.graph_name
    client._graph = client._client.select_graph(client.graph_name)
    return client


def _coordinator_epoch(store: GraphStore) -> int:
    root = store.read_version_root()
    assert root is not None
    return root["coordinator_epoch"]


def test_claim_cas_allows_only_one_writer_for_task_and_resources(isolated_console_graph):  # noqa: F811
    suffix = uuid.uuid4().hex
    setup = isolated_console_graph
    ids = setup.seed_claim_fixture(suffix)
    epoch = _coordinator_epoch(setup)
    clients = [_same_graph_client(setup), _same_graph_client(setup)]
    barrier = threading.Barrier(2)
    answers: list[dict[str, Any] | None] = [None, None]
    errors: list[BaseException] = []

    def contend(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            answers[index] = clients[index].claim_task(
                task_id=ids["task_id"],
                robot_id=ids[f"robot_{index}"],
                expected_task_version=0,
                coordinator_epoch=epoch,
                resource_ids=ids["resource_ids"],
                lease_expires_at_utc="2026-10-15T12:00:00Z",
                now_utc="2026-10-15T11:00:00Z",
            )
        except BaseException as exc:  # surface worker failures in the asserting thread
            errors.append(exc)

    threads = [threading.Thread(target=contend, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert sum(answer is not None for answer in answers) == 1
    winner = next(answer for answer in answers if answer is not None)
    assert winner["fence"] == 1
    assert set(winner["resource_fences"]) == set(ids["resource_ids"])
    assert all(fence == 1 for fence in winner["resource_fences"].values())
    assert all(client.cas_query_count == 1 for client in clients)
    assert setup.read_task_claims(ids["task_id"])[0]["id"] == winner["claim_id"]


def test_claim_rejects_stale_task_version_and_unresolved_expired_claim(isolated_console_graph):  # noqa: F811
    suffix = uuid.uuid4().hex
    store = isolated_console_graph
    ids = store.seed_claim_fixture(suffix)
    epoch = _coordinator_epoch(store)
    assert store.claim_task(
        task_id=ids["task_id"],
        robot_id=ids["robot_0"],
        expected_task_version=99,
        coordinator_epoch=epoch,
        resource_ids=ids["resource_ids"],
        lease_expires_at_utc="2026-10-15T12:00:00Z",
        now_utc="2026-10-15T11:00:00Z",
    ) is None
    assert store.claim_task(
        task_id=ids["task_id"],
        robot_id=ids["robot_0"],
        expected_task_version=0,
        coordinator_epoch=epoch,
        resource_ids=ids["resource_ids"],
        lease_expires_at_utc="2026-10-15T10:00:00Z",
        now_utc="2026-10-15T11:00:00Z",
    ) is None
    assert store.claim_task(
        task_id=ids["task_id"],
        robot_id=ids["robot_0"],
        expected_task_version=0,
        coordinator_epoch=epoch,
        resource_ids=ids["resource_ids"],
        lease_expires_at_utc="2026-10-15T12:00:00Z",
        now_utc="2026-10-15T11:00:00Z",
    ) is not None
    assert store.claim_task(
        task_id=ids["task_id"],
        robot_id=ids["robot_1"],
        expected_task_version=1,
        coordinator_epoch=epoch,
        resource_ids=ids["resource_ids"],
        lease_expires_at_utc="2026-10-15T13:00:00Z",
        now_utc="2026-10-15T11:30:00Z",
    ) is None


def test_different_tasks_conflict_on_shared_resource(isolated_console_graph):  # noqa: F811
    suffix = uuid.uuid4().hex
    store = isolated_console_graph
    ids = store.seed_claim_fixture(suffix, second_task=True)
    epoch = _coordinator_epoch(store)
    winner = store.claim_task(
        task_id=ids["task_id"], robot_id=ids["robot_0"], expected_task_version=0,
        coordinator_epoch=epoch, resource_ids=ids["resource_ids"],
        lease_expires_at_utc="2026-10-15T13:00:00Z", now_utc="2026-10-15T11:00:00Z",
    )
    loser = store.claim_task(
        task_id=ids["task_2_id"], robot_id=ids["robot_1"], expected_task_version=0,
        coordinator_epoch=epoch, resource_ids=[ids["resource_ids"][0]],
        lease_expires_at_utc="2026-10-15T13:00:00Z", now_utc="2026-10-15T11:00:00Z",
    )
    assert winner is not None
    assert loser is None
    assert len(store.read_resource_claims(ids["resource_ids"][0])) == 1


def test_disjoint_task_resource_claims_still_exclude_same_robot_atomically(isolated_console_graph):  # noqa: F811
    suffix = uuid.uuid4().hex
    setup = isolated_console_graph
    ids = setup.seed_claim_fixture(suffix, second_task=True)
    disjoint_task = ids['prefix'] + 'disjoint-task'
    setup.append_node('Task', disjoint_task, {'kind':'inspect','state':'READY','task_version':0,
        'required_predicates':'[]','priority':1,'claim_fence':0})
    setup.append_edge('REQUIRES_RESOURCE','Task',disjoint_task,'Resource',ids['resource_ids'][1])
    epoch = _coordinator_epoch(setup)
    clients = [_same_graph_client(setup), _same_graph_client(setup)]
    barrier = threading.Barrier(2)
    answers: list[dict[str, Any] | None] = [None, None]
    errors: list[BaseException] = []

    def contend(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            answers[index] = clients[index].claim_task(
                task_id=ids['task_2_id'] if index == 0 else disjoint_task,
                robot_id=ids["robot_0"], expected_task_version=0,
                coordinator_epoch=epoch, resource_ids=[ids["resource_ids"][index]],
                lease_expires_at_utc="2026-10-15T13:00:00Z", now_utc="2026-10-15T11:00:00Z",
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=contend, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert sum(answer is not None for answer in answers) == 1
    assert all(client.cas_query_count == 1 for client in clients)
    claims = setup._query(
        "MATCH (c:Claim)-[:HELD_BY]->(:Robot {id:$robot_id,tenant_id:$tenant_id}) "
        "WHERE c.state IN ['ACTIVE','UNKNOWN','REASSESS'] RETURN properties(c)",
        {"robot_id": ids["robot_0"], "tenant_id": setup.tenant_id},
    ).result_set
    assert len(claims) == 1
