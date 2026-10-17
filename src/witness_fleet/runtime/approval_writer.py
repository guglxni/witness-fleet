"""One source-bound local release approval CAS and immutable activation receipt."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from witness_fleet.domain import Observation, canonical_json_hash
from witness_fleet.graph.governance import validate_governance
from witness_fleet.graph.migrations import GRAPH_SCHEMA_VERSION
from witness_fleet.graph.verification import validate_release_verification
from witness_fleet.runtime.approval import ApprovalCommand, TrustedLocalPrincipal

_LABELS = ["Source", "Revision", "EvidenceSpan", "Owner", "Decision", "Restriction",
           "Release", "Permission", "ApprovalEvent", "Corridor", "DispatchEvent", "Observation"]


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("explicit UTC timestamp required")
    return parsed


class ApprovalWriter:
    """Configured-local authority, not authentication against in-process impersonation.

    Source and sensor records must already be committed through trusted local
    adapters. No request-supplied authority, roster grant, proof or predicate value
    enters the transaction. One graph version guards the entire validated snapshot.
    """

    def __init__(self, graph, sources, principal: TrustedLocalPrincipal, *, holder_id, clock=None):
        self.graph = graph
        self.sources = sources
        self.principal = principal
        self.holder_id = holder_id
        self.clock = clock or (lambda: datetime.now(UTC))

    def approve_release(self, command, *, effective_world_tick):
        if (not isinstance(self.principal, TrustedLocalPrincipal)
                or not isinstance(command, ApprovalCommand)
                or command.actor_id != self.principal.actor_id
                or command.tenant_id != self.principal.tenant_id
                or command.tenant_id != self.graph.tenant_id):
            raise ValueError("approval intent must match configured local principal")
        if type(effective_world_tick) is not int or effective_world_tick < 0:
            raise ValueError("approval world tick must be a nonnegative exact integer")
        command = ApprovalCommand.model_validate(command.model_dump(mode="json"))
        approval_id = "approval-" + hashlib.sha256(command.event_id.encode()).hexdigest()
        intent = command.model_dump(mode="json")
        existing = self.graph.get_node("DispatchEvent", command.event_id)
        if existing is not None:
            return self._replay(command, approval_id, effective_world_tick)
        root = self.graph.read_version_root()
        if (not isinstance(root, dict) or type(root.get("policy_epoch")) is not int
                or root["policy_epoch"] != command.expected_policy_epoch):
            raise ValueError("approval expected policy epoch is stale or invalid")
        now = self.clock()
        if (not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() != UTC.utcoffset(now)):
            raise ValueError("approval clock must be explicit UTC")
        if (not isinstance(self.holder_id, str) or not self.holder_id
                or root.get("coordinator_holder_id") != self.holder_id
                or type(root.get("coordinator_epoch")) is not int
                or root["coordinator_epoch"] < 1):
            raise ValueError("approval requires current configured coordinator holder")
        try:
            lease = _utc(root["coordinator_lease_expires_at_utc"])
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError("approval requires valid coordinator lease") from None
        if lease <= now:
            raise ValueError("approval coordinator lease is expired")
        snapshot = self.graph.read_snapshot(labels=_LABELS)
        if snapshot["versions"] != {key: root[key] for key in snapshot["versions"]}:
            raise ValueError("approval snapshot changed")
        witnesses, errors = validate_governance(snapshot, self.sources)
        if errors:
            raise ValueError("approval governance snapshot is invalid")
        witness = next((w for w in witnesses if w.id == command.target_id and w.kind == "release"), None)
        if (witness is None or witness.state != "staged" or not witness.source_valid
                or not witness.owner_valid or witness.owner_id != command.actor_id
                or effective_world_tick < witness.effective_from_tick
                or (witness.effective_to_tick is not None and effective_world_tick >= witness.effective_to_tick)):
            raise ValueError("approval requires exact staged release and owner scope")
        restriction = next((w for w in witnesses if w.id == witness.restriction_id), None)
        if restriction is None or restriction.kind != "restriction" or restriction.state != "active" or not restriction.approved:
            raise ValueError("approval requires exact active restriction")
        nodes = {n["id"]: n for n in snapshot["nodes"]}
        edges = snapshot["edges"]

        def linked(origin, relationship, label):
            rows = [nodes[e["target_id"]] for e in edges if e["source_id"] == origin
                    and e["relationship"] == relationship and label in nodes[e["target_id"]]["labels"]]
            if len(rows) != 1:
                raise ValueError("approval requires unique canonical evidence edge")
            return rows[0]

        release_span = linked(command.target_id, "SUPPORTED_BY", "EvidenceSpan")
        revision = linked(release_span["id"], "IN_REVISION", "Revision")
        retained = self.sources.get(revision["revision_id"])
        document = json.loads(retained.text)
        expected_document = {
            "kind": "release", "corridor_id": witness.corridor_id,
            "restriction_id": witness.restriction_id,
            "action_kinds": [item.value for item in witness.action_kinds],
            "robot_types": list(witness.robot_types),
            "required_predicates": ["recovery_verified", "courier_fit"],
        }
        if (document != expected_document or release_span["start_char"] != 0
                or release_span["end_char"] != len(retained.text)
                or release_span["quote"] != retained.text):
            raise ValueError("approval release source conditions are unsupported or mismatched")
        owner_span = linked(command.actor_id, "SUPPORTED_BY", "EvidenceSpan")
        verification = []
        for predicate in document["required_predicates"]:
            candidates = []
            for node in snapshot["nodes"]:
                if "Observation" not in node["labels"]:
                    continue
                try:
                    observed = Observation.model_validate_json(node["payload_json"])
                except (KeyError, TypeError, ValueError):
                    raise ValueError("approval observation record is invalid") from None
                if (observed.id != node["id"] or observed.tenant_id != self.graph.tenant_id
                        or observed.predicate != node["predicate"] or observed.value != node["value"]):
                    raise ValueError("approval observation identity mismatch")
                if (observed.predicate == predicate and observed.subject_id == witness.corridor_id
                        and dict(observed.scope) == {"corridor_id": witness.corridor_id,
                            "release_id": witness.id, "robot_type": "courier", "payload_class": "loaded"}
                        and observed.world_tick <= effective_world_tick
                        and observed.occurred_at <= now and observed.recorded_at <= now):
                    candidates.append(observed)
            if not candidates:
                raise ValueError("approval requires fresh post-inspection verification")
            newest = max(item.world_tick for item in candidates)
            latest = [item for item in candidates if item.world_tick == newest]
            if any(item.value is not True or item.visibility != "visible" or not item.sensor_config_hash
                   or item.expires_tick <= effective_world_tick for item in latest):
                raise ValueError("approval requires fresh post-inspection verification")
            verification.extend({"observation_id": item.id, "payload_hash": canonical_json_hash(item)} for item in sorted(latest, key=lambda o: o.id))
        verification_json = _canonical(verification)
        if not validate_release_verification(
                snapshot['nodes'], verification_json, tenant_id=self.graph.tenant_id,
                corridor_id=witness.corridor_id, release_id=witness.id,
                approved_at=now, effective_tick=effective_world_tick):
            raise ValueError('approval historical verification is invalid')
        intent_hash = canonical_json_hash(intent)
        payload = {
            "policy_epoch": command.expected_policy_epoch + 1,
            "expected_previous_policy_epoch": command.expected_policy_epoch,
            "policy_proof": {"proof_id": approval_id, "coordinator_epoch": root["coordinator_epoch"],
                "approval_hash": intent_hash, "target_id": command.target_id,
                "actor_id": command.actor_id, "restriction_id": witness.restriction_id,
                "span_id": witness.span_id, "owner_span_id": owner_span["id"]},
        }
        # Round DOWN: a submillisecond lease remainder can never prolong authority.
        delta = lease - datetime(1970, 1, 1, tzinfo=UTC)
        deadline_ms = delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds // 1000
        query = (
            "MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}), "
            "(r:Release {id:$target_id,tenant_id:$tenant_id})-[:LIFTS]->(ban:Restriction {id:$restriction_id,tenant_id:$tenant_id}), "
            "(r)-[:APPROVED_BY]->(owner:Owner {id:$actor_id,tenant_id:$tenant_id}), "
            "(r)-[:SUPPORTED_BY]->(span:EvidenceSpan {id:$span_id,tenant_id:$tenant_id}), "
            "(owner)-[:SUPPORTED_BY]->(roster:EvidenceSpan {id:$owner_span_id,tenant_id:$tenant_id}) "
            "WHERE s.graph_version=$version AND s.policy_epoch=$expected_epoch "
            "AND s.coordinator_epoch=$coordinator_epoch AND s.coordinator_holder_id=$holder_id "
            "AND s.coordinator_lease_expires_at_utc=$lease AND timestamp()<$deadline_ms "
            "AND r.state='staged' AND ban.state='active' "
            "AND NOT (r)<-[:APPROVES]-(:ApprovalEvent) "
            "WITH DISTINCT s,r,ban,owner,span,roster "
            "SET s.graph_version=s.graph_version+1,s.policy_epoch=s.policy_epoch+1, "
            "s.dispatch_sequence=s.dispatch_sequence+1,r.state='released',r.approval_event_id=$approval_id "
            "CREATE (a:ApprovalEvent {id:$approval_id,tenant_id:$tenant_id,schema_version:$schema_version, "
            "created_at:$now,recorded_at:$now,event_id:$event_id,actor_id:$actor_id,target_id:$target_id, "
            "action:'approve',expected_policy_epoch:$expected_epoch,payload_json:$intent_json,payload_hash:$intent_hash, "
            "activation_event_id:$event_id,dispatch_sequence:s.dispatch_sequence,coordinator_epoch:$coordinator_epoch, "
            "effective_world_tick:$tick,graph_version:s.graph_version,verification_json:$verification_json}) "
            "CREATE (e:DispatchEvent {id:$event_id,event_id:$event_id,tenant_id:$tenant_id,schema_version:$schema_version, "
            "created_at:$now,recorded_at:$now,occurred_at:$now,kind:'POLICY_ACTIVATION',sequence:s.dispatch_sequence, "
            "coordinator_epoch:$coordinator_epoch,effective_world_tick:$tick,payload_json:$payload_json, "
            "payload_hash:$payload_hash,subject_ids_json:$subjects_json}) "
            "CREATE (a)-[:APPROVES]->(r) CREATE (e)-[:DELIVERS]->(r) "
            "RETURN properties(s) AS state,properties(a) AS approval,properties(e) AS event"
        )
        params = {
            "tenant_id": self.graph.tenant_id, "target_id": command.target_id,
            "restriction_id": witness.restriction_id, "actor_id": command.actor_id,
            "span_id": witness.span_id, "owner_span_id": owner_span["id"],
            "version": root["graph_version"], "expected_epoch": command.expected_policy_epoch,
            "coordinator_epoch": root["coordinator_epoch"], "holder_id": self.holder_id,
            "lease": root["coordinator_lease_expires_at_utc"], "deadline_ms": deadline_ms,
            "approval_id": approval_id, "event_id": command.event_id, "schema_version": GRAPH_SCHEMA_VERSION,
            "now": now.isoformat().replace("+00:00", "Z"), "intent_json": _canonical(intent),
            "intent_hash": intent_hash, "tick": effective_world_tick, "verification_json": verification_json,
            "payload_json": _canonical(payload), "payload_hash": canonical_json_hash(payload),
            "subjects_json": _canonical([command.target_id, witness.restriction_id, command.actor_id,
                                        witness.span_id, owner_span["id"], approval_id]),
        }
        self.graph.query_count += 1
        self.graph.cas_query_count += 1
        result = self.graph._graph.query(query, params)
        if not result.result_set:
            raise ValueError("approval compare-and-swap lost or coordinator lease expired")
        row = dict(zip([header[1] for header in result.header], result.result_set[0], strict=True))
        return {"policy_epoch": row["state"]["policy_epoch"], "graph_version": row["state"]["graph_version"],
                "dispatch_sequence": row["state"]["dispatch_sequence"],
                "approval": dict(row["approval"]), "event": dict(row["event"])}

    def _replay(self, command, approval_id, tick):
        snapshot = self.graph.read_snapshot(labels=_LABELS)
        witnesses, errors = validate_governance(snapshot, self.sources)
        approval = next((node for node in snapshot["nodes"] if node["id"] == approval_id and "ApprovalEvent" in node["labels"]), None)
        event = next((node for node in snapshot["nodes"] if node["id"] == command.event_id and "DispatchEvent" in node["labels"]), None)
        witness = next((item for item in witnesses if item.id == command.target_id), None)
        if (errors or approval is None or event is None or witness is None or not witness.approved
                or approval.get("payload_json") != _canonical(command.model_dump(mode="json"))
                or approval.get("effective_world_tick") != tick):
            raise ValueError("approval event identity conflicts with exact committed intent")
        return {"policy_epoch": command.expected_policy_epoch + 1, "graph_version": approval["graph_version"],
                "dispatch_sequence": approval["dispatch_sequence"],
                "approval": {k: v for k, v in approval.items() if k != "labels"},
                "event": {k: v for k, v in event.items() if k != "labels"}}
