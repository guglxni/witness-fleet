"""Bounded, pose-local S0 observations; ground-truth model stays caller-private."""

from __future__ import annotations

import hashlib
import json

import mujoco
import numpy as np

MAX_RANGE_M = 4.0
OBSERVATION_LIFETIME_TICKS = 50
SENSOR_MODE = "S0"


def config_hash() -> str:
    config = {"mode": SENSOR_MODE, "max_range_m": MAX_RANGE_M, "lifetime_ticks": OBSERVATION_LIFETIME_TICKS, "rays": 9}
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def observe(world: object, robot_id: str) -> dict:
    """Synthesize scoped range and visibility from bounded rays, never truth labels."""
    if robot_id not in world._robot_body_ids:
        raise ValueError(f"unknown robot_id: {robot_id}")
    body_id = world._robot_body_ids[robot_id]
    site_id = world._robot_site_ids[robot_id]
    origin = (
        np.asarray(world.data.site_xpos[site_id], dtype=float).copy()
        if site_id >= 0
        else np.asarray(world.data.xpos[body_id], dtype=float).copy()
        + np.array([0.2 if robot_id == "recovery" else 0.3, 0.0, 0.03])
    )
    yaw = float(world.data.qpos[world._robot_qpos_adr[robot_id] + 2])
    ray_group = np.array([1, 1, 1, 1, 1, 0], dtype=np.uint8)
    ranges = []
    hit_geom = []
    for offset in np.linspace(-0.55, 0.55, 9):
        direction = np.array([np.cos(yaw + offset), np.sin(yaw + offset), 0.0])
        geom_id = np.array([-1], dtype=np.int32)
        # Include fixed fixtures and walls: they physically occlude rays even
        # though MuJoCo's query can optionally skip all static geometry.
        distance = mujoco.mj_ray(world.model, world.data, origin, direction, ray_group, True, body_id, geom_id)
        if distance < 0:
            ranges.append(MAX_RANGE_M)
            hit_geom.append(None)
        else:
            ranges.append(min(float(distance), MAX_RANGE_M))
            hit_geom.append(int(geom_id[0]) if distance <= MAX_RANGE_M else None)
    valid = [d for d in ranges if d < MAX_RANGE_M]
    visibility_fraction = len(valid) / len(ranges)

    gap = None
    obstruction = {"state": "unknown", "reason": "no_return_within_range"}
    object_name = world._obstruction_name
    oid = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_BODY, object_name)
    object_pos = np.asarray(world.data.xpos[oid], dtype=float).copy()
    relative = object_pos[:2] - origin[:2]
    distance_to_object = float(np.linalg.norm(relative))
    bearing = float(np.arctan2(relative[1], relative[0]) - yaw)
    bearing = float(np.arctan2(np.sin(bearing), np.cos(bearing)))
    object_geom = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_GEOM, f"{object_name}_geom")
    object_surface_distance = max(0.0, distance_to_object - float(np.linalg.norm(world.model.geom_size[object_geom, :2])))
    map_occluder_id = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_GEOM, "scenario_occluder")
    occluder_before_object = False
    if abs(bearing) <= 0.62 and object_surface_distance <= MAX_RANGE_M:
        ray_index = int(np.argmin(np.abs(np.linspace(-0.55, 0.55, 9) - bearing)))
        occluder_before_object = (
            hit_geom[ray_index] == map_occluder_id
            and ranges[ray_index] + float(world.model.geom_size[map_occluder_id, 0]) < object_surface_distance
        )
    detected = (
        abs(bearing) <= 0.62
        and object_surface_distance <= MAX_RANGE_M
        and object_geom in hit_geom
    )
    if detected:
        half_width = float(world.model.geom_size[object_geom, 1])
        center_y = float(object_pos[1])
        # A single opening must fit the largest robot. The other side of the
        # obstruction does not count as continuous free clearance.
        corridor_half_width = float(world._corridor_half_width)
        free_intervals = (center_y - half_width + corridor_half_width, corridor_half_width - center_y - half_width)
        gap_width = max(0.0, max(free_intervals))
        obstruction = {
            "state": "observed",
            "observed_pose": {"x": round(float(object_pos[0]), 4), "y": round(float(object_pos[1]), 4)},
            "range_m": round(distance_to_object, 3),
            "object_class": "box_like_obstruction",
        }
        gap = {
            "visibility": "visible",
            "width_m": [round(gap_width, 3), round(gap_width, 3)],
            "fits": {
                role: bool(gap_width >= footprint)
                for role, footprint in world._footprints.items()
            },
            "scope": "corridor-c-single-connected-clearance",
        }
    elif occluder_before_object:
        obstruction = {"state": "unknown", "reason": "occluded"}
    # Positive gate-clear evidence requires multiple unobstructed rays through a
    # declared connected lane. Missing obstacle returns alone remain unknown.
    if not detected and not occluder_before_object:
        lane_half_width = .30
        gate_x = 0.0
        coverage = []
        for lane_y in np.linspace(-lane_half_width, lane_half_width, 7):
            target = np.array([gate_x, lane_y, origin[2]])
            delta = target - origin
            target_distance = float(np.linalg.norm(delta))
            angle = float(np.arctan2(delta[1], delta[0]) - yaw)
            angle = float(np.arctan2(np.sin(angle), np.cos(angle)))
            if target_distance <= 0 or target_distance > MAX_RANGE_M or abs(angle) > .62:
                coverage.append(False)
                continue
            gid = np.array([-1], dtype=np.int32)
            hit_distance = mujoco.mj_ray(world.model, world.data, origin, delta / target_distance,
                                         ray_group, True, body_id, gid)
            coverage.append(hit_distance < 0 or hit_distance >= target_distance + .05)
        if all(coverage):
            obstruction = {'state': 'absent', 'reason': 'positive_gate_ray_coverage'}
            gap = {'visibility': 'visible', 'width_m': [.60, .60],
                   'fits': {role: footprint + .04 <= .60 for role, footprint in world._footprints.items()},
                   'scope': 'corridor-c-gate-ray-coverage'}
            visibility_fraction = 1.0
    if obstruction["state"] == "unknown" and min(ranges) < MAX_RANGE_M:
        obstruction["reason"] = "occluded"
        visibility_fraction = min(visibility_fraction, 0.2)
    visible = visibility_fraction >= 0.5
    return {
        "robot_id": robot_id,
        "world_tick": world.world_tick,
        "sensor": {
            "mode": SENSOR_MODE,
            "max_range_m": MAX_RANGE_M,
            "config_hash": config_hash(),
            "expires_tick": world.world_tick + OBSERVATION_LIFETIME_TICKS,
        },
        "pose": {"x": round(float(origin[0]), 4), "y": round(float(origin[1]), 4), "z": round(float(origin[2]), 4), "yaw": round(yaw, 5)},
        "visibility": {"fraction": round(visibility_fraction, 3), "state": "visible" if visible else "insufficient"},
        "obstruction": obstruction,
        "gap": gap,
        "ranges_m": [round(float(d), 3) for d in ranges],
    }
