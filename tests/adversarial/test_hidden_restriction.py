from test_policy_precedence import NOW, base_bundle, claim, observation, proposal, witness

from witness_fleet.domain import SkillKind
from witness_fleet.policy.authorizer import authorize


def test_relevant_restriction_after_many_candidates_is_still_evaluated():
    candidates = [witness(f"permission-{index}", "permission", action_kinds=(SkillKind.TRAVEL,))
                  for index in range(30)]
    candidates.append(witness("late-hidden-ban", "restriction", action_kinds=(SkillKind.TRAVEL,)))
    bundle = base_bundle(candidates, observations=(observation(),))
    result = authorize(proposal(), bundle, claim(), now_tick=120, now_utc=NOW, robot_type="courier")
    assert result.status == "DENY"
    assert "late-hidden-ban" in result.witness_ids
