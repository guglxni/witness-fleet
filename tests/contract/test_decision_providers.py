from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from witness_fleet.decisions import (
    DisabledProvider,
    MicrosoftSystemOneProvider,
    ProviderAnswer,
    ProviderQuestion,
)


def request(*, deadline=None, model="deployment-a"):
    return {
        "request_id": "req-synth-1",
        "family_id": "F-001",
        "question_schema_version": "f001-v1",
        "projection_version": "projection-v1",
        "graph_version": 3,
        "policy_epoch": 2,
        "evidence_dependencies": [["span-synth-1", "rev-synth-1"]],
        "input_hash": "a" * 64,
        "state": "CLAIM: synthetic claim\nQUOTED SOURCE: synthetic supporting text",
        "questions": [
            {
                "id": "relation",
                "type": "choice",
                "instructions": "Classify source relation.",
                "options": ["supports", "contradicts", "irrelevant", "insufficient"],
            }
        ],
        "deadline_monotonic": deadline or time.monotonic() + 4,
        "allowed_provider": "microsoft",
        "requested_model": model,
    }


def test_disabled_provider_is_unavailable_without_fabricated_answers_or_probabilities():
    result = DisabledProvider().decide(request())
    assert result["status"] == "unavailable" and result["answers"] == []
    assert result["resolved_model"] is None and result["usage"]["input_tokens"] is None
    assert result["provider"] == "disabled" and result["attempt_count"] == 0


def test_microsoft_adapter_is_hard_disabled_before_credential_or_network_access():
    provider = MicrosoftSystemOneProvider(
        endpoint="https://resource.example.test",
        allowed_hostname="resource.example.test",
        timeout=5.0,
    )
    result = provider.decide(request())
    assert result["status"] == "unavailable"
    assert result["error_class"] == "unverified_provider_schema"
    assert result["answers"] == []


def test_provider_requires_exact_https_configured_host_and_five_second_maximum():
    with pytest.raises(ValueError):
        MicrosoftSystemOneProvider(
            endpoint="http://resource.example.test",
            allowed_hostname="resource.example.test",
            timeout=5.0,
        )
    with pytest.raises(ValueError):
        MicrosoftSystemOneProvider(
            endpoint="https://evil.example", allowed_hostname="resource.example.test", timeout=5.0
        )
    with pytest.raises(ValueError):
        MicrosoftSystemOneProvider(
            endpoint="https://resource.example.test/openai/v1",
            allowed_hostname="resource.example.test",
            timeout=5.01,
        )


def test_provider_questions_are_strict_bounded_and_ordered():
    with pytest.raises(ValidationError):
        ProviderQuestion(id="x", type="choice", instructions="x", options=("a",), other="bad")
    with pytest.raises(ValidationError):
        ProviderQuestion(id="x", type="choice", instructions="x", options=("only-one",))
    with pytest.raises(ValidationError):
        ProviderQuestion(
            id="x", type="choice", instructions="x", options=tuple(f"label-{i}" for i in range(9))
        )
    valid = ProviderQuestion(id="relation", type="choice", instructions="x", options=("a", "b"))
    with pytest.raises((ValidationError, TypeError, AttributeError)):
        valid.id = "mutated"


def test_provider_answers_reject_nonfinite_mismatched_and_inconsistent_distributions():
    with pytest.raises(ValidationError):
        ProviderAnswer(
            question_id="q",
            type="choice",
            labels=("a", "b"),
            probabilities=(float("nan"), 1.0),
            selected_label="a",
        )
    with pytest.raises(ValidationError):
        ProviderAnswer(
            question_id="q",
            type="choice",
            labels=("a", "b"),
            probabilities=(0.4, 0.2),
            selected_label="a",
        )
    with pytest.raises(ValidationError):
        ProviderAnswer(
            question_id="q",
            type="choice",
            labels=tuple(f"label-{i}" for i in range(9)),
            probabilities=(1 / 9,) * 9,
            selected_label="label-0",
        )
    with pytest.raises(ValidationError):
        ProviderAnswer(
            question_id="q",
            type="choice",
            labels=("a", "b"),
            probabilities=(0.4, 0.6),
            selected_label="a",
        )


def test_score_answer_preserves_expected_continuous_level_not_a_fabricated_label():
    answer = ProviderAnswer(
        question_id="severity",
        type="score",
        labels=("low", "high"),
        probabilities=(0.5, 0.5),
        selected_label=None,
        expected_level=0.5,
    )
    assert answer.expected_level == 0.5 and answer.selected_label is None
    with pytest.raises(ValidationError):
        ProviderAnswer(
            question_id="severity",
            type="score",
            labels=("low", "high"),
            probabilities=(0.5, 0.5),
            selected_label=None,
            expected_level=1.0,
        )


def test_synthetic_wire_fixture_is_labeled_as_non_provider_evidence():
    fixture_path = (
        Path(__file__).parents[2] / "fixtures/evaluation/systemone_synthetic_protocol.json"
    )
    fixture = json.loads(fixture_path.read_text())
    assert fixture["fixture_kind"] == "synthetic_protocol_test"
    assert "not a Microsoft response" in fixture["warning"]
    result = MicrosoftSystemOneProvider(
        endpoint="https://resource.example.test", allowed_hostname="resource.example.test"
    ).decide(fixture["request"])
    assert result["status"] == "unavailable" and result["answers"] == []
