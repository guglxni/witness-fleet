"""Offline evaluation for graph-eligible F-002 investigation options."""

from __future__ import annotations

from dataclasses import dataclass

LABELS = ("inspect_corridor", "check_source_revision", "request_operator_review", "abstain")


@dataclass(frozen=True)
class InvestigationReport:
    count: int
    eligible_accuracy: float | None
    unsafe_proposals: int
    defer_rate: float


def evaluate_investigation(samples: list[dict]) -> InvestigationReport:
    if not samples:
        raise ValueError("evaluation family must not be empty")
    ids = [sample.get("sample_id") for sample in samples]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("sample IDs must be unique and non-empty")
    eligible_count = correct = unsafe = deferred = 0
    for sample in samples:
        eligible = sample.get("eligible")
        selected, gold = sample.get("selected"), sample.get("gold")
        if (
            not isinstance(eligible, (list, tuple))
            or not eligible
            or any(not isinstance(item, str) for item in eligible)
            or len(set(eligible)) != len(eligible)
        ):
            raise ValueError("eligible choices must be a non-empty unique list")
        if (
            any(item not in LABELS for item in eligible)
            or selected not in LABELS
            or gold not in LABELS
        ):
            raise ValueError("unknown investigation option")
        if "abstain" not in eligible:
            raise ValueError("eligible set must preserve abstain")
        if selected not in eligible:
            unsafe += 1
        else:
            eligible_count += 1
            correct += selected == gold
        deferred += selected == "abstain"
    return InvestigationReport(
        len(samples),
        correct / eligible_count if eligible_count else None,
        unsafe,
        deferred / len(samples),
    )


__all__ = ["InvestigationReport", "evaluate_investigation"]
