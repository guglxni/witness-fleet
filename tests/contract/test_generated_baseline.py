from __future__ import annotations

import json

from witness_fleet.decisions import GeneratedBaseline


def score_request() -> dict:
    return {
        "request_id": "generated-score-1",
        "input_hash": "b" * 64,
        "state": "synthetic score state",
        "questions": [
            {
                "id": "severity",
                "type": "score",
                "instructions": "Estimate severity on the ordered scale.",
                "options": ["low", "medium", "high"],
            }
        ],
    }


def test_generated_score_computes_expected_level_from_ordinal_distribution():
    baseline = GeneratedBaseline(
        lambda _: json.dumps({"severity": {"probabilities": [0.2, 0.3, 0.5]}})
    )

    result = baseline.decide(score_request())

    assert result["status"] == "ok"
    assert result["answers"] == [
        {
            "question_id": "severity",
            "type": "score",
            "labels": ["low", "medium", "high"],
            "probabilities": [0.2, 0.3, 0.5],
            "selected_label": None,
            "expected_level": 1.3,
            "vendor_confidence": None,
            "probability_kind": "generated_not_native",
        }
    ]


def test_non_object_generated_answer_is_reported_invalid_instead_of_raising():
    baseline = GeneratedBaseline(lambda _: json.dumps({"severity": [0.2, 0.3, 0.5]}))

    result = baseline.decide(score_request())

    assert result["status"] == "invalid"
    assert result["error_class"] == "invalid_generated_output"
    assert result["answers"] == []
