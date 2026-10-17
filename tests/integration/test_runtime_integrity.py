from __future__ import annotations

import json
import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401
from test_command_preparation import prepared_fixture

from witness_fleet.domain import (
    ActionProposal,
    AuthorizationResult,
    CommandIntent,
    VersionVector,
    canonical_json_hash,
    payload_hash,
)
from witness_fleet.runtime.storage import OutboxIntegrityError, TransitionStore

pytestmark = pytest.mark.integration


class _GraphResult:
    def __init__(self, events: list[dict]):
        self.result_set = [[event] for event in events]


class _OutboxGraph:
    tenant_id = "demo"

    def __init__(self, events: list[dict]):
        self.events = events

    def _query(self, query: str, params: dict) -> _GraphResult:
        return _GraphResult(self.events)


def _outbox_event(**updates) -> dict:
    payload = {"command_id": "it-payload-secret-marker"}
    event = {
        "id": "it-legacy-outbox-event",
        "event_id": "it-legacy-outbox-event",
        "tenant_id": "demo",
        "sequence": 41,
        "coordinator_epoch": 3,
        "kind": "COMMAND",
        "payload_hash": canonical_json_hash(payload),
        "payload_json": json.dumps(payload, sort_keys=True, separators=(",", ":")),
        "subject_ids_json": '["it-command-41"]',
        "effective_world_tick": 9,
    }
    event.update(updates)
    return event


def test_legacy_outbox_without_payload_json_fails_closed_with_safe_context():
    event = _outbox_event()
    event.pop("payload_json")
    transitions = TransitionStore(_OutboxGraph([event]))

    with pytest.raises(OutboxIntegrityError) as raised:
        transitions.read_outbox()

    error = raised.value
    assert error.event_id == "it-legacy-outbox-event"
    assert error.sequence == 41
    assert error.reason == "missing_payload_json"
    assert "it-payload-secret-marker" not in str(error)


def test_outbox_malformed_or_hash_mismatched_payload_fails_closed():
    event = _outbox_event(payload_json="{not-json")
    transitions = TransitionStore(_OutboxGraph([event]))

    with pytest.raises(OutboxIntegrityError) as malformed:
        transitions.read_outbox()
    assert malformed.value.reason == "malformed_payload_json"

    event = _outbox_event(payload_hash="0" * 64)
    transitions = TransitionStore(_OutboxGraph([event]))
    with pytest.raises(OutboxIntegrityError) as mismatched:
        transitions.read_outbox()
    assert mismatched.value.reason == "invalid_event_or_payload_hash"


def test_atomic_prepare_requires_selected_claim_to_reserve_each_resource(isolated_console_graph):  # noqa: F811
    graph, transitions, command, authorization, _ = prepared_fixture(isolated_console_graph)
    off_claim_resource = f"it-offclaim-resource-{uuid.uuid4().hex}"
    graph.append_node(
        "Resource", off_claim_resource,
        {"kind": "corridor", "resource_version": 0, "fence": 0},
    )
    graph.append_edge(
        "REQUIRES_RESOURCE", "Task", command.proposal.task_id,
        "Resource", off_claim_resource,
    )

    root = graph.read_version_root()
    task = graph.get_node("Task", command.proposal.task_id)
    assert root is not None and task is not None
    resources = {
        resource_id: graph.get_node("Resource", resource_id)
        for resource_id in (*command.proposal.required_resource_ids, off_claim_resource)
    }
    assert all(resources.values())
    assert graph.read_resource_claims(off_claim_resource) == []
    required_resources = (*command.proposal.required_resource_ids, off_claim_resource)
    fences = dict(command.resource_fences) | {off_claim_resource: resources[off_claim_resource]["fence"]}
    versions = VersionVector(
        graph_version=root["graph_version"],
        policy_epoch=root["policy_epoch"],
        coordinator_epoch=root["coordinator_epoch"],
        task_version=task["task_version"],
        dependency_versions={
            resource_id: resources[resource_id]["resource_version"]
            for resource_id in required_resources
        },
    )
    proposal = ActionProposal.model_validate({
        **command.proposal.model_dump(mode="json"),
        "required_resource_ids": required_resources,
        "expected_versions": versions.model_dump(mode="json"),
    })
    refreshed_hash = payload_hash(proposal)
    authorization = AuthorizationResult.model_validate({
        **authorization.model_dump(mode="json"),
        "versions": versions.model_dump(mode="json"),
        "action_payload_hash": refreshed_hash,
        "resource_fences": fences,
    })
    command = CommandIntent.model_validate({
        **command.model_dump(mode="json"),
        "proposal": proposal.model_dump(mode="json"),
        "payload_hash": refreshed_hash,
        "resource_fences": fences,
        "authorization": authorization.model_dump(mode="json"),
    })

    before = graph.read_version_root()
    assert before is not None
    result = transitions.prepare_command(
        command=command, authorization=authorization,
        expected_graph_version=before["graph_version"],
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == before["graph_version"]
    assert transitions.get_command(command.command_id) is None
