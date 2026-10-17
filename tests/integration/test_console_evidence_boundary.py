"""Graph-backed source and witness boundaries reject malformed membership."""
import uuid

import pytest
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.coordinator import Coordinator


@pytest.mark.parametrize('mutation', ['wrong_target', 'orphan', 'wrong_hash', 'duplicate_revision', 'duplicate_id'])
def test_source_and_witness_fail_closed(isolated_runtime_graph, tmp_path, mutation):  # noqa: F811
    graph = isolated_runtime_graph
    controller = Coordinator(graph, SourceStore(tmp_path / 'sources'), SimulatorService(tmp_path / 'sim'))
    try:
        unique = uuid.uuid4().hex
        state = controller.create_incident('SC-001', 3, 'source-boundary-' + unique)
        if mutation == 'wrong_target':
            with pytest.raises(ValueError):
                controller.witness(state['tasks'][0]['id'])
            return
        retained = controller.sources.retain('unrelated-' + unique, b'Unlinked retained source.')
        revision_id = 'unrelated-revision-' + unique
        attrs = {'revision_id': retained.revision_id, 'content_hash': retained.bytes_hash,
                 'normalized_hash': retained.normalized_hash,
                 'normalizer_version': retained.normalizer_version}
        if mutation == 'wrong_hash':
            attrs['normalized_hash'] = '0' * 64
        graph.append_node('Revision', revision_id, attrs)
        if mutation != 'orphan':
            source_id = 'unrelated-source-' + unique
            graph.append_node('Source', source_id, {'source_id': retained.source_id})
            graph.append_edge('REVISION_OF', 'Revision', revision_id, 'Source', source_id)
        if mutation == 'duplicate_revision':
            graph.append_node('Revision', revision_id + '-duplicate', attrs)
        elif mutation == 'duplicate_id':
            graph._query('CREATE (:Task {id:$id, tenant_id:$tenant})',
                         {'id': revision_id, 'tenant': graph.tenant_id}, write=True)
        with pytest.raises(ValueError):
            controller.source(retained.revision_id)
        if mutation == 'duplicate_id':
            with pytest.raises(ValueError):
                controller.witness(state['restrictions'][0]['id'])
    finally:
        controller.close()
