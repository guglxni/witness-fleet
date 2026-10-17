"""Complete tenant-wide validation of source-bound canonical governance roots."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from witness_fleet.domain import GovernanceWitness, SkillKind

_GOVERNANCE_LABELS = ("Decision", "Restriction", "Permission", "Release", "ApprovalEvent", "Owner")
_ROLE_TYPES = {"scout", "recovery", "courier"}
_POLICY_KINDS = {"restriction", "permission", "release"}


def validate_governance(snapshot: dict[str, Any], source_store: Any) -> tuple[tuple[GovernanceWitness, ...], tuple[str, ...]]:
    """Validate every governance root and return witnesses plus tenant-wide errors.

    Expected input is a materialized graph snapshot with ``nodes`` and ``edges``.
    SourceStore is the append-only retained-source reader. Missing or invalid graph
    material never becomes positive authority; a witness is still emitted for each
    Restriction, Permission and Release root so callers can retain the failure.
    """
    errors: set[str] = set()
    witnesses: list[GovernanceWitness] = []
    node_lists: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in snapshot.get("nodes", ()):
        if isinstance(node, dict) and isinstance(node.get("id"), str):
            node_lists[node["id"]].append(node)
        else:
            errors.add("INVALID_GOVERNANCE_NODE:missing-id")
    nodes = {node_id: values[0] for node_id, values in node_lists.items()}
    duplicate_ids = {node_id for node_id, values in node_lists.items() if len(values) > 1}
    for node_id in duplicate_ids:
        errors.add(f"DUPLICATE_NODE_ID:{node_id}")

    edges = [edge for edge in snapshot.get("edges", ()) if isinstance(edge, dict)]

    def labels(node: dict[str, Any] | None) -> set[str]:
        value = node.get("labels", ()) if node else ()
        return set(value) if isinstance(value, (list, tuple, set)) else set()

    def linked(node_id: str, relationship: str, label: str | None = None, *, reverse: bool = False
               ) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for edge in edges:
            if edge.get("relationship") != relationship:
                continue
            endpoint = edge.get("source_id") if reverse else edge.get("target_id")
            origin = edge.get("target_id") if reverse else edge.get("source_id")
            if origin != node_id or not isinstance(endpoint, str):
                continue
            item = nodes.get(endpoint)
            if item is None or (label is not None and label not in labels(item)):
                continue
            expected_edge_label = edge.get("source_label" if reverse else "target_label")
            if expected_edge_label is not None and label is not None and expected_edge_label != label:
                continue
            found.append(item)
        return found

    def exactly_one(items: list[dict[str, Any]]) -> dict[str, Any] | None:
        return items[0] if len(items) == 1 else None

    def report(code: str, node_id: str) -> None:
        errors.add(f"{code}:{node_id}")

    def parse_scope(node: dict[str, Any], report_id: str) -> dict[str, Any] | None:
        try:
            scope = json.loads(node["scope_json"])
            if not isinstance(scope, dict) or set(scope) != {"corridor_id", "action_kinds", "robot_types"}:
                raise ValueError("scope fields")
            corridor_id = scope["corridor_id"]
            action_kinds = scope["action_kinds"]
            robot_types = scope["robot_types"]
            if not isinstance(corridor_id, str) or not corridor_id or corridor_id in {"*", "all"}:
                raise ValueError("corridor must be exact")
            if not isinstance(action_kinds, list) or not action_kinds:
                raise ValueError("actions must be explicit")
            if not isinstance(robot_types, list) or not robot_types:
                raise ValueError("roles must be explicit")
            if any(not isinstance(action, str) for action in action_kinds):
                raise ValueError("action type")
            if any(not isinstance(role, str) or role not in _ROLE_TYPES for role in robot_types):
                raise ValueError("role must be explicit")
            if len(set(action_kinds)) != len(action_kinds) or len(set(robot_types)) != len(robot_types):
                raise ValueError("duplicate scope")
            parsed_actions = [SkillKind(action) for action in action_kinds]
            corridor = nodes.get(corridor_id)
            if corridor is None or "Corridor" not in labels(corridor):
                raise ValueError("unknown corridor")
            return {"corridor_id": corridor_id, "action_kinds": tuple(parsed_actions),
                    "robot_types": tuple(robot_types)}
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            report("INVALID_SCOPE", report_id)
            return None

    def source_chain(governance_node: dict[str, Any], report_id: str
                     ) -> tuple[dict[str, Any] | None, bool]:
        try:
            span = exactly_one(linked(governance_node["id"], "SUPPORTED_BY", "EvidenceSpan"))
            if span is None:
                raise ValueError("expected one EvidenceSpan")
            revision = exactly_one(linked(span["id"], "IN_REVISION", "Revision"))
            if revision is None:
                raise ValueError("expected one Revision")
            source = exactly_one(linked(revision["id"], "REVISION_OF", "Source"))
            if source is None:
                raise ValueError("expected one Source")
            if source_store is None:
                raise ValueError("source store unavailable")
            retained = source_store.get(revision["revision_id"])
            if (revision["revision_id"] != retained.revision_id
                    or source.get("source_id") != retained.source_id
                    or revision.get("source_id", retained.source_id) != retained.source_id
                    or revision["content_hash"] != retained.bytes_hash
                    or revision["normalized_hash"] != retained.normalized_hash
                    or revision["normalizer_version"] != retained.normalizer_version):
                raise ValueError("retained revision identity/hash mismatch")
            actual = source_store.validate_span(
                retained.revision_id, span["start_char"], span["end_char"], span["quote"]
            )
            quote_hash = hashlib.sha256(span["quote"].encode("utf-8")).hexdigest()
            if (actual["quote_hash"] != quote_hash or span["quote_hash"] != quote_hash
                    or actual["normalized_hash"] != revision["normalized_hash"]):
                raise ValueError("retained locator/hash mismatch")
            return span, True
        except (AttributeError, KeyError, OSError, TypeError, ValueError):
            report("INVALID_SOURCE_CHAIN", report_id)
            return None, False

    def owner_roster_valid(owner, scope, report_id):
        if owner is None or scope is None:
            report("INVALID_OWNER_ROSTER", report_id)
            return False
        span, valid = source_chain(owner, report_id)
        try:
            if not valid or span is None:
                raise ValueError("missing owner source")
            revision = exactly_one(linked(span['id'], 'IN_REVISION', 'Revision'))
            if revision is None or source_store is None:
                raise ValueError('missing retained roster revision')
            retained = source_store.get(revision['revision_id'])
            retained_text = retained.text_path.read_text(encoding='utf-8')
            if (span['start_char'] != 0 or span['end_char'] != len(retained_text)
                    or span['quote'] != retained_text):
                raise ValueError('owner roster must cover full retained document')
            document = json.loads(span["quote"])
            if not isinstance(document, dict) or set(document) != {'owners'}:
                raise ValueError('owner roster requires one typed document')
            owners = document["owners"]
            if not isinstance(owners, list) or not owners:
                raise ValueError("owner roster must be explicit")
            action_enum = {'travel', 'recover', 'deliver', 'inspect', 'verify', 'hold', 'wait'}
            ids = []
            for row in owners:
                if (not isinstance(row, dict)
                        or set(row) != {'owner_id', 'role', 'scope', 'actions'}
                        or not isinstance(row['owner_id'], str) or not row['owner_id']
                        or not isinstance(row['role'], str) or not row['role']
                        or not isinstance(row['scope'], list) or not row['scope']
                        or not all(isinstance(value, str) and value and value not in {'*', 'all'}
                                   for value in row['scope'])
                        or len(set(row['scope'])) != len(row['scope'])
                        or not isinstance(row['actions'], list) or not row['actions']
                        or not all(isinstance(value, str) and value in action_enum for value in row['actions'])
                        or len(set(row['actions'])) != len(row['actions'])):
                    raise ValueError('owner roster requires duplicate-free typed scopes')
                ids.append(row['owner_id'])
            if len(ids) != len(set(ids)):
                raise ValueError('duplicate roster owner identities')
            matches = [entry for entry in owners if isinstance(entry, dict)
                       and entry.get("owner_id") == owner["id"]]
            if len(matches) != 1:
                raise ValueError("owner identity ambiguous")
            entry = matches[0]
            if (entry.get("role") != "maintenance_owner"
                    or not isinstance(entry.get("scope"), list)
                    or scope["corridor_id"] not in entry["scope"]
                    or not isinstance(entry.get("actions"), list)
                    or not set(scope["action_kinds"]).issubset(set(entry["actions"]))):
                raise ValueError("roster scope mismatch")
            return True
        except (KeyError, TypeError, ValueError):
            report("INVALID_OWNER_ROSTER", report_id)
            return False

    def typed_policy_valid(policy, kind, scope, report_id):
        try:
            if scope is None:
                raise ValueError("scope missing")
            roles = json.loads(policy["subject_scope"])
            conditions = json.loads(policy["condition_json"])
            if (not isinstance(roles, list) or set(roles) != set(scope["robot_types"])
                    or not isinstance(conditions, dict)
                    or set(conditions) != {"corridor_id", "action_kinds"}
                    or conditions["corridor_id"] != scope["corridor_id"]
                    or not isinstance(conditions["action_kinds"], list)
                    or set(conditions["action_kinds"]) != set(scope["action_kinds"])):
                raise ValueError("typed scope mismatch")
            if kind == "permission" and policy.get("action_kind") not in scope["action_kinds"]:
                raise ValueError("permission action mismatch")
            if kind == "restriction" and policy.get("rule_type") != "prohibit":
                raise ValueError("unknown restriction rule")
            return True
        except (KeyError, TypeError, ValueError):
            report("INVALID_TYPED_POLICY", report_id)
            return False

    def approval_events(target: dict[str, Any], owner: dict[str, Any] | None,
                        *, required: bool, report_id: str) -> bool:
        events = linked(target["id"], "APPROVES", "ApprovalEvent", reverse=True)
        if len(events) != 1:
            if required or events:
                report("INVALID_APPROVAL", report_id)
            return False
        event = events[0]
        expected_epoch = event.get("expected_policy_epoch")
        valid = (owner is not None and event.get("actor_id") == owner["id"]
                 and event.get("target_id") == target["id"]
                 and event.get("action") == "approve"
                 and type(expected_epoch) is int and expected_epoch >= 0)
        if not valid:
            report("INVALID_APPROVAL", report_id)
        if "Release" in labels(target) and not release_activation_valid(target, event, owner):
            report("INVALID_ACTIVATION_PROVENANCE", report_id)
            return False
        return valid

    def release_activation_valid(target, approval, owner):
        """Bind historical release authority to its exact committed outbox evidence.

        Hashes bind identities, not authentication. Only the local graph writer may
        create these canonical records; arbitrary JSON is never positive authority.
        """
        from witness_fleet.domain import DispatchEvent, canonical_json_hash
        from witness_fleet.runtime.approval import ApprovalCommand

        def counter(value, minimum=0):
            return type(value) is int and value >= minimum

        try:
            activation = exactly_one(linked(target["id"], "DELIVERS", "DispatchEvent", reverse=True))
            if activation is None or owner is None:
                return False
            intent = ApprovalCommand.model_validate(json.loads(approval["payload_json"]))
            intent_hash = canonical_json_hash(intent)
            event = DispatchEvent.model_validate({
                key: activation[key] for key in (
                    "id", "tenant_id", "sequence", "coordinator_epoch", "kind",
                    "payload_hash", "effective_world_tick",
                )
            } | {"payload": json.loads(activation["payload_json"])})
            payload = event.model_dump(mode="json")["payload"]
            if set(payload) != {"policy_epoch", "expected_previous_policy_epoch", "policy_proof"}:
                return False
            proof = payload["policy_proof"]
            expected_proof_fields = {
                "proof_id", "coordinator_epoch", "approval_hash", "target_id",
                "actor_id", "restriction_id", "span_id", "owner_span_id",
            }
            if not isinstance(proof, dict) or set(proof) != expected_proof_fields:
                return False
            restriction = exactly_one(linked(target["id"], "LIFTS", "Restriction"))
            span = exactly_one(linked(target["id"], "SUPPORTED_BY", "EvidenceSpan"))
            owner_span = exactly_one(linked(owner["id"], "SUPPORTED_BY", "EvidenceSpan"))
            if restriction is None or span is None or owner_span is None:
                return False
            expected_epoch = approval["expected_policy_epoch"]
            counters = (
                approval["dispatch_sequence"], approval["coordinator_epoch"],
                approval["effective_world_tick"], approval["graph_version"],
                payload["policy_epoch"], payload["expected_previous_policy_epoch"],
                proof["coordinator_epoch"],
            )
            if not all(counter(value) for value in counters) or not counter(expected_epoch):
                return False
            if (intent.event_id != event.id or approval["event_id"] != event.id
                    or activation["event_id"] != event.id
                    or approval["activation_event_id"] != event.id
                    or event.kind != "POLICY_ACTIVATION"
                    or approval["tenant_id"] != intent.tenant_id or intent.tenant_id != event.tenant_id
                    or intent.actor_id != approval["actor_id"] or intent.actor_id != owner["id"]
                    or intent.target_id != target["id"] or approval["target_id"] != target["id"]
                    or intent.expected_policy_epoch != expected_epoch
                    or intent_hash != approval["payload_hash"]
                    or approval["action"] != "approve" or intent.action != "approve"
                    or target["approval_event_id"] != approval["id"]
                    or approval["dispatch_sequence"] != event.sequence
                    or approval["coordinator_epoch"] != event.coordinator_epoch
                    or approval["effective_world_tick"] != event.effective_world_tick
                    or payload["expected_previous_policy_epoch"] != expected_epoch
                    or payload["policy_epoch"] != expected_epoch + 1
                    or proof != {
                        "proof_id": approval["id"], "coordinator_epoch": event.coordinator_epoch,
                        "approval_hash": intent_hash, "target_id": target["id"],
                        "actor_id": owner["id"], "restriction_id": restriction["id"],
                        "span_id": span["id"], "owner_span_id": owner_span["id"],
                    }):
                return False
            subjects = [target["id"], restriction["id"], owner["id"], span["id"],
                        owner_span["id"], approval["id"]]
            if json.loads(activation["subject_ids_json"]) != subjects:
                return False
            if len(linked(approval["id"], "APPROVES")) != 1:
                return False
            if sum("DispatchEvent" in labels(node) and node.get("sequence") == event.sequence
                   for node in nodes.values()) != 1:
                return False
            versions = snapshot["versions"]
            if not all(counter(versions[key]) for key in (
                    "policy_epoch", "graph_version", "coordinator_epoch", "dispatch_sequence")):
                return False
            from witness_fleet.graph.verification import validate_release_verification

            scope = json.loads(target['scope_json'])
            if not isinstance(approval.get('created_at'), str):
                return False
            if not validate_release_verification(
                    snapshot['nodes'], approval['verification_json'], tenant_id=intent.tenant_id,
                    corridor_id=scope['corridor_id'], release_id=target['id'],
                    approved_at=datetime.fromisoformat(approval['created_at'].replace('Z', '+00:00')),
                    effective_tick=event.effective_world_tick):
                return False
            return (versions["policy_epoch"] >= payload["policy_epoch"]
                    and versions["graph_version"] >= approval["graph_version"]
                    and versions["coordinator_epoch"] >= event.coordinator_epoch
                    and versions["dispatch_sequence"] >= event.sequence)
        except (KeyError, TypeError, ValueError):
            return False

    def owner_for(decision: dict[str, Any] | None, *, release: dict[str, Any] | None,
                  report_id: str) -> dict[str, Any] | None:
        if decision is not None:
            owner = exactly_one(linked(decision["id"], "OWNED_BY", "Owner"))
        elif release is not None:
            owner = exactly_one(linked(release["id"], "APPROVED_BY", "Owner"))
        else:
            owner = None
        if owner is None:
            report("DETACHED_GOVERNANCE", report_id)
        return owner

    decision_context: dict[str, dict[str, Any]] = {}
    for decision in (node for node in nodes.values() if "Decision" in labels(node)):
        decision_id = decision["id"]
        imposed = linked(decision_id, "IMPOSES", "Restriction")
        granted = linked(decision_id, "GRANTS", "Permission")
        children = imposed + granted
        report_id = (children[0]["id"] if len(children) == 1 else
                     children[0]["id"] if children else decision_id)
        local_before = set(errors)
        if not children:
            report("DETACHED_GOVERNANCE", decision_id)
        owner = owner_for(decision, release=None, report_id=report_id)
        scope = parse_scope(decision, report_id)
        span, source_valid = source_chain(decision, report_id)
        if owner is not None and scope is not None and (
                owner.get("role") != "maintenance_owner"
                or owner.get("authority_scope") != scope["corridor_id"]):
            report("INVALID_OWNER_SCOPE", report_id)
        owner_roster_valid(owner, scope, report_id)
        state = decision.get("state", "staged")
        if state not in {"active", "staged"}:
            report("INVALID_STATE", report_id)
        required_decision_approval = state == "active"
        approved = approval_events(
            decision, owner, required=required_decision_approval, report_id=decision_id
        )
        decision_context[decision_id] = {
            "decision": decision, "owner": owner, "scope": scope, "span": span,
            "source_valid": source_valid, "approved": approved and state == "active",
            "state": state,
        }
        if report_id == decision_id and not children:
            # An unattached Decision root is explicitly surfaced even if its evidence
            # and owner edges are otherwise intact.
            report("DETACHED_GOVERNANCE", decision_id)
        if errors - local_before and not children:
            report("AMBIGUOUS_GOVERNANCE", decision_id)

    for policy in (node for node in nodes.values()
                   if labels(node) & {"Restriction", "Permission"}):
        policy_id = policy["id"]
        kind = "restriction" if "Restriction" in labels(policy) else "permission"
        relation = "IMPOSES" if kind == "restriction" else "GRANTS"
        parents = linked(policy_id, relation, "Decision", reverse=True)
        context = decision_context.get(parents[0]["id"]) if len(parents) == 1 else None
        if context is None:
            report("DETACHED_GOVERNANCE", policy_id)
        state = policy.get("state", "staged")
        if state not in {"active", "staged"}:
            report("INVALID_STATE", policy_id)
        scope = context["scope"] if context else None
        targets = linked(policy_id, "APPLIES_TO", "Corridor")
        if len(targets) != 1 or scope is None or targets[0]["id"] != scope["corridor_id"]:
            report("INVALID_APPLIES_TO", policy_id)
        if context is None:
            report("DETACHED_GOVERNANCE", policy_id)
            continue
        typed_policy_valid(policy, kind, scope, policy_id)
        if context is not None and scope is not None:
            decision_state = context["state"]
            effective_state = "active" if state == "active" and decision_state == "active" else "staged"
            witness_errors = tuple(sorted(error for error in errors
                                          if error.endswith(f":{policy_id}")
                                          or error.endswith(f":{parents[0]['id']}")))
            owner = context["owner"]
            span = context["span"]
            try:
                witness = GovernanceWitness(
                    id=policy_id, kind=kind, decision_id=parents[0]["id"],
                    owner_id=owner["id"] if owner else "missing-owner",
                    span_id=span["id"] if span else "missing-span",
                    corridor_id=scope["corridor_id"], action_kinds=scope["action_kinds"],
                    robot_types=scope["robot_types"], state=effective_state,
                    effective_from_tick=context["decision"].get("effective_from_tick", 0),
                    effective_to_tick=context["decision"].get("effective_to_tick"),
                    source_valid=context["source_valid"],
                    owner_valid=(owner is not None and owner.get("role") == "maintenance_owner"
                                 and owner.get("authority_scope") == scope["corridor_id"]),
                    approved=context["approved"], integrity_errors=witness_errors,
                )
                witnesses.append(witness)
            except (KeyError, TypeError, ValueError):
                report("INVALID_GOVERNANCE_INTERVAL", policy_id)
        if kind == "permission" and scope is not None:
            # Positive authority is never widened by wildcard corridor or role values;
            # parse_scope rejects these, this guard documents and defends the invariant.
            if scope["corridor_id"] in {"*", "all"} or any(
                    role in {"*", "all", "all_entry"} for role in scope["robot_types"]):
                report("INVALID_SCOPE", policy_id)

    for release in (node for node in nodes.values() if "Release" in labels(node)):
        release_id = release["id"]
        restrictions = linked(release_id, "LIFTS", "Restriction")
        restriction = exactly_one(restrictions)
        if restriction is None:
            report("DETACHED_GOVERNANCE", release_id)
        owner = owner_for(None, release=release, report_id=release_id)
        scope = parse_scope(release, release_id)
        span, source_valid = source_chain(release, release_id)
        if owner is not None and scope is not None and (
                owner.get("role") != "maintenance_owner"
                or owner.get("authority_scope") != scope["corridor_id"]):
            report("INVALID_OWNER_SCOPE", release_id)
        roster_valid = owner_roster_valid(owner, scope, release_id)
        owner_valid = (roster_valid and owner is not None and scope is not None
                       and owner.get("role") == "maintenance_owner"
                       and owner.get("authority_scope") == scope["corridor_id"])
        state = release.get("state", "staged")
        if state not in {"staged", "released"}:
            report("INVALID_STATE", release_id)
        approved = approval_events(release, owner, required=state == "released", report_id=release_id)
        if scope is not None and restriction is not None:
            parents = linked(restriction["id"], "IMPOSES", "Decision", reverse=True)
            original = decision_context.get(parents[0]["id"]) if len(parents) == 1 else None
            original_scope = original["scope"] if original else None
            if (original_scope is None or scope["corridor_id"] != original_scope["corridor_id"]
                    or not set(scope["action_kinds"]).issubset(set(original_scope["action_kinds"]))
                    or not set(scope["robot_types"]).issubset(set(original_scope["robot_types"]))):
                report("RELEASE_SCOPE_BROADENS", release_id)
        if scope is not None:
            try:
                witnesses.append(GovernanceWitness(
                    id=release_id, kind="release",
                    decision_id=release_id,
                    owner_id=owner["id"] if owner else "missing-owner",
                    span_id=span["id"] if span else "missing-span",
                    corridor_id=scope["corridor_id"], action_kinds=scope["action_kinds"],
                    robot_types=scope["robot_types"], state=state,
                    effective_from_tick=release.get("effective_from_tick", 0),
                    effective_to_tick=release.get("effective_to_tick"),
                    restriction_id=restriction["id"] if restriction else None,
                    source_valid=source_valid,
                    owner_valid=owner_valid,
                    approved=(state == "released" and approved and source_valid and owner_valid),
                    integrity_errors=tuple(sorted(error for error in errors
                                                  if error.endswith(f":{release_id}")
                                                  or (restriction is not None and
                                                      error.endswith(f":{restriction['id']}")))),
                ))
            except (KeyError, TypeError, ValueError):
                report("INVALID_GOVERNANCE_INTERVAL", release_id)

    # Every ApprovalEvent and Owner is a root in the tenant-wide scan, not merely
    # an optional endpoint reached from a valid restriction.
    for event in (node for node in nodes.values() if "ApprovalEvent" in labels(node)):
        event_id = event["id"]
        targets = linked(event_id, "APPROVES", reverse=False)
        valid_targets = [node for node in targets if labels(node) & {"Decision", "Release"}]
        if len(valid_targets) != 1:
            report("DETACHED_GOVERNANCE", event_id)
        elif event.get("target_id") != valid_targets[0]["id"] or event.get("action") != "approve":
            report("INVALID_APPROVAL", event_id)

    for owner in (node for node in nodes.values() if "Owner" in labels(node)):
        owner_id = owner["id"]
        decisions = linked(owner_id, "OWNED_BY", "Decision", reverse=True)
        releases = linked(owner_id, "APPROVED_BY", "Release", reverse=True)
        if not decisions and not releases:
            report("DETACHED_GOVERNANCE", owner_id)

    if duplicate_ids:
        duplicate_errors = {f"DUPLICATE_NODE_ID:{node_id}" for node_id in duplicate_ids}
        witnesses = [witness.model_copy(update={
            "approved": False,
            "source_valid": False,
            "owner_valid": False,
            "integrity_errors": tuple(sorted(set(witness.integrity_errors) | duplicate_errors)),
        }) for witness in witnesses]
    return tuple(sorted(witnesses, key=lambda item: item.id)), tuple(sorted(errors))
