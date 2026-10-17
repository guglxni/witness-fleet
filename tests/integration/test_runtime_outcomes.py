from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.domain import (
    ActionProposal,
    AuthorizationResult,
    CommandIntent,
    Observation,
    Pose,
    SkillKind,
    VersionVector,
    canonical_json_hash,
    payload_hash,
)
from witness_fleet.runtime.storage import TransitionStore

pytestmark = pytest.mark.integration


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _active_coordinator(graph) -> tuple[str, int, str]:
    root = graph.read_version_root()
    assert root is not None
    holder = root.get("coordinator_holder_id")
    lease = root.get("coordinator_lease_expires_at_utc")
    now = datetime.now(UTC)
    if not isinstance(holder, str) or not isinstance(lease, str) or datetime.fromisoformat(
        lease.replace("Z", "+00:00")
    ) <= now + timedelta(minutes=2):
        lease_now = now
        if isinstance(lease, str):
            retained = datetime.fromisoformat(lease.replace("Z", "+00:00"))
            lease_now = max(lease_now, retained + timedelta(milliseconds=1))
        lease_expiry = lease_now + timedelta(hours=1)
        acquired = TransitionStore(graph).acquire_coordinator(
            expected_epoch=root["coordinator_epoch"], holder_id=f"it-outcome-holder-{uuid.uuid4().hex}",
            now_utc=lease_now.isoformat(), lease_expires_at_utc=lease_expiry.isoformat(),
            event_id=f"it-outcome-barrier-{uuid.uuid4().hex}", effective_world_tick=0,
        )
        assert acquired is not None
        holder = acquired["coordinator_holder_id"]
        lease = acquired["coordinator_lease_expires_at_utc"]
        root = acquired
    return holder, root["coordinator_epoch"], lease


def _prepared_command(graph, *, expected_effects=("arrived",), second_task=False):
    suffix = uuid.uuid4().hex
    ids = graph.seed_claim_fixture(suffix, second_task=second_task)
    holder, epoch, lease = _active_coordinator(graph)
    corridor_id = f"it-outcome-{suffix}-corridor"
    episode_id = f"it-outcome-{suffix}-episode"
    graph.append_node("Map", f"it-outcome-{suffix}-map", {
        "map_version": 0, "configuration_hash": "a" * 64,
    })
    graph.append_node("Corridor", corridor_id, {
        "map_id": f"it-outcome-{suffix}-map", "map_version": 0, "nominal_width_m": 1.2,
    })
    graph.append_edge("USES", "Task", ids["task_id"], "Corridor", corridor_id)
    graph.append_node("Episode", episode_id, {
        "scenario_family": "SC-001", "outcome": "pending", "verification_state": "unverified",
        "configuration_hash": "a" * 64, "payload_json": _json({"episode_id": episode_id}),
    })
    graph.append_edge("CONTAINS", "Episode", episode_id, "Task", ids["task_id"])
    graph.append_edge("OCCURRED_AT", "Episode", episode_id, "Corridor", corridor_id)

    now = datetime.now(UTC)
    claim = graph.claim_task(
        task_id=ids["task_id"], robot_id=ids["robot_0"], expected_task_version=0,
        coordinator_epoch=epoch, resource_ids=ids["resource_ids"],
        lease_expires_at_utc=lease, now_utc=now.isoformat(),
    )
    assert claim is not None
    root = graph.read_version_root()
    task = graph.get_node("Task", ids["task_id"])
    resources = {rid: graph.get_node("Resource", rid) for rid in ids["resource_ids"]}
    assert root is not None and task is not None and all(resources.values())
    versions = VersionVector(
        graph_version=root["graph_version"], policy_epoch=root["policy_epoch"],
        coordinator_epoch=epoch, task_version=task["task_version"],
        dependency_versions={rid: resources[rid]["resource_version"] for rid in ids["resource_ids"]},
    )
    proposal = ActionProposal(
        id=f"it-outcome-{suffix}-proposal", robot_id=ids["robot_0"], task_id=ids["task_id"],
        kind=SkillKind.INSPECT, parameters={"target": "fixture"}, expected_versions=versions,
        required_predicates=(), required_resource_ids=tuple(ids["resource_ids"]),
        expected_effects=tuple(expected_effects), corridor_id=corridor_id,
    )
    authorization = AuthorizationResult(
        authorization_id=f"it-outcome-{suffix}-auth", status="ALLOW", reason_codes=(), witness_ids=(),
        versions=versions, action_payload_hash=payload_hash(proposal), valid_until_tick=100,
        claim_id=claim["claim_id"], task_id=ids["task_id"], robot_id=ids["robot_0"],
        fence=claim["fence"], resource_fences=claim["resource_fences"],
        governance_integrity_version=root["policy_epoch"],
    )
    command = CommandIntent(
        command_id=f"it-outcome-{suffix}-command", proposal=proposal,
        payload_hash=payload_hash(proposal), claim_id=claim["claim_id"], fence=claim["fence"],
        resource_fences=claim["resource_fences"], authorization_id=authorization.authorization_id,
        policy_epoch=root["policy_epoch"], coordinator_epoch=epoch,
        dispatch_sequence=root["dispatch_sequence"] + 1, effective_world_tick=1,
        authorization=authorization,
    )
    transitions = TransitionStore(graph, holder_id=holder)
    prepared = transitions.prepare_command(
        command=command, authorization=authorization, expected_graph_version=root["graph_version"],
    )
    assert prepared is not None
    return graph, holder, command, ids, episode_id, corridor_id


