"""Current-run inspection boundaries backed by additive isolated FalkorDB graphs."""
import json
import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.bootstrap import bootstrap
from witness_fleet.runtime.coordinator import Coordinator


@pytest.fixture
def console(isolated_console_graph, tmp_path):  # noqa: F811
    controller = Coordinator(isolated_console_graph, SourceStore(tmp_path / 'sources'),
                             SimulatorService(tmp_path / 'sim'))
    controller.create_incident('SC-001', 3, 'inspection-scope-' + uuid.uuid4().hex)
    try:
        yield controller
    finally:
        controller.close()


@pytest.mark.parametrize('origin', ['unrelated_archive', 'previous_run'])
def test_source_rejects_valid_unmanifested_revision(console, origin):
    graph = console.graph
    if origin == 'previous_run':
        historical = bootstrap(graph, console.sources, prefix='history-' + uuid.uuid4().hex,
                               scenario='SC-001', seed=3)
        revision = next(n for n in graph.read_snapshot()['nodes']
                        if n['labels'] == ['Revision'] and n['id'] in historical['node_ids'])
        revision_id = revision['revision_id']
    else:
        retained = console.sources.retain('archive-' + uuid.uuid4().hex, b'Valid but unrelated archive.')
        graph.append_node('Source', 'archive-source', {'source_id': retained.source_id})
        graph.append_node('Revision', 'archive-revision', {
            'revision_id': retained.revision_id, 'content_hash': retained.bytes_hash,
            'normalized_hash': retained.normalized_hash,
            'normalizer_version': retained.normalizer_version})
        graph.append_edge('REVISION_OF', 'Revision', 'archive-revision', 'Source', 'archive-source')
        revision_id = retained.revision_id
    assert console.sources.get(revision_id).text  # Valid retained data, not corruption.
    with pytest.raises(ValueError, match='active manifest'):
        console.source(revision_id)


def test_all_manifested_bootstrap_source_chains_remain_readable(console):
    sources = console.state()['sources']
    assert len(sources) == 4
    for source in sources:
        result = console.source(source['revision_id'])
        assert result['source_id'] == source['source_id']
        assert result['text'] == console.sources.get(source['revision_id']).text


def test_source_listing_excludes_unmanifested_revision_of_active_source(console):
    original = console.state()['sources'][0]
    retained = console.sources.retain(original['source_id'], b'Unmanifested newer archive revision.')
    graph = console.graph
    graph.append_node('Revision', 'later-archive-revision', {
        'revision_id': retained.revision_id, 'content_hash': retained.bytes_hash,
        'normalized_hash': retained.normalized_hash, 'normalizer_version': retained.normalizer_version})
    graph.append_edge('REVISION_OF', 'Revision', 'later-archive-revision', 'Source', original['id'])
    revisions = {source['revision_id'] for source in console.state()['sources']}
    assert original['revision_id'] in revisions
    assert retained.revision_id not in revisions


def test_witness_cannot_bypass_source_run_membership(console):
    historical = bootstrap(console.graph, console.sources, prefix='past-' + uuid.uuid4().hex,
                           scenario='SC-001', seed=3)
    with pytest.raises(ValueError, match='active manifest'):
        console.witness(historical['restrictions'][0])


@pytest.mark.parametrize('mutation', ['duplicate', 'wrong_label', 'cross_episode'])
def test_state_refuses_ambiguous_active_task_before_reporting_metrics(console, mutation):
    graph = console.graph
    task_id = console.manifest['task_ids'][0]
    if mutation == 'duplicate':
        # Migrated graphs reject same-label duplicates at storage; cross-label
        # collisions remain representable and must fail the projection boundary.
        graph._query('CREATE (:Command {id:$id, tenant_id:$tenant})',
                     {'id': task_id, 'tenant': graph.tenant_id}, write=True)
    elif mutation == 'wrong_label':
        graph._query('MATCH (t:Task {id:$id}) SET t:Command', {'id': task_id}, write=True)
    else:
        graph.append_node('Episode', 'alien-episode', {'scenario_family': 'SC-001'})
        graph.append_edge('CONTAINS', 'Episode', 'alien-episode', 'Task', task_id)
    with pytest.raises(ValueError):
        console.state()


