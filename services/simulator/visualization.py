"""Read-only projection of allowlisted compiled MuJoCo scene primitives."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from witness_fleet.hosting.scene import sanitize_scene_snapshot

# Names are the only scene entities exposed. The public sanitizer independently
# checks this allowlist so accidental additions here cannot expose native names.
_GEOMETRY_ALLOWLIST = {
    "floor", "corridor_south_wall", "corridor_north_wall_west",
    "corridor_north_wall_east", "west_wall", "east_wall", "scenario_occluder",
    "scout_chassis", "recovery_chassis", "recovery_pusher", "courier_chassis",
    "carton_geom", "heavy_box_geom", "parcel_geom", "alternate_block_geom",
}
_SITE_ALLOWLIST = {
    "south_staging", "north_staging", "recovery_bay", "delivery_zone",
    "scout_sensor", "recovery_sensor", "courier_sensor",
}
_GEOMETRY_KINDS = {
    int(mujoco.mjtGeom.mjGEOM_PLANE): "plane",
    int(mujoco.mjtGeom.mjGEOM_BOX): "box",
    int(mujoco.mjtGeom.mjGEOM_CYLINDER): "cylinder",
    int(mujoco.mjtGeom.mjGEOM_SPHERE): "sphere",
}
_MAX_GEOMETRIES = 64
_MAX_SITES = 16


def primitive_size_xyz(geom_type: int, raw_size: Any) -> list[float]:
    """Map MuJoCo sizes to xyz; cylinders use [radius, radius, half-height].

    Boxes retain half-extents, spheres expand their radius to xyz, and plane
    dimensions retain MuJoCo's compiled [half-width, half-height, depth] values.
    No full extents are inferred or fabricated.
    """
    values = [float(value) for value in raw_size]
    if geom_type == int(mujoco.mjtGeom.mjGEOM_PLANE):
        return values[:3]
    if geom_type == int(mujoco.mjtGeom.mjGEOM_BOX):
        return values[:3]
    if geom_type == int(mujoco.mjtGeom.mjGEOM_CYLINDER):
        return [values[0], values[0], values[1]]
    if geom_type == int(mujoco.mjtGeom.mjGEOM_SPHERE):
        return [values[0], values[0], values[0]]
    raise ValueError("unsupported MuJoCo primitive type")


def _id_name(model, object_type, object_id: int) -> str | None:
    return mujoco.mj_id2name(model, object_type, object_id)


def project_scene_snapshot(world) -> dict[str, Any]:
    """Return detached public scene data without stepping or forwarding physics.

    `model_sha256` intentionally fingerprints the facility XML source asset, not
    a claimed hash of MuJoCo's compiled in-memory representation.
    """
    if getattr(world, "_closed", False):
        raise RuntimeError("facility world is closed")
    model, data = world.model, world.data
    geometries = []
    for geom_id in range(model.ngeom):
        ident = _id_name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id)
        if ident not in _GEOMETRY_ALLOWLIST:
            continue
        geom_type = int(model.geom_type[geom_id])
        kind = _GEOMETRY_KINDS.get(geom_type)
        if kind is None:
            raise ValueError("allowlisted MuJoCo geometry is not a supported primitive")
        body_id = int(model.geom_bodyid[geom_id])
        body = None if body_id == 0 else _id_name(model, mujoco.mjtObj.mjOBJ_BODY, body_id)
        rotation = data.geom_xmat[geom_id]
        quaternion = np.zeros(4, dtype=float)
        mujoco.mju_mat2Quat(quaternion, rotation)
        geometries.append({
            "id": ident,
            "kind": kind,
            "position": [float(value) for value in data.geom_xpos[geom_id]],
            "quaternion": [float(value) for value in quaternion],
            "size": primitive_size_xyz(geom_type, model.geom_size[geom_id]),
            "rgba": [float(value) for value in model.geom_rgba[geom_id]],
            "body": body,
        })
    if len(geometries) > _MAX_GEOMETRIES:
        raise ValueError("compiled scene geometry count exceeds contract")

    sites = []
    for site_id in range(model.nsite):
        ident = _id_name(model, mujoco.mjtObj.mjOBJ_SITE, site_id)
        if ident not in _SITE_ALLOWLIST:
            continue
        radius = float(model.site_size[site_id, 0])
        sites.append({
            "id": ident,
            "position": [float(value) for value in data.site_xpos[site_id]],
            "size": [radius, radius, radius],
        })
    if len(sites) > _MAX_SITES:
        raise ValueError("compiled scene site count exceeds contract")

    asset = Path(__file__).with_name("assets") / "facility.xml"
    scene = {
        "schema_version": 1,
        "source": "mujoco_snapshot",
        "world_tick": world.world_tick,
        "model_sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
        "units": "m",
        "up_axis": "z",
        "geometries": geometries,
        "sites": sites,
    }
    return sanitize_scene_snapshot(scene)
