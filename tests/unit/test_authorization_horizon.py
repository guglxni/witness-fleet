from datetime import UTC, datetime, timedelta

import pytest

from witness_fleet.domain import (
    ActionProposal,
    Claim,
    EvidenceBundle,
    GovernanceWitness,
    Observation,
    Pose,
    SkillKind,
    VersionVector,
)
from witness_fleet.policy.authorizer import authorize

NOW = datetime(2026, 1, 1, tzinfo=UTC)
VERSIONS = VersionVector(graph_version=7, policy_epoch=4, coordinator_epoch=2)


def proposal(*, predicates=("clear",), parameters=None):
    return ActionProposal(
        id="proposal",
        robot_id="robot-1",
        task_id="task-1",
        kind=SkillKind.TRAVEL,
        parameters=parameters or {"footprint": "wide", "payload_class": "loaded"},
        expected_versions=VERSIONS,
        required_predicates=predicates,
        required_resource_ids=("door-1",),
        expected_effects=(),
        corridor_id="corridor-c",
    )


def permission(*, end=None):
    return GovernanceWitness(
        id="permit",
        kind="permission",
        decision_id="decision-permit",
        owner_id="owner",
        span_id="span-permit",
        corridor_id="corridor-c",
        action_kinds=(SkillKind.TRAVEL,),
        robot_types=("courier",),
        state="active",
        effective_from_tick=0,
        effective_to_tick=end,
        source_valid=True,
        owner_valid=True,
        approved=True,
        integrity_errors=(),
    )


def observation(*, predicate="clear", tick=10, expiry=80, robot_id="robot-1", scope=None):
    return Observation(
        id=f"{predicate}-{tick}-{expiry}",
        episode_id="episode-1",
        robot_id=robot_id,
        occurred_at=NOW,
        recorded_at=NOW,
        world_tick=tick,
        expires_tick=expiry,
        predicate=predicate,
        value=True,
        pose=Pose(x=0, y=0),
        visibility="visible",
        scope=scope or {
            "corridor_id": "corridor-c",
            "robot_type": "courier",
            "footprint": "wide",
            "payload_class": "loaded",
        },
        quality={},
        sensor_config_hash="sensor-v1",
        subject_id="corridor-c",
    )


def authorize_case(*, action=None, observations=None, policies=None, now_tick=20):
    evidence = EvidenceBundle(
        observations=tuple(observations or ()),
        planning_facts=(),
        governance_candidates=tuple(policies or (permission(),)),
        integrity_errors=(),
        versions=VERSIONS,
        completeness="complete",
    )
    claim = Claim(
        id="claim-1",
        task_id="task-1",
        robot_id="robot-1",
        holder_id="robot-1",
        coordinator_epoch=2,
        fence=8,
        resource_fences={"door-1": 5},
        lease_expires_at_utc=NOW + timedelta(hours=1),
        clock_domain="coordinator_epoch_utc_lease_v1",
        state="active",
    )
    return authorize(
        action or proposal(), evidence, claim, now_tick=now_tick, now_utc=NOW, robot_type="courier"
    )


def test_allow_validity_uses_fresh_evidence_beyond_next_tick():
    result = authorize_case(observations=(observation(expiry=80),))

    assert result.status == "ALLOW"
    assert result.valid_until_tick == 80


def test_allow_validity_uses_earliest_expiry_of_required_observations():
    action = proposal(predicates=("clear", "occupied"))
    result = authorize_case(
        action=action,
        observations=(observation(predicate="clear", expiry=80),
                      observation(predicate="occupied", tick=12, expiry=45)),
    )

    assert result.status == "ALLOW"
    assert result.valid_until_tick == 45


def test_allow_validity_is_capped_by_active_matching_policy_expiry():
    result = authorize_case(observations=(observation(expiry=80),), policies=(permission(end=50),))

    assert result.status == "ALLOW"
    assert result.valid_until_tick == 50


def test_observation_expiry_boundary_is_exclusive():
    result = authorize_case(observations=(observation(expiry=80),), now_tick=80)

    assert result.status == "NEEDS_EVIDENCE"


def test_missing_required_observation_still_needs_evidence():
    result = authorize_case(observations=())

    assert result.status == "NEEDS_EVIDENCE"


def test_allow_without_required_observations_gets_a_bounded_horizon():
    result = authorize_case(action=proposal(predicates=()), observations=())

    assert result.status == "ALLOW"
    assert result.valid_until_tick == 2020


def test_wrong_typed_now_tick_is_rejected():
    evidence = EvidenceBundle(
        observations=(observation(),),
        planning_facts=(),
        governance_candidates=(permission(),),
        integrity_errors=(),
        versions=VERSIONS,
        completeness="complete",
    )
    claim = Claim(
        id="claim-1",
        task_id="task-1",
        robot_id="robot-1",
        holder_id="robot-1",
        coordinator_epoch=2,
        fence=8,
        resource_fences={"door-1": 5},
        lease_expires_at_utc=NOW + timedelta(hours=1),
        clock_domain="coordinator_epoch_utc_lease_v1",
        state="active",
    )

    with pytest.raises(TypeError):
        authorize(proposal(), evidence, claim, now_tick=True, now_utc=NOW, robot_type="courier")
