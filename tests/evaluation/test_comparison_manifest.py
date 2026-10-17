from witness_fleet.evaluation.manifest import ComparisonManifest, validate_splits


def test_manifest_never_claims_measurements_without_provider_observations():
    manifest = ComparisonManifest.create(
        provider_configured=False, observations=0, model_modes=("advisory",)
    )
    assert manifest.run_status == "not_run"
    assert manifest.measured_claim is False
    assert manifest.enabled_modes == ("disabled", "shadow")
    assert manifest.provider_measurement == "not_measured_provider_absent"


def test_manifest_advisory_requires_accepted_calibration_report():
    pending = ComparisonManifest.create(
        provider_configured=True, observations=3, model_modes=("advisory",)
    )
    assert pending.enabled_modes == ("disabled", "shadow")
    accepted = ComparisonManifest.create(
        provider_configured=True,
        observations=3,
        model_modes=("advisory",),
        accepted_calibration_report="sha256:" + "a" * 64,
    )
    assert accepted.enabled_modes == ("disabled", "shadow")


def test_advisory_requires_valid_report_payload_and_separate_review_acceptance():
    from witness_fleet.evaluation.manifest import calibration_report_reference

    report = {
        "schema_version": "calibration-report-v1",
        "status": "complete",
        "fixture_kind": "none",
        "family": "F-001",
        "model": "pinned-model",
        "projection_version": "projection-v1",
        "provider_observations": 3,
        "calibration_ids": ["c1", "c2"],
        "test_ids": ["t1"],
        "target_risk": 0.1,
        "achieved_risk": 0.0,
        "threshold": 0.8,
        "accepted_count": 1,
    }
    # A source citation establishes the public wire contract; it is not a live-call validation.
    from pathlib import Path

    citation = Path(__file__).parents[2] / "DECISION_CONTRACTS.md"
    assert (
        "learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision"
        in citation.read_text()
    )
    reference = calibration_report_reference(report)
    base = dict(
        provider_configured=True,
        observations=3,
        model_modes=("advisory",),
        accepted_calibration_report=reference,
        calibration_report=report,
    )
    pending_review = ComparisonManifest.create(**base)
    assert pending_review.enabled_modes == ("disabled", "shadow")
    accepted = ComparisonManifest.create(**base, independent_review_accepted=True)
    assert accepted.enabled_modes == ("disabled", "shadow", "advisory")
    assert accepted.independent_review_accepted is True

    malformed = dict(report, achieved_risk=float("nan"))
    bad = ComparisonManifest.create(
        **{**base, "calibration_report": malformed}, independent_review_accepted=True
    )
    assert bad.enabled_modes == ("disabled", "shadow")
    forged = dict(report, family="different-family")
    mismatch = ComparisonManifest.create(
        **{**base, "calibration_report": forged}, independent_review_accepted=True
    )
    assert mismatch.enabled_modes == ("disabled", "shadow")
    fixture = dict(report, fixture_kind="synthetic_evaluation")
    synthetic = ComparisonManifest.create(
        **{**base, "calibration_report": fixture}, independent_review_accepted=True
    )
    assert synthetic.enabled_modes == ("disabled", "shadow")


def test_advisory_never_enabled_by_review_approval_without_report_or_provider_evidence():
    no_report = ComparisonManifest.create(
        provider_configured=True,
        observations=3,
        model_modes=("advisory",),
        independent_review_accepted=True,
    )
    no_provider = ComparisonManifest.create(
        provider_configured=False,
        observations=0,
        model_modes=("advisory",),
        independent_review_accepted=True,
    )
    assert no_report.enabled_modes == no_provider.enabled_modes == ("disabled", "shadow")


def test_calibration_digest_reference_must_be_exact_lowercase_sha256():
    for reference in ("sha256:" + "A" * 64, "sha256:" + "z" * 64, "sha256:" + "a" * 63):
        try:
            ComparisonManifest.create(
                provider_configured=True,
                observations=1,
                model_modes=("advisory",),
                accepted_calibration_report=reference,
                independent_review_accepted=True,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("malformed calibration digest references must be refused")


def test_synthetic_protocol_fixture_is_not_misrepresented_as_model_measurement():
    manifest = ComparisonManifest.create(
        provider_configured=False, observations=1, fixture_kind="synthetic_protocol"
    )
    assert manifest.fixture_kind == "synthetic_protocol"
    assert (
        manifest.measured_claim is False
        and manifest.provider_measurement == "not_measured_provider_absent"
    )


def test_train_calibration_and_test_split_ids_are_disjoint():
    validate_splits({"train": {"a"}, "calibration": {"b"}, "test": {"c"}})
    try:
        validate_splits({"train": {"a"}, "calibration": {"a"}, "test": {"c"}})
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("split leakage must be rejected")
