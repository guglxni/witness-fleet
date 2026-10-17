"""Small immutable helpers for keeping hypotheses distinct from verified facts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def fact_is_current(fact: Mapping[str, Any], observations: Sequence[Any], *, now_tick: int) -> bool:
    """A fact is current only when verified and observation-supported/fresh.

    Hypothesis and predicted-effect objects are intentionally never accepted as facts.
    """
    if fact.get("status") != "verified" or fact.get("kind") in {"hypothesis", "predicted_effect"}:
        return False
    observation_ids = tuple(fact.get("observation_ids", ()))
    if not observation_ids:
        return False
    by_id = {getattr(item, "id", None): item for item in observations}
    for observation_id in observation_ids:
        observation = by_id.get(observation_id)
        if observation is None or getattr(observation, "value", None) is not True:
            return False
        if getattr(observation, "world_tick", now_tick + 1) > now_tick:
            return False
        if now_tick >= getattr(observation, "expires_tick", now_tick):
            return False
    return True


def refute_hypothesis(hypothesis: Mapping[str, Any], observation: Any) -> dict[str, Any]:
    """Return a copied refutation event retaining prior history and observation identity."""
    identifier = getattr(observation, "id", None)
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("refutation requires a stable observation ID")
    history = tuple(hypothesis.get("refuted_by", ()))
    return {**hypothesis, "status": "refuted", "refuted_by": history + (identifier,)}
