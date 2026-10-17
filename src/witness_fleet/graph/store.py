from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from falkordb import FalkorDB
from redis.exceptions import ResponseError

from witness_fleet.graph.migrations import GRAPH_SCHEMA_VERSION, migrate

_TENANTS = frozenset({"demo", "other"})
_SNAPSHOT_NODE_LIMIT = 10_000
_SNAPSHOT_EDGE_LIMIT = 20_000
_SNAPSHOT_ATTEMPTS = 3


class StaleSnapshot(RuntimeError):
    """Raised when a bounded snapshot read cannot observe one graph version."""


class OversizeSnapshot(RuntimeError):
    """Raised instead of returning a silently truncated graph snapshot."""


_LABEL_FIELDS: dict[str, frozenset[str]] = {
    "FleetState": frozenset({"graph_version", "policy_epoch", "coordinator_epoch", "dispatch_sequence", "map_version"}),
    "Robot": frozenset({"robot_type", "footprint_m", "payload_kg", "capability_version", "available"}),
    "Capability": frozenset({"name", "limits_json"}),
    "Map": frozenset({"map_version", "configuration_hash"}),
    "HazardClass": frozenset({"name", "taxonomy_version"}),
    "Location": frozenset({"map_id", "map_version", "nominal_width_m"}),
    "Corridor": frozenset({"map_id", "map_version", "nominal_width_m"}),
    "Task": frozenset({"kind", "state", "task_version", "required_predicates", "priority", "claim_fence"}),
    "Resource": frozenset({"kind", "resource_version", "fence"}),
    "Claim": frozenset({"holder_id", "lease_expires_at_utc", "coordinator_epoch", "clock_domain", "fence", "resource_fences_json", "state", "task_id", "robot_id", "created_at"}),
    "Command": frozenset({"command_id", "payload_hash", "fence", "state", "authorization_id", "dispatch_sequence", "coordinator_epoch"}),
    "AuthorizationReceipt": frozenset({"proposal_id", "task_id", "robot_id", "claim_id", "decision", "reason_codes_json", "action_payload_hash", "versions_json", "resource_fences_json", "witness_ids_json", "governance_integrity_version", "valid_until_tick", "created_world_tick"}),
    "DispatchEvent": frozenset({"event_id", "sequence", "coordinator_epoch", "kind", "payload_hash", "subject_ids_json", "effective_world_tick", "occurred_at", "created_at"}),
    "DeliveryReceipt": frozenset({"dispatch_event_id", "applied_sequence", "receipt_state", "applied_world_tick", "payload_hash"}),
    "CancellationDisposition": frozenset({"original_event_id", "original_sequence", "original_payload_hash", "new_coordinator_epoch", "never_admitted_receipt_id", "reason"}),
    "Observation": frozenset({"predicate", "value", "robot_id", "pose", "frame", "visibility", "quality", "expires_tick", "scope_json", "payload_json"}),
    "Hypothesis": frozenset({"statement", "state", "proposed_by", "verification_spec", "payload_json"}),
    "PlanningFact": frozenset({"predicate", "value", "valid_until_tick", "scope_json", "derivation_version", "state", "payload_json"}),
    "Episode": frozenset({"scenario_family", "outcome", "verification_state", "configuration_hash", "payload_json"}),
    "Procedure": frozenset({"version", "state", "compatibility_json", "reviewer_id", "payload_json"}),
    "Source": frozenset({"source_id", "source_type", "display_name", "access_class"}),
    "Revision": frozenset({"revision_id", "content_hash", "normalized_hash", "normalizer_version", "source_effective_from_utc", "source_effective_to_utc"}),
    "EvidenceSpan": frozenset({"start_char", "end_char", "quote", "quote_hash"}),
    "Owner": frozenset({"owner_type", "role", "authority_scope"}),
    "Decision": frozenset({"kind", "state", "effective_clock_domain", "effective_from_tick", "effective_to_tick", "scope_json"}),
    "Restriction": frozenset({"rule_type", "subject_scope", "condition_json", "state"}),
    "Release": frozenset({"state", "effective_clock_domain", "effective_from_tick", "effective_to_tick", "scope_json", "approval_event_id"}),
    "Permission": frozenset({"action_kind", "subject_scope", "condition_json", "state"}),
    "Assessment": frozenset({"family_id", "status", "provider", "model", "question_version", "projection_version", "probabilities_json", "input_hash"}),
    "ApprovalEvent": frozenset({"actor_id", "target_id", "action", "expected_policy_epoch", "event_id"}),
}
_RELATIONSHIPS: frozenset[tuple[str, str, str]] = frozenset({
    ("HAS_CAPABILITY", "Robot", "Capability"), ("LOCATED_AT", "Robot", "Location"),
    ("IN_MAP", "Location", "Map"), ("IN_MAP", "Corridor", "Map"),
    ("FROM_LOCATION", "Corridor", "Location"), ("TO_LOCATION", "Corridor", "Location"),
    ("ASSIGNED_TO", "Robot", "Task"), ("DEPENDS_ON", "Task", "Task"),
    ("USES", "Task", "Corridor"), ("REQUIRES_RESOURCE", "Task", "Resource"),
    ("REQUIRES_FACT", "Task", "PlanningFact"), ("CLAIMS_TASK", "Claim", "Task"),
    ("RESERVES", "Claim", "Resource"), ("HELD_BY", "Claim", "Robot"),
    ("FOR_TASK", "Command", "Task"), ("UNDER_CLAIM", "Command", "Claim"),
    ("VERIFIED_BY", "Command", "Observation"),
    ("CHECKED_FACT", "Command", "PlanningFact"), ("AUTHORIZED_BY", "Command", "AuthorizationReceipt"),
    ("FOR_PROPOSAL_TASK", "AuthorizationReceipt", "Task"), ("FOR_ROBOT", "AuthorizationReceipt", "Robot"),
    ("UNDER_CLAIM", "AuthorizationReceipt", "Claim"),
    ("WITNESSED", "AuthorizationReceipt", "PlanningFact"),
    ("WITNESSED", "AuthorizationReceipt", "Decision"),
    ("WITNESSED", "AuthorizationReceipt", "Restriction"),
    ("WITNESSED", "AuthorizationReceipt", "Release"),
    ("WITNESSED", "AuthorizationReceipt", "Permission"),
    ("WITNESSED", "AuthorizationReceipt", "EvidenceSpan"),
    ("DELIVERS", "DispatchEvent", "Command"), ("ACKNOWLEDGES", "DeliveryReceipt", "DispatchEvent"),
    ("DELIVERS", "DispatchEvent", "Decision"), ("DELIVERS", "DispatchEvent", "Release"),
    ("DELIVERS", "DispatchEvent", "Claim"),
    ("SUPPORTED_BY", "PlanningFact", "Observation"), ("SUPPORTED_BY", "Decision", "EvidenceSpan"),
    ("SUPPORTED_BY", "Owner", "EvidenceSpan"),
    ("SUPPORTED_BY", "Release", "EvidenceSpan"), ("TESTED_BY", "Hypothesis", "Observation"),
    ("DEPENDS_ON", "Hypothesis", "Hypothesis"),
    ("CONTAINS", "Episode", "Observation"), ("CONTAINS", "Episode", "Command"),
    ("CONTAINS", "Episode", "Task"), ("OCCURRED_AT", "Episode", "Corridor"),
    ("INVOLVED_ROBOT", "Episode", "Robot"), ("CLASSIFIED_AS", "Episode", "HazardClass"),
    ("ON_MAP", "Episode", "Map"), ("DERIVED_FROM", "Procedure", "Episode"),
    ("IMPOSES", "Decision", "Restriction"), ("GRANTS", "Decision", "Permission"),
    ("OWNED_BY", "Decision", "Owner"), ("APPLIES_TO", "Restriction", "Corridor"),
    ("APPLIES_TO", "Permission", "Corridor"), ("LIFTS", "Release", "Restriction"),
    ("APPROVED_BY", "Release", "Owner"), ("APPROVES", "ApprovalEvent", "Release"),
    ("APPROVES", "ApprovalEvent", "Decision"), ("IN_REVISION", "EvidenceSpan", "Revision"),
    ("REVISION_OF", "Revision", "Source"), ("SUPERSEDES", "Revision", "Revision"),
    ("CONSIDERED", "Assessment", "EvidenceSpan"), ("CONSIDERED", "Assessment", "Observation"),
    ("CONSIDERED", "Assessment", "Episode"),
})

