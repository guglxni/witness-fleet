"""Canonical deterministic inert bootstrap fixtures for one corridor incident."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from witness_fleet.domain import SkillKind

_SCENARIOS = frozenset({"SC-001", "SC-002", "SC-003", "SC-004", "SC-005", "SC-008"})
_ROLES = ("scout", "recovery", "courier")
_OWNER_ACTIONS = ["travel", "recover", "deliver", "inspect", "verify", "hold", "wait"]
_RELEASE_ACTIONS = ["travel", "deliver"]
# Explicit native FacilityWorld contract values; avoid simulator imports here.
_FOOTPRINT_M = {"scout": 0.22, "recovery": 0.38, "courier": 0.50}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_MISSION_V2_TASKS = (
    ("scout-inspect", "scout", "inspect", {}, "inspected", []),
    ("recovery-recover", "recovery", "recover", {"target_displacement_m": 0.75},
     "obstruction_moved", ["obstacle_assessed"]),
    ("scout-park", "scout", "travel", {"target_x": -3.5, "target_y": -0.55}, "arrived", []),
    ("scout-verify", "scout", "verify", {}, "inspected", []),
    ("courier-approach", "courier", "travel", {"target_x": -3.5, "target_y": 0}, "arrived", []),
    ("courier-verify", "courier", "verify", {}, "inspected", []),
    ("courier-deliver", "courier", "deliver", {"target_x": 4, "target_y": 0},
     "delivered", ["recovery_verified", "courier_fit"]),
)


def bootstrap(graph, sources, *, prefix, scenario, seed, profile="inspection-v1"):
    """Retain a deterministic inert fixture using the selected manifest profile.

    ``inspection-v1`` is the byte-compatible default. ``mission-v2`` is an
    additive SC-001-only task plan. Neither profile creates claims, coordinator
    state, simulator commands, or release activation; setup approvals remain
    explicitly synthetic and are not human approval actions.
    """
    if not isinstance(profile, str) or profile not in {"inspection-v1", "mission-v2"}:
        raise ValueError("profile must be inspection-v1 or mission-v2")
    if profile == "mission-v2" and scenario != "SC-001":
        raise ValueError("mission-v2 profile is supported only for SC-001")
    if (not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,89}", prefix)):
        raise ValueError("prefix must be a trusted path-safe identifier of at most 90 characters")
    if not isinstance(scenario, str) or scenario not in _SCENARIOS:
        raise ValueError("scenario must be a known simulator scenario")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative exact integer")

    corridor_id = f"{prefix}-corridor-c"
    map_id = f"{prefix}-map"
    start_id = f"{prefix}-start"
    end_id = f"{prefix}-end"
    owner_id = f"{prefix}-owner"
    episode_id = f"{prefix}-episode"
    resource_id = f"{prefix}-corridor-workspace"
    if profile == "mission-v2":
        task_names = tuple(item[0] for item in _MISSION_V2_TASKS)
        task_ids = [f"{prefix}-task-{name}" for name in task_names]
    else:
        task_names = ("inspect", "recover", "verify", "park-scout", "deliver")
        task_ids = [f"{prefix}-task-{name}" for name in task_names]
    restriction_id = f"{prefix}-restriction-courier"
    release_id = f"{prefix}-release-courier"

    map_config = {
        "scenario": scenario,
        "seed": seed,
        "fixture_intent": "declared initial geometry only; no outcome is encoded",
        "corridor": {"x_min": -7, "x_max": 7, "y_min": -0.7, "y_max": 0.7},
        "inspection_viewpoints": [{"x": -3.5, "y": -0.55}],
        "safe_shoulder": {"x": -3.5, "y": -0.55},
        "courier_goal": {"x": 4, "y": 0},
        "sensor_ttl_ticks": 50,
    }
    manifest_result = {
        "prefix": prefix,
        "scenario": scenario,
        "seed": seed,
        "node_ids": [],
        "task_ids": task_ids,
        "release_id": release_id,
        "restrictions": [restriction_id],
        "corridor_id": corridor_id,
        "owners": [owner_id],
        "robots": list(_ROLES),
        "resources": [resource_id],
        "map_id": map_id,
        "episode_id": episode_id,
    }
    manifest_identity = {
        "kind": "canonical_inert_bootstrap",
        "version": 1,
        "prefix": prefix,
        "scenario": scenario,
        "seed": seed,
        "map_configuration": map_config,
    }
    if profile == "mission-v2":
        mission_task_plan = []
        for task_id, (key, robot_id, kind, parameters, effect, required) in zip(
                task_ids, _MISSION_V2_TASKS, strict=True):
            entry = {
                "key": key, "task_id": task_id, "robot_id": robot_id,
                "kind": kind, "parameters": parameters,
                "expected_effects": [effect], "required_predicates": required,
            }
            if key in {"courier-approach", "courier-deliver"}:
                entry["require_release"] = True
            mission_task_plan.append(entry)
        manifest_result.update(profile="mission-v2", task_plan=mission_task_plan)
        manifest_identity.update(kind="canonical_mission_bootstrap", version=2,
                                 profile="mission-v2")
    existing = graph.get_node("Episode", episode_id)
    if existing is not None:
        try:
            stored_manifest = json.loads(existing["payload_json"])
        except (KeyError, TypeError, json.JSONDecodeError):
            raise ValueError("bootstrap prefix conflict: existing incident manifest is invalid") from None
        if stored_manifest.get("identity") != manifest_identity:
            raise ValueError("bootstrap prefix conflict: existing incident has different scenario or seed")
        return stored_manifest["result"]

    node_ids: list[str] = []

    def node(label: str, node_id: str, attributes: dict[str, Any]) -> None:
        graph.append_node(label, node_id, attributes)
        node_ids.append(node_id)

    def edge(relationship: str, source_label: str, source_id: str,
             target_label: str, target_id: str) -> None:
        graph.append_edge(relationship, source_label, source_id, target_label, target_id)

    def evidence(source_key: str, display_name: str, text: str) -> tuple[str, str]:
        source_id = f"{prefix}-{source_key}"
        revision = sources.retain(source_id, text.encode("utf-8"))
        source_node = f"{source_id}-source"
        revision_node = f"{source_id}-revision"
        span_node = f"{source_id}-span"
        span = sources.validate_span(revision.revision_id, 0, len(revision.text), revision.text)
        node("Source", source_node, {
            "source_id": source_id,
            "source_type": "synthetic",
            "display_name": display_name,
            "access_class": "synthetic",
        })
        node("Revision", revision_node, {
            "revision_id": revision.revision_id,
            "content_hash": revision.bytes_hash,
            "normalized_hash": revision.normalized_hash,
            "normalizer_version": revision.normalizer_version,
        })
        node("EvidenceSpan", span_node, {
            "start_char": 0,
            "end_char": len(revision.text),
            "quote": revision.text,
            "quote_hash": span["quote_hash"],
        })
        edge("REVISION_OF", "Revision", revision_node, "Source", source_node)
        edge("IN_REVISION", "EvidenceSpan", span_node, "Revision", revision_node)
        return source_id, span_node

    # Retained declared-geometry fixture source; these values describe setup only.
    map_source_text = _json(map_config)
    evidence("scenario-map", "Synthetic declared map and initial setup", map_source_text)

    owner_text = _json({"owners": [{
        "owner_id": owner_id,
        "role": "maintenance_owner",
        "scope": [corridor_id],
        "actions": _OWNER_ACTIONS,
    }]})
    _, owner_span_id = evidence("owner-roster", "Synthetic maintenance owner roster", owner_text)

    policy_text = _json({
        "kind": "synthetic_bootstrap_policy_setup",
        "corridor_id": corridor_id,
        "restriction": "courier travel and delivery staged pending physical verification and release",
        "permissions_are_scoped_per_action_and_role": True,
        "not_a_human_approval": True,
    })
    _, policy_span_id = evidence("policy-setup", "Synthetic inert policy setup", policy_text)

    node("Map", map_id, {"map_version": 0, "configuration_hash": _hash(map_source_text)})
    node("Location", start_id, {"map_id": map_id, "map_version": 0, "nominal_width_m": 1.4})
    node("Location", end_id, {"map_id": map_id, "map_version": 0, "nominal_width_m": 1.4})
    node("Corridor", corridor_id, {"map_id": map_id, "map_version": 0, "nominal_width_m": 1.4})
    edge("IN_MAP", "Location", start_id, "Map", map_id)
    edge("IN_MAP", "Location", end_id, "Map", map_id)
    edge("IN_MAP", "Corridor", corridor_id, "Map", map_id)
    edge("FROM_LOCATION", "Corridor", corridor_id, "Location", start_id)
    edge("TO_LOCATION", "Corridor", corridor_id, "Location", end_id)

    node("Owner", owner_id, {
        "owner_type": "synthetic_fixture",
        "role": "maintenance_owner",
        "authority_scope": corridor_id,
    })
    edge("SUPPORTED_BY", "Owner", owner_id, "EvidenceSpan", owner_span_id)

    robots = {
        "scout": {"robot_type": "scout", "footprint_m": _FOOTPRINT_M["scout"], "payload_kg": 0.0,
                  "capability_version": 1, "available": True},
        "recovery": {"robot_type": "recovery", "footprint_m": _FOOTPRINT_M["recovery"], "payload_kg": 8.0,
                     "capability_version": 1, "available": True},
        "courier": {"robot_type": "courier", "footprint_m": 0.5, "payload_kg": 2.0,
                    "capability_version": 1, "available": True},
    }
    for robot_id in _ROLES:
        node("Robot", robot_id, robots[robot_id])

    node("Resource", resource_id, {
        "kind": "corridor_workspace",
        "resource_version": 0,
        "fence": 0,
    })

    action_role_pairs = [(action.value, role) for role in _ROLES for action in SkillKind]
    for action, role in action_role_pairs:
        key = f"permission-{role}-{action}"
        decision_id = f"{prefix}-decision-{key}"
        permission_id = f"{prefix}-{key}"
        approval_id = f"{prefix}-setup-approval-{key}"
        scope_json = _json({
            "corridor_id": corridor_id,
            "action_kinds": [action],
            "robot_types": [role],
        })
        node("Decision", decision_id, {
            "kind": "permission",
            "state": "active",
            "effective_clock_domain": "simulation_tick_v1",
            "effective_from_tick": 0,
            "effective_to_tick": None,
            "scope_json": scope_json,
        })
        node("Permission", permission_id, {
            "action_kind": action,
            "subject_scope": _json([role]),
            "condition_json": _json({"corridor_id": corridor_id, "action_kinds": [action]}),
            "state": "active",
        })
        node("ApprovalEvent", approval_id, {
            "actor_id": owner_id,
            "target_id": decision_id,
            "action": "approve",
            "expected_policy_epoch": 0,
            "event_id": approval_id,
        })
        edge("SUPPORTED_BY", "Decision", decision_id, "EvidenceSpan", policy_span_id)
        edge("OWNED_BY", "Decision", decision_id, "Owner", owner_id)
        edge("GRANTS", "Decision", decision_id, "Permission", permission_id)
        edge("APPLIES_TO", "Permission", permission_id, "Corridor", corridor_id)
        edge("APPROVES", "ApprovalEvent", approval_id, "Decision", decision_id)

    restriction_decision_id = f"{prefix}-decision-restriction-courier"
    restriction_scope = {
        "corridor_id": corridor_id,
        "action_kinds": _RELEASE_ACTIONS,
        "robot_types": ["courier"],
    }
    node("Decision", restriction_decision_id, {
        "kind": "restriction",
        "state": "active",
        "effective_clock_domain": "simulation_tick_v1",
        "effective_from_tick": 0,
        "effective_to_tick": None,
        "scope_json": _json(restriction_scope),
    })
    node("Restriction", restriction_id, {
        "rule_type": "prohibit",
        "subject_scope": _json(["courier"]),
        "condition_json": _json({"corridor_id": corridor_id, "action_kinds": _RELEASE_ACTIONS}),
        "state": "active",
    })
    restriction_approval_id = f"{prefix}-setup-approval-restriction-courier"
    node("ApprovalEvent", restriction_approval_id, {
        "actor_id": owner_id,
        "target_id": restriction_decision_id,
        "action": "approve",
        "expected_policy_epoch": 0,
        "event_id": restriction_approval_id,
    })
    edge("SUPPORTED_BY", "Decision", restriction_decision_id, "EvidenceSpan", policy_span_id)
    edge("OWNED_BY", "Decision", restriction_decision_id, "Owner", owner_id)
    edge("IMPOSES", "Decision", restriction_decision_id, "Restriction", restriction_id)
    edge("APPLIES_TO", "Restriction", restriction_id, "Corridor", corridor_id)
    edge("APPROVES", "ApprovalEvent", restriction_approval_id, "Decision", restriction_decision_id)

    release_text = _json({
        "kind": "release",
        "corridor_id": corridor_id,
        "restriction_id": restriction_id,
        "action_kinds": _RELEASE_ACTIONS,
        "robot_types": ["courier"],
        "required_predicates": ["recovery_verified", "courier_fit"],
    })
    _, release_span_id = evidence("release-conditions", "Synthetic staged release conditions", release_text)
    node("Release", release_id, {
        "state": "staged",
        "effective_clock_domain": "simulation_tick_v1",
        "effective_from_tick": 0,
        "effective_to_tick": None,
        "scope_json": _json(restriction_scope),
    })
    edge("SUPPORTED_BY", "Release", release_id, "EvidenceSpan", release_span_id)
    edge("LIFTS", "Release", release_id, "Restriction", restriction_id)
    edge("APPROVED_BY", "Release", release_id, "Owner", owner_id)

    if profile == "mission-v2":
        for index, task in enumerate(mission_task_plan):
            node("Task", task["task_id"], {
                "kind": task["kind"],
                "state": "READY",
                "task_version": 0,
                "required_predicates": _json(task["required_predicates"]),
                "priority": len(task_ids) - index,
                "claim_fence": 0,
            })
            edge("USES", "Task", task["task_id"], "Corridor", corridor_id)
            edge("REQUIRES_RESOURCE", "Task", task["task_id"], "Resource", resource_id)
            edge("ASSIGNED_TO", "Robot", task["robot_id"], "Task", task["task_id"])
        for task_id, prerequisite_id in zip(task_ids[1:], task_ids[:-1], strict=True):
            edge("DEPENDS_ON", "Task", task_id, "Task", prerequisite_id)
    else:
        task_robots = ("scout", "recovery", "courier", "scout", "courier")
        predicates = (
            [],
            ["obstacle_assessed"],
            [],  # Verification is an inspection task, not a gate on its own result.
            [],
            ["recovery_verified", "courier_fit"],
        )
        for index, (task_id, task_name, robot_id, required) in enumerate(
            zip(task_ids, task_names, task_robots, predicates, strict=True)
        ):
            node("Task", task_id, {
                "kind": "travel" if task_name == "park-scout" else task_name,
                "state": "READY",
                "task_version": 0,
                "required_predicates": _json(required),
                "priority": len(task_ids) - index,
                "claim_fence": 0,
            })
            edge("USES", "Task", task_id, "Corridor", corridor_id)
            edge("REQUIRES_RESOURCE", "Task", task_id, "Resource", resource_id)
            edge("ASSIGNED_TO", "Robot", robot_id, "Task", task_id)
        for task_id, prerequisite_id in zip(task_ids[1:], task_ids[:-1], strict=True):
            edge("DEPENDS_ON", "Task", task_id, "Task", prerequisite_id)
        # Delivery also waits for scout parking, without implying either has happened.
        edge("DEPENDS_ON", "Task", task_ids[-1], "Task", task_ids[-2])

    manifest_result["node_ids"] = list(dict.fromkeys(node_ids + [episode_id]))
    manifest_json = _json({"identity": manifest_identity, "result": manifest_result})
    node("Episode", episode_id, {
        "scenario_family": scenario,
        "outcome": "pending",
        "verification_state": "unverified",
        "configuration_hash": _hash(_json(map_config)),
        "payload_json": manifest_json,
    })
    edge("OCCURRED_AT", "Episode", episode_id, "Corridor", corridor_id)
    for robot_id in _ROLES:
        edge("INVOLVED_ROBOT", "Episode", episode_id, "Robot", robot_id)
    edge("ON_MAP", "Episode", episode_id, "Map", map_id)
    for task_id in task_ids:
        edge("CONTAINS", "Episode", episode_id, "Task", task_id)

    return manifest_result
