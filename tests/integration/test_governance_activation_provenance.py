"""A detached owner-shaped approval is not committed activation provenance."""

import json
from datetime import UTC, datetime

import pytest
from test_governance_release import release_snapshot

from witness_fleet.domain import Observation, Pose, canonical_json_hash
from witness_fleet.graph.governance import validate_governance


def approved_release(tmp_path):
    snapshot, sources, release = release_snapshot(tmp_path)
    release["state"] = "released"
    approval = {
        "labels": ["ApprovalEvent"], "id": "release-approval",
        "event_id": "release-approval", "tenant_id": "demo", "actor_id": "owner",
        "target_id": "release", "action": "approve", "expected_policy_epoch": 0,
    }
    snapshot["nodes"].append(approval)
    snapshot["edges"].append({
        "source_id": "release-approval", "target_id": "release",
        "relationship": "APPROVES",
    })
    return snapshot, sources, release, approval


def bind_release_activation(snapshot, release, approval):
    """Add only the declared sequenced proof to a valid offline source fixture."""
    activation_id = approval["id"] + "-activation"
    command = {
        "event_id": activation_id, "tenant_id": "demo", "actor_id": approval["actor_id"],
        "target_id": release["id"], "action": "approve",
        "expected_policy_epoch": approval["expected_policy_epoch"], "notes": "",
    }
    intent_hash = canonical_json_hash(command)
    payload = {
        "policy_epoch": approval["expected_policy_epoch"] + 1,
        "expected_previous_policy_epoch": approval["expected_policy_epoch"],
        "policy_proof": {
            "proof_id": approval["id"], "coordinator_epoch": 1,
            "approval_hash": intent_hash, "target_id": release["id"],
            "actor_id": approval["actor_id"], "restriction_id": "rule",
            "span_id": "span", "owner_span_id": "roster-span",
        },
    }
    approval.update({
        "tenant_id": "demo", "payload_json": json.dumps(command), "payload_hash": intent_hash,
        "event_id": activation_id, "activation_event_id": activation_id, "dispatch_sequence": 1,
        "coordinator_epoch": 1, "effective_world_tick": 1, "graph_version": 1,
    })
    # A positive activation fixture now includes the required retained physical
    # proof. This is synthetic test data, not a simulator-produced live result.
    now = datetime(2026, 1, 1, tzinfo=UTC)
    approval['created_at'] = now.isoformat()
    references = []
    for predicate in ('recovery_verified', 'courier_fit'):
        observation = Observation(
            id='activation-' + predicate, tenant_id='demo', episode_id='episode',
            robot_id='scout', occurred_at=now, recorded_at=now, world_tick=1,
            expires_tick=51, predicate=predicate, value=True,
            pose=Pose(x=-3.5, y=-.55), visibility='visible',
            scope={'corridor_id': 'corridor-c', 'release_id': release['id'],
                   'robot_type': 'courier', 'payload_class': 'loaded'},
            sensor_config_hash='sensor-v1', subject_id='corridor-c')
        snapshot['nodes'].append({'id': observation.id, 'labels': ['Observation'],
            'tenant_id': 'demo', 'predicate': predicate, 'value': True,
            'payload_json': observation.model_dump_json()})
        references.append({'observation_id': observation.id,
                           'payload_hash': canonical_json_hash(observation)})
    approval['verification_json'] = json.dumps(references)
    release["approval_event_id"] = approval["id"]
    activation = {
        "labels": ["DispatchEvent"], "id": activation_id, "event_id": activation_id,
        "tenant_id": "demo", "kind": "POLICY_ACTIVATION", "sequence": 1,
        "coordinator_epoch": 1, "effective_world_tick": 1, "payload_json": json.dumps(payload),
        "payload_hash": canonical_json_hash(payload), "subject_ids_json": json.dumps([
            release["id"], "rule", approval["actor_id"], "span", "roster-span", approval["id"],
        ]),
    }
    snapshot["nodes"].append(activation)
    snapshot["edges"].append({
        "source_id": activation["id"], "source_label": "DispatchEvent",
        "target_id": release["id"], "target_label": "Release", "relationship": "DELIVERS",
    })
    snapshot["versions"] = {
        "graph_version": 1, "policy_epoch": approval["expected_policy_epoch"] + 1,
        "coordinator_epoch": 1, "dispatch_sequence": 1, "map_version": 0,
    }
    return activation