def _retain_observation(graph, command, expected_episode_id, corridor_id, *, predicate="arrived",
                        value=True, link_episode=True, **changes):
    now = datetime.now(UTC)
    observation_payload = {
        "id": f"it-outcome-observation-{uuid.uuid4().hex}", "tenant_id": graph.tenant_id,
        "episode_id": expected_episode_id, "robot_id": command.proposal.robot_id, "occurred_at": now,
        "recorded_at": now, "world_tick": 2, "expires_tick": 20,
        "predicate": predicate, "value": value, "pose": Pose(x=0.0, y=0.0),
        "frame": "map", "visibility": "visible",
        "scope": {"corridor_id": corridor_id}, "quality": {"source": "integration-sensor"},
        "sensor_config_hash": "b" * 64, "subject_id": corridor_id,
    }
    observation_payload.update(changes)
    observation = Observation.model_validate(observation_payload)
    if observation.episode_id == expected_episode_id and link_episode:
        from witness_fleet.runtime.observation_store import retain_observations

        return retain_observations(graph, (observation,), episode_id=expected_episode_id)[0]
    graph.append_node("Observation", observation.id, {
        "predicate": observation.predicate, "value": observation.value,
        "robot_id": observation.robot_id,
        "pose": _json(observation.pose.model_dump(mode="json")), "frame": observation.frame,
        "visibility": observation.visibility, "quality": _json(dict(observation.quality)),
        "expires_tick": observation.expires_tick, "scope_json": _json(dict(observation.scope)),
        "payload_json": _json(observation.model_dump(mode="json")),
    })
    return observation


def test_verified_outcome_atomically_completes_task_and_is_idempotent(isolated_runtime_graph):  # noqa: F811
    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    before = graph.read_version_root()
    assert before is not None

    from witness_fleet.runtime.outcomes import OutcomeStore

    retained_command = graph.get_node("Command", command.command_id)
    assert retained_command is not None
    raw_command = json.loads(retained_command["payload_json"])
    assert retained_command["payload_hash"] == canonical_json_hash(raw_command)
    assert retained_command["payload_hash"] != command.payload_hash
    retained_observation = graph.get_node("Observation", observation.id)
    assert retained_observation is not None
    assert not {"episode_id", "world_tick", "subject_id", "payload_hash"} & set(retained_observation)

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert result is not None
    assert result["command"]["state"] == "OUTCOME_VERIFIED"
    assert result["task"]["state"] == "VERIFIED"
    assert result["task"]["task_version"] == command.proposal.expected_versions.task_version + 1
    assert result["claim"]["state"] == "RELEASED"
    assert result["outcome"]["observation_refs"] == [{
        "observation_id": observation.id,
        "payload_hash": canonical_json_hash(observation),
        "predicate": observation.predicate,
        "world_tick": observation.world_tick,
    }]
    assert graph.read_version_root()["graph_version"] == before["graph_version"] + 1
    assert graph.get_node("Command", command.command_id)["outcome_hash"]
    linked = graph._query(
        "MATCH (:Command {id:$command_id,tenant_id:$tenant_id})-[:VERIFIED_BY]->"
        "(o:Observation {id:$observation_id,tenant_id:$tenant_id}) RETURN o.id",
        {"command_id": command.command_id, "observation_id": observation.id,
         "tenant_id": graph.tenant_id},
    )
    assert linked.result_set == [[observation.id]]

    version_after_commit = graph.read_version_root()["graph_version"]
    replay = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )
    assert replay == result
    assert graph.read_version_root()["graph_version"] == version_after_commit


def test_verified_outcome_rejects_stale_graph_version_without_mutation(isolated_runtime_graph):  # noqa: F811
    from witness_fleet.runtime.outcomes import OutcomeStore

    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    current = graph.read_version_root()
    assert current is not None
    stale = current["graph_version"] - 1

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=stale,
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == current["graph_version"]
    assert graph.get_node("Task", command.proposal.task_id)["state"] != "VERIFIED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "ACTIVE"


def test_verified_outcome_rejects_empty_expected_effects(isolated_runtime_graph):  # noqa: F811
    from witness_fleet.runtime.outcomes import OutcomeStore

    graph, holder, command, _, episode_id, corridor_id = _prepared_command(
        isolated_runtime_graph, expected_effects=(),
    )
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == before["graph_version"]
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"
    assert graph.get_node("Task", command.proposal.task_id)["state"] != "VERIFIED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "ACTIVE"


