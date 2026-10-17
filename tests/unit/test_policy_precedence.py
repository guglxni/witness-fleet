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
VERSIONS = VersionVector(graph_version=7, policy_epoch=4, coordinator_epoch=2,
                         task_version=3, dependency_versions={"dep": 9})


def proposal(kind=SkillKind.TRAVEL, predicates=("clearance",)):
    return ActionProposal(id="p", robot_id="robot-1", task_id="task-1", kind=kind,
        parameters={"payload_class": "loaded", "footprint": "wide"}, expected_versions=VERSIONS,
        required_predicates=predicates, required_resource_ids=("door-1",), expected_effects=(),
        corridor_id="corridor-c")


def witness(id, kind, *, state="active", action_kinds=(SkillKind.TRAVEL,),
            robot_types=("courier",), corridor="corridor-c", restriction_id=None,
            source_valid=True, owner_valid=True, approved=True, errors=(), start=0, end=None):
    return GovernanceWitness(id=id, kind=kind, decision_id=f"decision-{id}", owner_id="owner-1",
        span_id=f"span-{id}", corridor_id=corridor, action_kinds=action_kinds,
        robot_types=robot_types, state=state, effective_from_tick=start, effective_to_tick=end,
        restriction_id=restriction_id, source_valid=source_valid, owner_valid=owner_valid,
        approved=approved, integrity_errors=errors)


def observation(*, value=True, tick=100, expiry=200, recorded=NOW, scope=None, predicate="clearance"):
    return Observation(id=f"obs-{tick}-{value}", episode_id="episode-1", robot_id="robot-1",
        occurred_at=NOW, recorded_at=recorded, world_tick=tick, expires_tick=expiry,
        predicate=predicate, value=value, pose=Pose(x=0, y=0), visibility="visible",
        scope=scope or {"corridor_id": "corridor-c", "robot_type": "courier", "footprint": "wide", "payload_class": "loaded"},
        quality={}, sensor_config_hash="sensor-v1", subject_id="corridor-c")


DEFAULT_OBSERVATION = observation()


def base_bundle(governance=(), observations=None, *, completeness="complete", errors=(),
                versions=VERSIONS):
    if observations is None:
        observations = (DEFAULT_OBSERVATION,)
    return EvidenceBundle(observations=observations, planning_facts=(),
        governance_candidates=tuple(governance), integrity_errors=tuple(errors),
        versions=versions, completeness=completeness)


def claim(*, expiry=NOW + timedelta(hours=1), state="active", epoch=2,
          resource_fences=None, robot="robot-1", task="task-1"):
    return Claim(id="claim-1", task_id=task, robot_id=robot, holder_id=robot,
        coordinator_epoch=epoch, fence=8, resource_fences=(
            {"door-1": 5} if resource_fences is None else resource_fences),
        lease_expires_at_utc=expiry, clock_domain="coordinator_epoch_utc_lease_v1", state=state)


def authorize_case(p=None, bundle=None, c=None, *, tick=120, utc=NOW):
    return authorize(p or proposal(), bundle or base_bundle([witness("permit", "permission")]),
                     c or claim(), now_tick=tick, now_utc=utc, robot_type="courier")


def test_active_restriction_dominates_permission_and_physical_clearance():
    restriction = witness("ban", "restriction", action_kinds=(SkillKind.TRAVEL,))
    result = authorize_case(bundle=base_bundle([witness("permit", "permission"), restriction]))
    assert result.status == "DENY"
    assert "ACTIVE_RESTRICTION" in result.reason_codes
    assert "ban" in result.witness_ids


def test_release_only_lifts_its_exact_restriction_and_requires_fresh_clearance():
    restriction = witness("ban", "restriction")
    release = witness("release-1", "release", state="released", restriction_id="ban")
    governance = [witness("permit", "permission"), restriction, release]
    assert authorize_case(bundle=base_bundle(governance)).status == "ALLOW"
    # Release never substitutes for the independent physical predicate.
    missing_physics = authorize_case(bundle=base_bundle(governance, observations=()))
    assert missing_physics.status == "NEEDS_EVIDENCE"


