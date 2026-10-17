import pytest

from witness_fleet.evaluation.rerank import evaluate_rerank


def test_rerank_reports_four_way_metrics_without_collapsing_neutral_subtypes():
    report = evaluate_rerank(
        [
            {"sample_id": "s1", "probabilities": [0.7, 0.1, 0.1, 0.1], "gold": "supports"},
            {"sample_id": "s2", "probabilities": [0.1, 0.6, 0.2, 0.1], "gold": "contradicts"},
            {"sample_id": "s3", "probabilities": [0.1, 0.1, 0.7, 0.1], "gold": "irrelevant"},
            {"sample_id": "s4", "probabilities": [0.1, 0.1, 0.1, 0.7], "gold": "insufficient"},
        ]
    )
    assert report.count == 4 and report.accuracy == 1.0
    assert report.confusion["irrelevant"]["irrelevant"] == 1
    assert report.confusion["insufficient"]["insufficient"] == 1
    assert report.brier_score == pytest.approx(0.145)


def test_rerank_rejects_bad_distributions_and_empty_family():
    for samples in [
        [],
        [{"sample_id": "s", "probabilities": [0.8, 0.2], "gold": "supports"}],
        [{"sample_id": "s", "probabilities": [0.8, 0.1, 0.1, 0.1], "gold": "supports"}],
    ]:
        try:
            evaluate_rerank(samples)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid family/distribution must fail closed")


def test_rerank_rejects_nonfinite_probability_even_when_sum_comparison_would_pass():
    with pytest.raises(ValueError):
        evaluate_rerank(
            [{"sample_id": "s", "probabilities": [float("nan"), 0.1, 0.1, 0.1], "gold": "supports"}]
        )
