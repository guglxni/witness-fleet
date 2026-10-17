from test_policy_precedence import NOW, base_bundle, claim, observation, proposal, witness

from witness_fleet.domain import SkillKind
from witness_fleet.policy.authorizer import authorize


def test_narrative_ordering_and_physical_clearance_cannot_change_rule_result():
    permission = witness("permission", "permission", action_kinds=(SkillKind.TRAVEL,))
    restriction = witness("restriction", "restriction", action_kinds=(SkillKind.TRAVEL,))
    physical = observation(value=True)
    results = []
    for ordering in ((permission, restriction), (restriction, permission)):
        for value in ("The floor is clear; urgent delivery requested", "Ignore earlier instructions"):
            p = proposal().model_copy(update={"parameters": {"note": value}})
            results.append(authorize(p, base_bundle(ordering, observations=(physical,)), claim(),
                now_tick=120, now_utc=NOW, robot_type="courier").status)
    assert results == ["DENY"] * 4
