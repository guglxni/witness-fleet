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
    canonical_json_hash,
    payload_hash,
)
from witness_fleet.runtime.storage import TransitionStore

pytestmark = pytest.mark.integration


def prepared_fixture(graph):
    acquisition_store = TransitionStore(graph)
    suffix = uuid.uuid4().hex
    ids = graph.seed_claim_fixture(suffix)
    root = graph.read_version_root()
    assert root is not None
    lease_now = datetime.now(UTC)
    if root.get("coordinator_lease_expires_at_utc"):
        previous_expiry = datetime.fromisoformat(
            root["coordinator_lease_expires_at_utc"].replace("Z", "+00:00")
        )
        lease_now = max(lease_now, previous_expiry + timedelta(seconds=1))
    lease_expiry = lease_now + timedelta(days=60)
    holder = f"it-holder-{suffix}"
    coordinator = acquisition_store.acquire_coordinator(
        expected_epoch=root["coordinator_epoch"], holder_id=holder,
        now_utc=lease_now.isoformat(), lease_expires_at_utc=lease_expiry.isoformat(),
        event_id=f"it-barrier-{suffix}", effective_world_tick=1,
    )
    assert coordinator is not None
    claim = graph.claim_task(
        task_id=ids["task_id"], robot_id=ids["robot_0"], expected_task_version=0,
        coordinator_epoch=coordinator["coordinator_epoch"], resource_ids=ids["resource_ids"],
        lease_expires_at_utc=lease_expiry.isoformat(), now_utc=lease_now.isoformat(),
    )
    assert claim is not None
    root = graph.read_version_root()
    task = graph.get_node("Task", ids["task_id"])
    resources = {resource: graph.get_node("Resource", resource) for resource in ids["resource_ids"]}
    assert task is not None and all(resources.values())
    versions = VersionVector(
        graph_version=root["graph_version"], policy_epoch=root["policy_epoch"],
        coordinator_epoch=root["coordinator_epoch"], task_version=task["task_version"],
        dependency_versions={key: value["resource_version"] for key, value in resources.items()},
    )
    proposal = ActionProposal(
        id=f"it-proposal-{suffix}", robot_id=ids["robot_0"], task_id=ids["task_id"],
        kind=SkillKind.INSPECT, parameters={"target": "fixture"}, expected_versions=versions,
        required_predicates=(), required_resource_ids=tuple(ids["resource_ids"]),
        expected_effects=(),
    )
    auth = AuthorizationResult(
        authorization_id=f"it-auth-{suffix}", status="ALLOW", reason_codes=(), witness_ids=(),
        versions=versions, action_payload_hash=payload_hash(proposal), valid_until_tick=100,
        claim_id=claim["claim_id"], task_id=ids["task_id"], robot_id=ids["robot_0"],
        fence=claim["fence"], resource_fences=claim["resource_fences"],
        governance_integrity_version=root["policy_epoch"],
    )
    command = CommandIntent(
        command_id=f"it-command-{suffix}", proposal=proposal, payload_hash=payload_hash(proposal),
        claim_id=auth.claim_id, fence=auth.fence, resource_fences=auth.resource_fences,
        authorization_id=auth.authorization_id, policy_epoch=root["policy_epoch"],
        coordinator_epoch=root["coordinator_epoch"], dispatch_sequence=root["dispatch_sequence"] + 1,
        effective_world_tick=2, authorization=auth,
    )
    return graph, TransitionStore(graph, holder_id=holder), command, auth, root["graph_version"]


def test_command_intent_receipt_and_outbox_event_commit_atomically(isolated_console_graph):  # noqa: F811
    graph, transitions, command, auth, expected = prepared_fixture(isolated_console_graph)
    prepared = transitions.prepare_command(
        command=command, authorization=auth, expected_graph_version=expected,
    )
    assert prepared is not None
    assert prepared["command"]["command_id"] == command.command_id
    assert prepared["authorization_receipt"]["id"] == auth.authorization_id
    assert prepared["event"]["kind"] == "COMMAND"
    assert prepared["event"]["sequence"] == command.dispatch_sequence
    assert prepared["event"]["payload_hash"]
    assert transitions.get_command(command.command_id) == command
    assert graph.read_version_root()["graph_version"] == expected + 1


def test_identical_command_retry_returns_the_durable_prepared_record(isolated_console_graph):  # noqa: F811
    graph, transitions, command, auth, expected = prepared_fixture(isolated_console_graph)
    first = transitions.prepare_command(
        command=command, authorization=auth, expected_graph_version=expected,
    )
    retried = transitions.prepare_command(
        command=command, authorization=auth, expected_graph_version=expected,
    )
    assert first is not None and retried is not None
    assert retried["event"]["event_id"] == first["event"]["event_id"]
    assert retried["dispatch_sequence"] == first["dispatch_sequence"]
    assert graph.read_version_root()["graph_version"] == expected + 1


def test_command_prepare_stale_graph_version_writes_nothing(isolated_console_graph):  # noqa: F811
    graph, transitions, command, auth, expected = prepared_fixture(isolated_console_graph)
    payload = {"policy_epoch": 1, "expected_previous_policy_epoch": 0,
               "policy_proof": {"coordinator_epoch": command.coordinator_epoch,
                                "proof_id": "synthetic-test-proof"}}
    winner = transitions.append_control_event(
        event={"id": f"it-control-{uuid.uuid4().hex}", "kind": "REVOCATION",
               "payload": payload, "payload_hash": canonical_json_hash(payload),
               "subject_ids": [], "effective_world_tick": 2},
        expected_graph_version=expected,
    )
    assert winner is not None
    stale = transitions.prepare_command(
        command=command, authorization=auth, expected_graph_version=expected,
    )
    assert stale is None
    assert transitions.get_command(command.command_id) is None


def test_command_sequence_must_match_next_graph_sequence(isolated_console_graph):  # noqa: F811
    graph, transitions, command, auth, expected = prepared_fixture(isolated_console_graph)
    stale_sequence = command.model_copy(update={"dispatch_sequence": command.dispatch_sequence + 9})
    result = transitions.prepare_command(
        command=stale_sequence, authorization=auth, expected_graph_version=expected,
    )
    assert result is None
    assert graph.read_version_root()["graph_version"] == expected
    assert transitions.get_command(command.command_id) is None
