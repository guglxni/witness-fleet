from datetime import UTC, datetime, timedelta

from witness_fleet.domain import Observation, Pose
from witness_fleet.policy.observations import evaluate_observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def obs(id, tick, value, *, expiry=50, recorded=NOW, scope=None, predicate="clear"):
    return Observation(id=id, episode_id="e", robot_id="r1", occurred_at=NOW,
        recorded_at=recorded, world_tick=tick, expires_tick=expiry, predicate=predicate,
        value=value, pose=Pose(x=0, y=0), visibility="visible", scope=scope or
        {"corridor_id": "c", "robot_type": "courier", "footprint": "wide", "payload_class": "loaded"},
        quality={}, sensor_config_hash="s", subject_id="c")


def evaluate(observations, *, now_tick=10):
    return evaluate_observation(observations, "clear", subject_id="c", robot_id="r1",
        robot_type="courier", now_tick=now_tick, now_utc=NOW,
        expected_scope={"footprint": "wide", "payload_class": "loaded"})


def test_latest_world_tick_wins_not_ingestion_or_recorded_order():
    older = obs("old", 4, False, recorded=NOW + timedelta(seconds=1))
    newer = obs("new", 7, True, recorded=NOW)
    assert evaluate((older, newer)).status == "VERIFIED"


def test_conflicting_observations_at_same_event_tick_are_unknown():
    result = evaluate((obs("a", 8, True), obs("b", 8, False)))
    assert result.status == "UNKNOWN"
    assert "CONTRADICTORY_OBSERVATIONS" in result.reason_codes


def test_stale_future_or_scope_mismatched_observations_do_not_satisfy():
    assert evaluate((obs("stale", 2, True, expiry=10),), now_tick=10).status == "UNKNOWN"
    assert evaluate((obs("future", 11, True),), now_tick=10).status == "UNKNOWN"
    wrong_scope = obs("wrong", 8, True, scope={"corridor_id": "c", "robot_type": "scout"})
    assert evaluate((wrong_scope,)).status == "UNKNOWN"


def test_unknown_and_false_are_not_clear():
    assert evaluate((obs("unknown", 8, None),)).status == "UNKNOWN"
    assert evaluate((obs("false", 8, False),)).status == "NOT_SATISFIED"


def test_lower_bound_and_full_robot_scope_gate_numeric_clearance():
    reading = obs("gap", 8, 1.2, scope={"corridor_id": "c", "robot_type": "courier",
        "footprint": "wide", "payload_class": "loaded"})
    reading = reading.model_copy(update={"quality": {"lower_bound": 0.8}})
    result = evaluate_observation((reading,), "clear", subject_id="c", robot_id="r1",
        robot_type="courier", now_tick=10, now_utc=NOW,
        expected_scope={"footprint": "wide", "payload_class": "loaded"}, minimum_value=0.9)
    assert result.status == "NOT_SATISFIED"
