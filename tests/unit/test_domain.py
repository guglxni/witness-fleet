from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from witness_fleet.domain import Pose, StrictModel


def test_strict_model_rejects_unknown_fields():
    class Sample(StrictModel):
        value: int

    with pytest.raises(ValidationError):
        Sample(value=1, unexpected=True)


def test_pose_rejects_non_finite_coordinates():
    with pytest.raises(ValidationError):
        Pose(x=float("nan"), y=0)


def test_pose_is_frozen():
    pose = Pose(x=1, y=2)
    with pytest.raises(ValidationError):
        pose.x = 3


def test_pose_round_trips_json():
    pose = Pose(x=1.25, y=-3)
    assert Pose.model_validate_json(pose.model_dump_json()) == pose


def test_utc_to_ticks_uses_exact_microseconds():
    from witness_fleet.domain import utc_to_ticks

    epoch = datetime(2026, 1, 1, tzinfo=UTC)
    assert utc_to_ticks(epoch + timedelta(microseconds=2500), epoch, 1000) == 3


@pytest.mark.parametrize(("offset_us", "expected"), [(1, 1), (1000, 1), (1001, 2), (-1, 0), (-1000, -1), (-1001, -1)])
def test_utc_to_ticks_uses_ceiling_for_positive_and_negative_offsets(offset_us, expected):
    from witness_fleet.domain import utc_to_ticks

    epoch = datetime(2026, 1, 1, tzinfo=UTC)
    assert utc_to_ticks(epoch + timedelta(microseconds=offset_us), epoch, 1000) == expected


def test_utc_to_ticks_rejects_naive_datetime():
    from witness_fleet.domain import utc_to_ticks

    with pytest.raises(ValueError):
        utc_to_ticks(datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=UTC), 1000)


def test_utc_to_ticks_rejects_non_utc_datetime():
    from witness_fleet.domain import utc_to_ticks

    with pytest.raises(ValueError):
        utc_to_ticks(datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2))),
                     datetime(2026, 1, 1, tzinfo=UTC), 1000)


def test_utc_to_ticks_rejects_nonpositive_frequency():
    from witness_fleet.domain import utc_to_ticks

    epoch = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError):
        utc_to_ticks(epoch, epoch, 0)


def test_version_vector_rejects_negative_values():
    from witness_fleet.domain import VersionVector

    with pytest.raises(ValidationError):
        VersionVector(graph_version=-1, policy_epoch=0, coordinator_epoch=0)


def test_version_vector_round_trips_and_defaults_are_independent():
    from witness_fleet.domain import VersionVector

    left = VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3)
    right = VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3)
    with pytest.raises(TypeError):
        left.dependency_versions["graph"] = 4
    assert right.dependency_versions == {}
    assert VersionVector.model_validate_json(right.model_dump_json()) == right


def test_observation_requires_expiry_after_world_tick():
    from witness_fleet.domain import Observation

    instant = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Observation(id="o1", episode_id="e1", robot_id="r1", occurred_at=instant,
                    recorded_at=instant, world_tick=4, expires_tick=4, predicate="safe",
                    value=True, pose=Pose(x=0, y=0), sensor_config_hash="sha")


def test_observation_requires_utc_timestamps():
    from witness_fleet.domain import Observation

    instant = datetime(2026, 1, 1)
    with pytest.raises(ValidationError):
        Observation(id="o1", episode_id="e1", robot_id="r1", occurred_at=instant,
                    recorded_at=instant, world_tick=0, expires_tick=1, predicate="safe",
                    value=True, pose=Pose(x=0, y=0), sensor_config_hash="sha")


def test_observation_rejects_non_finite_value():
    from witness_fleet.domain import Observation

    instant = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Observation(id="o1", episode_id="e1", robot_id="r1", occurred_at=instant,
                    recorded_at=instant, world_tick=0, expires_tick=1, predicate="range",
                    value=float("inf"), pose=Pose(x=0, y=0), sensor_config_hash="sha")


def test_observation_rejects_negative_ticks():
    from witness_fleet.domain import Observation

    instant = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Observation(id="o1", episode_id="e1", robot_id="r1", occurred_at=instant,
                    recorded_at=instant, world_tick=-1, expires_tick=2, predicate="safe",
                    value=True, pose=Pose(x=0, y=0), sensor_config_hash="sha")


def test_skill_kind_values_are_wire_stable():
    from witness_fleet.domain import SkillKind

    assert [item.value for item in SkillKind] == ["inspect", "travel", "recover", "verify",
                                                  "deliver", "hold", "wait"]


