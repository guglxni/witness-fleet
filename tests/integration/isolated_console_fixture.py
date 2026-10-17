"""Per-case additive graph namespaces on a retained private test container."""
import json
import uuid
from pathlib import Path

import pytest
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.graph import GraphStore


@pytest.fixture
def isolated_console_graph(isolated_runtime_graph):  # noqa: F811
    server = isolated_runtime_graph
    graph = GraphStore(host=server.host, port=server.port, username='default')
    graph.graph_name = 'wf:demo:inspection-' + uuid.uuid4().hex
    graph._graph = graph._client.select_graph(graph.graph_name)
    graph.initialize()
    record = Path('artifacts/integration-20261017/console-graphs.jsonl')
    record.parent.mkdir(parents=True, exist_ok=True)
    with record.open('a') as stream:
        stream.write(json.dumps({'port': server.port, 'graph': graph.graph_name}) + '\n')
    yield graph
    # Preserve the graph and backing volume, including malformed negative fixtures.
