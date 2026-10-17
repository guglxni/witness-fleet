"""Real writer compatibility, not evidence of motion or policy authorization."""
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.domain import (
    ActionProposal,
    AuthorizationResult,
    CommandIntent,
    SkillKind,
    VersionVector,
    payload_hash,
)
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.coordinator import Coordinator
from witness_fleet.runtime.storage import TransitionStore

pytestmark = pytest.mark.integration


def prepare_inspection(controller):
    """Use the production writer with an explicitly synthetic authorization fixture."""
    graph = controller.graph
    task_id = controller.manifest['task_ids'][0]
    now = datetime.now(UTC)
    expiry = (now + timedelta(minutes=10)).isoformat()
    transitions = TransitionStore(graph, holder_id=controller.holder_id)
    root = graph.read_version_root()
    leased = transitions.acquire_coordinator(
        expected_epoch=root['coordinator_epoch'], holder_id=controller.holder_id,
        now_utc=now.isoformat(), lease_expires_at_utc=expiry,
        event_id='identity-barrier-' + uuid.uuid4().hex, effective_world_tick=0,
    )
    assert leased is not None
    resources = controller.manifest['resources']
    claim = graph.claim_task(
        task_id=task_id, robot_id='scout', expected_task_version=0,
        coordinator_epoch=leased['coordinator_epoch'], resource_ids=resources,
        lease_expires_at_utc=expiry, now_utc=now.isoformat(),
    )
    assert claim is not None
    root = graph.read_version_root()
    task = graph.get_node('Task', task_id)
    versions = VersionVector(
        graph_version=root['graph_version'], policy_epoch=root['policy_epoch'],
        coordinator_epoch=root['coordinator_epoch'], task_version=task['task_version'],
        dependency_versions={rid: graph.get_node('Resource', rid)['resource_version'] for rid in resources},
    )
    proposal = ActionProposal(
        id='identity-proposal-' + uuid.uuid4().hex, robot_id='scout', task_id=task_id,
        kind=SkillKind.INSPECT, parameters={}, expected_versions=versions,
        required_predicates=(), required_resource_ids=tuple(resources), expected_effects=(),
        corridor_id=controller.manifest['corridor_id'],
    )
    auth = AuthorizationResult(
        authorization_id='synthetic-identity-auth-' + uuid.uuid4().hex,
        status='ALLOW', reason_codes=(), witness_ids=(), versions=versions,
        action_payload_hash=payload_hash(proposal), valid_until_tick=50,
        claim_id=claim['claim_id'], task_id=task_id, robot_id='scout',
        fence=claim['fence'], resource_fences=claim['resource_fences'],
        governance_integrity_version=root['policy_epoch'],
    )
    command = CommandIntent(
        command_id='identity-command-' + uuid.uuid4().hex, proposal=proposal,
        payload_hash=payload_hash(proposal), claim_id=claim['claim_id'], fence=claim['fence'],
        resource_fences=claim['resource_fences'], authorization_id=auth.authorization_id,
        policy_epoch=root['policy_epoch'], coordinator_epoch=root['coordinator_epoch'],
        dispatch_sequence=root['dispatch_sequence'] + 1, effective_world_tick=0, authorization=auth,
    )
    result = transitions.prepare_command(command=command, authorization=auth,
                                         expected_graph_version=root['graph_version'])
    assert result is not None
    return command


@pytest.fixture
def command_console(isolated_console_graph, tmp_path):  # noqa: F811
    controller = Coordinator(isolated_console_graph, SourceStore(tmp_path / 'sources'),
                             SimulatorService(tmp_path / 'sim'))
    controller.create_incident('SC-001', 3, 'identity-' + uuid.uuid4().hex)
    try:
        command = prepare_inspection(controller)
        yield controller, command
    finally:
        controller.close()


def test_filtered_writer_records_keep_persisted_identity(command_console):
    controller, command = command_console
    for label in ('Command', 'DispatchEvent'):
        snapshot = controller.graph.read_snapshot(labels=[label], node_ids=[command.command_id])
        assert len(snapshot['nodes']) == 1
        assert snapshot['nodes'][0]['id'] == command.command_id
        assert 'persisted_id' not in snapshot['nodes'][0]


@pytest.mark.parametrize('corruption', [
    'hash', 'payload', 'epoch', 'sequence', 'tick', 'event_id', 'subjects',
    'missing_edge', 'extra_edge', 'third_node', 'projection_collision',
])
def test_malformed_command_pair_never_bypasses_duplicate_guard(command_console, corruption, monkeypatch):
    from witness_fleet.graph.identity import event_projection_id

    controller, command = command_console
    graph = controller.graph
    params = {'id': command.command_id, 'tenant': graph.tenant_id}
    if corruption in {'hash', 'payload', 'epoch', 'sequence', 'tick', 'event_id', 'subjects'}:
        field, value = {
            'hash': ('payload_hash', '0' * 64), 'payload': ('payload_json', '{}'),
            'epoch': ('coordinator_epoch', 99), 'sequence': ('sequence', 99),
            'tick': ('effective_world_tick', 99), 'event_id': ('event_id', 'other'),
            'subjects': ('subject_ids_json', '[]'),
        }[corruption]
        graph._query(f'MATCH (e:DispatchEvent {{id:$id,tenant_id:$tenant}}) SET e.{field}=$value',
                     {**params, 'value': value}, write=True)
    elif corruption == 'missing_edge':
        # Synthetic corrupt snapshot, not a deletion from retained graph evidence.
        from witness_fleet.graph.identity import project_command_event_identities
        snapshot = graph.read_snapshot()
        projected = event_projection_id(graph.tenant_id, command.command_id)
        for node in snapshot['nodes']:
            if node['id'] == projected:
                node['id'] = node.pop('persisted_id')
        snapshot['edges'] = [e for e in snapshot['edges']
                             if not (e['source_id'] == projected and e['relationship'] == 'DELIVERS')]
        monkeypatch.setattr(controller, '_snapshot',
                            lambda: project_command_event_identities(snapshot, tenant_id=graph.tenant_id))
    elif corruption == 'extra_edge':
        graph.append_edge('DELIVERS', 'DispatchEvent', command.command_id,
                          'Release', controller.manifest['release_id'])
    elif corruption == 'third_node':
        graph.append_node('Source', command.command_id, {'source_id': 'collision'})
    elif corruption == 'projection_collision':
        graph.append_node('Source', event_projection_id(graph.tenant_id, command.command_id),
                          {'source_id': 'collision'})
    with pytest.raises(ValueError):
        controller.state()
    assert controller.simulator.started_commands == 0


def test_writer_command_event_pair_supports_read_only_console(command_console):
    controller, command = command_console
    before = controller.graph.read_version_root()
    state = controller.state()
    assert [item['command_id'] for item in state['commands']] == [command.command_id]
    event = next(item for item in state['events'] if item['kind'] == 'COMMAND')
    assert event['event_id'] == command.command_id
    assert controller.command(command.command_id)['status'] == 'NOT_FOUND'
    for source in state['sources']:
        assert controller.source(source['revision_id'])['text']
    witness = controller.witness(controller.manifest['restrictions'][0])
    assert witness['completeness'] == 'complete'
    assert controller.simulator.started_commands == 0
    assert controller.graph.read_version_root() == before
    retained_command = controller.graph.get_node('Command', command.command_id)
    retained_event = controller.graph.get_node('DispatchEvent', command.command_id)
    assert retained_command['id'] == retained_event['id'] == command.command_id
    assert json.loads(retained_event['payload_json']) == command.model_dump(mode='json')
