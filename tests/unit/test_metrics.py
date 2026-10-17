from __future__ import annotations

import math

import pytest

from witness_fleet.evaluation.metrics import (
    brier_score,
    expected_calibration_error,
    selective_metrics,
    threshold_for_target_risk,
    total_cost,
)


def test_oversized_integer_confidence_is_rejected_with_value_error():
    with pytest.raises(ValueError):
        selective_metrics([10**5000], [True], threshold=0.5)


def test_multiclass_brier_uses_full_unrenormalized_distribution():
    assert brier_score([[0.7, 0.1, 0.1, 0.1]], [0]) == pytest.approx(0.12)


def test_selective_risk_coverage_denominator_includes_provider_errors():
    result = selective_metrics([0.9, 0.8, None, 0.2], [True, False, False, True], threshold=0.8)
    assert result.coverage == 0.5
    assert result.selected == 2 and result.errors == 1
    assert result.risk == 0.5


def test_zero_selected_cases_have_zero_coverage_and_undefined_risk():
    result = selective_metrics([0.4, None], [False, True], threshold=0.9)
    assert result.coverage == 0 and result.selected == 0 and result.risk is None


def test_ece_and_unknown_cost_are_explicit():
    assert expected_calibration_error([0.9, 0.2], [True, False], bins=10) == pytest.approx(0.15)
    assert total_cost([1.5, None, 3.0]) is None
    assert total_cost([1.5, 2.0]) == 3.5


def test_calibration_requires_exact_boolean_correctness_labels():
    with pytest.raises(ValueError, match="correctness labels must be booleans"):
        threshold_for_target_risk(
            confidences=[1.0],
            correct=[1],  # type: ignore[list-item]
            sample_ids=["c"],
            calibration_ids={"c"},
            target_risk=0.0,
        )


@pytest.mark.parametrize(
    "bad_threshold",
    [
        math.nextafter(math.nextafter(1.0, math.inf), math.inf),
        1.1,
        -0.1,
        True,
        float("nan"),
        float("inf"),
    ],
)
def test_selective_metrics_rejects_thresholds_other_than_exact_abstain_sentinel(bad_threshold):
    with pytest.raises(ValueError):
        selective_metrics([1.0], [True], threshold=bad_threshold)


def test_selective_metrics_rejects_abstain_sentinel_as_confidence():
    sentinel = math.nextafter(1.0, math.inf)
    with pytest.raises(ValueError):
        selective_metrics([sentinel], [True], threshold=0.0)


def test_calibration_threshold_uses_calibration_ids_only_and_rejects_overlap():
    threshold, used = threshold_for_target_risk(
        confidences=[0.95, 0.8, 0.6, 0.4],
        correct=[True, True, False, False],
        sample_ids=["c1", "c2", "c3", "c4"],
        calibration_ids={"c1", "c2", "c3", "c4"},
        target_risk=0.0,
    )
    assert threshold == 0.8 and used == 4
    try:
        threshold_for_target_risk(
            confidences=[0.8],
            correct=[True],
            sample_ids=["x"],
            calibration_ids={"x"},
            evaluation_ids={"x"},
            target_risk=0.1,
        )
    except ValueError as exc:
        assert "disjoint" in str(exc)
    else:
        raise AssertionError("overlapping calibration and evaluation IDs must be refused")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.1, 1.1, True])
def test_calibration_rejects_nonfinite_or_nonprobability_risk(bad):
    with pytest.raises(ValueError):
        threshold_for_target_risk(
            confidences=[0.9],
            correct=[True],
            sample_ids=["c"],
            calibration_ids={"c"},
            target_risk=bad,
        )


def test_calibration_rejects_oversized_integer_target_risk_with_value_error():
    with pytest.raises(ValueError):
        threshold_for_target_risk(
            confidences=[0.9], correct=[True], sample_ids=["c"],
            calibration_ids={"c"}, target_risk=10**5000,
        )


def test_brier_rejects_nonfinite_or_mismatched_multiclass_distributions():
    for distributions in (
        [[float("nan"), float("nan")]],
        [[1.1, -0.1]],
        [[0.8, 0.8]],
        [[0.5, 0.5], [0.2, 0.3, 0.5]],
    ):
        with pytest.raises(ValueError):
            brier_score(distributions, [0] * len(distributions))


def test_metrics_reject_boolean_as_numeric_or_correctness_input():
    with pytest.raises(ValueError):
        brier_score([[0.7, 0.3]], [True])
    with pytest.raises(ValueError):
        expected_calibration_error([0.9], [1])  # type: ignore[list-item]
    with pytest.raises(ValueError):
        selective_metrics([0.9], ["yes"], threshold=0.5)  # type: ignore[list-item]
    with pytest.raises(ValueError):
        total_cost([True])


def test_no_feasible_calibration_threshold_composes_to_abstain_all_even_at_confidence_one():
    threshold, used = threshold_for_target_risk(
        confidences=[1.0],
        correct=[False],
        sample_ids=["c"],
        calibration_ids={"c"},
        target_risk=0.0,
    )

    result = selective_metrics([1.0], [False], threshold=threshold)

    assert used == 1
    assert threshold > 1.0
    assert result.coverage == 0.0
    assert result.selected == 0
    assert result.errors == 0
    assert result.risk is None
