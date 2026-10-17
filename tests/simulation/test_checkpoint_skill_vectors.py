"""Native JSON checkpoints preserve skill controller vectors and reject corruption."""

import copy
import json

import numpy as np
import pytest

from services.simulator import FacilityWorld


def _json_default(item):
    if isinstance(item, np.ndarray):
        return item.tolist()
    raise TypeError(f"not JSON serializable: {type(item).__name__}")


def _json_roundtrip(value):
    return json.loads(json.dumps(value, default=_json_default))


@pytest.mark.parametrize(
    ("robot", "kind", "parameters", "vector_key"),
    [
        ("courier", "travel", {"target_x": 2.0, "target_y": 1.0}, "target"),
        ("recovery", "recover", {"target_displacement_m": 0.75}, "approach_target"),
    ],
)
def test_json_checkpoint_restores_active_skill_vectors_for_status_and_controller(
    robot, kind, parameters, vector_key
):
    with FacilityWorld(seed=19, scenario="SC-001", episode_id="json-skill") as original:
        assert original.start_skill(robot, kind, parameters)["status"] == "accepted"
        original.step()
        checkpoint = _json_roundtrip(original.checkpoint())

    with FacilityWorld(seed=19, scenario="SC-001", episode_id="json-skill") as restored:
        restored.restore(checkpoint)
        status = restored.skill_status(robot)
        assert status["status"] == "running"
        assert len(status[vector_key]) == (2 if vector_key != "initial_object" else 3)

        restored.step()
        assert restored.skill_status(robot)["status"] == "running"


@pytest.mark.parametrize(
    ("robot", "kind", "vector_key", "bad_vector"),
    [
        ("courier", "travel", "target", [1.0]),
        ("courier", "travel", "target", [1.0, float("nan")]),
        ("recovery", "recover", "approach_target", [1.0]),
        ("recovery", "recover", "approach_target", [1.0, float("inf")]),
        ("recovery", "recover", "initial_object", [1.0, 2.0]),
        ("recovery", "recover", "initial_object", [1.0, 2.0, float("nan")]),
    ],
)
def test_malformed_skill_vectors_are_rejected_before_live_world_mutation(
    robot, kind, vector_key, bad_vector
):
    with FacilityWorld(seed=19, scenario="SC-001", episode_id="json-invalid-skill") as original:
        assert original.start_skill(robot, kind)["status"] == "accepted"
        checkpoint = _json_roundtrip(original.checkpoint())

    checkpoint["qpos"] = (np.asarray(checkpoint["qpos"]) + 1.0).tolist()
    checkpoint["world_tick"] += 7
    checkpoint["skills"][robot][vector_key] = bad_vector

    with FacilityWorld(seed=19, scenario="SC-001", episode_id="json-invalid-skill") as target:
        target.step(2)
        qpos_before = target.data.qpos.copy()
        time_before = target.data.time
        tick_before = target.world_tick

        with pytest.raises(ValueError, match="skill|vector"):
            target.restore(copy.deepcopy(checkpoint))

        assert np.array_equal(target.data.qpos, qpos_before)
        assert target.data.time == time_before
        assert target.world_tick == tick_before
