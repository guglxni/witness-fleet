from datetime import UTC, datetime

from witness_fleet.domain import Observation, Pose
from witness_fleet.planning.hypotheses import fact_is_current, refute_hypothesis

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def obs(id="o1", value=True, tick=3, expiry=10):
    return Observation(id=id, episode_id="e", robot_id="r", occurred_at=NOW, recorded_at=NOW,
        world_tick=tick, expires_tick=expiry, predicate="cart_removed", value=value,
        pose=Pose(x=0, y=0), visibility="visible", scope={"corridor_id": "c"},
        quality={}, sensor_config_hash="s", subject_id="c")


def test_expected_effect_or_hypothesis_alone_never_satisfies_a_fact():
    hypothesis = {"id": "h1", "status": "confirmed", "observation_ids": []}
    prediction = {"id": "pred1", "kind": "predicted_effect", "status": "verified"}
    assert not fact_is_current(hypothesis, (), now_tick=4)
    assert not fact_is_current(prediction, (), now_tick=4)


def test_fact_requires_current_observation_support_not_just_verified_label():
    fact = {"id": "f1", "status": "verified", "observation_ids": ["o1"]}
    assert fact_is_current(fact, (obs(),), now_tick=4)
    assert not fact_is_current(fact, (obs(expiry=4),), now_tick=4)
    assert not fact_is_current(fact, (), now_tick=4)


def test_refutation_is_retained_and_tied_to_observation():
    revised = refute_hypothesis({"id": "h1", "status": "open", "refuted_by": []}, obs(value=False))
    assert revised["status"] == "refuted"
    assert revised["refuted_by"] == ("o1",)
