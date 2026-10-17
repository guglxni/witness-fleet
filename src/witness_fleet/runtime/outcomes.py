"""Fenced atomic task completion from retained physical observations.

The coordinator calls this only after its local adapter validates the native
command receipt. This store independently rereads the retained command and
claim, then performs one graph compare-and-swap for all authoritative changes.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

from witness_fleet.domain import CommandIntent, Observation, canonical_json_hash

_ALLOWED_COMMAND_STATES = frozenset({
    "PREPARED", "SENT", "ACCEPTED", "RUNNING", "CONTROLLER_DONE",
})
_ALLOWED_TASK_STATES = frozenset({"READY", "PENDING", "ACTIVE", "RUNNING"})


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("retained timestamp is missing or invalid")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("retained timestamp must be explicit UTC")
    return parsed.astimezone(UTC)


def _deadline_ms(value: datetime) -> int:
    delta = value - datetime(1970, 1, 1, tzinfo=UTC)
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000


def _is_nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _one_row(result: Any) -> dict[str, Any] | None:
    if not result.result_set:
        return None
    return dict(zip((item[1] for item in result.header), result.result_set[0], strict=True))


class OutcomeStore:
    """Write one fenced outcome, or fail closed without changing graph state."""

    def __init__(self, graph, holder_id: str):
        if not isinstance(holder_id, str) or not holder_id:
            raise ValueError("configured coordinator holder_id is required")
        self.graph = graph
        self.holder_id = holder_id

    def finish(
        self,
        command_id: str,
        *,
        expected_graph_version: int,
        observations: tuple[Observation, ...],
        world_tick: int,
        outcome: str = "verified",
    ) -> dict[str, Any] | None:
        """Atomically finish a task using its retained command and sensor evidence.

        ``VERIFIED_BY`` is an explicit outcome-evidence relationship introduced
        here; it points from the retained Command to the exact retained Observation
        records whose canonical payload hashes are committed in ``outcome_json``.
        """
        if not isinstance(command_id, str) or not command_id:
            raise ValueError("command_id is required")
        if not _is_nonnegative_int(expected_graph_version):
            raise ValueError("expected_graph_version must be a nonnegative exact integer")
        if not _is_nonnegative_int(world_tick):
            raise ValueError("world_tick must be a nonnegative exact integer")
        if outcome not in {"verified", "failed"}:
            raise ValueError("outcome must be 'verified' or 'failed'")
        if not isinstance(observations, tuple) or any(
            not isinstance(item, Observation) for item in observations
        ):
            raise ValueError("observations must be a tuple of typed Observation records")
        if len({item.id for item in observations}) != len(observations):
            raise ValueError("observation IDs must be unique")

        from witness_fleet.runtime.measurement_validation import measured_effect_valid

        now = datetime.now(UTC)
        command_node = self.graph.get_node("Command", command_id)
        if command_node is None:
            return None
        try:
            if (command_node.get("tenant_id") != self.graph.tenant_id
                    or command_node.get("id") != command_id
                    or command_node.get("command_id") != command_id):
                return None
            raw_command = json.loads(command_node["payload_json"])
            command = CommandIntent.model_validate(raw_command)
            command_envelope_hash = canonical_json_hash(raw_command)
            if (command.command_id != command_id
                    or command_node.get("payload_hash") != command_envelope_hash
                    or command_node.get("fence") != command.fence
                    or command_node.get("authorization_id") != command.authorization_id
                    or command_node.get("dispatch_sequence") != command.dispatch_sequence
                    or command_node.get("coordinator_epoch") != command.coordinator_epoch):
                return None
        except (KeyError, TypeError, ValueError):
            return None

        episode_ids = self._episode_ids(command)
        if observations and (
            len(episode_ids) != 1
            or episode_ids != {item.episode_id for item in observations}
        ):
            return None
        episode_id: str | None = None
        if len(episode_ids) == 1:
            episode_id = next(iter(episode_ids))
        proof_refs: list[dict[str, Any]] = []
        proof_payloads: list[str] = []
        evidence_episode: str | None = None
        for proposed in observations:
            retained = self.graph.get_node("Observation", proposed.id)
            if retained is None:
                return None
            try:
                raw_observation = json.loads(retained["payload_json"])
                observation = Observation.model_validate(raw_observation)
                digest = canonical_json_hash(raw_observation)
                if (observation != proposed or observation.id != retained.get("id")
                        or observation.tenant_id != self.graph.tenant_id
                        or retained.get("tenant_id") != self.graph.tenant_id
                        or digest != canonical_json_hash(proposed)
                        or retained.get("predicate") != observation.predicate
                        or type(retained.get("value")) is not type(observation.value)
                        or retained.get("value") != observation.value
                        or retained.get("robot_id") != observation.robot_id
                        or retained.get("visibility") != observation.visibility
                        or retained.get("expires_tick") != observation.expires_tick
                        or retained.get("scope_json") != _canonical(dict(observation.scope))):
                    return None
                if (episode_id is None or observation.episode_id != episode_id
                        or (evidence_episode is not None and observation.episode_id != evidence_episode)
                        or observation.robot_id != command.proposal.robot_id
                        or observation.subject_id != command.proposal.corridor_id
                        or dict(observation.scope) != {"corridor_id": command.proposal.corridor_id}
                        or observation.world_tick > world_tick
                        or observation.expires_tick <= world_tick
                        or observation.occurred_at > now or observation.recorded_at > now
                        or not observation.sensor_config_hash
                        or not all(math.isfinite(item) for item in self._finite_numbers(observation))):
                    return None
                if outcome == "verified" and (
                    type(observation.value) is not bool or observation.value is not True
                    or (observation.visibility != "visible"
                        and not measured_effect_valid(command, observation))
                ):
                    return None
                evidence_episode = observation.episode_id
            except (KeyError, TypeError, ValueError, AttributeError):
                return None
            proof_refs.append({
                "observation_id": observation.id,
                "payload_hash": digest,
                "predicate": observation.predicate,
                "world_tick": observation.world_tick,
            })
            proof_payloads.append(_canonical(raw_observation))

        if outcome == "verified":
            required = set(command.proposal.expected_effects)
            observed = {item["predicate"] for item in proof_refs}
            if not required or not observations or observed != required:
                return None
        outcome_record = {
            "command_id": command_id,
            "command_payload_hash": command_envelope_hash,
            "outcome": outcome,
            "world_tick": world_tick,
            "observation_refs": proof_refs,
        }
        outcome_json = _canonical(outcome_record)
        outcome_hash = canonical_json_hash(outcome_record)

        # Exact replay of a committed proof is read-only and does not require its
        # former expected version to remain the current graph version.
        if command_node.get("state") in {"OUTCOME_VERIFIED", "FAILED"}:
            return self._replay(command_node, command, outcome, outcome_json, outcome_hash)
        if command_node.get("state") not in _ALLOWED_COMMAND_STATES:
            return None

        root = self.graph.read_version_root()
        if (not isinstance(root, dict)
                or root.get("tenant_id") != self.graph.tenant_id
                or not _is_nonnegative_int(root.get("graph_version"))
                or root["graph_version"] != expected_graph_version
                or root.get("coordinator_holder_id") != self.holder_id
                or root.get("coordinator_epoch") != command.coordinator_epoch):
            return None
        try:
            coordinator_lease = root["coordinator_lease_expires_at_utc"]
            coordinator_deadline = _utc(coordinator_lease)
            if coordinator_deadline <= now:
                return None
        except (KeyError, TypeError, ValueError):
            return None

        claim_node = self.graph.get_node("Claim", command.claim_id)
        if claim_node is None:
            return None
        try:
            retained_fences_json = claim_node.get("resource_fences_json")
            claim_resource_fences = (
                self._claim_resource_fences(command.claim_id)
                if retained_fences_json is None else json.loads(retained_fences_json)
            )
            if (claim_node.get("tenant_id") != self.graph.tenant_id
                    or claim_node.get("id") != command.claim_id
                    or claim_node.get("task_id") != command.proposal.task_id
                    or claim_node.get("robot_id") != command.proposal.robot_id
                    or claim_node.get("state") != "ACTIVE"
                    or claim_node.get("coordinator_epoch") != command.coordinator_epoch
                    or claim_node.get("fence") != command.fence
                    or not isinstance(claim_resource_fences, dict)
                    or claim_resource_fences != dict(command.resource_fences)):
                return None
            claim_lease = claim_node["lease_expires_at_utc"]
            claim_deadline = _utc(claim_lease)
            if claim_deadline <= now:
                return None
        except (KeyError, TypeError, ValueError):
            return None

        task = self.graph.get_node("Task", command.proposal.task_id)
        if (task is None or task.get("tenant_id") != self.graph.tenant_id
                or task.get("state") not in _ALLOWED_TASK_STATES
                or task.get("task_version") != command.proposal.expected_versions.task_version
                or task.get("claim_fence") != command.fence):
            return None

        auth_read = self.graph._query(
            "MATCH (c:Command {id:$command_id,tenant_id:$tenant_id})-[:AUTHORIZED_BY]->"
            "(a:AuthorizationReceipt {id:$authorization_id,tenant_id:$tenant_id}) "
            "RETURN properties(a) AS authorization",
            {"command_id": command_id, "authorization_id": command.authorization_id,
             "tenant_id": self.graph.tenant_id},
        )
        auth_row = _one_row(auth_read)
        if auth_row is None:
            return None
        auth_record = auth_row.get("authorization")
        try:
            if (json.loads(auth_record["payload_json"])
                    != command.authorization.model_dump(mode="json")
                    or auth_record.get("decision") != "ALLOW"
                    or auth_record.get("claim_id") != command.claim_id
                    or auth_record.get("task_id") != command.proposal.task_id
                    or auth_record.get("robot_id") != command.proposal.robot_id):
                return None
        except (KeyError, TypeError, ValueError):
            return None

        required_resources = list(command.proposal.required_resource_ids)
        if (not required_resources
                or set(required_resources) != set(command.resource_fences)
                or set(required_resources) != set(command.proposal.expected_versions.dependency_versions)):
            return None
        if observations:
            if len(episode_ids) != 1 or episode_ids != {item.episode_id for item in observations}:
                return None
            episode_id = next(iter(episode_ids))
        elif len(episode_ids) == 1:
            episode_id = next(iter(episode_ids))
        else:
            return None

        terminal_command = "OUTCOME_VERIFIED" if outcome == "verified" else "FAILED"
        terminal_task = "VERIFIED" if outcome == "verified" else "FAILED"
        terminal_claim = "RELEASED" if outcome == "verified" else "REASSESS"
        observed_at = now.isoformat().replace("+00:00", "Z")
        query = (
            "MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}), "
            "(c:Command {id:$command_id,tenant_id:$tenant_id}), "
            "(t:Task {id:$task_id,tenant_id:$tenant_id}), "
            "(cl:Claim {id:$claim_id,tenant_id:$tenant_id}), "
            "(robot:Robot {id:$robot_id,tenant_id:$tenant_id}), "
            "(corridor:Corridor {id:$corridor_id,tenant_id:$tenant_id}), "
            "(auth:AuthorizationReceipt {id:$authorization_id,tenant_id:$tenant_id}) "
            "WHERE s.graph_version=$expected_version AND s.coordinator_holder_id=$holder_id "
            "AND s.coordinator_epoch=$coordinator_epoch "
            "AND s.coordinator_lease_expires_at_utc=$coordinator_lease "
            "AND timestamp()<$coordinator_deadline_ms "
            "AND c.state IN ['PREPARED','SENT','ACCEPTED','RUNNING','CONTROLLER_DONE'] "
            "AND c.payload_hash=$command_payload_hash AND c.payload_json=$command_json "
            "AND c.fence=$fence AND c.dispatch_sequence=$dispatch_sequence "
            "AND c.coordinator_epoch=$coordinator_epoch AND c.authorization_id=$authorization_id "
            "AND t.task_version=$task_version AND t.state IN ['READY','PENDING','ACTIVE','RUNNING'] "
            "AND t.claim_fence=$fence "
            "AND cl.state='ACTIVE' AND cl.coordinator_epoch=$coordinator_epoch "
            "AND cl.task_id=$task_id AND cl.robot_id=$robot_id AND cl.fence=$fence "
            "AND cl.lease_expires_at_utc=$claim_lease "
            "AND timestamp()<$claim_deadline_ms "
            "MATCH (c)-[:FOR_TASK]->(t) MATCH (c)-[:UNDER_CLAIM]->(cl) "
            "MATCH (c)-[:AUTHORIZED_BY]->(auth) MATCH (cl)-[:CLAIMS_TASK]->(t) "
            "MATCH (cl)-[:HELD_BY]->(robot) MATCH (t)-[:USES]->(corridor) "
            "MATCH (episode:Episode)-[:CONTAINS]->(t) "
            "WITH DISTINCT s,c,t,cl,robot,corridor,auth,collect(DISTINCT episode) AS episodes "
            "WHERE size(episodes)=1 AND episodes[0].id=$episode_id "
            "AND episodes[0].tenant_id=$tenant_id "
            "WITH s,c,t,cl,robot,corridor,auth,episodes[0] AS ep "
            "MATCH (ep)-[:OCCURRED_AT]->(corridor) "
            "MATCH (cl)-[:RESERVES]->(first_resource:Resource {tenant_id:$tenant_id}) "
            "WITH DISTINCT s,c,t,cl,robot,corridor,auth,ep "
            "MATCH (t)-[:REQUIRES_RESOURCE]->(r:Resource {tenant_id:$tenant_id}) "
            "WITH s,c,t,cl,robot,corridor,auth,ep,collect(DISTINCT r) AS resources "
            "WHERE size(resources)=size($resource_ids) "
            "AND all(r IN resources WHERE r.id IN $resource_ids "
            "AND r.fence=$resource_fences[r.id] "
            "AND r.resource_version=$dependency_versions[r.id] "
            "AND (cl)-[:RESERVES]->(r)) "
            "AND all(id IN $resource_ids WHERE any(r IN resources WHERE r.id=id)) "
            "WITH s,c,t,cl,robot,corridor,auth,ep,resources "
            "UNWIND CASE WHEN size($observations)=0 THEN [null] ELSE $observations END AS proof "
            "OPTIONAL MATCH (owner:Episode)-[:CONTAINS]->"
            "(o:Observation {id:proof.id,tenant_id:$tenant_id}) "
            "WHERE proof IS NOT NULL AND o.payload_json=proof.payload_json "
            "AND o.predicate=proof.predicate AND o.value=proof.value "
            "AND o.visibility=proof.visibility AND o.robot_id=proof.robot_id "
            "AND o.expires_tick=proof.expires_tick "
            "AND o.scope_json=proof.scope_json "
            "WITH s,c,t,cl,robot,corridor,auth,ep,resources,proof, "
            "collect(DISTINCT owner.id) AS owners,collect(DISTINCT o) AS proof_evidence "
            "WHERE proof IS NULL OR (size(owners)=1 AND owners[0]=$episode_id "
            "AND size(proof_evidence)=1) "
            "WITH s,c,t,cl,robot,corridor,auth,ep,resources, "
            "collect(CASE WHEN proof IS NULL THEN null ELSE proof_evidence[0] END) AS evidence "
            "WHERE size(evidence)=size($observations) "
            "AND ($outcome='failed' OR all(o IN evidence WHERE o.value=true "
            "AND (o.visibility='visible' OR o.id IN $native_measurement_ids))) "
            "SET s.graph_version=s.graph_version+1, c.state=$terminal_command, "
            "c.outcome_json=$outcome_json, c.outcome_hash=$outcome_hash, "
            "c.outcome_world_tick=$world_tick, c.outcome_recorded_at=$observed_at, "
            "t.state=$terminal_task,t.task_version=t.task_version+1,cl.state=$terminal_claim "
            "FOREACH (o IN evidence | CREATE (c)-[:VERIFIED_BY]->(o)) "
            "RETURN properties(s) AS state,properties(c) AS command, "
            "properties(t) AS task,properties(cl) AS claim"
        )
        params = {
            "tenant_id": self.graph.tenant_id,
            "command_id": command_id,
            "task_id": command.proposal.task_id,
            "claim_id": command.claim_id,
            "robot_id": command.proposal.robot_id,
            "corridor_id": command.proposal.corridor_id,
            "episode_id": episode_id,
            "authorization_id": command.authorization_id,
            "expected_version": expected_graph_version,
            "holder_id": self.holder_id,
            "coordinator_epoch": command.coordinator_epoch,
            "coordinator_lease": coordinator_lease,
            "coordinator_deadline_ms": _deadline_ms(coordinator_deadline),
            "claim_lease": claim_lease,
            "claim_deadline_ms": _deadline_ms(claim_deadline),
            "command_payload_hash": command_envelope_hash,
            "command_json": _canonical(raw_command),
            "dispatch_sequence": command.dispatch_sequence,
            "fence": command.fence,
            "task_version": command.proposal.expected_versions.task_version,
            "resource_fences_json": _canonical(dict(command.resource_fences)),
            "resource_ids": required_resources,
            "resource_fences": dict(command.resource_fences),
            "dependency_versions": dict(command.proposal.expected_versions.dependency_versions),
            "observations": [
                {"id": item["observation_id"], "payload_json": proof,
                 "predicate": item["predicate"],
                 "value": json.loads(proof)["value"],
                 "visibility": json.loads(proof)["visibility"],
                 "robot_id": json.loads(proof)["robot_id"],
                 "expires_tick": json.loads(proof)["expires_tick"],
                 "scope_json": _canonical(json.loads(proof)["scope"])}
                for item, proof in zip(proof_refs, proof_payloads, strict=True)
            ],
            "world_tick": world_tick,
            "outcome": outcome,
            "native_measurement_ids": [
                item.id for item in observations if measured_effect_valid(command, item)
            ],
            "terminal_command": terminal_command,
            "terminal_task": terminal_task,
            "terminal_claim": terminal_claim,
            "outcome_json": outcome_json,
            "outcome_hash": outcome_hash,
            "observed_at": observed_at,
        }
        self.graph.query_count += 1
        self.graph.cas_query_count += 1
        # Call-before-write seam lets tests inject additive graph writers before CAS.
        result = self.graph._graph.query(query, params)
        row = _one_row(result)
        if row is None:
            return None
        return {
            "graph_version": row["state"]["graph_version"],
            "command": dict(row["command"]),
            "task": dict(row["task"]),
            "claim": dict(row["claim"]),
            "outcome": outcome_record,
        }

    @staticmethod
    def _finite_numbers(observation: Observation) -> tuple[float, ...]:
        numbers: list[float] = []
        if isinstance(observation.value, float):
            numbers.append(observation.value)
        for coordinate in (observation.pose.x, observation.pose.y,
                           observation.pose.z, observation.pose.yaw):
            numbers.append(coordinate)
        return tuple(numbers)

    def _claim_resource_fences(self, claim_id: str) -> dict[str, int]:
        result = self.graph._query(
            "MATCH (cl:Claim {id:$claim_id,tenant_id:$tenant_id})-[:RESERVES]->"
            "(r:Resource {tenant_id:$tenant_id}) RETURN r.id AS id,r.fence AS fence",
            {"claim_id": claim_id, "tenant_id": self.graph.tenant_id},
        )
        return {row[0]: row[1] for row in result.result_set}

    def _episode_ids(self, command: CommandIntent) -> set[str]:
        result = self.graph._query(
            "MATCH (ep:Episode)-[:CONTAINS]->"
            "(t:Task {id:$task_id,tenant_id:$tenant_id}) "
            "WITH collect(DISTINCT ep) AS owners "
            "WHERE size(owners)=1 AND owners[0].tenant_id=$tenant_id "
            "WITH owners[0] AS ep "
            "MATCH (ep)-[:OCCURRED_AT]->(corridor:Corridor {id:$corridor_id,tenant_id:$tenant_id}) "
            "RETURN ep.id AS id",
            {"tenant_id": self.graph.tenant_id, "task_id": command.proposal.task_id,
             "corridor_id": command.proposal.corridor_id},
        )
        return {row[0] for row in result.result_set}

    def _replay(self, command_node, command, outcome, outcome_json, outcome_hash):
        expected_state = "OUTCOME_VERIFIED" if outcome == "verified" else "FAILED"
        expected_task = "VERIFIED" if outcome == "verified" else "FAILED"
        expected_claim = "RELEASED" if outcome == "verified" else "REASSESS"
        if (command_node.get("state") != expected_state
                or command_node.get("outcome_json") != outcome_json
                or command_node.get("outcome_hash") != outcome_hash):
            return None
        refs = {item["observation_id"]: item for item in json.loads(outcome_json)["observation_refs"]}
        evidence_result = self.graph._query(
            "MATCH (c:Command {id:$command_id,tenant_id:$tenant_id})-[:VERIFIED_BY]->"
            "(o:Observation {tenant_id:$tenant_id}) RETURN o.id AS id,o.payload_json AS payload_json",
            {"command_id": command.command_id, "tenant_id": self.graph.tenant_id},
        )
        linked = {row[0]: row[1] for row in evidence_result.result_set}
        if set(linked) != set(refs):
            return None
        try:
            for observation_id, payload_json in linked.items():
                payload = json.loads(payload_json)
                if (canonical_json_hash(payload) != refs[observation_id]["payload_hash"]
                        or payload.get("id") != observation_id):
                    return None
        except (TypeError, ValueError, KeyError):
            return None
        episode_ids = self._episode_ids(command)
        if len(episode_ids) != 1:
            return None
        selected_episode_id = next(iter(episode_ids))
        episode_edges = self.graph._query(
            "MATCH (ep:Episode)-[:CONTAINS]->"
            "(o:Observation {tenant_id:$tenant_id}) WHERE o.id IN $observation_ids "
            "RETURN o.id AS id,collect(DISTINCT {id:ep.id,tenant_id:ep.tenant_id}) AS owners",
            {"tenant_id": self.graph.tenant_id,
             "observation_ids": list(refs)},
        )
        memberships = {row[0]: row[1] for row in episode_edges.result_set}
        expected_owners = [{"id": selected_episode_id, "tenant_id": self.graph.tenant_id}]
        if (set(memberships) != set(refs)
                or any(owners != expected_owners for owners in memberships.values())):
            return None
        result = self.graph._query(
            "MATCH (c:Command {id:$command_id,tenant_id:$tenant_id})-[:FOR_TASK]->"
            "(t:Task {tenant_id:$tenant_id}), (c)-[:UNDER_CLAIM]->"
            "(cl:Claim {tenant_id:$tenant_id}), (s:FleetState {id:'fleet',tenant_id:$tenant_id}) "
            "WHERE t.state=$task_state AND cl.state=$claim_state "
            "RETURN s.graph_version AS graph_version,properties(c) AS command, "
            "properties(t) AS task,properties(cl) AS claim",
            {"command_id": command.command_id, "tenant_id": self.graph.tenant_id,
             "task_state": expected_task, "claim_state": expected_claim},
        )
        row = _one_row(result)
        if row is None:
            return None
        return {
            "graph_version": row["graph_version"],
            "command": dict(row["command"]),
            "task": dict(row["task"]),
            "claim": dict(row["claim"]),
            "outcome": json.loads(outcome_json),
        }