def test_action_payload_hash_is_canonical_and_binds_all_fields():
    from witness_fleet.domain import ActionProposal, SkillKind, VersionVector, payload_hash

    versions = VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3)
    proposal = ActionProposal(id="a", robot_id="r", task_id="t", kind=SkillKind.TRAVEL,
                              parameters={"distance": 2}, expected_versions=versions,
                              required_predicates=("clear",), required_resource_ids=("c1",),
                              expected_effects=("arrived",))
    same = ActionProposal.model_validate_json(proposal.model_dump_json())
    changed = proposal.model_copy(update={"task_id": "other"})
    assert payload_hash(proposal) == payload_hash(same)
    assert payload_hash(proposal) != payload_hash(changed)


def test_action_proposal_rejects_non_json_parameters():
    from witness_fleet.domain import ActionProposal, SkillKind, VersionVector

    versions = VersionVector(graph_version=0, policy_epoch=0, coordinator_epoch=0)
    with pytest.raises(ValidationError):
        ActionProposal(id="a", robot_id="r", task_id="t", kind=SkillKind.HOLD,
                      parameters={"bad": object()}, expected_versions=versions,
                      required_predicates=(), required_resource_ids=(), expected_effects=())


def test_governance_witness_rejects_empty_half_open_interval():
    from witness_fleet.domain import GovernanceWitness

    with pytest.raises(ValidationError):
        GovernanceWitness(id="g", kind="restriction", decision_id="d", owner_id="o",
                          span_id="s", corridor_id="c", action_kinds=(), robot_types=(),
                          state="active", effective_from_tick=5, effective_to_tick=5,
                          source_valid=True, owner_valid=True, approved=True, integrity_errors=())


def test_claim_rejects_negative_fences_and_wrong_clock_domain():
    from witness_fleet.domain import Claim

    with pytest.raises(ValidationError):
        Claim(id="cl", task_id="t", robot_id="r", holder_id="h", coordinator_epoch=0,
              fence=-1, resource_fences={}, lease_expires_at_utc=datetime.now(UTC),
              clock_domain="other", state="active")


def test_canonical_json_hash_sorts_keys_and_rejects_nan():
    from witness_fleet.domain import canonical_json_hash

    assert canonical_json_hash({"b": 2, "a": 1}) == canonical_json_hash({"a": 1, "b": 2})
    with pytest.raises((ValueError, ValidationError)):
        canonical_json_hash({"bad": float("nan")})


def test_authorization_result_rejects_negative_tick():
    from witness_fleet.domain import AuthorizationResult, VersionVector

    with pytest.raises(ValidationError):
        AuthorizationResult(authorization_id="auth", status="ALLOW", reason_codes=(),
                            witness_ids=(), versions=VersionVector(graph_version=0, policy_epoch=0,
                            coordinator_epoch=0), action_payload_hash="hash", valid_until_tick=-1,
                            claim_id="c", task_id="t", robot_id="r", resource_fences={},
                            governance_integrity_version=0)


def test_command_intent_rejects_mismatched_proposal_hash():
    from witness_fleet.domain import (
        ActionProposal,
        AuthorizationResult,
        CommandIntent,
        SkillKind,
        VersionVector,
        payload_hash,
    )

    versions = VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3)
    proposal = ActionProposal(id="a", robot_id="r", task_id="t", kind=SkillKind.HOLD,
                              parameters={}, expected_versions=versions, required_predicates=(),
                              required_resource_ids=(), expected_effects=())
    auth = AuthorizationResult(authorization_id="x", status="ALLOW", reason_codes=(),
        witness_ids=(), versions=versions, action_payload_hash=payload_hash(proposal),
        valid_until_tick=10, claim_id="c", task_id="t", robot_id="r", fence=1,
        resource_fences={}, governance_integrity_version=1)
    with pytest.raises(ValidationError):
        CommandIntent(command_id="cmd", proposal=proposal, payload_hash="wrong", claim_id="c",
            fence=1, resource_fences={}, authorization_id="x", policy_epoch=2,
            coordinator_epoch=3, dispatch_sequence=1, effective_world_tick=0, authorization=auth)


def test_dispatch_event_rejects_payload_hash_mismatch():
    from witness_fleet.domain import DispatchEvent

    with pytest.raises(ValidationError):
        DispatchEvent(id="e", sequence=1, coordinator_epoch=0, kind="COMMAND", payload={"a": 1},
                      payload_hash="wrong", effective_world_tick=0)


