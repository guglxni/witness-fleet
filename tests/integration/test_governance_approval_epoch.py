"""Offline retained-source checks for approval epoch identity."""

import pytest
from test_governance_integrity import valid_snapshot
from test_governance_release import release_snapshot

from witness_fleet.graph.governance import validate_governance

_MISSING = object()


def approval_fixture(tmp_path, target):
    if target == "decision":
        snapshot, sources = valid_snapshot(tmp_path)
        event = next(node for node in snapshot["nodes"] if node["id"] == "decision-approval")
        witness_id = "rule"
    else:
        snapshot, sources, release = release_snapshot(tmp_path)
        release["state"] = "released"
        event = {
            "labels": ["ApprovalEvent"], "id": "release-approval", "actor_id": "owner",
            "target_id": "release", "action": "approve", "event_id": "release-approval",
        }
        snapshot["nodes"].append(event)
        snapshot["edges"].append({
            "source_id": "release-approval", "target_id": "release", "relationship": "APPROVES",
        })
        witness_id = "release"
    for node in snapshot["nodes"]:
        if "ApprovalEvent" in node.get("labels", ()):
            node["expected_policy_epoch"] = 7
    snapshot["versions"] = {"policy_epoch": 7}
    if target == "release":
        from test_governance_activation_provenance import bind_release_activation
        release_node = next(n for n in snapshot["nodes"] if n["id"] == "release")
        bind_release_activation(snapshot, release_node, event)
    return snapshot, sources, event, witness_id


@pytest.mark.parametrize("target", ["decision", "release"])
@pytest.mark.parametrize(
    "epoch", [_MISSING, True, False, 1.5, -1, "7", None],
    ids=["missing", "true", "false", "fractional", "negative", "string", "null"],
)
def test_approval_requires_nonnegative_exact_integer_epoch(tmp_path, target, epoch):
    snapshot, sources, event, witness_id = approval_fixture(tmp_path, target)
    if epoch is _MISSING:
        event.pop("expected_policy_epoch")
    else:
        event["expected_policy_epoch"] = epoch
    witnesses, errors = validate_governance(snapshot, sources)
    witness = next(item for item in witnesses if item.id == witness_id)
    assert f"INVALID_APPROVAL:{target}" in errors
    assert witness.approved is False


@pytest.mark.parametrize("target", ["decision", "release"])
def test_typed_approval_epoch_keeps_exact_owner_and_source_chain(tmp_path, target):
    snapshot, sources, _, witness_id = approval_fixture(tmp_path, target)
    witnesses, errors = validate_governance(snapshot, sources)
    witness = next(item for item in witnesses if item.id == witness_id)
    assert errors == ()
    assert witness.approved is True
    assert witness.owner_valid is True and witness.source_valid is True
