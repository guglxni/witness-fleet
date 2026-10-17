"""Actual FalkorDB + MuJoCo seven-task chain, with explicit local release.

This test composes production boundaries. It does not manufacture ALLOW receipts,
physical observation values, or graph task completion.
"""
import uuid
from datetime import UTC, datetime

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.approval import ApprovalCommand, TrustedLocalPrincipal
from witness_fleet.runtime.approval_writer import ApprovalWriter
from witness_fleet.runtime.bootstrap import bootstrap
from witness_fleet.runtime.coordinator import Coordinator
from witness_fleet.runtime.effects import capture_recovery_verification
from witness_fleet.runtime.execution import FleetExecution
from witness_fleet.runtime.observation_store import retain_observations
from witness_fleet.runtime.sensing import capture_evidence


@pytest.fixture
def mission_console(isolated_console_graph, tmp_path):  # noqa: F811
    graph = isolated_console_graph
    sources = SourceStore(tmp_path / 'sources')
    prefix = 'mission-' + uuid.uuid4().hex[:16]
    manifest = bootstrap(graph, sources, prefix=prefix, scenario='SC-001', seed=3,
                         profile='mission-v2')
    service = SimulatorService(tmp_path / 'sim')
    service.create_episode(manifest['episode_id'], 'SC-001', 3)
    service.load_payload('courier', prefix + '-parcel')
    owner = Coordinator(graph, sources, service)
    try:
        yield owner
    finally:
        owner.close()


def observe(owner, actor, recovery_command_id=None):
    now = datetime.now(UTC)
    args = dict(tenant_id=owner.graph.tenant_id, corridor_id=owner.manifest['corridor_id'],
                release_id=owner.manifest['release_id'], now_utc=now, observer_ids=(actor,))
    observations = capture_evidence(owner.simulator, **args)
    if recovery_command_id:
        observations += capture_recovery_verification(owner.simulator,
            command_id=recovery_command_id, **args)
    return observations


def test_full_native_mission_requires_owner_release_and_delivers_payload(mission_console):
    owner = mission_console
    runner = FleetExecution(owner)
    runner.acquire()
    plan = owner.manifest['task_plan']
    recovery_id = None
    for entry in plan[:4]:
        observations = observe(owner, 'recovery') if entry['kind'] == 'recover' else ()
        result = runner.execute_task(entry['task_id'], parameters=entry['parameters'],
            expected_effects=tuple(entry['expected_effects']), observations=observations)
        assert result['task']['state'] == 'VERIFIED'
        if entry['kind'] == 'recover':
            recovery_id = owner.state()['commands'][-1]['command_id']

    proof = observe(owner, 'scout', recovery_id)
    assert {o.predicate for o in proof if o.value is True} >= {'courier_fit', 'recovery_verified'}
    retain_observations(owner.graph, proof, episode_id=owner.manifest['episode_id'])
    before = owner.state()
    assert before['metrics']['delivery_completed'] == 0
    assert owner.graph.get_node('Release', owner.manifest['release_id'])['state'] == 'staged'
    assert not any(c['robot_id'] == 'courier' for c in before['commands'])
    principal = TrustedLocalPrincipal(actor_id=owner.manifest['owners'][0],
        tenant_id=owner.graph.tenant_id, role='maintenance_owner', trust_mode='configured_local')
    intent = ApprovalCommand(event_id='release-' + uuid.uuid4().hex,
        target_id=owner.manifest['release_id'], actor_id=principal.actor_id,
        tenant_id=principal.tenant_id, expected_policy_epoch=before['policy_epoch'],
        notes='Explicit test-owned maintenance release after retained native verification')
    ApprovalWriter(owner.graph, owner.sources, principal, holder_id=owner.holder_id).approve_release(
        intent, effective_world_tick=owner.simulator.status()['world_tick'])
    runner._drain()
    assert owner.ready()
    assert owner.graph.get_node('Release', intent.target_id)['state'] == 'released'

    for entry in plan[4:]:
        observations = observe(owner, 'courier', recovery_id) if entry['kind'] == 'deliver' else ()
        if entry['kind'] == 'deliver':
            assert {o.predicate for o in observations if o.value is True} >= {'courier_fit', 'recovery_verified'}
            assert all(o.robot_id == 'courier' for o in observations)
        result = runner.execute_task(entry['task_id'], parameters=entry['parameters'],
            expected_effects=tuple(entry['expected_effects']), observations=observations)
        assert result['task']['state'] == 'VERIFIED'

    final = owner.state()
    assert len(final['commands']) == len(plan) == 7
    assert all(t['state'] == 'VERIFIED' for t in final['tasks'])
    assert final['metrics']['delivery_completed'] == 1
    delivered = next(c for c in final['commands'] if c['kind'] == 'deliver')
    receipt = owner.simulator.command(delivered['command_id'])
    assert receipt['state'] == 'OUTCOME_VERIFIED'
    assert receipt['native']['result']['postcondition']['payload_in_delivery_zone'] is True
    assert owner.simulator.observations()['robots']['courier']['payload']['delivery_zone'] is True
    assert owner.ready()
