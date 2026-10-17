"""New source-backed bootstrap fixture exercises writer's common-episode gate."""
import json
from datetime import UTC, datetime, timedelta

import pytest
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.domain import Observation, Pose
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.approval import ApprovalCommand, TrustedLocalPrincipal
from witness_fleet.runtime.approval_writer import ApprovalWriter
from witness_fleet.runtime.bootstrap import bootstrap
from witness_fleet.runtime.storage import TransitionStore


def test_writer_rejects_mixed_episode_proof_before_cas(isolated_runtime_graph, tmp_path):  # noqa: F811
    graph = isolated_runtime_graph
    sources = SourceStore(tmp_path / 'sources')
    manifest = bootstrap(graph, sources, prefix='writer-proof', scenario='SC-001', seed=3)
    now = datetime.now(UTC)
    root = graph.read_version_root()
    TransitionStore(graph).acquire_coordinator(expected_epoch=root['coordinator_epoch'],
        holder_id='writer-proof-holder', now_utc=now.isoformat(),
        lease_expires_at_utc=(now + timedelta(minutes=5)).isoformat(),
        event_id='writer-proof-barrier', effective_world_tick=0)
    for index, predicate in enumerate(('recovery_verified', 'courier_fit')):
        observation = Observation(id='writer-proof-' + predicate, tenant_id='demo',
            episode_id='different-episode-' + str(index), robot_id='scout',
            occurred_at=now, recorded_at=now, world_tick=10, expires_tick=60,
            predicate=predicate, value=True, pose=Pose(x=-3.5, y=-.55), visibility='visible',
            scope={'corridor_id': manifest['corridor_id'], 'release_id': manifest['release_id'],
                   'robot_type': 'courier', 'payload_class': 'loaded'},
            sensor_config_hash='synthetic-test-sensor', subject_id=manifest['corridor_id'])
        graph.append_node('Observation', observation.id, {'predicate': predicate, 'value': True,
            'robot_id': 'scout', 'visibility': 'visible', 'expires_tick': 60,
            'scope_json': json.dumps(dict(observation.scope)), 'payload_json': observation.model_dump_json()})
    principal = TrustedLocalPrincipal(actor_id=manifest['owners'][0], tenant_id='demo',
                                     role='maintenance_owner', trust_mode='configured_local')
    before = graph.read_version_root()
    command = ApprovalCommand(event_id='writer-proof-approval', target_id=manifest['release_id'],
        actor_id=principal.actor_id, tenant_id='demo', expected_policy_epoch=before['policy_epoch'])
    with pytest.raises(ValueError, match='verification'):
        ApprovalWriter(graph, sources, principal, holder_id='writer-proof-holder').approve_release(
            command, effective_world_tick=10)
    assert graph.read_version_root() == before
    assert graph.get_node('DispatchEvent', command.event_id) is None
    assert graph.get_node('Release', command.target_id)['state'] == 'staged'
