"""Deterministic filtering of sensor observations; no hidden world-state access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Any

from witness_fleet.domain import Observation


@dataclass(frozen=True)
class ObservationEvaluation:
    status: str
    reason_codes: tuple[str, ...]
    observations: tuple[Observation, ...] = ()
    valid_until_tick: int | None = None


def _matches_scope(observation: Observation, expected_scope: dict[str, Any]) -> bool:
    for key, value in expected_scope.items():
        actual = observation.scope.get(key)
        # Corridor and robot class are also represented by top-level DTO fields.
        if key == "corridor_id":
            actual = observation.scope.get(key, observation.subject_id)
        elif key == "robot_type":
            actual = observation.scope.get(key)
        if actual != value:
            return False
    return True


def evaluate_observation(
    observations: tuple[Observation, ...] | list[Observation],
    predicate: str,
    *,
    subject_id: str,
    robot_id: str,
    robot_type: str,
    now_tick: int,
    now_utc: datetime,
    expected_scope: dict[str, Any] | None = None,
    minimum_value: float | None = None,
) -> ObservationEvaluation:
    """Evaluate the newest world-tick evidence matching exact actor, target, and scope.

    Recorded timestamps are only checked for future evidence; they never order facts.
    Conflicting values at the same latest world tick are unknown. Numeric clearance
    needs both an explicit threshold and a conservative quality.lower_bound.
    """
    scope = {"corridor_id": subject_id, "robot_type": robot_type, **(expected_scope or {})}
    candidates: list[Observation] = []
    for item in observations:
        if item.predicate != predicate or item.robot_id != robot_id:
            continue
        if item.subject_id != subject_id or item.world_tick > now_tick:
            continue
        if item.recorded_at > now_utc or item.occurred_at > now_utc:
            continue
        if now_tick >= item.expires_tick or not _matches_scope(item, scope):
            continue
        candidates.append(item)

    if not candidates:
        return ObservationEvaluation("UNKNOWN", ("MISSING_OR_STALE_OBSERVATION",))

    newest_tick = max(item.world_tick for item in candidates)
    latest = tuple(sorted((item for item in candidates if item.world_tick == newest_tick), key=lambda o: o.id))
    values = {repr(item.value) for item in latest}
    if len(values) > 1:
        return ObservationEvaluation("UNKNOWN", ("CONTRADICTORY_OBSERVATIONS",), latest)

    selected = latest[-1]
    value = selected.value
    if type(value) is bool:
        status = "VERIFIED" if value is True else "NOT_SATISFIED"
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        bound = selected.quality.get("lower_bound")
        if (minimum_value is None or isinstance(bound, bool) or not isinstance(bound, (int, float))
                or not isfinite(float(bound))):
            return ObservationEvaluation("UNKNOWN", ("NO_CONSERVATIVE_NUMERIC_BOUND",), latest,
                                         selected.expires_tick)
        status = "VERIFIED" if float(bound) >= minimum_value else "NOT_SATISFIED"
    else:
        status = "UNKNOWN"
    reason = {"VERIFIED": "OBSERVATION_VERIFIED", "NOT_SATISFIED": "OBSERVATION_FALSE",
              "UNKNOWN": "OBSERVATION_UNKNOWN"}[status]
    return ObservationEvaluation(status, (reason,), latest, selected.expires_tick)
