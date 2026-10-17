"""Synthetic additive source fixture for atomic approval regression tests."""

import json
import uuid
from datetime import UTC, datetime, timedelta

from witness_fleet.domain import Observation, Pose
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.approval import ApprovalCommand, TrustedLocalPrincipal
from witness_fleet.runtime.storage import TransitionStore


def staged_fixture(graph, tmp_path):
    """Seed named synthetic approval data only in the caller's isolated graph."""
    sources = SourceStore(tmp_path / "sources")
    holder = "atomic-approval-test-holder"
    now = datetime.now(UTC)
    root = graph.read_version_root()
    assert root is not None
    lease = root.get("coordinator_lease_expires_at_utc")
    if lease is None or datetime.fromisoformat(lease.replace("Z", "+00:00")) <= now:
        acquired = TransitionStore(graph).acquire_coordinator(
            expected_epoch=root["coordinator_epoch"], holder_id=holder,
            now_utc=now.isoformat(), lease_expires_at_utc=(now + timedelta(minutes=5)).isoformat(),
            event_id="approval-test-barrier-" + uuid.uuid4().hex, effective_world_tick=0,
        )
        assert acquired is not None
    else:
        assert root["coordinator_holder_id"] == holder, "live foreign lease may not be overwritten"

    prefix = "aw-" + uuid.uuid4().hex[:16] + "-"
    ids = {name: prefix + name for name in ("corridor", "owner", "decision", "restriction", "release")}
    ids["holder"] = holder
    scope = {"corridor_id": ids["corridor"], "action_kinds": ["travel", "deliver"], "robot_types": ["courier"]}
    graph.append_node("Corridor", ids["corridor"], {"nominal_width_m": 1.4})

    def source_chain(name, document):
        source_id = prefix + name
        text = json.dumps(document, sort_keys=True, separators=(",", ":"))
        retained = sources.retain(source_id, text.encode())
        checked = sources.validate_span(retained.revision_id, 0, len(text), text)
        source_node, revision_node, span_node = (prefix + name + suffix for suffix in ("-source", "-revision", "-span"))
        graph.append_node("Source", source_node, {"source_id": source_id, "source_type": "synthetic",
                          "display_name": "Atomic approval fixture", "access_class": "synthetic"})
        graph.append_node("Revision", revision_node, {
            "revision_id": retained.revision_id, "content_hash": retained.bytes_hash,
            "normalized_hash": retained.normalized_hash, "normalizer_version": retained.normalizer_version,
        })
        graph.append_node("EvidenceSpan", span_node, {"start_char": 0, "end_char": len(text),
                          "quote": text, "quote_hash": checked["quote_hash"]})
        graph.append_edge("REVISION_OF", "Revision", revision_node, "Source", source_node)
        graph.append_edge("IN_REVISION", "EvidenceSpan", span_node, "Revision", revision_node)
        return span_node

    owner_span = source_chain("roster", {"owners": [{"owner_id": ids["owner"], "role": "maintenance_owner",
                                          "scope": [ids["corridor"]], "actions": ["travel", "deliver"]}]})
    restriction_span = source_chain("restriction-source", {"kind": "restriction", **scope})
    release_span = source_chain("release-source", {
        "kind": "release", **scope, "restriction_id": ids["restriction"],
        "required_predicates": ["recovery_verified", "courier_fit"],
    })
    graph.append_node("Owner", ids["owner"], {"role": "maintenance_owner", "authority_scope": ids["corridor"]})
    graph.append_edge("SUPPORTED_BY", "Owner", ids["owner"], "EvidenceSpan", owner_span)
    graph.append_node("Decision", ids["decision"], {"kind": "restriction", "state": "active",
                      "scope_json": json.dumps(scope), "effective_clock_domain": "world_tick",
                      "effective_from_tick": 0})
    graph.append_node("Restriction", ids["restriction"], {
        "state": "active", "rule_type": "prohibit", "subject_scope": json.dumps(["courier"]),
        "condition_json": json.dumps({"corridor_id": ids["corridor"], "action_kinds": ["travel", "deliver"]}),
    })
    graph.append_node("Release", ids["release"], {"state": "staged", "scope_json": json.dumps(scope),
                      "effective_clock_domain": "world_tick", "effective_from_tick": 0})
    graph.append_edge("OWNED_BY", "Decision", ids["decision"], "Owner", ids["owner"])
    graph.append_edge("SUPPORTED_BY", "Decision", ids["decision"], "EvidenceSpan", restriction_span)
    graph.append_edge("IMPOSES", "Decision", ids["decision"], "Restriction", ids["restriction"])
    graph.append_edge("APPLIES_TO", "Restriction", ids["restriction"], "Corridor", ids["corridor"])
    graph.append_edge("LIFTS", "Release", ids["release"], "Restriction", ids["restriction"])
    graph.append_edge("APPROVED_BY", "Release", ids["release"], "Owner", ids["owner"])
    graph.append_edge("SUPPORTED_BY", "Release", ids["release"], "EvidenceSpan", release_span)
    decision_approval = prefix + "initial-decision-approval"
    graph.append_node("ApprovalEvent", decision_approval, {"actor_id": ids["owner"], "target_id": ids["decision"],
                      "action": "approve", "expected_policy_epoch": 0, "event_id": decision_approval})
    graph.append_edge("APPROVES", "ApprovalEvent", decision_approval, "Decision", ids["decision"])

    for predicate in ("recovery_verified", "courier_fit"):
        observation = Observation(
            id=prefix + predicate, tenant_id=graph.tenant_id, episode_id=prefix + "episode", robot_id="courier",
            occurred_at=now, recorded_at=now, world_tick=10, expires_tick=60,
            predicate=predicate, value=True, pose=Pose(x=-3.5, y=-0.55), visibility="visible",
            scope={"corridor_id": ids["corridor"], "release_id": ids["release"],
                   "robot_type": "courier", "payload_class": "loaded"},
            quality={"lower_bound": 1.0}, sensor_config_hash="fixture-sensor-v1", subject_id=ids["corridor"],
        )
        graph.append_node("Observation", observation.id, {"predicate": predicate, "value": True,
                          "robot_id": "courier", "visibility": "visible", "expires_tick": 60,
                          "scope_json": json.dumps(dict(observation.scope)),
                          "payload_json": observation.model_dump_json()})
    principal = TrustedLocalPrincipal(actor_id=ids["owner"], tenant_id=graph.tenant_id,
                                      role="maintenance_owner", trust_mode="configured_local")
    final_root = graph.read_version_root()
    assert final_root is not None
    command = ApprovalCommand(event_id=prefix + "activation", target_id=ids["release"],
                              actor_id=principal.actor_id, tenant_id=graph.tenant_id,
                              expected_policy_epoch=final_root["policy_epoch"])
    return graph, sources, principal, command, ids
