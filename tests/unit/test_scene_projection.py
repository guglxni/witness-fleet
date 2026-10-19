"""Strict allowlist and schema boundary for the hosted MuJoCo scene DTO."""
import copy

import mujoco
import numpy as np
import pytest

from services.simulator.visualization import primitive_size_xyz, project_scene_snapshot
from services.simulator.world import FacilityWorld
from witness_fleet.hosting.scene import sanitize_scene_snapshot


def valid_scene():
    return {
        "schema_version": 1,
        "source": "mujoco_snapshot",
        "world_tick": 4,
        "model_sha256": "a" * 64,
        "units": "m",
        "up_axis": "z",
        "geometries": [{
            "id": "floor",
            "kind": "plane",
            "position": [0.0, 0.0, 0.0],
            "quaternion": [1.0, 0.0, 0.0, 0.0],
            "size": [12.0, 8.0, 0.1],
            "rgba": [0.7, 0.72, 0.74, 1.0],
            "body": None,
        }],
        "sites": [{"id": "delivery_zone", "position": [4.0, 0.0, 0.03],
                   "size": [0.45, 0.45, 0.45]}],
    }


def test_scene_sanitizer_returns_detached_exact_contract():
    source = valid_scene()
    result = sanitize_scene_snapshot(source)

    assert result == source
    assert set(result) == {
        "schema_version", "source", "world_tick", "model_sha256", "units",
        "up_axis", "geometries", "sites",
    }
    source["geometries"][0]["position"][0] = 99.0
    assert result["geometries"][0]["position"][0] == 0.0


@pytest.mark.parametrize("injected", [
    {"owner": "/Users/private"},
    {"path": "/tmp/snapshot"},
    {"secret": "do-not-project"},
    {"qpos": [1.0, 2.0]},
])
def test_scene_sanitizer_rejects_raw_state_and_private_fields(injected):
    scene = valid_scene()
    scene.update(injected)

    with pytest.raises(ValueError):
        sanitize_scene_snapshot(scene)


def test_scene_sanitizer_rejects_non_allowlisted_entities_and_unbounded_values():
    unknown_entity = copy.deepcopy(valid_scene())
    unknown_entity["geometries"][0]["id"] = "untrusted_model_geom"
    unbounded = copy.deepcopy(valid_scene())
    unbounded["geometries"][0]["position"][0] = 1e20

    with pytest.raises(ValueError):
        sanitize_scene_snapshot(unknown_entity)
    with pytest.raises(ValueError):
        sanitize_scene_snapshot(unbounded)


def test_scene_projection_uses_compiled_world_poses_and_primitive_dimensions():
    world = FacilityWorld(seed=4, scenario="SC-001", episode_id="projection-test")
    scene = project_scene_snapshot(world)

    assert scene["schema_version"] == 1
    assert scene["source"] == "mujoco_snapshot"
    assert scene["world_tick"] == 0
    assert scene["units"] == "m" and scene["up_axis"] == "z"
    assert len(scene["geometries"]) <= 64 and len(scene["sites"]) <= 16
    by_id = {geometry["id"]: geometry for geometry in scene["geometries"]}
    floor_id = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    chassis_id = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_GEOM, "recovery_chassis")
    pusher_id = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_GEOM, "recovery_pusher")

    assert by_id["floor"]["kind"] == "plane"
    assert by_id["floor"]["size"] == pytest.approx(world.model.geom_size[floor_id].tolist())
    assert by_id["recovery_chassis"]["kind"] == "cylinder"
    assert by_id["recovery_chassis"]["size"] == pytest.approx(
        [world.model.geom_size[chassis_id, 0], world.model.geom_size[chassis_id, 0],
         world.model.geom_size[chassis_id, 1]]
    )
    assert by_id["recovery_chassis"]["position"] == pytest.approx(
        world.data.geom_xpos[chassis_id].tolist()
    )
    assert by_id["recovery_pusher"]["position"] == pytest.approx(
        world.data.geom_xpos[pusher_id].tolist()
    )
    expected_quat = np.empty(4)
    mujoco.mju_mat2Quat(expected_quat, world.data.geom_xmat[pusher_id])
    assert by_id["recovery_pusher"]["quaternion"] == pytest.approx(expected_quat.tolist())
    assert by_id["recovery_pusher"]["quaternion"] == pytest.approx(
        [np.sqrt(0.5), 0.0, 0.0, np.sqrt(0.5)], abs=1e-6
    )
    assert by_id["courier_chassis"]["body"] == "courier"
    assert all(set(item) == {"id", "kind", "position", "quaternion", "size", "rgba", "body"}
               for item in scene["geometries"])
    assert all(set(item) == {"id", "position", "size"} for item in scene["sites"])
    world.close()


def test_scene_projection_uses_scenario_compiled_sizes_and_keeps_hidden_positions():
    world = FacilityWorld(seed=2, scenario="SC-003", episode_id="scenario-projection")
    scene = project_scene_snapshot(world)
    by_id = {geometry["id"]: geometry for geometry in scene["geometries"]}
    carton_id = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_GEOM, "carton_geom")

    assert by_id["carton_geom"]["size"] == pytest.approx([0.34, 0.45, 0.18])
    assert by_id["carton_geom"]["position"] == pytest.approx(world.data.geom_xpos[carton_id].tolist())
    heavy_box_id = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_GEOM, "heavy_box_geom")
    assert by_id["heavy_box_geom"]["position"] == pytest.approx(
        world.data.geom_xpos[heavy_box_id].tolist()
    )
    assert by_id["heavy_box_geom"]["position"] == pytest.approx([10.0, 5.0, -1.0])
    world.close()


@pytest.mark.parametrize("geom_type,raw,expected", [
    (mujoco.mjtGeom.mjGEOM_SPHERE, [0.2, 0.0, 0.0], [0.2, 0.2, 0.2]),
    (mujoco.mjtGeom.mjGEOM_CYLINDER, [0.3, 0.4, 0.0], [0.3, 0.3, 0.4]),
])
def test_scene_projection_preserves_radius_and_half_height(geom_type, raw, expected):
    assert primitive_size_xyz(geom_type, np.asarray(raw)) == pytest.approx(expected)
