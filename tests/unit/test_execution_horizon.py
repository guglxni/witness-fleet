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
NOW_TICK = 20
VERSIONS = VersionVector(graph_version=7, policy_epoch=4, coordinator_epoch=2)


def proposal(*, predicates=("clear",), parameters=None):
    if parameters is None:
        parameters = {"footprint": "wide", "payload_class": "loaded"}
    return ActionProposal(
        id="proposal",
        robot_id="robot-1",
        task_id="task-1",
        kind=SkillKind.TRAVEL,
        parameters=parameters,
        expected_versions=VERSIONS,
        required_predicates=predicates,
        required_resource_ids=("door-1",),
        expected_effects=(),
        corridor_id="corridor-c",
    )


def witness(
    witness_id,
    kind,
    *,
    state="active",
    start=0,
    end=None,
    corridor="corridor-c",
    action_kinds=(SkillKind.TRAVEL,),
    robot_types=("courier",),
    restriction_id=None,
    approved=True,
    source_valid=True,
    owner_valid=True,
):
    return GovernanceWitness(
        id=witness_id,
        kind=kind,
        decision_id=f"decision-{witness_id}",
        owner_id="owner",
        span_id=f"span-{witness_id}",
        corridor_id=corridor,
        action_kinds=action_kinds,
        robot_types=robot_types,
        state=state,
        effective_from_tick=start,
        effective_to_tick=end,
        restriction_id=restriction_id,
        source_valid=source_valid,
        owner_valid=owner_valid,
        approved=approved,
        integrity_errors=(),
    )


def observation(*, tick=10, expiry=80, recorded=NOW, occurred=NOW):
    return Observation(
        id=f"clear-{tick}-{expiry}",
        episode_id="episode-1",
        robot_id="robot-1",
        occurred_at=occurred,
        recorded_at=recorded,
        world_tick=tick,
        expires_tick=expiry,
        predicate="clear",
        value=True,
        pose=Pose(x=0, y=0),
        visibility="visible",
        scope={
            "corridor_id": "corridor-c",
            "robot_type": "courier",
            "footprint": "wide",
            "payload_class": "loaded",
        },
        quality={},
        sensor_config_hash="sensor-v1",
        subject_id="corridor-c",
    )


def authorize_case(*, action=None, observations=None, policies=None, now_tick=NOW_TICK):
    evidence = EvidenceBundle(
        observations=tuple((observation(),) if observations is None else observations),
        planning_facts=(),
        governance_candidates=tuple(
            (witness("permit", "permission"),) if policies is None else policies
        ),
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
        action or proposal(), evidence, claim,
        now_tick=now_tick, now_utc=NOW, robot_type="courier",
    )


def with_window(deadline=1520, *, timeout_ticks=None):
    parameters = {"footprint": "wide", "payload_class": "loaded",
                  "execution_until_tick": deadline}
    if timeout_ticks is not None:
        parameters["timeout_ticks"] = timeout_ticks
    return proposal(parameters=parameters)


def test_explicit_null_execution_deadline_is_denied():
    result = authorize_case(action=with_window(None))

    assert result.status == "DENY"
    assert "INVALID_EXECUTION_WINDOW" in result.reason_codes


@pytest.mark.parametrize("deadline", [True, "1520", 20, 2021])
def test_invalid_execution_deadline_is_denied(deadline):
    result = authorize_case(action=with_window(deadline))

    assert result.status == "DENY"
    assert "INVALID_EXECUTION_WINDOW" in result.reason_codes


@pytest.mark.parametrize("timeout", [True, "1500", 0, -1])
def test_invalid_timeout_with_execution_deadline_is_denied(timeout):
    result = authorize_case(action=with_window(40, timeout_ticks=timeout))

    assert result.status == "DENY"
    assert "INVALID_EXECUTION_WINDOW" in result.reason_codes


def test_explicit_window_respects_positive_timeout_and_exact_upper_boundary():
    result = authorize_case(action=with_window(70, timeout_ticks=50))

    assert result.status == "ALLOW"


def test_explicit_window_defaults_timeout_and_caps_it_at_2000_ticks():
    at_cap = authorize_case(action=with_window(2020, timeout_ticks=9999))
    beyond_default_cap = authorize_case(action=with_window(2021))

    assert at_cap.status == "ALLOW"
    assert beyond_default_cap.status == "DENY"
    assert "INVALID_EXECUTION_WINDOW" in beyond_default_cap.reason_codes


def test_execution_window_does_not_extend_fresh_observation_admission():
    result = authorize_case(action=with_window(1520), observations=(observation(expiry=50),))

    assert result.status == "ALLOW"
    assert result.valid_until_tick == 50


def test_legacy_proposal_without_execution_deadline_keeps_existing_horizon():
    result = authorize_case(action=proposal(predicates=()), observations=())

    assert result.status == "ALLOW"
    assert result.valid_until_tick == NOW_TICK + 2000


def test_execution_window_requires_current_exact_permission_covering_deadline():
    exact_end = authorize_case(action=with_window(1520), policies=(witness("permit", "permission", end=1520),))
    short_end = authorize_case(action=with_window(1520), policies=(witness("permit", "permission", end=1519),))
    starts_later = authorize_case(action=with_window(1520), policies=(witness("permit", "permission", start=21),))

    assert exact_end.status == "ALLOW"
    assert short_end.status == "DENY"
    assert starts_later.status == "DENY"


def test_execution_window_requires_release_to_cover_full_interval():
    restriction = witness("ban", "restriction")
    release_exact = witness("release", "release", state="released", restriction_id="ban", end=1520)
    release_short = witness("release", "release", state="released", restriction_id="ban", end=1519)
    exact = authorize_case(action=with_window(1520), policies=(
        witness("permit", "permission"), restriction, release_exact,
    ))
    short = authorize_case(action=with_window(1520), policies=(
        witness("permit", "permission"), restriction, release_short,
    ))

    assert exact.status == "ALLOW"
    assert short.status == "DENY"


def test_execution_window_blocks_future_active_and_staged_restrictions():
    future_active = authorize_case(action=with_window(1520), policies=(
        witness("permit", "permission"), witness("future-ban", "restriction", start=21),
    ))
    future_staged = authorize_case(action=with_window(1520), policies=(
        witness("permit", "permission"),
        witness("pending-ban", "restriction", state="staged", start=21),
    ))
    wrong_scope = authorize_case(action=with_window(1520), policies=(
        witness("permit", "permission"),
        witness("other-ban", "restriction", start=21, corridor="other-corridor"),
    ))

    assert future_active.status == "DENY"
    assert future_staged.status == "NEEDS_APPROVAL"
    assert wrong_scope.status == "ALLOW"


def test_stale_or_future_observations_cannot_authorize_execution_window():
    stale = authorize_case(action=with_window(1520), observations=(observation(expiry=20),))
    future = authorize_case(action=with_window(1520), observations=(
        observation(tick=21, recorded=NOW + timedelta(seconds=1), occurred=NOW + timedelta(seconds=1)),
    ))

    assert stale.status != "ALLOW"
    assert future.status != "ALLOW"
