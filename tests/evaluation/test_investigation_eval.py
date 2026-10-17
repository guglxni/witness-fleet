from witness_fleet.evaluation.investigation import evaluate_investigation


def test_investigation_metrics_separate_eligible_accuracy_from_unsafe_proposals():
    report = evaluate_investigation(
        [
            {
                "sample_id": "i1",
                "eligible": ["inspect_corridor", "abstain"],
                "selected": "inspect_corridor",
                "gold": "inspect_corridor",
            },
            {
                "sample_id": "i2",
                "eligible": ["check_source_revision", "abstain"],
                "selected": "request_operator_review",
                "gold": "check_source_revision",
            },
            {"sample_id": "i3", "eligible": ["abstain"], "selected": "abstain", "gold": "abstain"},
        ]
    )
    assert report.count == 3
    assert report.eligible_accuracy == 1.0
    assert report.unsafe_proposals == 1
    assert report.defer_rate == 1 / 3


def test_investigation_rejects_empty_samples_and_unknown_selected_labels():
    for samples in [
        [],
        [{"sample_id": "i", "eligible": ["abstain"], "selected": "invented", "gold": "abstain"}],
    ]:
        try:
            evaluate_investigation(samples)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid/empty evaluation must fail closed")


def test_investigation_accuracy_is_undefined_not_nan_when_every_proposal_is_unsafe():
    report = evaluate_investigation(
        [
            {
                "sample_id": "i1",
                "eligible": ["inspect_corridor", "abstain"],
                "selected": "request_operator_review",
                "gold": "inspect_corridor",
            },
        ]
    )
    assert report.unsafe_proposals == 1
    assert report.eligible_accuracy is None