_ATOMIC_UPDATE_FIELDS: dict[str, frozenset[str]] = {
    # Atomic updates are deliberately narrower than the appendable property set.
    # Identity, definition and evidence fields remain immutable after creation.
    "Robot": frozenset({"available"}),
    "Task": frozenset({"state", "task_version", "claim_fence"}),
    "Resource": frozenset({"resource_version", "fence"}),
    "Claim": frozenset({"lease_expires_at_utc", "state"}),
    "Command": frozenset({"state"}),
    "DeliveryReceipt": frozenset({"receipt_state", "applied_sequence", "applied_world_tick"}),
    "CancellationDisposition": frozenset({"reason"}),
}


def _utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("timestamps must be explicit UTC ISO-8601")
    return parsed.isoformat().replace("+00:00", "Z")


def _properties(node: Any) -> dict[str, Any]:
    return dict(node.properties)


class GraphStore:
    """Narrow tenant-scoped repository over a single canonical FalkorDB ops graph."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6380,
        tenant_id: str = "demo",
        username: str = "wf_ops",
        password: str | None = None,
        *,
        socket_timeout: float = 5,
        max_nodes: int = _SNAPSHOT_NODE_LIMIT,
        max_edges: int = _SNAPSHOT_EDGE_LIMIT,
        max_attempts: int = _SNAPSHOT_ATTEMPTS,
    ) -> None:
        if tenant_id not in _TENANTS:
            raise ValueError("tenant must be a trusted configured tenant")
        if min(max_nodes, max_edges, max_attempts) < 1:
            raise ValueError("snapshot node, edge, and attempt limits must be positive")
        self.tenant_id = tenant_id
        self.graph_name = f"wf:{tenant_id}:ops"
        self.username = username
        self.host = host
        self.port = port
        self._snapshot_node_limit = max_nodes
        self._snapshot_edge_limit = max_edges
        self._snapshot_attempts = max_attempts
        self._client = FalkorDB(
            host=host, port=port, username=username, password=password,
            socket_timeout=socket_timeout, socket_connect_timeout=socket_timeout,
        )
        self._graph = self._client.select_graph(self.graph_name)
        self.query_count = 0
        self.cas_query_count = 0

    def _query(self, cypher: str, params: dict[str, Any] | None = None, *, write: bool = False) -> Any:
        self.query_count += 1
        return self._graph.query(cypher, params or {}) if write else self._graph.ro_query(cypher, params or {})

    def health(self) -> bool:
        result = self._query("RETURN 1 AS healthy")
        return bool(result.result_set and result.result_set[0][0] == 1)

    def initialize(self) -> dict[str, Any]:
        result = self._query(
            "MERGE (s:FleetState {id:$id, tenant_id:$tenant_id}) "
            "ON CREATE SET s.schema_version=$schema_version, s.created_at=$created_at, "
            "s.recorded_at=$created_at, s.graph_version=0, s.policy_epoch=0, "
            "s.coordinator_epoch=0, s.dispatch_sequence=0, s.map_version=0 "
            "RETURN properties(s) AS state",
            {"id": "fleet", "tenant_id": self.tenant_id, "schema_version": GRAPH_SCHEMA_VERSION,
             "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z")},
            write=True,
        )
        state = dict(result.result_set[0][0])
        migration_queries = migrate(self.graph_name, self._client)
        self.query_count += migration_queries
        return state

    def read_version_root(self) -> dict[str, Any] | None:
        try:
            result = self._query(
                "MATCH (s:FleetState {id:$id, tenant_id:$tenant_id}) RETURN properties(s) AS state",
                {"id": "fleet", "tenant_id": self.tenant_id},
            )
        except ResponseError as exc:
            if "Invalid graph operation on empty key" not in str(exc):
                raise
            return None
        return dict(result.result_set[0][0]) if result.result_set else None

    def append_node(self, label: str, node_id: str, attributes: dict[str, Any]) -> dict[str, Any]:
        if label not in _LABEL_FIELDS or label == "FleetState":
            raise ValueError("label is not an appendable canonical node type")
        if not node_id or set(attributes) - _LABEL_FIELDS[label]:
            raise ValueError(f"attributes are not approved for {label}")
        for value in attributes.values():
            if isinstance(value, (dict, list, tuple)):
                raise TypeError("graph node attributes must be scalar; encode JSON explicitly")
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        creation_token = uuid.uuid4().hex
        params = {"id": node_id, "tenant_id": self.tenant_id, "schema_version": GRAPH_SCHEMA_VERSION,
                  "created_at": now, "recorded_at": now, "attributes": attributes,
                  "creation_token": creation_token}
        result = self._query(
            f"MATCH (s:FleetState {{id:'fleet', tenant_id:$tenant_id}}) "
            f"MERGE (n:{label} {{id:$id, tenant_id:$tenant_id}}) "
            "ON CREATE SET n._wf_creation_token=$creation_token, n.schema_version=$schema_version, "
            "n.created_at=$created_at, n.recorded_at=$recorded_at, n += $attributes "
            "WITH s,n,n._wf_creation_token=$creation_token AS created REMOVE n._wf_creation_token "
            "SET s.graph_version=s.graph_version+CASE WHEN created THEN 1 ELSE 0 END "
            "RETURN properties(n) AS node",
            params, write=True,
        )
        if not result.result_set:
            raise RuntimeError("append_node requires FleetState initialization")
        node = dict(result.result_set[0][0])
        if any(node.get(key) != value for key, value in attributes.items()):
            raise ValueError("stable node ID already exists with different immutable attributes")
        return node

    def append_edge(
        self, relationship: str, source_label: str, source_id: str,
        target_label: str, target_id: str, attributes: dict[str, Any] | None = None,
    ) -> None:
        if (relationship, source_label, target_label) not in _RELATIONSHIPS:
            raise ValueError("relationship direction/types are not in canonical graph schema")
        attrs = attributes or {}
        if any(isinstance(v, (dict, list, tuple)) for v in attrs.values()):
            raise TypeError("relationship attributes must be scalar")
        query = (
            "MATCH (s:FleetState {id:'fleet', tenant_id:$tenant_id}) "
            f"MATCH (a:{source_label} {{id:$source_id, tenant_id:$tenant_id}}), "
            f"(b:{target_label} {{id:$target_id, tenant_id:$tenant_id}}) "
            f"MERGE (a)-[r:{relationship}]->(b) "
            "ON CREATE SET r._wf_creation_token=$creation_token "
            "WITH s,r,r._wf_creation_token=$creation_token AS created "
            "FOREACH (_ IN CASE WHEN created THEN [1] ELSE [] END | SET r += $attributes) "
            "REMOVE r._wf_creation_token "
            "SET s.graph_version=s.graph_version+CASE WHEN created THEN 1 ELSE 0 END "
            "RETURN properties(r) AS relationship"
        )
        creation_token = uuid.uuid4().hex
        result = self._query(query, {"source_id": source_id, "target_id": target_id,
                                     "tenant_id": self.tenant_id, "attributes": attrs,
                                     "creation_token": creation_token}, write=True)
        if not result.result_set:
            raise KeyError("edge endpoint is missing from this tenant graph")
        edge = dict(result.result_set[0][0])
        if any(edge.get(key) != value for key, value in attrs.items()):
            raise ValueError("stable edge already exists with different immutable attributes")

    def append_event(
        self, *, event_id: str, kind: str, payload_hash: str,
        subject_ids_json: str, effective_world_tick: int,
    ) -> dict[str, Any]:
        if not event_id or not payload_hash or effective_world_tick < 0:
            raise ValueError("event id/hash and nonnegative world tick are required")
        try:
            subjects = json.loads(subject_ids_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("subject_ids_json must be valid JSON") from exc
        if not isinstance(subjects, list) or any(not isinstance(item, str) for item in subjects):
            raise ValueError("subject_ids_json must encode a list of string IDs")
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        creation_token = uuid.uuid4().hex
        values = {"event_id": event_id, "tenant_id": self.tenant_id,
                  "schema_version": GRAPH_SCHEMA_VERSION, "created_at": now, "recorded_at": now,
                  "occurred_at": now, "kind": kind, "payload_hash": payload_hash,
                  "subject_ids_json": subject_ids_json, "effective_world_tick": effective_world_tick,
                  "coordinator_epoch": 0, "sequence": 0,
                  "_wf_creation_token": creation_token}
        graph = self._graph
        result = graph.query(
            "MERGE (e:DispatchEvent {id:$event_id, tenant_id:$tenant_id}) "
            "ON CREATE SET e += $values "
            "WITH e,e._wf_creation_token=$creation_token AS created "
            "MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}) "
            "SET s.graph_version=s.graph_version+CASE WHEN created THEN 1 ELSE 0 END "
            "REMOVE e._wf_creation_token "
            "RETURN properties(e) AS event,created AS created",
            {"event_id": event_id, "tenant_id": self.tenant_id, "values": values,
             "creation_token": creation_token},
        )
        self.query_count += 1
        event = dict(result.result_set[0][0])
        if event.get("payload_hash") != payload_hash or any(
            event.get(key) != values.get(key)
            for key in ("kind", "subject_ids_json", "effective_world_tick")
        ):
            raise ValueError("event id already exists with different payload hash or immutable payload fields")
        event["created"] = bool(result.result_set[0][1])
        return event

    def atomic_update(
        self, *, expected_graph_version: int, label: str, node_id: str,
        attributes: dict[str, Any], event: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if label not in _LABEL_FIELDS or label == "FleetState":
            raise ValueError("label is not an appendable canonical node type")
        if set(attributes) - _LABEL_FIELDS[label] or any(
            isinstance(v, (dict, list, tuple)) for v in attributes.values()
        ):
            raise ValueError("attributes must be approved scalar fields")
        if not attributes:
            raise ValueError("atomic update requires at least one approved mutable field")
        event_values: dict[str, Any] | None = None
        if event is not None:
            if ("DELIVERS", "DispatchEvent", label) not in _RELATIONSHIPS:
                raise ValueError(f"DELIVERS does not support a {label} target")
            event_id = event.get("event_id")
            required = {"kind", "payload_hash", "subject_ids_json", "effective_world_tick"}
            if not event_id or required - set(event):
                raise ValueError("dispatch event fields are incomplete")
            if json.loads(event["subject_ids_json"]).__class__ is not list:
                raise ValueError("subject_ids_json must encode a list")
            event_values = {"id": event_id, "event_id": event_id, "tenant_id": self.tenant_id,
                            "schema_version": GRAPH_SCHEMA_VERSION,
                            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                            "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                            "kind": event["kind"], "payload_hash": event["payload_hash"],
                            "subject_ids_json": event["subject_ids_json"],
                            "effective_world_tick": int(event["effective_world_tick"])}
        else:
            event_values = None
        if event_values is None:
            update_params = {f"update_{key}": value for key, value in attributes.items()}
            cypher = (
                "MATCH (s:FleetState {id:'fleet', tenant_id:$tenant_id}) "
                "WHERE s.graph_version=$expected_version "
                f"MERGE (n:{label} {{id:$node_id, tenant_id:$tenant_id}}) "
                "ON CREATE SET n._wf_creation_token=$creation_token, n.schema_version=$schema_version, "
                "n.created_at=$created_at, n.recorded_at=$created_at "
                "WITH s,n,coalesce(n._wf_creation_token=$creation_token,false) AS created "
                "WHERE created OR all(key IN keys($attributes) WHERE key IN $mutable_fields) "
                "SET n += $attributes, s.graph_version=s.graph_version+1 "
                "REMOVE n._wf_creation_token "
                "RETURN s.graph_version AS graph_version, properties(n) AS node"
            )
            params = {"tenant_id": self.tenant_id, "expected_version": expected_graph_version,
                      "node_id": node_id, "schema_version": GRAPH_SCHEMA_VERSION,
                      "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                      "creation_token": uuid.uuid4().hex,
                      "mutable_fields": sorted(_ATOMIC_UPDATE_FIELDS.get(label, frozenset())),
                      "attributes": attributes, **update_params}
        else:
            update_params = {f"update_{key}": value for key, value in attributes.items()}
            cypher = (
                "MATCH (s:FleetState {id:'fleet', tenant_id:$tenant_id}) "
                "WHERE s.graph_version=$expected_version "
                f"MERGE (n:{label} {{id:$node_id, tenant_id:$tenant_id}}) "
                "ON CREATE SET n._wf_creation_token=$creation_token, n.schema_version=$schema_version, "
                "n.created_at=$created_at, n.recorded_at=$created_at "
                "WITH s,n,n._wf_creation_token=$creation_token AS created "
                "WHERE created "
                "SET n += $attributes "
                "REMOVE n._wf_creation_token "
                "SET s.graph_version=s.graph_version+1, "
                "s.dispatch_sequence=s.dispatch_sequence+1 "
                "CREATE (e:DispatchEvent) SET e += $event_values, e.sequence=s.dispatch_sequence, "
                "e.coordinator_epoch=s.coordinator_epoch "
                "CREATE (e)-[:DELIVERS]->(n) "
                "RETURN s.graph_version AS graph_version, properties(n) AS node, properties(e) AS event"
            )
            params = {"tenant_id": self.tenant_id, "expected_version": expected_graph_version,
                      "node_id": node_id, "schema_version": GRAPH_SCHEMA_VERSION,
                      "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                      "creation_token": uuid.uuid4().hex,
                      "attributes": attributes, "event_values": event_values,
                      **update_params}
        self.query_count += 1
        self.cas_query_count += 1
        result = self._graph.query(cypher, params)
        if not result.result_set:
            return None
        return dict(zip([h[1] for h in result.header], result.result_set[0], strict=True))

    def claim_task(
        self, *, task_id: str, robot_id: str, expected_task_version: int,
        coordinator_epoch: int, resource_ids: list[str], lease_expires_at_utc: str, now_utc: str,
    ) -> dict[str, Any] | None:
        if not task_id or not robot_id or not resource_ids or len(set(resource_ids)) != len(resource_ids):
            raise ValueError("task, robot, and unique nonempty resource ids are required")
        lease = _utc(lease_expires_at_utc)
        now = _utc(now_utc)
        if datetime.fromisoformat(lease.replace("Z", "+00:00")) <= datetime.fromisoformat(now.replace("Z", "+00:00")):
            return None
        claim_id = f"cl-{self.tenant_id}-{uuid.uuid4().hex}"
        cypher = (
            "MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}), "
            "(t:Task {id:$task_id,tenant_id:$tenant_id}), (robot:Robot {id:$robot_id,tenant_id:$tenant_id}) "
            "WHERE s.coordinator_epoch=$epoch AND t.task_version=$expected_task_version "
            "AND coalesce(robot.available,false)=true AND t.state IN ['READY','PENDING','ACTIVE'] "
            "AND NOT (robot)<-[:HELD_BY]-(:Claim {state:'ACTIVE'}) "
            "AND NOT (robot)<-[:HELD_BY]-(:Claim {state:'UNKNOWN'}) "
            "AND NOT (robot)<-[:HELD_BY]-(:Claim {state:'REASSESS'}) "
            "AND NOT (t)<-[:CLAIMS_TASK]-(:Claim {state:'ACTIVE'}) "
            "AND NOT (t)<-[:CLAIMS_TASK]-(:Claim {state:'UNKNOWN'}) "
            "AND NOT (t)<-[:CLAIMS_TASK]-(:Claim {state:'REASSESS'}) "
            "WITH s,t,robot "
            "MATCH (t)-[:REQUIRES_RESOURCE]->(required:Resource) "
            "WHERE required.tenant_id=$tenant_id "
            "WITH s,t,robot,collect(DISTINCT required) AS resources "
            "WHERE size(resources)=size($resource_ids) AND size(resources)>0 "
            "AND all(resource IN resources WHERE resource.id IN $resource_ids) "
            "UNWIND resources AS resource "
            "WITH s,t,robot,resource "
            "WHERE NOT (resource)<-[:RESERVES]-(:Claim {state:'ACTIVE'}) "
            "AND NOT (resource)<-[:RESERVES]-(:Claim {state:'UNKNOWN'}) "
            "AND NOT (resource)<-[:RESERVES]-(:Claim {state:'REASSESS'}) "
            "WITH s,t,robot,collect(DISTINCT resource) AS resources "
            "WHERE size(resources)=size($resource_ids) "
            "CREATE (cl:Claim {id:$claim_id,tenant_id:$tenant_id,schema_version:$schema_version,created_at:$now,recorded_at:$now, "
            "holder_id:$robot_id,robot_id:$robot_id,task_id:$task_id,lease_expires_at_utc:$lease,coordinator_epoch:$epoch, "
            "clock_domain:'coordinator_epoch_utc_lease_v1',fence:coalesce(t.claim_fence,0)+1,state:'ACTIVE'}) "
            "CREATE (cl)-[:CLAIMS_TASK]->(t) CREATE (cl)-[:HELD_BY]->(robot) "
            "FOREACH (resource IN resources | CREATE (cl)-[:RESERVES]->(resource) "
            "SET resource.fence=coalesce(resource.fence,0)+1, resource.resource_version=coalesce(resource.resource_version,0)+1) "
            "SET t.claim_fence=cl.fence,t.task_version=t.task_version+1,s.graph_version=s.graph_version+1 "
            "WITH cl,t,s,resources UNWIND resources AS resource "
            "RETURN properties(cl) AS claim, t.claim_fence AS task_fence, "
            "collect({id:resource.id,fence:resource.fence}) AS resource_fences,s.graph_version AS graph_version"
        )
        self.query_count += 1
        self.cas_query_count += 1
        result = self._graph.query(cypher, {
            "tenant_id": self.tenant_id, "task_id": task_id, "robot_id": robot_id,
            "expected_task_version": expected_task_version, "epoch": coordinator_epoch,
            "resource_ids": resource_ids, "claim_id": claim_id,
            "schema_version": GRAPH_SCHEMA_VERSION, "lease": lease, "now": now,
        })
        if not result.result_set:
            return None
        row = dict(zip([header[1] for header in result.header], result.result_set[0], strict=True))
        claim = dict(row["claim"])
        fences = {item["id"]: item["fence"] for item in row["resource_fences"]}
        claim.update({"claim_id": claim["id"], "fence": row["task_fence"],
                      "resource_fences": fences, "graph_version": row["graph_version"]})
        claim["resource_fences_json"] = json.dumps(fences, sort_keys=True, separators=(",", ":"))
        return claim

    def read_snapshot(
        self, *, labels: list[str] | None = None, node_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        selected = labels or list(_LABEL_FIELDS)
        if not selected or set(selected) - set(_LABEL_FIELDS):
            raise ValueError("snapshot labels must be a nonempty canonical label set")
        if node_ids is not None and (
            not node_ids or any(not isinstance(node_id, str) or not node_id for node_id in node_ids)
            or len(set(node_ids)) != len(node_ids)
        ):
            raise ValueError("snapshot node_ids must be a nonempty list of unique nonempty strings")
        label_filter = " OR ".join(f"'{label}' IN labels(n)" for label in selected)
        node_filter = " AND n.id IN $node_ids" if node_ids is not None else ""
        node_params: dict[str, Any] = {"tenant_id": self.tenant_id,
                                       "limit": self._snapshot_node_limit + 1}
        if node_ids is not None:
            node_params["node_ids"] = node_ids
        # These reads aren't a FalkorDB transaction. Bracket both materialized
        # queries with graph_version checks and retry boundedly on interleaving.
        # Fetch one beyond each cap so truncation is rejected, never implied complete.
        for _ in range(self._snapshot_attempts):
            before = self.read_version_root()
            if before is None:
                raise RuntimeError("tenant graph has no FleetState version root")
            node_result = self._query(
                f"MATCH (n) WHERE n.tenant_id=$tenant_id AND ({label_filter}){node_filter} "
                "RETURN labels(n) AS labels, properties(n) AS properties "
                "LIMIT $limit",
                node_params,
            )
            selected_node_ids = [dict(row[1])["id"] for row in node_result.result_set]
            edge_params: dict[str, Any] = {
                "tenant_id": self.tenant_id,
                "selected_node_ids": selected_node_ids,
                "selected_labels": selected,
                "limit": self._snapshot_edge_limit + 1,
            }
            edge_result = self._query(
                "MATCH (a)-[r]->(b) WHERE a.tenant_id=$tenant_id AND b.tenant_id=$tenant_id "
                "AND a.id IN $selected_node_ids AND b.id IN $selected_node_ids "
                "AND any(label IN labels(a) WHERE label IN $selected_labels) "
                "AND any(label IN labels(b) WHERE label IN $selected_labels) "
                "RETURN labels(a) AS source_labels,a.id AS source_id,type(r) AS relationship, "
                "labels(b) AS target_labels,b.id AS target_id,properties(r) AS properties "
                "LIMIT $limit",
                edge_params,
            )
            after = self.read_version_root()
            if after is None:
                raise RuntimeError("tenant graph has no FleetState version root")
            if before["graph_version"] != after["graph_version"]:
                continue
            if len(node_result.result_set) > self._snapshot_node_limit:
                raise OversizeSnapshot(f"snapshot nodes exceed {self._snapshot_node_limit}")
            if len(edge_result.result_set) > self._snapshot_edge_limit:
                raise OversizeSnapshot(f"snapshot edges exceed {self._snapshot_edge_limit}")
            nodes = [{"labels": row[0], **dict(row[1])} for row in node_result.result_set]
            edges = [{"source_label": row[0][0], "source_id": row[1], "relationship": row[2],
                      "target_label": row[3][0], "target_id": row[4], "properties": dict(row[5])}
                     for row in edge_result.result_set]
            from witness_fleet.graph.identity import project_command_event_identities

            return project_command_event_identities({"nodes": nodes, "edges": edges,
                    "versions": {key: after[key] for key in
                                 ("graph_version", "policy_epoch", "coordinator_epoch", "dispatch_sequence", "map_version")}},
                    tenant_id=self.tenant_id)
        raise StaleSnapshot(f"graph changed during all {self._snapshot_attempts} snapshot attempts")

    def get_node(self, label: str, node_id: str) -> dict[str, Any] | None:
        if label not in _LABEL_FIELDS:
            raise ValueError("unknown canonical node label")
        try:
            result = self._query(
                f"MATCH (n:{label} {{id:$id,tenant_id:$tenant_id}}) RETURN properties(n) AS node",
                {"id": node_id, "tenant_id": self.tenant_id},
            )
        except ResponseError as exc:
            if "Invalid graph operation on empty key" not in str(exc):
                raise
            return None
        return dict(result.result_set[0][0]) if result.result_set else None

    def seed_claim_fixture(self, suffix: str, *, second_task: bool = False) -> dict[str, Any]:
        if not suffix.isalnum():
            raise ValueError("fixture suffix must be alphanumeric")
        prefix = f"it-{suffix}-"
        task_id, task_2_id = prefix + "task", prefix + "task-2"
        robot_ids = [prefix + "robot-0", prefix + "robot-1"]
        resource_ids = [prefix + "resource-0", prefix + "resource-1"]
        for robot_id in robot_ids:
            self.append_node("Robot", robot_id, {"robot_type": "courier", "footprint_m": 0.5,
                              "payload_kg": 2.0, "capability_version": 1, "available": True})
        self.append_node("Task", task_id, {"kind": "inspect", "state": "READY", "task_version": 0,
                                            "required_predicates": "[]", "priority": 1, "claim_fence": 0})
        if second_task:
            self.append_node("Task", task_2_id, {"kind": "inspect", "state": "READY", "task_version": 0,
                                                 "required_predicates": "[]", "priority": 1, "claim_fence": 0})
        for resource_id in resource_ids:
            self.append_node("Resource", resource_id, {"kind": "corridor", "resource_version": 0, "fence": 0})
        for resource_id in resource_ids:
            self.append_edge("REQUIRES_RESOURCE", "Task", task_id, "Resource", resource_id)
        if second_task:
            self.append_edge("REQUIRES_RESOURCE", "Task", task_2_id, "Resource", resource_ids[0])
        return {"task_id": task_id, "task_2_id": task_2_id, "robot_0": robot_ids[0],
                "robot_1": robot_ids[1], "resource_ids": resource_ids, "prefix": prefix}

    def read_task_claims(self, task_id: str) -> list[dict[str, Any]]:
        result = self._query(
            "MATCH (c:Claim)-[:CLAIMS_TASK]->(t:Task {id:$task_id,tenant_id:$tenant_id}) "
            "RETURN properties(c) AS claim", {"task_id": task_id, "tenant_id": self.tenant_id},
        )
        return [dict(row[0]) for row in result.result_set]

    def read_resource_claims(self, resource_id: str) -> list[dict[str, Any]]:
        result = self._query(
            "MATCH (c:Claim)-[:RESERVES]->(r:Resource {id:$resource_id,tenant_id:$tenant_id}) "
            "RETURN properties(c) AS claim", {"resource_id": resource_id, "tenant_id": self.tenant_id},
        )
        return [dict(row[0]) for row in result.result_set]

    def delete_test_records(self, prefix: str) -> int:
        if not prefix.startswith("it-") or len(prefix) < 8:
            raise ValueError("cleanup prefix must be a sufficiently specific integration-test ID")
        result = self._query(
            "MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}) "
            "OPTIONAL MATCH (n) WHERE n.tenant_id=$tenant_id AND n.id STARTS WITH $prefix "
            "WITH s,[x IN collect(n) WHERE x IS NOT NULL] AS nodes "
            "FOREACH (node IN nodes | DETACH DELETE node) "
            "WITH s,size(nodes) AS deleted "
            "SET s.graph_version=s.graph_version+CASE WHEN deleted>0 THEN 1 ELSE 0 END "
            "RETURN deleted",
            {"tenant_id": self.tenant_id, "prefix": prefix}, write=True,
        )
        return int(result.result_set[0][0]) if result.result_set else 0

    @property
    def raw_graph_query_for_acl_test(self) -> Any:
        raise AttributeError("raw graph query access is intentionally not exposed")

    def _forbidden_direct_query(self) -> None:
        raise AssertionError("internal helper must never be exposed")

__all__ = ["GraphStore"]
