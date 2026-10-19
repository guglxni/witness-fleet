"""Strict allowlist and schema boundary for the hosted MuJoCo scene DTO."""
from __future__ import annotations

import math
import re
from typing import Any

_GEOMETRIES = {
    "floor": ("plane", None),
    "corridor_south_wall": ("box", None),
    "corridor_north_wall_west": ("box", None),
    "corridor_north_wall_east": ("box", None),
    "west_wall": ("box", None),
    "east_wall": ("box", None),
    "scenario_occluder": ("box", None),
    "scout_chassis": ("cylinder", "scout"),
    "recovery_chassis": ("cylinder", "recovery"),
    "recovery_pusher": ("box", "recovery"),
    "courier_chassis": ("box", "courier"),
    "carton_geom": ("box", "carton"),
    "heavy_box_geom": ("box", "heavy_box"),
    "parcel_geom": ("box", "parcel"),
    "alternate_block_geom": ("box", "alternate_route_block"),
}
_SITES = frozenset({
    "south_staging", "north_staging", "recovery_bay", "delivery_zone",
    "scout_sensor", "recovery_sensor", "courier_sensor",
})
_TOP_KEYS = frozenset({
    "schema_version", "source", "world_tick", "model_sha256", "units",
    "up_axis", "geometries", "sites",
})
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MAX_ABS_COORDINATE = 100.0
_MAX_SIZE = 20.0


def _vector(value: Any, length: int, *, field: str, low: float, high: float) -> list[float]:
    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise ValueError(f"invalid {field}")
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int | float):
            raise ValueError(f"invalid {field}")
        number = float(item)
        if not math.isfinite(number) or number < low or number > high:
            raise ValueError(f"invalid {field}")
        result.append(number)
    return result


def sanitize_scene_snapshot(scene: Any) -> dict[str, Any]:
    """Validate and detach only the exact, bounded public scene contract."""
    if not isinstance(scene, dict) or set(scene) != _TOP_KEYS:
        raise ValueError("scene must contain only the v1 public fields")
    if (type(scene["schema_version"]) is not int or scene["schema_version"] != 1
            or scene["source"] != "mujoco_snapshot"
            or type(scene["world_tick"]) is not int or scene["world_tick"] < 0
            or not isinstance(scene["model_sha256"], str)
            or not _HEX_DIGEST.fullmatch(scene["model_sha256"])
            or scene["units"] != "m" or scene["up_axis"] != "z"):
        raise ValueError("scene header does not match schema v1")
    geometries, sites = scene["geometries"], scene["sites"]
    if not isinstance(geometries, list) or len(geometries) > 64:
        raise ValueError("scene geometry count exceeds contract")
    if not isinstance(sites, list) or len(sites) > 16:
        raise ValueError("scene site count exceeds contract")

    detached_geometries = []
    seen_geometry_ids: set[str] = set()
    geometry_fields = {"id", "kind", "position", "quaternion", "size", "rgba", "body"}
    for geometry in geometries:
        if not isinstance(geometry, dict) or set(geometry) != geometry_fields:
            raise ValueError("geometry must contain only public primitive fields")
        ident = geometry["id"]
        if not isinstance(ident, str) or ident in seen_geometry_ids or ident not in _GEOMETRIES:
            raise ValueError("geometry identity is not allowlisted")
        kind, body = _GEOMETRIES[ident]
        if geometry["kind"] != kind or geometry["body"] != body:
            raise ValueError("geometry kind or body does not match allowlist")
        position = _vector(geometry["position"], 3, field="position",
                           low=-_MAX_ABS_COORDINATE, high=_MAX_ABS_COORDINATE)
        quaternion = _vector(geometry["quaternion"], 4, field="quaternion", low=-1.000001, high=1.000001)
        norm = math.sqrt(sum(component * component for component in quaternion))
        if not math.isfinite(norm) or abs(norm - 1.0) > 1e-5:
            raise ValueError("geometry quaternion must be normalized wxyz")
        size = _vector(geometry["size"], 3, field="size", low=0.0, high=_MAX_SIZE)
        rgba = _vector(geometry["rgba"], 4, field="rgba", low=0.0, high=1.0)
        detached_geometries.append({
            "id": ident, "kind": kind, "position": position, "quaternion": quaternion,
            "size": size, "rgba": rgba, "body": body,
        })
        seen_geometry_ids.add(ident)

    detached_sites = []
    seen_site_ids: set[str] = set()
    for site in sites:
        if not isinstance(site, dict) or set(site) != {"id", "position", "size"}:
            raise ValueError("site must contain only public fields")
        ident = site["id"]
        if not isinstance(ident, str) or ident not in _SITES or ident in seen_site_ids:
            raise ValueError("site identity is not allowlisted")
        position = _vector(site["position"], 3, field="site position",
                           low=-_MAX_ABS_COORDINATE, high=_MAX_ABS_COORDINATE)
        size = _vector(site["size"], 3, field="site size", low=0.0, high=_MAX_SIZE)
        detached_sites.append({"id": ident, "position": position, "size": size})
        seen_site_ids.add(ident)

    return {
        "schema_version": 1, "source": "mujoco_snapshot",
        "world_tick": scene["world_tick"], "model_sha256": scene["model_sha256"],
        "units": "m", "up_axis": "z", "geometries": detached_geometries,
        "sites": detached_sites,
    }
