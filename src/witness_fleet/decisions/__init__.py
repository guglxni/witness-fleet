"""Bounded provider adapter and strict provider-boundary value types."""

from __future__ import annotations

import math
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .generator import GeneratedBaseline


class ProviderQuestion(BaseModel):
    """Strict provider-specific projection; deliberately independent of domain DTOs."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    type: Literal["noul", "choice", "score"]
    instructions: str = Field(min_length=1, max_length=1200)
    options: tuple[str, ...] = ()

    @field_validator("options")
    @classmethod
    def options_are_bounded_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if (
            len(value) > 8
            or len(set(value)) != len(value)
            or any(not x or len(x) > 80 for x in value)
        ):
            raise ValueError("options must be unique, non-empty, and at most eight")
        return value

    @model_validator(mode="after")
    def valid_shape(self) -> ProviderQuestion:
        if self.type == "choice" and not 2 <= len(self.options) <= 8:
            raise ValueError("choice requires two to eight ordered options")
        if self.type == "noul" and self.options and len(self.options) != 2:
            raise ValueError("noul options, when supplied, must be binary")
        if self.type == "score" and not 2 <= len(self.options) <= 8:
            raise ValueError("score requires two to eight ordered levels")
        return self


class ProviderAnswer(BaseModel):
    """An ordered, validated answer preserving provider probability values verbatim."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)
    question_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    type: Literal["noul", "choice", "score"]
    labels: tuple[str, ...]
    probabilities: tuple[float, ...]
    selected_label: str | None
    expected_level: float | None = None
    vendor_confidence: float | None = None
    probability_kind: Literal["native", "generated_not_native"] = "native"

    @field_validator("labels")
    @classmethod
    def bounded_unique_labels(cls, labels: tuple[str, ...]) -> tuple[str, ...]:
        if (
            not 1 <= len(labels) <= 8
            or len(set(labels)) != len(labels)
            or any(not isinstance(label, str) or not label or len(label) > 80 for label in labels)
        ):
            raise ValueError("labels must be unique non-empty strings, at most eight")
        return labels

    @field_validator("probabilities")
    @classmethod
    def finite_probabilities(cls, values: tuple[float, ...]) -> tuple[float, ...]:
        if not values or any(not math.isfinite(p) or p < 0.0 or p > 1.0 for p in values):
            raise ValueError("probabilities must be finite values in [0,1]")
        return values

    @model_validator(mode="after")
    def answer_shape(self) -> ProviderAnswer:
        if (
            len(self.labels) != len(self.probabilities)
            or not self.labels
            or len(set(self.labels)) != len(self.labels)
        ):
            raise ValueError(
                "labels and probabilities must have equal nonzero length and unique labels"
            )
        if self.type == "noul" and (
            self.labels != ("true",)
            or self.selected_label is not None
            or self.expected_level is not None
        ):
            raise ValueError("noul answer must preserve only its single true-probability label")
        if self.type == "choice" and len(self.labels) < 2:
            raise ValueError("choice answer requires at least two labels")
        if self.type in ("choice", "score") and abs(sum(self.probabilities) - 1.0) > 1e-6:
            raise ValueError("choice and score probabilities must sum to one without normalization")
        if self.type == "score" and (len(self.labels) < 2 or self.expected_level is None):
            raise ValueError("score answer requires an ordinal distribution and expected level")
        if self.type == "score" and self.expected_level is not None:
            weighted_level = sum(
                index * probability for index, probability in enumerate(self.probabilities)
            )
            if abs(self.expected_level - weighted_level) > 1e-3:
                raise ValueError("score must equal the probability-weighted ordinal level")
        if self.type == "score" and self.selected_label is not None:
            raise ValueError("score answer must not invent a discrete selected label")
        if self.type == "choice" and (
            self.selected_label is None or self.expected_level is not None
        ):
            raise ValueError("choice answer requires a selected label")
        if self.selected_label is not None and self.selected_label not in self.labels:
            raise ValueError("selected label must be among answer labels")
        if (
            self.type == "choice"
            and self.selected_label is not None
            and self.probabilities[self.labels.index(self.selected_label)]
            != max(self.probabilities)
        ):
            raise ValueError("selected choice must have a maximum probability")
        if self.expected_level is not None and (
            not math.isfinite(self.expected_level)
            or self.expected_level < 0
            or self.expected_level > len(self.labels) - 1
        ):
            raise ValueError("expected score level is outside the declared ordinal scale")
        if self.vendor_confidence is not None and (
            not math.isfinite(self.vendor_confidence) or not 0 <= self.vendor_confidence <= 1
        ):
            raise ValueError("vendor confidence must be finite and in [0,1]")
        return self


class DisabledProvider:
    """No-call default; explicitly unavailable with no inferred result."""

    def decide(self, request: dict, **_: object) -> dict:
        return _result(
            request,
            "unavailable",
            error_class="provider_disabled",
            provider="disabled",
            attempt_count=0,
        )


class MicrosoftSystemOneProvider:
    """Fail-closed placeholder until the exact official answer wire schema is verified."""

    def __init__(self, *, endpoint: str, allowed_hostname: str, timeout: float = 5.0):
        if not 0 < timeout <= 5.0:
            raise ValueError("timeout must be in (0, 5] seconds")
        parsed = httpx.URL(endpoint)
        if (
            parsed.scheme != "https"
            or parsed.host != allowed_hostname
            or parsed.port not in (None, 443)
            or parsed.username
            or parsed.password
        ):
            raise ValueError("endpoint must be HTTPS on the exact configured hostname")
        path = parsed.path.rstrip("/")
        for suffix in ("/openai/v1", "/openai", "/v1"):
            if path.endswith(suffix):
                path = path[: -len(suffix)]
                break
        if path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("endpoint must identify the configured resource host root")
        self.url = f"https://{allowed_hostname}/providers/microsoft/v1/systemone"
        self.allowed_hostname = allowed_hostname
        self.timeout = timeout

    def decide(
        self,
        request: dict,
        *,
        current_graph_version: int | None = None,
        current_policy_epoch: int | None = None,
    ) -> dict:
        return _result(
            request, "unavailable", error_class="unverified_provider_schema", attempt_count=0
        )


def _result(
    request: dict,
    status: str,
    latency_ms: int = 0,
    error_class: str | None = None,
    *,
    provider: str = "microsoft",
    attempt_count: int = 1,
) -> dict:
    return {
        "request_id": request.get("request_id", ""),
        "input_hash": request.get("input_hash", ""),
        "status": status,
        "provider": provider,
        "requested_model": request.get("requested_model", ""),
        "resolved_model": None,
        "model_version_evidence": "unknown",
        "answers": [],
        "latency_ms": latency_ms,
        "attempt_count": attempt_count,
        "usage": {"input_tokens": None, "billed_units": None, "output_tokens": None},
        "error_class": error_class,
        "calibration_version": None,
        "decision_policy_version": "decision-policy-v1",
    }


__all__ = [
    "DisabledProvider",
    "GeneratedBaseline",
    "MicrosoftSystemOneProvider",
    "ProviderAnswer",
    "ProviderQuestion",
]