def test_command_receipt_rejects_negative_tick():
    from witness_fleet.domain import CommandReceipt

    with pytest.raises(ValidationError):
        CommandReceipt(command_id="cmd", payload_hash="h", state="ACCEPTED", world_tick=-1,
                       accepted_sequence=0, reason_codes=(), observations=())


def test_decision_result_rejects_negative_latency():
    from witness_fleet.domain import DecisionResult

    with pytest.raises(ValidationError):
        DecisionResult(request_id="req", status="ok", probabilities={}, provider="p", model="m",
                       usage={}, latency_ms=-1)


def test_fleet_event_requires_utc_recorded_time():
    from witness_fleet.domain import FleetEvent

    with pytest.raises(ValidationError):
        FleetEvent(id="f", type="status", episode_id="e", world_tick=0, sequence=0,
                   payload={}, recorded_at=datetime(2026, 1, 1))


def test_fleet_event_rejects_negative_sequence():
    from witness_fleet.domain import FleetEvent

    with pytest.raises(ValidationError):
        FleetEvent(id="f", type="status", episode_id="e", world_tick=0, sequence=-1,
                   payload={}, recorded_at=datetime(2026, 1, 1, tzinfo=UTC))


def test_command_intent_requires_authorized_proposal_versions():
    from witness_fleet.domain import (
        ActionProposal,
        AuthorizationResult,
        CommandIntent,
        SkillKind,
        VersionVector,
        payload_hash,
    )

    expected = VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3)
    stale_auth_versions = VersionVector(graph_version=9, policy_epoch=2, coordinator_epoch=3)
    proposal = ActionProposal(id="a", robot_id="r", task_id="t", kind=SkillKind.HOLD,
        parameters={}, expected_versions=expected, required_predicates=(),
        required_resource_ids=(), expected_effects=())
    auth = AuthorizationResult(authorization_id="x", status="ALLOW", reason_codes=(),
        witness_ids=(), versions=stale_auth_versions, action_payload_hash=payload_hash(proposal),
        valid_until_tick=10, claim_id="c", task_id="t", robot_id="r", fence=1,
        resource_fences={}, governance_integrity_version=1)
    with pytest.raises(ValidationError):
        CommandIntent(command_id="cmd", proposal=proposal, payload_hash=payload_hash(proposal),
            claim_id="c", fence=1, resource_fences={}, authorization_id="x", policy_epoch=9,
            coordinator_epoch=3, dispatch_sequence=1, effective_world_tick=0, authorization=auth)


def test_nested_non_finite_decision_values_are_rejected():
    from witness_fleet.domain import DecisionResult

    with pytest.raises(ValidationError):
        DecisionResult(request_id="req", status="ok", probabilities={"yes": 0.5}, provider="p",
            model="m", usage={"raw": float("nan")}, latency_ms=0)


def test_observation_requires_a_pose():
    from witness_fleet.domain import Observation

    instant = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Observation(id="o1", episode_id="e1", robot_id="r1", occurred_at=instant,
                    recorded_at=instant, world_tick=0, expires_tick=1, predicate="safe",
                    value=True, sensor_config_hash="sha")


def test_decision_request_claim_is_atomic_text_not_claim_dto():
    from witness_fleet.domain import DecisionRequest, VersionVector

    versions = VersionVector(graph_version=0, policy_epoch=0, coordinator_epoch=0)
    request = DecisionRequest(id="d", family_id="f", claim="door is clear", span={},
                              labels=(), source_ids=(), versions=versions)
    assert request.claim == "door is clear"
    with pytest.raises(ValidationError):
        DecisionRequest(id="d", family_id="f", claim={"id": "claim"}, span={}, labels=(),
                        source_ids=(), versions=versions)


def test_frozen_domain_json_is_deeply_immutable_and_detached_from_inputs():
    from witness_fleet.domain import ActionProposal, SkillKind, VersionVector, payload_hash

    deps = {"graph": 4}
    versions = VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3,
                              dependency_versions=deps)
    nested = {"route": [{"points": [1, 2]}]}
    proposal = ActionProposal(id="a", robot_id="r", task_id="t", kind=SkillKind.TRAVEL,
                              parameters=nested, expected_versions=versions,
                              required_predicates=(), required_resource_ids=(), expected_effects=())
    original_hash = payload_hash(proposal)
    deps["graph"] = 99
    nested["route"][0]["points"].append(3)
    assert versions.dependency_versions["graph"] == 4
    assert payload_hash(proposal) == original_hash
    restored = ActionProposal.model_validate_json(proposal.model_dump_json())
    assert restored == proposal
    assert proposal.model_dump(mode="json")["parameters"] == {"route": [{"points": [1, 2]}]}
    assert payload_hash(restored) == original_hash
    with pytest.raises((TypeError, AttributeError)):
        proposal.parameters["route"][0]["points"].append(4)
    with pytest.raises((TypeError, AttributeError)):
        versions.dependency_versions["graph"] = 5


