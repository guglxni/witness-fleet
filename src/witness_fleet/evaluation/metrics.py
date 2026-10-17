"""Proper scores, selective metrics, and calibration-only threshold fitting."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

_ABSTAIN_ALL_THRESHOLD = math.nextafter(1.0, math.inf)


def _check_probability(value: float) -> None:
    if type(value) not in (int, float) or value < 0.0 or value > 1.0 or not math.isfinite(value):
        raise ValueError("probabilities/confidences must be finite and in [0,1]")


def brier_score(distributions: Sequence[Sequence[float]], gold_indices: Sequence[int]) -> float:
    if not distributions or len(distributions) != len(gold_indices):
        raise ValueError("non-empty distributions and matching gold labels required")
    expected_width = len(distributions[0])
    if expected_width < 2:
        raise ValueError("multiclass distributions must contain at least two labels")
    total = 0.0
    for row, gold in zip(distributions, gold_indices, strict=True):
        if len(row) != expected_width or type(gold) is not int or not 0 <= gold < len(row):
            raise ValueError("gold index out of range")
        for p in row:
            _check_probability(p)
        if abs(sum(row) - 1.0) > 1e-6:
            raise ValueError(
                "multiclass probability distributions must sum to one without normalization"
            )
        total += sum((p - (1.0 if idx == gold else 0.0)) ** 2 for idx, p in enumerate(row))
    return total / len(distributions)


def expected_calibration_error(
    confidences: Sequence[float], correct: Sequence[bool], *, bins: int = 10
) -> float:
    if not confidences or len(confidences) != len(correct) or bins <= 0:
        raise ValueError("non-empty matched data and positive bins required")
    if any(type(value) is not bool for value in correct):
        raise ValueError("correctness labels must be booleans")
    buckets: list[list[int]] = [[] for _ in range(bins)]
    for i, (confidence, _is_correct) in enumerate(zip(confidences, correct, strict=True)):
        _check_probability(confidence)
        buckets[min(int(confidence * bins), bins - 1)].append(i)
    n = len(confidences)
    return sum(
        len(bucket)
        / n
        * abs(
            sum(bool(correct[i]) for i in bucket) / len(bucket)
            - sum(confidences[i] for i in bucket) / len(bucket)
        )
        for bucket in buckets
        if bucket
    )


@dataclass(frozen=True)
class SelectiveMetrics:
    coverage: float
    selected: int
    errors: int
    risk: float | None


def selective_metrics(
    confidences: Sequence[float | None], correct: Sequence[bool], *, threshold: float
) -> SelectiveMetrics:
    if type(threshold) is not float or threshold != _ABSTAIN_ALL_THRESHOLD:
        _check_probability(threshold)
    if not confidences or len(confidences) != len(correct):
        raise ValueError("non-empty matched data required")
    if any(type(value) is not bool for value in correct):
        raise ValueError("correctness labels must be booleans")
    for value in confidences:
        if value is not None:
            _check_probability(value)
    accepted = [
        i for i, value in enumerate(confidences) if value is not None and value >= threshold
    ]
    errors = sum(not correct[i] for i in accepted)
    return SelectiveMetrics(
        len(accepted) / len(confidences),
        len(accepted),
        errors,
        errors / len(accepted) if accepted else None,
    )


def total_cost(costs: Sequence[float | None]) -> float | None:
    if not costs:
        raise ValueError("cost list must not be empty")
    if any(value is None for value in costs):
        return None
    vals = [float(value) for value in costs if value is not None]
    if any(type(value) is bool for value in costs if value is not None):
        raise ValueError("costs must be numeric values, not booleans")
    if any(not math.isfinite(value) or value < 0 for value in vals):
        raise ValueError("costs must be finite and non-negative")
    return sum(vals)


def threshold_for_target_risk(
    *,
    confidences: Sequence[float],
    correct: Sequence[bool],
    sample_ids: Sequence[str],
    calibration_ids: set[str],
    target_risk: float,
    evaluation_ids: set[str] | None = None,
) -> tuple[float, int]:
    if (
        type(target_risk) not in (int, float)
        or not 0 <= target_risk <= 1
        or not math.isfinite(target_risk)
        or not confidences
        or len(confidences) != len(correct)
        or len(confidences) != len(sample_ids)
    ):
        raise ValueError("invalid calibration inputs")
    if len(set(sample_ids)) != len(sample_ids) or set(sample_ids) != calibration_ids:
        raise ValueError("calibration sample IDs must exactly match calibration_ids")
    if evaluation_ids is not None and calibration_ids & evaluation_ids:
        raise ValueError("calibration and evaluation IDs must be disjoint")
    for confidence in confidences:
        _check_probability(confidence)
    if any(type(value) is not bool for value in correct):
        raise ValueError("correctness labels must be booleans")
    candidates = sorted(set(confidences))
    for threshold in candidates:
        chosen = [idx for idx, value in enumerate(confidences) if value >= threshold]
        risk = sum(not correct[idx] for idx in chosen) / len(chosen)
        if risk <= target_risk:
            return threshold, len(sample_ids)
    return _ABSTAIN_ALL_THRESHOLD, len(sample_ids)


__all__ = [
    "SelectiveMetrics",
    "brier_score",
    "expected_calibration_error",
    "selective_metrics",
    "threshold_for_target_risk",
    "total_cost",
]
