"""A retained native checkpoint cannot silently change the physical model."""

import copy

import numpy as np
import pytest

from services.simulator import FacilityWorld


@pytest.mark.parametrize("physical_change", ["geometry", "mass", "friction"])
def test_restore_rejects_different_physical_model_before_mutating_live_state(physical_change):
    with FacilityWorld(seed=3, episode_id="model-identity") as original:
        original.step(2)
        checkpoint = original.checkpoint()

    with FacilityWorld(seed=3, episode_id="model-identity") as target:
        if physical_change == "geometry":
            target.model.geom_size[target._robot_geom_ids["courier"], 0] += 0.01
        elif physical_change == "mass":
            target.model.body_mass[target._robot_body_ids["courier"]] += 0.01
        else:
            target.model.geom_friction[target._robot_geom_ids["courier"], 0] += 0.01

        before = {
            name: getattr(target.data, name).copy() for name in ("qpos", "qvel", "act", "ctrl")
        }
        time_before = target.data.time
        tick_before = target.world_tick
        with pytest.raises(ValueError, match="model"):
            target.restore(checkpoint)
        for name, value in before.items():
            assert np.array_equal(getattr(target.data, name), value)
        assert target.data.time == time_before
        assert target.world_tick == tick_before


def test_checkpoint_fingerprints_compiled_model_asset_runtime_and_controller_schema():
    with FacilityWorld(seed=3, episode_id="model-identity") as world:
        identity = world.checkpoint()["model_identity"]

    assert set(identity) == {
        "mujoco_version",
        "asset_sha256",
        "compiled_model_sha256",
        "controller_schema",
    }
    assert identity["mujoco_version"]
    assert len(identity["asset_sha256"]) == 64
    assert len(identity["compiled_model_sha256"]) == 64
    assert identity["controller_schema"]


@pytest.mark.parametrize(
    "identity_field", ["mujoco_version", "asset_sha256", "compiled_model_sha256", "controller_schema"]
)
def test_restore_rejects_tampered_native_identity_before_mutating_live_state(identity_field):
    with FacilityWorld(seed=3, episode_id="model-identity") as original:
        checkpoint = original.checkpoint()
    checkpoint["model_identity"][identity_field] = "not-the-original-identity"

    with FacilityWorld(seed=3, episode_id="model-identity") as target:
        before = target.data.qpos.copy()
        with pytest.raises(ValueError, match="model"):
            target.restore(checkpoint)
        assert np.array_equal(target.data.qpos, before)
        assert target.world_tick == 0


def test_legacy_checkpoint_without_native_identity_requires_a_new_episode():
    with FacilityWorld(seed=3, episode_id="model-identity") as original:
        checkpoint = original.checkpoint()
    checkpoint.pop("model_identity")

    with FacilityWorld(seed=3, episode_id="model-identity") as target:
        before = {
            name: getattr(target.data, name).copy() for name in ("qpos", "qvel", "act", "ctrl")
        }
        checkpoint["qpos"] = checkpoint["qpos"] + 1
        with pytest.raises(ValueError, match="new episode"):
            target.restore(checkpoint)
        for name, value in before.items():
            assert np.array_equal(getattr(target.data, name), value)
        assert target.world_tick == 0


def test_identical_native_model_restore_replays_physics_time_and_payload():
    with FacilityWorld(seed=1, episode_id="model-identity") as original:
        original.load_payload("courier", "parcel")
        original.step(4)
        checkpoint = original.checkpoint()
        expected_arrays = {
            name: np.asarray(checkpoint[name]).copy() for name in ("qpos", "qvel", "act", "ctrl")
        }
        expected_time = checkpoint["sim_time"]
        expected_tick = checkpoint["world_tick"]

    with FacilityWorld(seed=1, episode_id="model-identity") as restored:
        restored.step(1)
        restored.restore(copy.deepcopy(checkpoint))
        for name, value in expected_arrays.items():
            assert np.array_equal(getattr(restored.data, name), value)
        assert restored.data.time == expected_time
        assert restored.world_tick == expected_tick
        assert restored.inspect("courier")["payload"]["payload_id"] == "parcel"