def test_domain_mappings_resist_dict_mutation_descriptors():
    from witness_fleet.domain import ActionProposal, SkillKind, VersionVector

    proposal = ActionProposal(
        id="a", robot_id="r", task_id="t", kind=SkillKind.TRAVEL,
        parameters={"route": {"points": [1, 2]}},
        expected_versions=VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3,
                                        dependency_versions={"graph": 4}),
        required_predicates=(), required_resource_ids=(), expected_effects=(),
    )

    with pytest.raises(TypeError):
        dict.__setitem__(proposal.parameters, "route", {})
    with pytest.raises(TypeError):
        dict.update(proposal.parameters, route={})
    with pytest.raises(TypeError):
        dict.__setitem__(proposal.parameters["route"], "points", ())
    with pytest.raises(TypeError):
        dict.__setitem__(proposal.expected_versions.dependency_versions, "graph", 99)


@pytest.mark.parametrize("model_name", ["proposal", "request", "dispatch", "fleet"])
def test_domain_json_mappings_round_trip_as_plain_json(model_name):
    from witness_fleet.domain import (
        ActionProposal,
        DecisionRequest,
        DispatchEvent,
        FleetEvent,
        SkillKind,
        VersionVector,
        canonical_json_hash,
    )

    versions = VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3,
                             dependency_versions={"g": 4})
    payload = {"nested": [{"v": 1}]}
    models = {
        "proposal": ActionProposal(
            id="a", robot_id="r", task_id="t", kind=SkillKind.TRAVEL, parameters=payload,
            expected_versions=versions, required_predicates=(), required_resource_ids=(),
            expected_effects=()),
        "request": DecisionRequest(id="d", family_id="f", claim="claim", span=payload,
                                   labels=(), source_ids=(), versions=versions),
        "dispatch": DispatchEvent(id="e", sequence=1, coordinator_epoch=0, kind="COMMAND",
                                  payload=payload, payload_hash=canonical_json_hash(payload),
                                  effective_world_tick=0),
        "fleet": FleetEvent(id="f", type="status", episode_id="e", world_tick=0, sequence=0,
                            payload=payload, recorded_at=datetime(2026, 1, 1, tzinfo=UTC)),
    }
    model = models[model_name]
    restored = type(model).model_validate_json(model.model_dump_json())
    assert restored == model
    assert restored.model_dump(mode="json") == model.model_dump(mode="json")
    assert isinstance(model.model_dump(mode="json"), dict)


def test_canonical_json_hash_accepts_read_only_mappings():
    from types import MappingProxyType

    from witness_fleet.domain import canonical_json_hash

    assert canonical_json_hash(MappingProxyType({"a": (1, 2)})) == canonical_json_hash(
        {"a": [1, 2]})


def test_command_intent_rejects_auth_not_allow_and_expired_tick():
    from witness_fleet.domain import (
        ActionProposal,
        AuthorizationResult,
        CommandIntent,
        SkillKind,
        VersionVector,
        payload_hash,
    )

    versions = VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3)
    proposal = ActionProposal(id="a", robot_id="r", task_id="t", kind=SkillKind.HOLD,
                              parameters={}, expected_versions=versions, required_predicates=(),
                              required_resource_ids=(), expected_effects=())
    digest = payload_hash(proposal)
    auth_fields = dict(authorization_id="x", reason_codes=(), witness_ids=(), versions=versions,
                       action_payload_hash=digest, valid_until_tick=10, claim_id="c", task_id="t",
                       robot_id="r", fence=1, resource_fences={}, governance_integrity_version=1)
    intent_fields = dict(command_id="cmd", proposal=proposal, payload_hash=digest, claim_id="c",
                         fence=1, resource_fences={}, authorization_id="x", policy_epoch=2,
                         coordinator_epoch=3, dispatch_sequence=1)
    for status, tick in (("DENY", 0), ("ALLOW", 10)):
        auth = AuthorizationResult(status=status, **auth_fields)
        with pytest.raises(ValidationError):
            CommandIntent(**intent_fields, effective_world_tick=tick, authorization=auth)


