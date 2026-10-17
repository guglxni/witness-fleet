"""Safe constrained-generation baseline; emitted numbers are never native probabilities."""

from __future__ import annotations

import json
from collections.abc import Callable


class GeneratedBaseline:
    def __init__(self, generator: Callable[[str], str] | None = None):
        self.generator = generator

    def decide(self, request: dict) -> dict:
        from . import ProviderAnswer

        if self.generator is None:
            return {
                "request_id": request.get("request_id", ""),
                "input_hash": request.get("input_hash", ""),
                "status": "unavailable",
                "provider": "generator",
                "requested_model": "unknown",
                "resolved_model": None,
                "model_version_evidence": "unknown",
                "answers": [],
                "latency_ms": 0,
                "attempt_count": 0,
                "usage": {"input_tokens": None, "billed_units": None, "output_tokens": None},
                "error_class": "generator_unconfigured",
                "calibration_version": None,
                "decision_policy_version": "decision-policy-v1",
            }
        try:
            prompt = json.dumps(
                {"state": request["state"], "questions": request["questions"]}, sort_keys=True
            )
            output = json.loads(self.generator(prompt))
            expected_ids = [q["id"] for q in request["questions"]]
            if not isinstance(output, dict) or set(output) != set(expected_ids):
                raise ValueError("generated answers must exactly name questions")
            normalized = []
            for q in request["questions"]:
                raw = output[q["id"]]
                if not isinstance(raw, dict):
                    raise ValueError("generated answer must be an object")
                labels = tuple(q["options"])
                probabilities = tuple(raw.get("probabilities", ()))
                selected = None if q["type"] == "score" else raw.get("selected_label")
                if q["type"] != "score" and selected not in labels:
                    raise ValueError("generated label outside declared options")
                normalized.append(
                    ProviderAnswer(
                        question_id=q["id"],
                        type=q["type"],
                        labels=labels,
                        probabilities=probabilities,
                        selected_label=selected,
                        expected_level=(
                            sum(index * probability for index, probability in enumerate(probabilities))
                            if q["type"] == "score"
                            else None
                        ),
                        probability_kind="generated_not_native",
                    ).model_dump(mode="json")
                )
            return {
                "request_id": request["request_id"],
                "input_hash": request["input_hash"],
                "status": "ok",
                "provider": "generator",
                "requested_model": "unknown",
                "resolved_model": None,
                "model_version_evidence": "unknown",
                "answers": normalized,
                "latency_ms": 0,
                "attempt_count": 1,
                "usage": {"input_tokens": None, "billed_units": None, "output_tokens": None},
                "error_class": None,
                "calibration_version": None,
                "decision_policy_version": "decision-policy-v1",
            }
        except (KeyError, TypeError, ValueError):
            return {
                "request_id": request.get("request_id", ""),
                "input_hash": request.get("input_hash", ""),
                "status": "invalid",
                "provider": "generator",
                "requested_model": "unknown",
                "resolved_model": None,
                "model_version_evidence": "unknown",
                "answers": [],
                "latency_ms": 0,
                "attempt_count": 1,
                "usage": {"input_tokens": None, "billed_units": None, "output_tokens": None},
                "error_class": "invalid_generated_output",
                "calibration_version": None,
                "decision_policy_version": "decision-policy-v1",
            }


__all__ = ["GeneratedBaseline"]