def test_events_require_exclusive_active_run_target(console):
    graph = console.graph
    historical = bootstrap(graph, console.sources, prefix='old-' + uuid.uuid4().hex,
                           scenario='SC-001', seed=3)
    for number, (event_id, targets) in enumerate([
        ('event-current', [console.manifest['release_id']]),
        ('event-historical', [historical['release_id']]),
        ('event-unscoped', []),
        ('event-mixed', [console.manifest['release_id'], historical['release_id']]),
    ], start=1):
        graph.append_node('DispatchEvent', event_id, {
            'event_id': event_id, 'sequence': number, 'coordinator_epoch': 0,
            'kind': 'POLICY_ACTIVATION', 'effective_world_tick': 0,
            'subject_ids_json': json.dumps([console.manifest['release_id']])})
        for target in targets:
            graph.append_edge('DELIVERS', 'DispatchEvent', event_id, 'Release', target)
    state = console.state()
    assert [event['id'] for event in state['events']] == ['event-current']
    assert state['metrics']['delivery_completed'] == 0
    assert state['metrics']['recovery_verified'] == 0


def test_duplicate_task_rows_in_snapshot_fail_closed(console, monkeypatch):
    # Explicit synthetic corrupt-snapshot probe: don't drop real DB constraints
    # merely to represent a same-label historical/corrupt snapshot.
    snapshot = console.graph.read_snapshot()
    task = next(n for n in snapshot['nodes'] if n['id'] == console.manifest['task_ids'][0])
    snapshot['nodes'].append({**task, 'kind': 'deliver', 'state': 'VERIFIED'})
    monkeypatch.setattr(console, '_snapshot', lambda: snapshot)
    with pytest.raises(ValueError, match='ambiguous canonical node identity'):
        console.state()


@pytest.mark.parametrize('mutation', ['missing_span', 'ambiguous_span', 'manifest_drift'])
def test_source_requires_retained_manifest_and_unique_span_chain(console, mutation):
    graph = console.graph
    snapshot = graph.read_snapshot()
    revision = next(n for n in snapshot['nodes'] if n['labels'] == ['Revision']
                    and n['id'] in console.manifest['node_ids'])
    if mutation == 'manifest_drift':
        console.manifest = {**console.manifest, 'node_ids': console.manifest['node_ids'][:-1]}
    elif mutation == 'missing_span':
        # Corrupt only this case's isolated fixture; preserve all nodes/edges.
        graph._query('MATCH (s:EvidenceSpan)-[:IN_REVISION]->(r:Revision {id:$id}) '
                     'SET s:Task', {'id': revision['id']}, write=True)
    else:
        span_id = next(e['source_id'] for e in snapshot['edges']
                       if e['relationship'] == 'IN_REVISION' and e['target_id'] == revision['id'])
        other = next(n for n in snapshot['nodes'] if n['labels'] == ['Revision']
                     and n['id'] != revision['id'])
        graph.append_edge('IN_REVISION', 'EvidenceSpan', span_id, 'Revision', other['id'])
    with pytest.raises(ValueError):
        console.source(revision['revision_id'])


def test_http_scope_rejections_do_not_disclose_archive_or_false_outcomes(console):
    from fastapi.testclient import TestClient

    from witness_fleet.api.app import create_app

    graph = console.graph
    historical = bootstrap(graph, console.sources, prefix='archive-http-' + uuid.uuid4().hex,
                           scenario='SC-001', seed=3)
    revision = next(n for n in graph.read_snapshot()['nodes']
                    if n['labels'] == ['Revision'] and n['id'] in historical['node_ids'])
    client = TestClient(create_app(console))
    for url in ['/api/sources/' + revision['revision_id'],
                '/api/decisions/' + historical['restrictions'][0] + '/witness']:
        response = client.get(url)
        assert response.status_code == 409
        assert response.json() == {'detail': {'code': 'STATE_CONFLICT'}}
    graph._query('CREATE (:Command {id:$id, tenant_id:$tenant})',
                 {'id': console.manifest['task_ids'][0], 'tenant': graph.tenant_id}, write=True)
    response = client.get('/api/state')
    assert response.status_code == 409
    assert 'metrics' not in response.json()