def test_command_intent_binds_task_fence_and_rejects_boolean_or_zero_sequence():
    from witness_fleet.domain import (
        ActionProposal,
        AuthorizationResult,
        CommandIntent,
        SkillKind,
        VersionVector,
        payload_hash,
    )

    versions = VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3)
    proposal = ActionProposal(id="a", robot_id="r", task_id="t", kind=SkillKind.HOLD,
                              parameters={}, expected_versions=versions, required_predicates=(),
                              required_resource_ids=(), expected_effects=())
    digest = payload_hash(proposal)
    auth = AuthorizationResult(authorization_id="x", status="ALLOW", reason_codes=(),
        witness_ids=(), versions=versions, action_payload_hash=digest, valid_until_tick=10,
        claim_id="c", task_id="t", robot_id="r", fence=2, resource_fences={},
        governance_integrity_version=1)
    intent_fields = dict(command_id="cmd", proposal=proposal, payload_hash=digest, claim_id="c",
        fence=1, resource_fences={}, authorization_id="x", policy_epoch=2, coordinator_epoch=3,
        dispatch_sequence=1, effective_world_tick=0, authorization=auth)
    with pytest.raises(ValidationError):
        CommandIntent(**intent_fields)
    for sequence in (-1, 0, True):
        with pytest.raises(ValidationError):
            CommandIntent(**{**intent_fields, "fence": 2, "dispatch_sequence": sequence})
    with pytest.raises(ValidationError):
        CommandIntent(**{**intent_fields, "command_id": "", "fence": 2})


def test_command_intent_requires_exact_claim_task_robot_and_resource_fences():
    from witness_fleet.domain import (
        ActionProposal,
        AuthorizationResult,
        CommandIntent,
        SkillKind,
        VersionVector,
        payload_hash,
    )

    versions = VersionVector(graph_version=1, policy_epoch=2, coordinator_epoch=3)
    proposal = ActionProposal(id="a", robot_id="r", task_id="t", kind=SkillKind.HOLD,
                              parameters={}, expected_versions=versions, required_predicates=(),
                              required_resource_ids=(), expected_effects=())
    digest = payload_hash(proposal)
    intent_fields = dict(command_id="cmd", proposal=proposal, payload_hash=digest, claim_id="c",
        fence=1, resource_fences={"door": 4}, authorization_id="x", policy_epoch=2,
        coordinator_epoch=3, dispatch_sequence=1, effective_world_tick=0)
    auth_fields = dict(authorization_id="x", status="ALLOW", reason_codes=(), witness_ids=(),
        versions=versions, action_payload_hash=digest, valid_until_tick=10, claim_id="c",
        task_id="t", robot_id="r", fence=1, resource_fences={"door": 4},
        governance_integrity_version=1)
    valid_auth = AuthorizationResult(**auth_fields)
    assert CommandIntent(**intent_fields, authorization=valid_auth).authorization == valid_auth
    with pytest.raises(ValidationError):
        AuthorizationResult(**{**auth_fields, "resource_fences": {"": 4}})
    for mismatch in ({"claim_id": "other"}, {"task_id": "other"}, {"robot_id": "other"},
                     {"resource_fences": {"door": 5}}):
        auth = AuthorizationResult(**{**auth_fields, **mismatch})
        with pytest.raises(ValidationError):
            CommandIntent(**intent_fields, authorization=auth)


@pytest.mark.parametrize("model_input", [
    {"id": "", "sequence": 1, "coordinator_epoch": 0, "kind": "COMMAND", "payload": {},
     "payload_hash": "", "effective_world_tick": 0},
    {"id": "e", "sequence": 0, "coordinator_epoch": 0, "kind": "COMMAND", "payload": {},
     "payload_hash": "", "effective_world_tick": 0},
    {"id": "e", "sequence": True, "coordinator_epoch": 0, "kind": "COMMAND", "payload": {},
     "payload_hash": "", "effective_world_tick": 0},
])
def test_dispatch_event_requires_nonempty_id_and_positive_sequence(model_input):
    from witness_fleet.domain import DispatchEvent, canonical_json_hash

    model_input["payload_hash"] = canonical_json_hash({})
    with pytest.raises(ValidationError):
        DispatchEvent(**model_input)


def test_identifier_fields_and_identifier_lists_reject_empty_values():
    from witness_fleet.domain import ActionProposal, SkillKind, VersionVector

    common = dict(robot_id="r", task_id="t", kind=SkillKind.HOLD, parameters={},
                  expected_versions=VersionVector(graph_version=0, policy_epoch=0,
                  coordinator_epoch=0), required_predicates=(), required_resource_ids=(),
                  expected_effects=())
    with pytest.raises(ValidationError):
        ActionProposal(id="", **common)
    with pytest.raises(ValidationError):
        ActionProposal(id="a", **{**common, "required_resource_ids": ("",)})
