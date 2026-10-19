"""Locked service snapshots are detached reads of the live native scene."""
import hashlib
import json

import mujoco
import pytest

from services.simulator.service import SimulatorService


def _checkpoint_digest(world):
    checkpoint = world.checkpoint()
    plain = {
        key: value.tolist() if hasattr(value, "tolist") else value
        for key, value in checkpoint.items()
    }
    return hashlib.sha256(
        json.dumps(plain, sort_keys=True, default=str).encode()
    ).hexdigest()


def test_snapshot_is_explicitly_unavailable_before_episode_without_checkpoint_write(tmp_path):
    service = SimulatorService(tmp_path)
    before = service.journal.checkpoint()

    assert service.scene_snapshot() == {"status": "unavailable"}
    assert service.journal.checkpoint() == before
    service.close()


def test_snapshot_matches_live_compiled_data_and_does_not_advance_or_mutate(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode("scene-test", "SC-001", 7)
    world = service.world
    assert world is not None
    assert world.start_skill("scout", "travel", {"target_x": -2.0, "target_y": 0.2})["status"] == "accepted"
    service.advance(23)
    before_digest = _checkpoint_digest(world)
    before_journal_checkpoint = service.journal.checkpoint()
    before_tick = world.world_tick
    before_time = float(world.data.time)
    before_native_arrays = {
        name: getattr(world.data, name).copy()
        for name in ("qpos", "qvel", "qacc", "act", "ctrl", "geom_xpos", "geom_xmat",
                     "site_xpos", "xpos", "cvel")
    }

    scene = service.scene_snapshot()

    assert scene["world_tick"] == before_tick == 23
    assert float(world.data.time) == before_time
    assert _checkpoint_digest(world) == before_digest
    assert service.journal.checkpoint() == before_journal_checkpoint
    for name, value in before_native_arrays.items():
        assert (getattr(world.data, name) == value).all()
    assert set(scene) == {
        "schema_version", "source", "world_tick", "model_sha256", "units",
        "up_axis", "geometries", "sites",
    }
    assert len(scene["model_sha256"]) == 64
    assert scene["model_sha256"] == world.checkpoint()["model_identity"]["asset_sha256"]
    assert "compiled_model_sha256" not in scene["model_sha256"]

    by_id = {item["id"]: item for item in scene["geometries"]}
    geom_id = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_GEOM, "scout_chassis")
    assert by_id["scout_chassis"]["position"] == pytest.approx(world.data.geom_xpos[geom_id].tolist())
    assert by_id["scout_chassis"]["position"][0] != pytest.approx(-4.0)
    site_id = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_SITE, "scout_sensor")
    site = next(item for item in scene["sites"] if item["id"] == "scout_sensor")
    assert site["position"] == pytest.approx(world.data.site_xpos[site_id].tolist())
    assert scene["geometries"] is not world.model.geom_pos
    allowed_names = {
        "floor", "corridor_south_wall", "corridor_north_wall_west",
        "corridor_north_wall_east", "west_wall", "east_wall", "scenario_occluder",
        "scout_chassis", "recovery_chassis", "recovery_pusher", "courier_chassis",
        "carton_geom", "heavy_box_geom", "parcel_geom", "alternate_block_geom",
    }
    assert {item["id"] for item in scene["geometries"]} <= allowed_names
    assert all(
        sum(value * value for value in item["quaternion"]) == pytest.approx(1.0, abs=1e-5)
        and all(0.0 <= channel <= 1.0 for channel in item["rgba"])
        for item in scene["geometries"]
    )
    assert all(
        all(value == value and abs(value) < 100.0
            for value in item["position"] + item["size"] + item.get("quaternion", []) + item.get("rgba", []))
        for item in scene["geometries"] + scene["sites"]
    )
    assert not any(key in scene for key in ("qpos", "qvel", "ctrl", "owner", "path", "secret"))
    assert all(not any(key in item for key in ("qpos", "owner", "path", "secret"))
               for item in scene["geometries"] + scene["sites"])
    service.close()
