"""Offline metrics for F-001 evidence relation ranking."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .metrics import brier_score

LABELS = ("supports", "contradicts", "irrelevant", "insufficient")


@dataclass(frozen=True)
class RerankReport:
    count: int
    accuracy: float
    brier_score: float
    confusion: dict[str, dict[str, int]]


def evaluate_rerank(samples: list[dict]) -> RerankReport:
    if not samples:
        raise ValueError("evaluation family must not be empty")
    ids = [sample.get("sample_id") for sample in samples]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("sample IDs must be unique and non-empty")
    gold_indices: list[int] = []
    predictions: list[int] = []
    distributions: list[list[float]] = []
    confusion = {gold: {pred: 0 for pred in LABELS} for gold in LABELS}
    for sample in samples:
        gold = sample.get("gold")
        probs = sample.get("probabilities")
        if (
            not isinstance(gold, str)
            or gold not in LABELS
            or not isinstance(probs, (list, tuple))
            or len(probs) != len(LABELS)
        ):
            raise ValueError("invalid gold or F-001 distribution")
        if (
            any(
                type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                for p in probs
            )
            or abs(sum(probs) - 1.0) > 1e-6
        ):
            raise ValueError("invalid/non-normalized F-001 distribution")
        pred = max(range(len(probs)), key=probs.__getitem__)
        gold_idx = LABELS.index(gold)
        gold_indices.append(gold_idx)
        predictions.append(pred)
        distributions.append(list(probs))
        confusion[gold][LABELS[pred]] += 1
    return RerankReport(
        len(samples),
        sum(p == g for p, g in zip(predictions, gold_indices, strict=True)) / len(samples),
        brier_score(distributions, gold_indices),
        confusion,
    )


__all__ = ["RerankReport", "evaluate_rerank"]