def test_verified_outcome_requires_every_expected_effect_from_retained_sensor_data(isolated_runtime_graph):  # noqa: F811
    from witness_fleet.runtime.outcomes import OutcomeStore

    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(
        graph, command, episode_id, corridor_id, predicate="other_fact", value=True,
    )
    current = graph.read_version_root()
    assert current is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=current["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == current["graph_version"]
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"


def test_failed_outcome_without_sensor_proof_is_committed_as_failure(isolated_runtime_graph):  # noqa: F811
    from witness_fleet.runtime.outcomes import OutcomeStore

    graph, holder, command, _, _, _ = _prepared_command(isolated_runtime_graph)
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(), world_tick=5, outcome="failed",
    )

    assert result is not None
    assert result["command"]["state"] == "FAILED"
    assert result["task"]["state"] == "FAILED"
    assert result["claim"]["state"] == "REASSESS"
    assert result["outcome"]["observation_refs"] == []
    assert graph.read_version_root()["graph_version"] == before["graph_version"] + 1


@pytest.mark.parametrize(("changes", "world_tick"), [
    ({"robot_id": "foreign-robot"}, 5),
    ({"episode_id": "foreign-episode"}, 5),
    ({"subject_id": "foreign-corridor"}, 5),
    ({"scope": {"corridor_id": "foreign-corridor"}}, 5),
    ({"visibility": "insufficient"}, 5),
    ({"expires_tick": 4}, 5),
    ({"world_tick": 6, "expires_tick": 20}, 5),
])
def test_verified_outcome_rejects_foreign_or_stale_sensor_evidence(
    isolated_runtime_graph,  # noqa: F811
    changes,
    world_tick,
):
    from witness_fleet.runtime.outcomes import OutcomeStore

    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id, **changes)
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=world_tick,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == before["graph_version"]
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"
    assert graph.get_node("Task", command.proposal.task_id)["state"] != "VERIFIED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "ACTIVE"


def test_verified_outcome_rejects_tampered_retained_sensor_payload(isolated_runtime_graph):  # noqa: F811
    from witness_fleet.runtime.outcomes import OutcomeStore

    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    tampered = observation.model_dump(mode="json")
    tampered["predicate"] = "forged-arrival"
    graph._graph.query(
        "MATCH (o:Observation {id:$id,tenant_id:$tenant_id}) SET o.payload_json=$payload_json",
        {"id": observation.id, "tenant_id": graph.tenant_id, "payload_json": _json(tampered)},
    )
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == before["graph_version"]
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"


def test_verified_outcome_rejects_expired_coordinator_lease_without_mutation(isolated_runtime_graph):  # noqa: F811
    from witness_fleet.runtime.outcomes import OutcomeStore

    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    graph._graph.query(
        "MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}) "
        "SET s.coordinator_lease_expires_at_utc=$expired, s.graph_version=s.graph_version+1",
        {"tenant_id": graph.tenant_id,
         "expired": (datetime.now(UTC) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")},
    )
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == before["graph_version"]
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "ACTIVE"


def test_verified_outcome_rejects_stale_resource_fence_without_mutation(isolated_runtime_graph):  # noqa: F811
    from witness_fleet.runtime.outcomes import OutcomeStore

    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    before = graph.read_version_root()
    assert before is not None
    resource_id = command.proposal.required_resource_ids[0]
    resource = graph.get_node("Resource", resource_id)
    assert resource is not None
    changed = graph.atomic_update(
        expected_graph_version=before["graph_version"], label="Resource", node_id=resource_id,
        attributes={"fence": resource["fence"] + 1,
                    "resource_version": resource["resource_version"] + 1},
    )
    assert changed is not None
    changed_version = graph.read_version_root()["graph_version"]

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=changed_version,
        observations=(observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == changed_version
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"
    assert graph.get_node("Task", command.proposal.task_id)["state"] != "VERIFIED"
    assert graph.get_node("Claim", command.claim_id)["state"] == "ACTIVE"


def test_verified_outcome_rejects_missing_retained_observation(isolated_runtime_graph):  # noqa: F811
    from witness_fleet.runtime.outcomes import OutcomeStore

    graph, holder, command, _, episode_id, corridor_id = _prepared_command(isolated_runtime_graph)
    observation = _retain_observation(graph, command, episode_id, corridor_id)
    missing_observation = observation.model_copy(update={
        "id": f"missing-{uuid.uuid4().hex}",
    })
    before = graph.read_version_root()
    assert before is not None

    result = OutcomeStore(graph, holder).finish(
        command.command_id, expected_graph_version=before["graph_version"],
        observations=(missing_observation,), world_tick=5,
    )

    assert result is None
    assert graph.read_version_root()["graph_version"] == before["graph_version"]
    assert graph.get_node("Command", command.command_id)["state"] == "PREPARED"
