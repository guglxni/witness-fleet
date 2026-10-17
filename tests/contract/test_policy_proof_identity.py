import pytest

from witness_fleet.domain import DispatchEvent, canonical_json_hash
from witness_fleet.simulation.protocol import preflight


@pytest.mark.parametrize("kind", ["POLICY_ACTIVATION", "REVOCATION"])
@pytest.mark.parametrize(
    ("proof_id", "include_proof_id", "accepted"),
    [
        pytest.param(None, False, False, id="missing"),
        pytest.param("", True, False, id="empty-string"),
        pytest.param(123, True, False, id="integer"),
        pytest.param(True, True, False, id="boolean"),
        pytest.param(1.5, True, False, id="float"),
        pytest.param(["proof"], True, False, id="list"),
        pytest.param({"id": "proof"}, True, False, id="object"),
        pytest.param("proof-1", True, True, id="ordinary-string"),
        pytest.param("  ", True, True, id="nonempty-string-is-not-normalized"),
    ],
)
def test_policy_transition_requires_nonempty_string_proof_id(
    kind, proof_id, include_proof_id, accepted
):
    proof = {"coordinator_epoch": 0}
    if include_proof_id:
        proof["proof_id"] = proof_id
    payload = {
        "expected_previous_policy_epoch": 0,
        "policy_epoch": 1,
        "policy_proof": proof,
    }
    event = DispatchEvent(
        id="policy-transition",
        sequence=1,
        kind=kind,
        coordinator_epoch=0,
        effective_world_tick=0,
        payload=payload,
        payload_hash=canonical_json_hash(payload),
    )

    result = preflight(
        event,
        last_sequence=0,
        coordinator_epoch=0,
        policy_epoch=0,
        task_fences={},
        resource_fences={},
        current_tick=0,
    )

    assert result["status"] == ("ACCEPTED" if accepted else "REJECTED")
    assert result["reason_codes"] == ([] if accepted else ["UNTRUSTED_POLICY_PROOF"])
