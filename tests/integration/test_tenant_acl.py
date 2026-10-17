from __future__ import annotations

import threading
import uuid
from typing import Any

import pytest
from falkordb import FalkorDB
from isolated_acl_fixture import isolated_acl_server  # noqa: F401
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401
from redis.exceptions import ResponseError

from witness_fleet.graph import GraphStore

pytestmark = pytest.mark.integration


def _same_graph_client(store: GraphStore) -> GraphStore:
    """Open another client on the exact per-test graph namespace."""
    client = GraphStore(host=store.host, port=store.port, tenant_id=store.tenant_id,
                        username="default")
    client.graph_name = store.graph_name
    client._graph = client._client.select_graph(store.graph_name)
    return client


def _coordinator_epoch(store: GraphStore) -> int:
    root = store.read_version_root()
    assert root is not None
    return root["coordinator_epoch"]


def test_claim_cas_allows_only_one_writer_for_task_and_resources(isolated_console_graph) -> None:  # noqa: F811
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
                task_id=ids["task_id"], robot_id=ids[f"robot_{index}"],
                expected_task_version=0, coordinator_epoch=epoch, resource_ids=ids["resource_ids"],
                lease_expires_at_utc="2026-10-15T12:00:00Z", now_utc="2026-10-15T11:00:00Z",
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
    winner = next(answer for answer in answers if answer is not None)
    assert winner["fence"] == 1
    assert set(winner["resource_fences"]) == set(ids["resource_ids"])
    assert all(fence == 1 for fence in winner["resource_fences"].values())
    assert all(client.cas_query_count == 1 for client in clients)
    assert setup.read_task_claims(ids["task_id"])[0]["id"] == winner["claim_id"]


def test_claim_rejects_stale_task_version_and_expiry_is_not_reassignment(isolated_console_graph) -> None:  # noqa: F811
    store = isolated_console_graph
    ids = store.seed_claim_fixture(uuid.uuid4().hex)
    epoch = _coordinator_epoch(store)
    assert store.claim_task(
        task_id=ids["task_id"], robot_id=ids["robot_0"], expected_task_version=99,
        coordinator_epoch=epoch, resource_ids=ids["resource_ids"],
        lease_expires_at_utc="2026-10-15T12:00:00Z", now_utc="2026-10-15T11:00:00Z",
    ) is None
    assert store.claim_task(
        task_id=ids["task_id"], robot_id=ids["robot_0"], expected_task_version=0,
        coordinator_epoch=epoch, resource_ids=ids["resource_ids"],
        lease_expires_at_utc="2026-10-15T12:00:00Z", now_utc="2026-10-15T11:00:00Z",
    ) is not None
    assert store.claim_task(
        task_id=ids["task_id"], robot_id=ids["robot_1"], expected_task_version=1,
        coordinator_epoch=epoch, resource_ids=ids["resource_ids"],
        lease_expires_at_utc="2026-10-15T13:00:00Z", now_utc="2026-10-15T11:30:00Z",
    ) is None


def test_different_tasks_conflict_on_shared_resource(isolated_console_graph) -> None:  # noqa: F811
    store = isolated_console_graph
    ids = store.seed_claim_fixture(uuid.uuid4().hex, second_task=True)
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


def test_tenant_graph_key_is_derived_not_caller_selected(isolated_acl_server) -> None:  # noqa: F811
    host, port = isolated_acl_server.host, isolated_acl_server.port
    demo = GraphStore(host=host, port=port, tenant_id="demo", username="wf_ops")
    other = GraphStore(host=host, port=port, tenant_id="other", username="wf_other")
    assert demo.graph_name == "wf:demo:ops"
    assert other.graph_name == "wf:other:ops"
    demo.initialize()
    assert other.read_version_root() is None
    with pytest.raises(ValueError, match="tenant"):
        GraphStore(host=host, port=port, tenant_id="arbitrary", username="wf_ops")
    with pytest.raises(TypeError):
        GraphStore(host=host, port=port, tenant_id="demo", username="wf_ops",
                   **{"graph_name": "wf:other:ops"})  # type: ignore[call-arg]


def test_database_acl_denies_cross_key_and_readonly_write(isolated_acl_server) -> None:  # noqa: F811
    host, port = isolated_acl_server.host, isolated_acl_server.port
    read_client = FalkorDB(host=host, port=port, username="wf_read")
    other_client = FalkorDB(host=host, port=port, username="wf_other")
    readonly_probe = f"it-forbidden-{uuid.uuid4().hex}"
    cross_key_probe = f"it-forbidden-{uuid.uuid4().hex}"
    with pytest.raises(ResponseError, match="permissions"):
        read_client.select_graph("wf:demo:ops").query(
            "CREATE (:Robot {id:$id,tenant_id:'demo'})", {"id": readonly_probe}
        )
    with pytest.raises(ResponseError, match="permissions"):
        other_client.select_graph("wf:demo:ops").query(
            "CREATE (:Robot {id:$id,tenant_id:'demo'})", {"id": cross_key_probe}
        )
    reader = GraphStore(host=host, port=port, tenant_id="demo", username="wf_read")
    other = GraphStore(host=host, port=port, tenant_id="other", username="wf_other")
    assert reader.get_node("Robot", readonly_probe) is None
    assert other.get_node("Robot", cross_key_probe) is None
