"""Coordinator authority is bound and live at the new-command CAS boundary."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.domain import (
    ActionProposal,
    AuthorizationResult,
    CommandIntent,
    SkillKind,
    VersionVector,
    payload_hash,
)
from witness_fleet.runtime.storage import TransitionStore

pytestmark = pytest.mark.integration


def _epoch_milliseconds(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    delta = parsed - datetime(1970, 1, 1, tzinfo=UTC)
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000


def _prepared_fixture(graph):
    suffix = uuid.uuid4().hex
    ids = graph.seed_claim_fixture(suffix)
    root = graph.read_version_root()
    assert root is not None
    now = datetime.now(UTC)
    lease = (now + timedelta(minutes=10, microseconds=987)).isoformat().replace("+00:00", "Z")
    holder = f"command-coordinator-{suffix}"
    acquired = TransitionStore(graph).acquire_coordinator(
        expected_epoch=root["coordinator_epoch"], holder_id=holder,
        now_utc=now.isoformat().replace("+00:00", "Z"), lease_expires_at_utc=lease,
        event_id=f"it-command-barrier-{suffix}", effective_world_tick=1,
    )
    assert acquired is not None
    claim = graph.claim_task(
        task_id=ids["task_id"], robot_id=ids["robot_0"], expected_task_version=0,
        coordinator_epoch=acquired["coordinator_epoch"], resource_ids=ids["resource_ids"],
        lease_expires_at_utc=lease, now_utc=now.isoformat().replace("+00:00", "Z"),
    )
    assert claim is not None
    root = graph.read_version_root()
    task = graph.get_node("Task", ids["task_id"])
    resources = {resource: graph.get_node("Resource", resource) for resource in ids["resource_ids"]}
    assert root is not None and task is not None and all(resources.values())
    versions = VersionVector(
        graph_version=root["graph_version"], policy_epoch=root["policy_epoch"],
        coordinator_epoch=root["coordinator_epoch"], task_version=task["task_version"],
        dependency_versions={key: value["resource_version"] for key, value in resources.items()},
    )
    proposal = ActionProposal(
        id=f"it-command-proposal-{suffix}", robot_id=ids["robot_0"], task_id=ids["task_id"],
        kind=SkillKind.INSPECT, parameters={"target": "coordinator-lease-fixture"},
        expected_versions=versions, required_predicates=(),
        required_resource_ids=tuple(ids["resource_ids"]), expected_effects=(),
    )
    authorization = AuthorizationResult(
        authorization_id=f"it-command-auth-{suffix}", status="ALLOW", reason_codes=(),
        witness_ids=(), versions=versions, action_payload_hash=payload_hash(proposal),
        valid_until_tick=100, claim_id=claim["claim_id"], task_id=ids["task_id"],
        robot_id=ids["robot_0"], fence=claim["fence"],
        resource_fences=claim["resource_fences"],
        governance_integrity_version=root["policy_epoch"],
    )
    command = CommandIntent(
        command_id=f"it-command-{suffix}", proposal=proposal, payload_hash=payload_hash(proposal),
        claim_id=claim["claim_id"], fence=claim["fence"],
        resource_fences=claim["resource_fences"], authorization_id=authorization.authorization_id,
        policy_epoch=root["policy_epoch"], coordinator_epoch=root["coordinator_epoch"],
        dispatch_sequence=root["dispatch_sequence"] + 1, effective_world_tick=2,
        authorization=authorization,
    )
    return graph, TransitionStore(graph, holder_id=holder), holder, lease, command, authorization, root


def _set_coordinator_fields(graph, assignments: dict[str, object]) -> None:
    allowed = {
        "coordinator_holder_id", "coordinator_epoch", "coordinator_lease_expires_at_utc",
    }
    assert assignments and set(assignments) <= allowed
    setters = ", ".join(f"s.{field}=${field}" for field in assignments)
    graph._graph.query(
        f"MATCH (s:FleetState {{id:'fleet',tenant_id:$tenant_id}}) SET {setters} RETURN s.id",
        {"tenant_id": graph.tenant_id, **assignments},
    )


def test_new_command_requires_configured_live_coordinator_lease(isolated_console_graph):  # noqa: F811
    graph, transitions, holder, lease, command, authorization, root = _prepared_fixture(
        isolated_console_graph,
    )
    before = graph.read_version_root()

    prepared = transitions.prepare_command(
        command=command, authorization=authorization,
        expected_graph_version=root["graph_version"],
    )

    assert prepared is not None
    assert prepared["command"]["command_id"] == command.command_id
    assert before is not None and graph.read_version_root()["graph_version"] == before["graph_version"] + 1


def test_new_command_without_configured_coordinator_holder_fails_closed(isolated_console_graph):  # noqa: F811
    graph, _, _, _, command, authorization, root = _prepared_fixture(isolated_console_graph)
    transitions = TransitionStore(graph)
    before = graph.read_version_root()

    result = transitions.prepare_command(
        command=command, authorization=authorization,
        expected_graph_version=root["graph_version"],
    )

    assert result is None
    assert before == graph.read_version_root()
    assert transitions.get_command(command.command_id) is None


@pytest.mark.parametrize(
    "lease_change",
    [
        {"coordinator_holder_id": "foreign-coordinator"},
        {"coordinator_holder_id": None},
        {"coordinator_lease_expires_at_utc": None},
        {"coordinator_lease_expires_at_utc": "not-a-utc-lease"},
        {"coordinator_lease_expires_at_utc": "2000-01-01T00:00:00Z"},
    ],
    ids=["wrong-holder", "missing-holder", "missing-lease", "malformed-lease", "expired-lease"],
)
def test_invalid_coordinator_lease_does_not_authorize_new_command(
    isolated_console_graph, lease_change,  # noqa: F811
):  # noqa: F811
    graph, transitions, _, _, command, authorization, root = _prepared_fixture(isolated_console_graph)
    _set_coordinator_fields(graph, lease_change)
    before = graph.read_version_root()

    result = transitions.prepare_command(
        command=command, authorization=authorization,
        expected_graph_version=root["graph_version"],
    )

    assert result is None
    assert before == graph.read_version_root()
    assert transitions.get_command(command.command_id) is None


@pytest.mark.parametrize(
    "takeover",
    [
        {"coordinator_holder_id": "replacement-holder"},
        {"coordinator_epoch": 99},
        {"coordinator_lease_expires_at_utc": "2099-01-01T00:00:00.123456Z"},
    ],
    ids=["holder", "epoch", "lease-identity"],
)
def test_coordinator_takeover_between_read_and_cas_writes_nothing(
    isolated_console_graph, monkeypatch, takeover,  # noqa: F811
):  # noqa: F811
    graph, transitions, holder, lease, command, authorization, root = _prepared_fixture(
        isolated_console_graph,
    )
    before = graph.read_version_root()
    original_query = graph._graph.query
    injected = []

    def take_over_before_command_cas(query, params=None, **kwargs):
        if "CREATE (c:Command" in query:
            injected.append((query, dict(params)))
            _set_coordinator_fields(graph, takeover)
        return original_query(query, params, **kwargs)

    monkeypatch.setattr(graph._graph, "query", take_over_before_command_cas)
    result = transitions.prepare_command(
        command=command, authorization=authorization,
        expected_graph_version=root["graph_version"],
    )

    assert result is None
    assert len(injected) == 1
    query, params = injected[0]
    assert "s.coordinator_holder_id=$coordinator_holder_id" in query
    assert "s.coordinator_lease_expires_at_utc=$coordinator_lease" in query
    assert params["coordinator_holder_id"] == holder
    assert params["coordinator_epoch"] == command.coordinator_epoch
    assert params["coordinator_lease"] == lease
    after = graph.read_version_root()
    assert after is not None
    assert after["graph_version"] == before["graph_version"]
    assert all(after[field] == value for field, value in takeover.items())
    assert transitions.get_command(command.command_id) is None


def test_coordinator_expiry_at_cas_boundary_is_rejected(isolated_console_graph, monkeypatch):  # noqa: F811
    graph, transitions, holder, lease, command, authorization, root = _prepared_fixture(
        isolated_console_graph,
    )
    before = graph.read_version_root()
    original_query = graph._graph.query
    captured = []

    def expire_lease_at_command_cas(query, params=None, **kwargs):
        if "CREATE (c:Command" in query:
            captured.append((query, dict(params)))
            params = {**params, "coordinator_deadline_ms": 0}
        return original_query(query, params, **kwargs)

    monkeypatch.setattr(graph._graph, "query", expire_lease_at_command_cas)
    result = transitions.prepare_command(
        command=command, authorization=authorization,
        expected_graph_version=root["graph_version"],
    )

    assert result is None
    assert len(captured) == 1
    query, params = captured[0]
    assert "timestamp()<$coordinator_deadline_ms" in query
    assert params["coordinator_holder_id"] == holder
    assert params["coordinator_lease"] == lease
    assert params["coordinator_deadline_ms"] == _epoch_milliseconds(lease)
    assert before is not None and graph.read_version_root()["graph_version"] == before["graph_version"]
    assert transitions.get_command(command.command_id) is None


def test_fractional_coordinator_lease_uses_exact_guard_and_integer_server_deadline(
    isolated_console_graph, monkeypatch,  # noqa: F811
):  # noqa: F811
    graph, transitions, holder, lease, command, authorization, root = _prepared_fixture(
        isolated_console_graph,
    )
    original_query = graph._graph.query
    captured = []

    def capture_command_cas(query, params=None, **kwargs):
        if "CREATE (c:Command" in query:
            captured.append((query, dict(params)))
        return original_query(query, params, **kwargs)

    monkeypatch.setattr(graph._graph, "query", capture_command_cas)
    result = transitions.prepare_command(
        command=command, authorization=authorization,
        expected_graph_version=root["graph_version"],
    )

    assert result is not None
    assert len(captured) == 1
    query, params = captured[0]
    assert "." in lease.split("Z")[0]
    assert "s.coordinator_lease_expires_at_utc=$coordinator_lease" in query
    assert "timestamp()<$coordinator_deadline_ms" in query
    assert params["coordinator_holder_id"] == holder
    assert params["coordinator_epoch"] == command.coordinator_epoch
    assert params["coordinator_lease"] == lease
    assert params["coordinator_deadline_ms"] == _epoch_milliseconds(lease)


def test_cached_command_retry_remains_read_only_after_coordinator_lease_expires(isolated_console_graph):  # noqa: F811
    graph, transitions, _, _, command, authorization, root = _prepared_fixture(isolated_console_graph)
    first = transitions.prepare_command(
        command=command, authorization=authorization,
        expected_graph_version=root["graph_version"],
    )
    assert first is not None
    committed_root = graph.read_version_root()
    assert committed_root is not None
    _set_coordinator_fields(
        graph, {"coordinator_lease_expires_at_utc": "2000-01-01T00:00:00Z"},
    )

    retry = transitions.prepare_command(
        command=command, authorization=authorization,
        expected_graph_version=root["graph_version"],
    )

    assert retry is not None
    assert retry["event"] == first["event"]
    assert graph.read_version_root()["graph_version"] == committed_root["graph_version"]
