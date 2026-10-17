"""Atomic approval consumes a configured principal, never caller-nominated authority."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.runtime.approval import ApprovalCommand, TrustedLocalPrincipal
from witness_fleet.runtime.approval_writer import ApprovalWriter


def test_approval_writer_rejects_foreign_actor_before_graph_access():
    principal = TrustedLocalPrincipal(actor_id="owner", tenant_id="demo",
                                      role="maintenance_owner", trust_mode="configured_local")
    writer = ApprovalWriter(SimpleNamespace(tenant_id="demo"), None, principal,
                            holder_id="coordinator", clock=lambda: datetime(2026, 10, 16, tzinfo=UTC))
    command = ApprovalCommand(event_id="approval", target_id="release", actor_id="other-owner",
                              tenant_id="demo", expected_policy_epoch=0)
    with pytest.raises(ValueError, match="principal"):
        writer.approve_release(command, effective_world_tick=0)


@pytest.mark.parametrize("tick", [True, False, -1, 1.5, "0", None])
def test_approval_writer_rejects_invalid_world_tick_before_graph_access(tick):
    principal = TrustedLocalPrincipal(actor_id="owner", tenant_id="demo",
                                      role="maintenance_owner", trust_mode="configured_local")
    writer = ApprovalWriter(SimpleNamespace(tenant_id="demo"), None, principal, holder_id="coordinator")
    command = ApprovalCommand(event_id="approval", target_id="release", actor_id="owner",
                              tenant_id="demo", expected_policy_epoch=0)
    with pytest.raises(ValueError, match="world tick"):
        writer.approve_release(command, effective_world_tick=tick)


def test_release_commit_has_one_authoritative_epoch_and_activation(isolated_console_graph, tmp_path):  # noqa: F811
    import json

    from approval_db_fixture import staged_fixture

    from witness_fleet.graph.governance import validate_governance

    graph, sources, principal, command, ids = staged_fixture(isolated_console_graph, tmp_path)
    before = graph.read_version_root()
    writer = ApprovalWriter(graph, sources, principal, holder_id=ids["holder"])
    result = writer.approve_release(command, effective_world_tick=10)
    assert result["policy_epoch"] == before["policy_epoch"] + 1
    assert result["graph_version"] == before["graph_version"] + 1
    assert result["dispatch_sequence"] == before["dispatch_sequence"] + 1
    release = graph.get_node("Release", command.target_id)
    assert release is not None
    assert release["state"] == "released"
    approval = graph.get_node("ApprovalEvent", release["approval_event_id"])
    activation = graph.get_node("DispatchEvent", command.event_id)
    assert approval["activation_event_id"] == activation["id"]
    assert json.loads(activation["payload_json"])["policy_proof"]["proof_id"] == approval["id"]
    snapshot = graph.read_snapshot(labels=["Source", "Revision", "EvidenceSpan", "Owner", "Decision",
        "Restriction", "Release", "Permission", "ApprovalEvent", "Corridor", "DispatchEvent", "Observation"])
    witnesses, errors = validate_governance(snapshot, sources)
    assert errors == ()
    assert next(w for w in witnesses if w.id == command.target_id).approved is True


def test_stale_expected_policy_epoch_mutates_nothing(isolated_console_graph, tmp_path):  # noqa: F811
    from approval_db_fixture import staged_fixture

    graph, sources, principal, command, ids = staged_fixture(isolated_console_graph, tmp_path)
    stale = command.model_copy(update={"expected_policy_epoch": command.expected_policy_epoch + 1})
    before = graph.read_version_root()
    writer = ApprovalWriter(graph, sources, principal, holder_id=ids["holder"])
    with pytest.raises(ValueError, match="policy epoch"):
        writer.approve_release(stale, effective_world_tick=10)
    assert graph.read_version_root() == before
    assert graph.get_node("Release", command.target_id)["state"] == "staged"
    assert graph.get_node("DispatchEvent", command.event_id) is None


def test_exact_replay_returns_original_receipt_without_epoch_or_version_increase(isolated_console_graph, tmp_path):  # noqa: F811
    from approval_db_fixture import staged_fixture

    graph, sources, principal, command, ids = staged_fixture(isolated_console_graph, tmp_path)
    writer = ApprovalWriter(graph, sources, principal, holder_id=ids["holder"])
    first = writer.approve_release(command, effective_world_tick=10)
    after = graph.read_version_root()
    assert writer.approve_release(command, effective_world_tick=10) == first
    assert graph.read_version_root() == after
    conflicting = command.model_copy(update={"notes": "different intent"})
    with pytest.raises(ValueError, match="conflicts"):
        writer.approve_release(conflicting, effective_world_tick=10)
    assert graph.read_version_root() == after


def test_expired_postinspection_facts_leave_release_staged_without_activation(isolated_console_graph, tmp_path):  # noqa: F811
    from approval_db_fixture import staged_fixture

    graph, sources, principal, command, ids = staged_fixture(isolated_console_graph, tmp_path)
    before = graph.read_version_root()
    writer = ApprovalWriter(graph, sources, principal, holder_id=ids["holder"])
    with pytest.raises(ValueError, match="fresh post-inspection"):
        writer.approve_release(command, effective_world_tick=60)
    assert graph.read_version_root() == before
    assert graph.get_node("Release", command.target_id)["state"] == "staged"


def test_two_independent_connections_same_epoch_have_one_winner(isolated_console_graph, tmp_path):  # noqa: F811
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from approval_db_fixture import staged_fixture

    from witness_fleet.graph import GraphStore

    graph, sources, principal, command, ids = staged_fixture(isolated_console_graph, tmp_path)
    before = graph.read_version_root()
    barrier = Barrier(2)

    def attempt(event_id):
        independent = GraphStore(
            host=graph.host, port=graph.port, tenant_id=graph.tenant_id, username=graph.username,
        )
        independent.graph_name = graph.graph_name
        independent._graph = independent._client.select_graph(graph.graph_name)
        assert independent is not graph
        assert independent._client is not graph._client
        assert independent.graph_name == graph.graph_name
        writer = ApprovalWriter(independent, sources, principal, holder_id=ids["holder"])
        intent = command.model_copy(update={"event_id": event_id})
        barrier.wait(timeout=5)
        try:
            return writer.approve_release(intent, effective_world_tick=10)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [command.event_id + "-a", command.event_id + "-b"]))
    assert sum(item is not None for item in results) == 1
    after = graph.read_version_root()
    assert after["policy_epoch"] == before["policy_epoch"] + 1
    assert after["dispatch_sequence"] == before["dispatch_sequence"] + 1
    assert after["graph_version"] == before["graph_version"] + 1


def test_server_cas_rejects_deadline_expired_after_preflight(isolated_console_graph, tmp_path, monkeypatch):  # noqa: F811
    from approval_db_fixture import staged_fixture

    graph, sources, principal, command, ids = staged_fixture(isolated_console_graph, tmp_path)
    before = graph.read_version_root()
    original_query = graph._graph.query
    exercised = []

    def expiry_interleaving(query, params=None, **kwargs):
        if "CREATE (a:ApprovalEvent" in query:
            # Deterministic expiry interleaving; execute the real database CAS.
            assert "timestamp()<$deadline_ms" in query
            exercised.append(params["deadline_ms"])
            params = {**params, "deadline_ms": 0}
        return original_query(query, params, **kwargs)

    monkeypatch.setattr(graph._graph, "query", expiry_interleaving)
    writer = ApprovalWriter(graph, sources, principal, holder_id=ids["holder"])
    with pytest.raises(ValueError, match="compare-and-swap|expired"):
        writer.approve_release(command, effective_world_tick=10)
    assert len(exercised) == 1
    assert graph.read_version_root() == before
    release = graph.get_node("Release", command.target_id)
    assert release is not None and release["state"] == "staged"
    assert graph.get_node("DispatchEvent", command.event_id) is None


def test_constraint_failure_rolls_back_release_and_entire_activation_cas(isolated_console_graph, tmp_path, monkeypatch):  # noqa: F811
    from approval_db_fixture import staged_fixture
    from redis.exceptions import ResponseError

    graph, sources, principal, command, ids = staged_fixture(isolated_console_graph, tmp_path)
    before = graph.read_version_root()
    existing_source = ids["release"].removesuffix("release") + "roster-source"
    assert graph.get_node("Source", existing_source) is not None
    original_query = graph._graph.query

    def constraint_failure(query, params=None, **kwargs):
        if "CREATE (a:ApprovalEvent" in query:
            # Exercise actual engine rollback after the production writes but before RETURN.
            query = query.replace("RETURN properties(s) AS state,properties(a)",
                "CREATE (:Source {id:$conflict_id,tenant_id:$tenant_id}) "
                "RETURN properties(s) AS state,properties(a)")
            params = {**params, "conflict_id": existing_source}
        return original_query(query, params, **kwargs)

    monkeypatch.setattr(graph._graph, "query", constraint_failure)
    writer = ApprovalWriter(graph, sources, principal, holder_id=ids["holder"])
    with pytest.raises(ResponseError):
        writer.approve_release(command, effective_world_tick=10)
    assert graph.read_version_root() == before
    release = graph.get_node("Release", command.target_id)
    assert release is not None and release["state"] == "staged"
    assert graph.get_node("DispatchEvent", command.event_id) is None