@pytest.mark.parametrize("label,first", [
    ("ApprovalEvent", False), ("ApprovalEvent", True),
    ("DispatchEvent", False), ("DispatchEvent", True),
])
def test_duplicate_canonical_approval_or_dispatch_id_never_approves_release(tmp_path, label, first):
    snapshot, sources, release, approval = approved_release(tmp_path)
    activation = bind_release_activation(snapshot, release, approval)
    original = approval if label == "ApprovalEvent" else activation
    duplicate = dict(original)
    if label == "ApprovalEvent":
        duplicate["action"] = "reject"
    else:
        duplicate["payload_hash"] = "sha256:forged"
    snapshot["nodes"].remove(original)
    snapshot["nodes"].extend([duplicate, original] if first else [original, duplicate])

    witnesses, errors = validate_governance(snapshot, sources)

    assert f"DUPLICATE_NODE_ID:{original['id']}" in errors
    assert next(w for w in witnesses if w.id == "release").approved is False


def test_unrelated_duplicate_canonical_id_fails_closed_for_release_projection(tmp_path):
    snapshot, sources, release, approval = approved_release(tmp_path)
    bind_release_activation(snapshot, release, approval)
    corridor = next(node for node in snapshot["nodes"] if node["id"] == "corridor-c")
    snapshot["nodes"].append(dict(corridor))

    witnesses, errors = validate_governance(snapshot, sources)

    assert "DUPLICATE_NODE_ID:corridor-c" in errors
    assert next(w for w in witnesses if w.id == release["id"]).approved is False




def test_release_approval_without_sequenced_activation_is_not_authority(tmp_path):
    snapshot, sources, _, _ = approved_release(tmp_path)
    witnesses, errors = validate_governance(snapshot, sources)
    assert "INVALID_ACTIVATION_PROVENANCE:release" in errors
    assert next(w for w in witnesses if w.id == "release").approved is False


def test_exact_sequenced_activation_binds_owner_target_intent_and_source(tmp_path):
    snapshot, sources, release, approval = approved_release(tmp_path)
    bind_release_activation(snapshot, release, approval)
    witnesses, errors = validate_governance(snapshot, sources)
    assert errors == ()
    assert next(w for w in witnesses if w.id == "release").approved is True


def test_release_approval_requires_valid_release_source_chain(tmp_path):
    snapshot, sources, release, approval = approved_release(tmp_path)
    bind_release_activation(snapshot, release, approval)
    next(node for node in snapshot["nodes"] if node["id"] == "span")["quote"] = "tampered release source"

    witnesses, errors = validate_governance(snapshot, sources)

    witness = next(w for w in witnesses if w.id == release["id"])
    assert "INVALID_SOURCE_CHAIN:release" in errors
    assert witness.source_valid is False
    assert witness.approved is False


def test_release_approval_requires_valid_owner_roster_source_chain(tmp_path):
    snapshot, sources, release, approval = approved_release(tmp_path)
    bind_release_activation(snapshot, release, approval)
    next(node for node in snapshot["nodes"] if node["id"] == "roster-span")["quote"] = "tampered owner roster"

    witnesses, errors = validate_governance(snapshot, sources)

    witness = next(w for w in witnesses if w.id == release["id"])
    assert "INVALID_SOURCE_CHAIN:release" in errors
    assert "INVALID_OWNER_ROSTER:release" in errors
    assert witness.owner_valid is False
    assert witness.approved is False


