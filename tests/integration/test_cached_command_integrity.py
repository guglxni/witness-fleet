"""Offline corruption seam for retained command retries, without graph mutations."""
import json
from types import SimpleNamespace

import pytest
from test_protocol_commands import command_event

from witness_fleet.domain import CommandIntent, canonical_json_hash
from witness_fleet.runtime.storage import TransitionStore


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class CachedGraph:
    tenant_id = "demo"

    def __init__(self, command, *, corruption=None):
        body = command.model_dump(mode="json")
        auth = command.authorization.model_dump(mode="json")
        subject_ids = [
            command.command_id,
            command.proposal.task_id,
            command.proposal.robot_id,
            command.claim_id,
            command.authorization_id,
        ]
        self.command = {
            "id": command.command_id,
            "command_id": command.command_id,
            "tenant_id": self.tenant_id,
            "payload_hash": canonical_json_hash(body),
            "payload_json": canonical(body),
            "dispatch_sequence": command.dispatch_sequence,
            "coordinator_epoch": command.coordinator_epoch,
            "authorization_id": command.authorization_id,
            "fence": command.fence,
        }
        self.authorization = {
            "id": command.authorization_id,
            "tenant_id": self.tenant_id,
            "proposal_id": command.proposal.id,
            "task_id": command.proposal.task_id,
            "robot_id": command.proposal.robot_id,
            "claim_id": command.claim_id,
            "decision": "ALLOW",
            "reason_codes_json": canonical(list(command.authorization.reason_codes)),
            "action_payload_hash": command.authorization.action_payload_hash,
            "versions_json": canonical(command.authorization.versions.model_dump(mode="json")),
            "resource_fences_json": canonical(dict(command.resource_fences)),
            "witness_ids_json": canonical(list(command.authorization.witness_ids)),
            "governance_integrity_version": command.authorization.governance_integrity_version,
            "valid_until_tick": command.authorization.valid_until_tick,
            "created_world_tick": command.effective_world_tick,
            "payload_json": canonical(auth),
        }
        self.event = {
            "id": command.command_id,
            "event_id": command.command_id,
            "tenant_id": self.tenant_id,
            "sequence": command.dispatch_sequence,
            "coordinator_epoch": command.coordinator_epoch,
            "kind": "COMMAND",
            "payload_hash": canonical_json_hash(body),
            "payload_json": canonical(body),
            "subject_ids_json": canonical(subject_ids),
            "effective_world_tick": command.effective_world_tick,
        }
        if corruption == "command_json":
            self.command["payload_json"] = canonical({"unexpected": "corrupt-command-marker"})
        elif corruption == "event_body":
            self.event["payload_json"] = canonical({"unexpected": "corrupt-event-marker"})
        elif corruption == "event_hash":
            self.event["payload_hash"] = "0" * 64
        elif corruption == "event_sequence":
            self.event["sequence"] += 1
        elif corruption == "event_subject_ids":
            self.event["subject_ids_json"] = canonical(["wrong-subject"])
        elif corruption == "event_tick":
            self.event["effective_world_tick"] += 1

        self.query_calls = 0
        self.root_calls = 0

    def _query(self, query, params):
        self.query_calls += 1
        return SimpleNamespace(
            header=[(0, "command"), (0, "authorization_receipt"), (0, "event")],
            result_set=[[self.command, self.authorization, self.event]],
        )

    def read_version_root(self):
        self.root_calls += 1
        # A cached retry is allowed even after the current graph version moves.
        return {"graph_version": 9}


def test_cached_retry_rejects_corrupt_command_json_despite_matching_hash_field():
    command = CommandIntent.model_validate(command_event().payload)
    graph = CachedGraph(command, corruption="command_json")
    with pytest.raises(ValueError):
        TransitionStore(graph).prepare_command(
            command=command, authorization=command.authorization, expected_graph_version=1,
        )


@pytest.mark.parametrize(
    "corruption",
    ["event_body", "event_hash", "event_sequence", "event_subject_ids", "event_tick"],
)
def test_cached_retry_rejects_corrupt_event_payload_or_binding(corruption):
    command = CommandIntent.model_validate(command_event().payload)
    graph = CachedGraph(command, corruption=corruption)
    with pytest.raises(ValueError):
        TransitionStore(graph).prepare_command(
            command=command, authorization=command.authorization, expected_graph_version=1,
        )
    assert graph.root_calls == 0


def test_corrupt_cached_payload_error_does_not_disclose_stored_data():
    command = CommandIntent.model_validate(command_event().payload)
    graph = CachedGraph(command, corruption="command_json")
    with pytest.raises(ValueError) as caught:
        TransitionStore(graph).prepare_command(
            command=command, authorization=command.authorization, expected_graph_version=1,
        )
    assert str(caught.value) == "cached command record failed integrity validation"
    assert "corrupt-command-marker" not in str(caught.value)


@pytest.mark.parametrize(
    ("record", "field", "corrupt_value"),
    [
        ("command", "fence", True),
        ("command", "coordinator_epoch", False),
        ("command", "dispatch_sequence", 1.0),
        ("authorization", "governance_integrity_version", True),
        ("authorization", "valid_until_tick", 10.0),
        ("authorization", "created_world_tick", False),
        ("authorization", "resource_fences_json", canonical({"corridor": True})),
        (
            "authorization",
            "versions_json",
            canonical({
                "graph_version": True,
                "policy_epoch": 0,
                "coordinator_epoch": 0,
                "task_version": 0,
                "dependency_versions": {},
            }),
        ),
    ],
)
def test_cached_retry_rejects_equal_but_wrongly_typed_stored_counter(record, field, corrupt_value):
    command = CommandIntent.model_validate(command_event().payload)
    graph = CachedGraph(command)
    getattr(graph, record)[field] = corrupt_value
    with pytest.raises(ValueError):
        TransitionStore(graph).prepare_command(
            command=command, authorization=command.authorization, expected_graph_version=1,
        )
    assert graph.root_calls == 0


def test_valid_cached_retry_returns_durable_record_without_rebinding_graph_version():
    command = CommandIntent.model_validate(command_event().payload)
    graph = CachedGraph(command)
    result = TransitionStore(graph).prepare_command(
        command=command, authorization=command.authorization, expected_graph_version=1,
    )
    assert result is not None
    assert result["graph_version"] == 9
    assert result["dispatch_sequence"] == command.dispatch_sequence
    assert result["command"] == graph.command
    assert result["authorization_receipt"] == graph.authorization
    assert result["event"] == graph.event
    assert (graph.query_calls, graph.root_calls) == (1, 1)
