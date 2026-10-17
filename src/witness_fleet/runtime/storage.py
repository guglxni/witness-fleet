"""Atomic graph transitions for coordinator leases and durable control outbox."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from witness_fleet.domain import canonical_json_hash
from witness_fleet.graph.migrations import GRAPH_SCHEMA_VERSION


class OutboxIntegrityError(RuntimeError):
    """A durable outbox row cannot be trusted as a complete control event."""

    def __init__(self, *, event_id: str, sequence: int | None, reason: str):
        self.event_id = event_id
        self.sequence = sequence
        self.reason = reason
        super().__init__(
            f"outbox event {event_id} sequence {sequence} integrity failure: {reason}"
        )


def _utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("timestamps must be explicit UTC ISO-8601")
    return parsed.isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _is_counter(value: Any, *, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def _is_counter_map(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(key, str) and bool(key) and _is_counter(counter)
        for key, counter in value.items()
    )


class TransitionStore:
    """Tenant-scoped serialized graph writer; each method uses one graph CAS query."""

    def __init__(self, graph, *, holder_id: str | None = None):
        self.graph = graph
        self.holder_id = holder_id

    def acquire_coordinator(
        self, *, expected_epoch: int, holder_id: str, now_utc: str,
        lease_expires_at_utc: str, event_id: str, effective_world_tick: int,
    ) -> dict[str, Any] | None:
        if (type(expected_epoch) is not int or expected_epoch < 0
                or not isinstance(holder_id, str) or not holder_id
                or not isinstance(event_id, str) or not event_id
                or type(effective_world_tick) is not int or effective_world_tick < 0):
            raise ValueError("epoch, holder, event ID and nonnegative world tick are required")
        now, expires = _utc(now_utc), _utc(lease_expires_at_utc)
        now_datetime = datetime.fromisoformat(now.replace("Z", "+00:00"))
        expires_datetime = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if expires_datetime <= now_datetime:
            raise ValueError("coordinator lease expiry must be after now")

        root = self.graph.read_version_root()
        if not isinstance(root, dict):
            return None
        expected_version = root.get("graph_version")
        root_epoch = root.get("coordinator_epoch")
        if (not _is_counter(expected_version) or not _is_counter(root_epoch)
                or root_epoch != expected_epoch):
            return None
        retained_lease = root.get("coordinator_lease_expires_at_utc")
        if retained_lease is not None:
            if not isinstance(retained_lease, str):
                return None
            try:
                parsed_retained_lease = _utc(retained_lease)
            except (TypeError, ValueError):
                return None
            retained_datetime = datetime.fromisoformat(
                parsed_retained_lease.replace("Z", "+00:00")
            )
            if retained_datetime > now_datetime:
                return None

        if retained_lease is None:
            retained_lease_guard = "s.coordinator_lease_expires_at_utc IS NULL"
        else:
            retained_lease_guard = (
                "s.coordinator_lease_expires_at_utc=$retained_lease"
            )
        epoch = expected_epoch + 1
        payload = {"coordinator_epoch": epoch, "holder_id": holder_id,
                   "lease_expires_at_utc": expires}
        payload_json = _canonical(payload)
        event_hash = canonical_json_hash(payload)
        created_at = now
        query = (
            "MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}) "
            "WHERE s.graph_version=$expected_version "
            "AND s.coordinator_epoch=$expected_epoch "
            f"AND {retained_lease_guard} "
            "SET s.coordinator_epoch=$epoch, s.coordinator_holder_id=$holder_id, "
            "s.coordinator_lease_expires_at_utc=$expires, "
            "s.dispatch_sequence=s.dispatch_sequence+1, s.graph_version=s.graph_version+1 "
            "CREATE (e:DispatchEvent {id:$event_id,event_id:$event_id,tenant_id:$tenant_id, "
            "schema_version:$schema_version,created_at:$created_at,recorded_at:$created_at, "
            "occurred_at:$created_at,sequence:s.dispatch_sequence,coordinator_epoch:$epoch, "
            "kind:'EPOCH_BARRIER',payload_hash:$payload_hash,payload_json:$payload_json, "
            "subject_ids_json:$subject_ids_json,effective_world_tick:$tick}) "
            "RETURN properties(s) AS state,properties(e) AS event"
        )
        self.graph.query_count += 1
        self.graph.cas_query_count += 1
        params = {
            "tenant_id": self.graph.tenant_id, "expected_epoch": expected_epoch,
            "expected_version": expected_version, "epoch": epoch, "holder_id": holder_id,
            "expires": expires, "event_id": event_id,
            "schema_version": GRAPH_SCHEMA_VERSION, "created_at": created_at,
            "payload_hash": event_hash, "payload_json": payload_json,
            "subject_ids_json": "[]", "tick": effective_world_tick,
        }
        if retained_lease is not None:
            params["retained_lease"] = retained_lease
        result = self.graph._graph.query(query, params)
        if not result.result_set:
            return None
        row = dict(zip([header[1] for header in result.header], result.result_set[0], strict=True))
        return {**dict(row["state"]), "event": dict(row["event"])}

    def prepare_command(self, *, command, authorization, expected_graph_version):
        from witness_fleet.domain import (
            AuthorizationResult,
            CommandIntent,
            DispatchEvent,
            VersionVector,
        )

        if not isinstance(command, CommandIntent):
            command = CommandIntent.model_validate(command)
        if not isinstance(authorization, AuthorizationResult):
            authorization = AuthorizationResult.model_validate(authorization)
        if command.authorization != authorization or authorization.status != "ALLOW":
            raise ValueError("command must carry its matching ALLOW authorization")
        if type(expected_graph_version) is not int or expected_graph_version < 0:
            raise ValueError("expected_graph_version must be a nonnegative integer")
        if command.effective_world_tick >= authorization.valid_until_tick:
            raise ValueError("authorization is expired for the command effective tick")
        command_json = command.model_dump(mode="json")
        authorization_json = authorization.model_dump(mode="json")
        payload = command_json
        payload_hash = canonical_json_hash(payload)
        subject_ids = [command.command_id, command.proposal.task_id, command.proposal.robot_id,
                       command.claim_id, authorization.authorization_id]
        command_id = command.command_id
        query = (
            "MATCH (c:Command {id:$command_id,tenant_id:$tenant_id})-[:AUTHORIZED_BY]->(a:AuthorizationReceipt), "
            "(e:DispatchEvent {id:$command_id,tenant_id:$tenant_id}) "
            "RETURN properties(c) AS command,properties(a) AS authorization_receipt, "
            "properties(e) AS event"
        )
        existing = self.graph._query(query, {"command_id": command_id,
                                             "tenant_id": self.graph.tenant_id})
        if existing.result_set:
            row = dict(zip([header[1] for header in existing.header], existing.result_set[0], strict=True))
            stored_command = dict(row["command"])
            stored_auth = dict(row["authorization_receipt"])
            stored_event = dict(row["event"])
            try:
                if not all((
                    _is_counter(stored_command.get("dispatch_sequence"), minimum=1),
                    _is_counter(stored_command.get("coordinator_epoch")),
                    _is_counter(stored_command.get("fence")),
                    _is_counter(stored_auth.get("governance_integrity_version")),
                    _is_counter(stored_auth.get("valid_until_tick")),
                    _is_counter(stored_auth.get("created_world_tick")),
                )):
                    raise ValueError
                stored_command_json = json.loads(stored_command["payload_json"])
                validated_command = CommandIntent.model_validate(stored_command_json)
                stored_versions = VersionVector.model_validate(
                    json.loads(stored_auth["versions_json"])
                )
                stored_resource_fences = json.loads(stored_auth["resource_fences_json"])
                if not _is_counter_map(stored_resource_fences):
                    raise ValueError
                if (
                    validated_command.model_dump(mode="json") != command_json
                    or canonical_json_hash(stored_command_json) != payload_hash
                    or stored_command.get("payload_hash") != payload_hash
                    or stored_command.get("id") != command_id
                    or stored_command.get("command_id") != command_id
                    or stored_command.get("tenant_id") != self.graph.tenant_id
                    or stored_command.get("authorization_id") != authorization.authorization_id
                    or stored_command.get("dispatch_sequence") != command.dispatch_sequence
                    or stored_command.get("coordinator_epoch") != command.coordinator_epoch
                    or stored_command.get("fence") != command.fence
                    or stored_auth.get("id") != authorization.authorization_id
                    or stored_auth.get("tenant_id") != self.graph.tenant_id
                    or stored_auth.get("proposal_id") != command.proposal.id
                    or stored_auth.get("task_id") != command.proposal.task_id
                    or stored_auth.get("robot_id") != command.proposal.robot_id
                    or stored_auth.get("claim_id") != command.claim_id
                    or stored_auth.get("decision") != authorization.status
                    or stored_auth.get("action_payload_hash") != authorization.action_payload_hash
                    or json.loads(stored_auth["reason_codes_json"])
                    != list(authorization.reason_codes)
                    or stored_versions.model_dump(mode="json")
                    != authorization.versions.model_dump(mode="json")
                    or json.loads(stored_auth["witness_ids_json"])
                    != list(authorization.witness_ids)
                    or stored_auth.get("governance_integrity_version")
                    != authorization.governance_integrity_version
                    or stored_auth.get("valid_until_tick") != authorization.valid_until_tick
                    or stored_auth.get("created_world_tick") != command.effective_world_tick
                    or stored_resource_fences != dict(command.resource_fences)
                    or stored_auth.get("payload_json") != _canonical(authorization_json)
                ):
                    raise ValueError
                stored_event_payload = json.loads(stored_event["payload_json"])
                validated_event = DispatchEvent.model_validate({
                    "id": stored_event.get("id"),
                    "tenant_id": stored_event.get("tenant_id"),
                    "sequence": stored_event.get("sequence"),
                    "coordinator_epoch": stored_event.get("coordinator_epoch"),
                    "kind": stored_event.get("kind"),
                    "payload": stored_event_payload,
                    "payload_hash": stored_event.get("payload_hash"),
                    "effective_world_tick": stored_event.get("effective_world_tick"),
                })
                subject_ids = [command.command_id, command.proposal.task_id,
                               command.proposal.robot_id, command.claim_id,
                               authorization.authorization_id]
                if (
                    canonical_json_hash(stored_event_payload) != validated_event.payload_hash
                    or canonical_json_hash(stored_event_payload) != payload_hash
                    or validated_event.id != command_id
                    or stored_event.get("event_id") != command_id
                    or validated_event.tenant_id != self.graph.tenant_id
                    or validated_event.sequence != command.dispatch_sequence
                    or validated_event.coordinator_epoch != command.coordinator_epoch
                    or validated_event.kind != "COMMAND"
                    or validated_event.effective_world_tick != command.effective_world_tick
                    or json.loads(stored_event["subject_ids_json"]) != subject_ids
                ):
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise ValueError("cached command record failed integrity validation") from None
            root = self.graph.read_version_root()
            return {"graph_version": root["graph_version"],
                    "dispatch_sequence": stored_event["sequence"],
                    "command": stored_command, "authorization_receipt": stored_auth,
                    "event": stored_event}
        if expected_graph_version != authorization.versions.graph_version:
            raise ValueError('atomic expected version must equal bound authorization evidence version')
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        dependency_versions = dict(command.proposal.expected_versions.dependency_versions)
        resource_fences = dict(command.resource_fences)
        required_resources = list(command.proposal.required_resource_ids)
        if set(resource_fences) != set(required_resources):
            raise ValueError("command resource fences must exactly match required resources")
        if set(dependency_versions) != set(required_resources):
            raise ValueError("command dependency versions must exactly match required resources")
        claim_id = command.claim_id
        task_id = command.proposal.task_id
        robot_id = command.proposal.robot_id
        lease_read = self.graph._query(
            "MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}), "
            "(cl:Claim {id:$claim_id,tenant_id:$tenant_id}) "
            "WHERE s.graph_version=$expected_version "
            "RETURN s.graph_version AS graph_version,cl.lease_expires_at_utc AS claim_lease, "
            "s.coordinator_holder_id AS coordinator_holder_id, "
            "s.coordinator_epoch AS coordinator_epoch, "
            "s.coordinator_lease_expires_at_utc AS coordinator_lease",
            {"tenant_id": self.graph.tenant_id, "claim_id": claim_id,
             "expected_version": expected_graph_version},
        )
        if not lease_read.result_set:
            return None
        (preflight_version, claim_lease, coordinator_holder_id,
         coordinator_epoch, coordinator_lease) = lease_read.result_set[0]
        if (
            preflight_version != expected_graph_version
            or self.holder_id is None
            or not isinstance(self.holder_id, str)
            or not self.holder_id
            or coordinator_holder_id != self.holder_id
            or type(coordinator_epoch) is not int
            or coordinator_epoch != command.coordinator_epoch
            or not isinstance(coordinator_lease, str)
            or not coordinator_lease
            or not isinstance(claim_lease, str)
        ):
            return None
        try:
            parsed_claim_lease = datetime.fromisoformat(claim_lease.replace("Z", "+00:00"))
            parsed_coordinator_lease = datetime.fromisoformat(
                coordinator_lease.replace("Z", "+00:00")
            )
            if any(
                value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
                for value in (parsed_claim_lease, parsed_coordinator_lease)
            ):
                return None
        except (TypeError, ValueError):
            return None
        unix_epoch = datetime(1970, 1, 1, tzinfo=UTC)
        claim_delta = parsed_claim_lease.astimezone(UTC) - unix_epoch
        claim_deadline_ms = (
            claim_delta.days * 86_400_000
            + claim_delta.seconds * 1_000
            + claim_delta.microseconds // 1_000
        )
        coordinator_delta = parsed_coordinator_lease.astimezone(UTC) - unix_epoch
        coordinator_deadline_ms = (
            coordinator_delta.days * 86_400_000
            + coordinator_delta.seconds * 1_000
            + coordinator_delta.microseconds // 1_000
        )
        query = (
            "MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}), "
            "(t:Task {id:$task_id,tenant_id:$tenant_id}), "
            "(cl:Claim {id:$claim_id,tenant_id:$tenant_id}), "
            "(robot:Robot {id:$robot_id,tenant_id:$tenant_id}) "
            "WHERE s.graph_version=$expected_version AND s.policy_epoch=$policy_epoch "
            "AND s.coordinator_holder_id=$coordinator_holder_id "
            "AND s.coordinator_epoch=$coordinator_epoch "
            "AND s.coordinator_lease_expires_at_utc=$coordinator_lease "
            "AND timestamp()<$coordinator_deadline_ms "
            "AND t.task_version=$task_version "
            "AND t.state IN ['READY','PENDING','ACTIVE'] AND cl.state='ACTIVE' "
            "AND cl.fence=$fence AND cl.coordinator_epoch=s.coordinator_epoch "
            "AND cl.robot_id=$robot_id AND cl.lease_expires_at_utc=$claim_lease "
            "AND timestamp()<$deadline_ms "
            "AND coalesce(robot.available,false)=true "
            "MATCH (cl)-[:CLAIMS_TASK]->(t) MATCH (cl)-[:HELD_BY]->(robot) "
            "WITH s,t,cl,robot MATCH (t)-[:REQUIRES_RESOURCE]->(r:Resource) "
            "WHERE r.tenant_id=$tenant_id "
            "WITH s,t,cl,robot,collect(DISTINCT r) AS required_resources "
            "WHERE size(required_resources)=size($resource_ids) "
            "AND all(r IN required_resources WHERE r.id IN $resource_ids) "
            "UNWIND required_resources AS r "
            "WITH s,t,cl,robot,r WHERE (cl)-[:RESERVES]->(r) "
            "AND r.fence=$resource_fences[r.id] "
            "AND r.resource_version=$dependency_versions[r.id] "
            "WITH s,t,cl,robot,collect(DISTINCT r) AS resources "
            "WHERE size(resources)=size($resource_ids) "
            "AND s.dispatch_sequence+1=$dispatch_sequence "
            "SET s.dispatch_sequence=s.dispatch_sequence+1,s.graph_version=s.graph_version+1 "
            "CREATE (c:Command {id:$command_id,command_id:$command_id,tenant_id:$tenant_id, "
            "schema_version:$schema_version,created_at:$now,recorded_at:$now, "
            "payload_hash:$payload_hash,fence:$fence,state:'PREPARED', "
            "authorization_id:$authorization_id,dispatch_sequence:s.dispatch_sequence, "
            "coordinator_epoch:s.coordinator_epoch,payload_json:$command_json}) "
            "CREATE (a:AuthorizationReceipt {id:$authorization_id,tenant_id:$tenant_id, "
            "schema_version:$schema_version,created_at:$now,recorded_at:$now, "
            "proposal_id:$proposal_id,task_id:$task_id,robot_id:$robot_id,claim_id:$claim_id, "
            "decision:$decision,reason_codes_json:$reason_codes_json, "
            "action_payload_hash:$action_payload_hash,versions_json:$versions_json, "
            "resource_fences_json:$resource_fences_json,witness_ids_json:$witness_ids_json, "
            "governance_integrity_version:$integrity_version,valid_until_tick:$valid_until_tick, "
            "created_world_tick:$effective_world_tick,payload_json:$authorization_json}) "
            "CREATE (c)-[:FOR_TASK]->(t) CREATE (c)-[:UNDER_CLAIM]->(cl) "
            "CREATE (c)-[:AUTHORIZED_BY]->(a) "
            "CREATE (a)-[:FOR_PROPOSAL_TASK]->(t) CREATE (a)-[:FOR_ROBOT]->(robot) "
            "CREATE (a)-[:UNDER_CLAIM]->(cl) CREATE (e:DispatchEvent {id:$event_id, "
            "event_id:$event_id,tenant_id:$tenant_id,schema_version:$schema_version, "
            "created_at:$now,recorded_at:$now,occurred_at:$now,sequence:s.dispatch_sequence, "
            "coordinator_epoch:s.coordinator_epoch,kind:'COMMAND',payload_hash:$payload_hash, "
            "payload_json:$event_payload_json,subject_ids_json:$subject_ids_json, "
            "effective_world_tick:$effective_world_tick}) CREATE (e)-[:DELIVERS]->(c) "
            "RETURN properties(s) AS state,properties(c) AS command, "
            "properties(a) AS authorization_receipt,properties(e) AS event"
        )
        self.graph.query_count += 1
        self.graph.cas_query_count += 1
        result = self.graph._graph.query(query, {
            "tenant_id": self.graph.tenant_id, "expected_version": expected_graph_version,
            "task_id": task_id, "claim_id": claim_id, "robot_id": robot_id,
            "policy_epoch": command.policy_epoch, "coordinator_epoch": command.coordinator_epoch,
            "deadline_ms": claim_deadline_ms, "claim_lease": claim_lease,
            "coordinator_holder_id": self.holder_id,
            "coordinator_lease": coordinator_lease,
            "coordinator_deadline_ms": coordinator_deadline_ms,
            "task_version": command.proposal.expected_versions.task_version,
            "fence": command.fence, "now": now, "resource_ids": required_resources,
            "dispatch_sequence": command.dispatch_sequence,
            "resource_fences": resource_fences, "dependency_versions": dependency_versions,
            "command_id": command.command_id, "schema_version": GRAPH_SCHEMA_VERSION,
            "payload_hash": payload_hash, "authorization_id": authorization.authorization_id,
            "command_json": _canonical(command_json), "proposal_id": command.proposal.id,
            "decision": authorization.status, "reason_codes_json": _canonical(list(authorization.reason_codes)),
            "action_payload_hash": authorization.action_payload_hash,
            "versions_json": _canonical(authorization.versions.model_dump(mode="json")),
            "resource_fences_json": _canonical(resource_fences),
            "witness_ids_json": _canonical(list(authorization.witness_ids)),
            "integrity_version": authorization.governance_integrity_version,
            "valid_until_tick": authorization.valid_until_tick,
            "effective_world_tick": command.effective_world_tick,
            "authorization_json": _canonical(authorization_json),
            "event_id": command.command_id, "event_payload_json": _canonical(payload),
            "subject_ids_json": _canonical(subject_ids),
        })
        if not result.result_set:
            return None
        row = dict(zip([header[1] for header in result.header], result.result_set[0], strict=True))
        return {"graph_version": row["state"]["graph_version"],
                "dispatch_sequence": row["state"]["dispatch_sequence"],
                "command": dict(row["command"]),
                "authorization_receipt": dict(row["authorization_receipt"]),
                "event": dict(row["event"])}

    def append_control_event(self, *, event, expected_graph_version):
        event_id = event.get("id")
        kind = event.get("kind")
        payload = event.get("payload")
        subject_ids = event.get("subject_ids", [])
        tick = event.get("effective_world_tick")
        if not event_id or kind not in {"POLICY_ACTIVATION", "REVOCATION", "FENCE_INSTALL"}:
            raise ValueError("control event ID and supported control kind are required")
        if not isinstance(payload, dict) or not isinstance(subject_ids, list) or any(
            not isinstance(subject, str) or not subject for subject in subject_ids
        ):
            raise ValueError("control event payload and subject IDs are invalid")
        if type(tick) is not int or tick < 0:
            raise ValueError("control event effective_world_tick must be nonnegative")
        payload_hash = canonical_json_hash(payload)
        if event.get("payload_hash") != payload_hash:
            raise ValueError("control event payload_hash does not match payload")
        payload_json = _canonical(payload)
        subject_ids_json = _canonical(subject_ids)
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        query = (
            "MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}) "
            "WHERE s.graph_version=$expected_version "
            "SET s.dispatch_sequence=s.dispatch_sequence+1,s.graph_version=s.graph_version+1 "
            "CREATE (e:DispatchEvent {id:$event_id,event_id:$event_id,tenant_id:$tenant_id, "
            "schema_version:$schema_version,created_at:$now,recorded_at:$now,occurred_at:$now, "
            "sequence:s.dispatch_sequence,coordinator_epoch:s.coordinator_epoch,kind:$kind, "
            "payload_hash:$payload_hash,payload_json:$payload_json,subject_ids_json:$subject_ids_json, "
            "effective_world_tick:$tick}) "
            "RETURN properties(s) AS state,properties(e) AS event"
        )
        self.graph.query_count += 1
        self.graph.cas_query_count += 1
        result = self.graph._graph.query(query, {
            "tenant_id": self.graph.tenant_id, "expected_version": expected_graph_version,
            "event_id": event_id, "schema_version": GRAPH_SCHEMA_VERSION, "now": now,
            "kind": kind, "payload_hash": payload_hash, "payload_json": payload_json,
            "subject_ids_json": subject_ids_json, "tick": tick,
        })
        if not result.result_set:
            return None
        row = dict(zip([header[1] for header in result.header], result.result_set[0], strict=True))
        return {**dict(row["event"]), "graph_version": row["state"]["graph_version"],
                "dispatch_sequence": row["state"]["dispatch_sequence"],
                "payload": payload}

    def read_outbox(self, after_sequence=0):
        if type(after_sequence) is not int or after_sequence < 0:
            raise ValueError("after_sequence must be a nonnegative integer")
        result = self.graph._query(
            "MATCH (e:DispatchEvent {tenant_id:$tenant_id}) WHERE e.sequence>$after_sequence "
            "RETURN properties(e) AS event ORDER BY e.sequence",
            {"tenant_id": self.graph.tenant_id, "after_sequence": after_sequence},
        )
        rows = []
        for row in result.result_set:
            item = dict(row[0])
            raw_event_id = item.get("event_id", item.get("id"))
            event_id = (raw_event_id if isinstance(raw_event_id, str)
                        and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", raw_event_id)
                        else "<unknown>")
            raw_sequence = item.get("sequence")
            sequence = (raw_sequence if type(raw_sequence) is int and raw_sequence >= 0
                        else None)
            if "payload_json" not in item or not isinstance(item["payload_json"], str):
                raise OutboxIntegrityError(event_id=event_id, sequence=sequence,
                                           reason="missing_payload_json")
            try:
                payload = json.loads(item["payload_json"])
            except (TypeError, ValueError):
                raise OutboxIntegrityError(event_id=event_id, sequence=sequence,
                                           reason="malformed_payload_json") from None
            if not isinstance(payload, dict):
                raise OutboxIntegrityError(event_id=event_id, sequence=sequence,
                                           reason="invalid_payload_shape")
            try:
                from witness_fleet.domain import DispatchEvent

                DispatchEvent.model_validate({
                    key: item[key] for key in (
                        "id", "tenant_id", "sequence", "coordinator_epoch", "kind",
                        "payload_hash", "effective_world_tick",
                    ) if key in item
                } | {"payload": payload})
            except Exception:
                raise OutboxIntegrityError(event_id=event_id, sequence=sequence,
                                           reason="invalid_event_or_payload_hash") from None
            try:
                subject_ids = json.loads(item["subject_ids_json"])
            except (KeyError, TypeError, ValueError):
                raise OutboxIntegrityError(event_id=event_id, sequence=sequence,
                                           reason="malformed_subject_ids_json") from None
            if not isinstance(subject_ids, list) or any(
                not isinstance(subject_id, str) or not subject_id for subject_id in subject_ids
            ):
                raise OutboxIntegrityError(event_id=event_id, sequence=sequence,
                                           reason="invalid_subject_ids_shape")
            item["payload"] = payload
            item["subject_ids"] = subject_ids
            rows.append(item)
        return rows

    def get_command(self, command_id):
        item = self.graph.get_node("Command", command_id)
        if item is None:
            return None
        from witness_fleet.domain import CommandIntent
        return CommandIntent.model_validate(json.loads(item["payload_json"]))