def test_wrong_hash_activation_never_makes_owner_shaped_approval_authority(tmp_path):
    snapshot, sources, release, approval = approved_release(tmp_path)
    activation = bind_release_activation(snapshot, release, approval)
    activation["payload_hash"] = "sha256:forged"
    witnesses, errors = validate_governance(snapshot, sources)
    assert "INVALID_ACTIVATION_PROVENANCE:release" in errors
    assert next(w for w in witnesses if w.id == "release").approved is False



@pytest.mark.parametrize("field,value", [
    ("policy_epoch", True), ("expected_previous_policy_epoch", False),
    ("policy_epoch", 2), ("expected_previous_policy_epoch", 1),
])
def test_rehashed_activation_cannot_alias_or_skip_approval_epoch(tmp_path, field, value):
    snapshot, sources, release, approval = approved_release(tmp_path)
    activation = bind_release_activation(snapshot, release, approval)
    payload = json.loads(activation["payload_json"])
    payload[field] = value
    activation["payload_json"] = json.dumps(payload)
    activation["payload_hash"] = canonical_json_hash(payload)
    witnesses, errors = validate_governance(snapshot, sources)
    assert "INVALID_ACTIVATION_PROVENANCE:release" in errors
    assert next(w for w in witnesses if w.id == "release").approved is False


@pytest.mark.parametrize("field,value", [
    ("proof_id", "wrong-approval"), ("actor_id", "other-owner"),
    ("target_id", "other-release"), ("restriction_id", "other-restriction"),
    ("span_id", "other-span"), ("owner_span_id", "other-roster"),
    ("coordinator_epoch", True), ("approval_hash", "sha256:forged"),
])
def test_rehashed_proof_must_bind_every_original_identity(tmp_path, field, value):
    snapshot, sources, release, approval = approved_release(tmp_path)
    activation = bind_release_activation(snapshot, release, approval)
    payload = json.loads(activation["payload_json"])
    payload["policy_proof"][field] = value
    activation["payload_json"] = json.dumps(payload)
    activation["payload_hash"] = canonical_json_hash(payload)
    witnesses, errors = validate_governance(snapshot, sources)
    assert "INVALID_ACTIVATION_PROVENANCE:release" in errors
    assert next(w for w in witnesses if w.id == "release").approved is False


def test_historical_approval_remains_bound_after_later_policy_epoch(tmp_path):
    snapshot, sources, release, approval = approved_release(tmp_path)
    bind_release_activation(snapshot, release, approval)
    snapshot["versions"].update({"policy_epoch": 9, "graph_version": 30,
                                 "dispatch_sequence": 12, "coordinator_epoch": 4})
    witnesses, errors = validate_governance(snapshot, sources)
    assert errors == ()
    assert next(w for w in witnesses if w.id == "release").approved is True


def test_two_activations_of_one_release_are_ambiguous_not_authority(tmp_path):
    snapshot, sources, release, approval = approved_release(tmp_path)
    activation = bind_release_activation(snapshot, release, approval)
    duplicate = {**activation, "id": "other-activation", "event_id": "other-activation", "sequence": 2}
    snapshot["nodes"].append(duplicate)
    snapshot["edges"].append({"source_id": duplicate["id"], "target_id": "release",
                              "relationship": "DELIVERS"})
    witnesses, errors = validate_governance(snapshot, sources)
    assert "INVALID_ACTIVATION_PROVENANCE:release" in errors
    assert next(w for w in witnesses if w.id == "release").approved is False


def test_intent_notes_cannot_change_after_commit_even_with_same_actor_and_epoch(tmp_path):
    snapshot, sources, release, approval = approved_release(tmp_path)
    bind_release_activation(snapshot, release, approval)
    intent = json.loads(approval["payload_json"])
    intent["notes"] = "changed after commit"
    approval["payload_json"] = json.dumps(intent)
    witnesses, errors = validate_governance(snapshot, sources)
    assert "INVALID_ACTIVATION_PROVENANCE:release" in errors
    assert next(w for w in witnesses if w.id == "release").approved is False


