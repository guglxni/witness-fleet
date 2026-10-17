"""Comparison manifest that distinguishes protocol work from measured evidence."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ComparisonManifest:
    run_status: str
    provider_configured: bool
    observations: int
    measured_claim: bool
    provider_measurement: str
    fixture_kind: str
    enabled_modes: tuple[str, ...]
    accepted_calibration_report: str | None
    independent_review_accepted: bool
    manifest_sha256: str

    @classmethod
    def create(
        cls,
        *,
        provider_configured: bool,
        observations: int,
        model_modes: tuple[str, ...] = (),
        fixture_kind: str = "none",
        accepted_calibration_report: str | None = None,
        calibration_report: dict[str, Any] | None = None,
        independent_review_accepted: bool = False,
    ) -> ComparisonManifest:
        if type(provider_configured) is not bool or type(independent_review_accepted) is not bool:
            raise ValueError("provider and independent review flags must be booleans")
        if type(observations) is not int or observations < 0:
            raise ValueError("observations must be non-negative")
        if fixture_kind not in {"none", "synthetic_protocol", "synthetic_evaluation"}:
            raise ValueError("fixture_kind not recognized")
        if any(mode not in {"disabled", "shadow", "advisory"} for mode in model_modes):
            raise ValueError("unknown model mode")
        if accepted_calibration_report is not None and not _valid_digest(
            accepted_calibration_report
        ):
            raise ValueError(
                "accepted calibration report must be a lowercase sha256 digest reference"
            )
        modes = ["disabled", "shadow"]
        report_valid = False
        if calibration_report is not None and accepted_calibration_report is not None:
            try:
                validate_calibration_report(calibration_report)
                report_valid = (
                    calibration_report_reference(calibration_report) == accepted_calibration_report
                )
            except (TypeError, ValueError):
                report_valid = False
        if (
            provider_configured
            and observations > 0
            and fixture_kind == "none"
            and "advisory" in model_modes
            and report_valid
            and independent_review_accepted
        ):
            modes.append("advisory")
        measured = bool(provider_configured and observations and fixture_kind == "none")
        measurement = "observed" if measured else "not_measured_provider_absent"
        run_status = "measured" if measured else "not_run"
        enabled_modes = tuple(modes)
        body = {
            "run_status": run_status,
            "provider_configured": provider_configured,
            "observations": observations,
            "measured_claim": measured,
            "provider_measurement": measurement,
            "fixture_kind": fixture_kind,
            "enabled_modes": enabled_modes,
            "accepted_calibration_report": accepted_calibration_report,
            "independent_review_accepted": independent_review_accepted,
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        return cls(
            run_status=run_status,
            provider_configured=provider_configured,
            observations=observations,
            measured_claim=measured,
            provider_measurement=measurement,
            fixture_kind=fixture_kind,
            enabled_modes=enabled_modes,
            accepted_calibration_report=accepted_calibration_report,
            independent_review_accepted=independent_review_accepted,
            manifest_sha256=digest,
        )


_REPORT_FIELDS = {
    "schema_version",
    "status",
    "fixture_kind",
    "family",
    "model",
    "projection_version",
    "provider_observations",
    "calibration_ids",
    "test_ids",
    "target_risk",
    "achieved_risk",
    "threshold",
    "accepted_count",
}


def _valid_digest(reference: str) -> bool:
    return (
        isinstance(reference, str)
        and len(reference) == 71
        and reference.startswith("sha256:")
        and all(char in "0123456789abcdef" for char in reference[7:])
    )


def validate_calibration_report(report: dict[str, Any]) -> None:
    """Validate a complete, non-fixture report before it can support advisory mode."""
    if not isinstance(report, dict) or set(report) != _REPORT_FIELDS:
        raise ValueError("calibration report fields do not match schema")
    if (
        report["schema_version"] != "calibration-report-v1"
        or report["status"] != "complete"
        or report["fixture_kind"] != "none"
    ):
        raise ValueError("calibration report is incomplete or fixture-derived")
    for field in ("family", "model", "projection_version"):
        if not isinstance(report[field], str) or not report[field].strip():
            raise ValueError(f"calibration report {field} must be non-empty")
    for field in ("calibration_ids", "test_ids"):
        values = report[field]
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value for value in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError(f"calibration report {field} must contain unique non-empty IDs")
    if set(report["calibration_ids"]) & set(report["test_ids"]):
        raise ValueError("calibration and test report IDs must be disjoint")
    if type(report["provider_observations"]) is not int or report["provider_observations"] < len(
        report["calibration_ids"]
    ):
        raise ValueError("provider observations must cover the calibration examples")
    for field in ("target_risk", "achieved_risk", "threshold"):
        value = report[field]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"calibration report {field} must be finite and in [0,1]")
    if report["achieved_risk"] > report["target_risk"]:
        raise ValueError("calibration report does not meet target risk")
    if type(report["accepted_count"]) is not int or not 1 <= report["accepted_count"] <= len(
        report["calibration_ids"]
    ):
        raise ValueError("calibration report accepted_count is invalid")


def calibration_report_reference(report: dict[str, Any]) -> str:
    validate_calibration_report(report)
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def validate_splits(splits: dict[str, set[str]]) -> None:
    if set(splits) != {"train", "calibration", "test"}:
        raise ValueError("splits must name train, calibration, and test")
    seen: set[str] = set()
    for name in ("train", "calibration", "test"):
        values = splits[name]
        if seen & values:
            raise ValueError(f"split overlap detected in {name}")
        seen |= values


__all__ = [
    "ComparisonManifest",
    "calibration_report_reference",
    "validate_calibration_report",
    "validate_splits",
]