def test_staged_release_is_not_effective_authority():
    governance = [witness("permit", "permission"), witness("ban", "restriction"),
                  witness("staged-release", "release", state="staged", restriction_id="ban",
                          approved=False)]
    result = authorize_case(bundle=base_bundle(governance))
    assert result.status == "NEEDS_APPROVAL"
    assert "RELEASE_NOT_APPROVED" in result.reason_codes


def test_release_does_not_lift_another_overlapping_restriction():
    governance = [witness("permit", "permission"), witness("ban-1", "restriction"),
                  witness("ban-2", "restriction"),
                  witness("release-1", "release", state="released", restriction_id="ban-1")]
    result = authorize_case(bundle=base_bundle(governance))
    assert result.status == "DENY"
    assert "ban-2" in result.witness_ids


def test_permissions_and_restrictions_use_half_open_tick_intervals():
    permission = witness("permit", "permission", start=120, end=121)
    assert authorize_case(bundle=base_bundle([permission]), tick=120).status == "ALLOW"
    assert authorize_case(bundle=base_bundle([permission], observations=(observation(expiry=121),)), tick=120).status == "ALLOW"
    assert authorize_case(bundle=base_bundle([permission]), tick=121).status == "DENY"


def test_all_entry_role_marker_does_not_wildcard_the_action():
    broad_role_only = witness("permit", "permission", action_kinds=(SkillKind.TRAVEL,),
                              robot_types=("all_entry",))
    result = authorize_case(p=proposal(kind=SkillKind.INSPECT),
                            bundle=base_bundle([broad_role_only]))
    assert result.status == "DENY"
    assert "NO_BASE_PERMISSION" in result.reason_codes


@pytest.mark.parametrize("scope", [
    {"robot_types": ("all_entry",)}, {"robot_types": ("all",)},
    {"robot_types": ("*",)}, {"corridor": "*"}, {"corridor": "all"},
])
def test_permission_wildcard_scope_cannot_grant_positive_authority(scope):
    permission = witness("permit", "permission", **scope)
    result = authorize_case(bundle=base_bundle([permission]))
    assert result.status != "ALLOW"
    assert "INVALID_PERMISSION_SCOPE" in result.reason_codes


def test_blanket_restriction_still_denies_every_explicit_action_with_valid_base_permission():
    permission = witness("permit", "permission")
    restriction = witness("ban", "restriction", robot_types=("all_entry",))
    result = authorize_case(bundle=base_bundle([permission, restriction]))
    assert result.status == "DENY"
    assert "ACTIVE_RESTRICTION" in result.reason_codes


def test_claim_holder_must_match_the_trusted_proposal_robot():
    mismatched = claim().model_copy(update={'holder_id': 'other-robot'})
    result = authorize_case(c=mismatched)
    assert result.status == 'STALE'
    assert 'CLAIM_STALE_OR_MISMATCHED' in result.reason_codes


def test_claim_and_full_version_vector_are_bound_exactly():
    assert authorize_case(c=claim(expiry=NOW)).status == "STALE"
    mismatch = VersionVector(graph_version=7, policy_epoch=4, coordinator_epoch=2,
                             task_version=3, dependency_versions={"dep": 8})
    assert authorize_case(bundle=base_bundle([witness("permit", "permission")], versions=mismatch)).status == "STALE"
    assert authorize_case(c=claim(resource_fences={})).status == "STALE"


def test_invalid_or_orphaned_governance_fails_closed_even_when_out_of_scope():
    orphan = witness("orphan", "restriction", corridor="another-corridor", source_valid=False,
                     errors=("missing_support_edge",))
    result = authorize_case(bundle=base_bundle([witness("permit", "permission"), orphan]))
    assert result.status != "ALLOW"
    assert "GOVERNANCE_INTEGRITY" in result.reason_codes
    assert "orphan" in result.witness_ids


def test_future_recorded_evidence_cannot_authorize():
    future = observation(recorded=NOW + timedelta(seconds=1))
    result = authorize_case(bundle=base_bundle([witness("permit", "permission")],
                                               observations=(future,)))
    assert result.status == "NEEDS_EVIDENCE"
