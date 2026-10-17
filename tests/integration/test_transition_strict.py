from datetime import UTC, datetime

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401
from test_command_preparation import prepared_fixture

from witness_fleet.runtime.storage import TransitionStore


def test_command_receipt_evidence_version_must_equal_atomic_expected_graph_version(isolated_console_graph):  # noqa: F811
    graph, transitions, command, auth, expected = prepared_fixture(isolated_console_graph)
    # Intervening mutation cannot rebind old evidence by passing a fresh CAS version.
    graph.append_node('Resource', 'drift-' + command.command_id, {'kind': 'corridor', 'resource_version': 0, 'fence': 0})
    current = graph.read_version_root()['graph_version']
    with pytest.raises(ValueError):
        transitions.prepare_command(command=command, authorization=auth, expected_graph_version=current)


@pytest.mark.parametrize('epoch', [True, 1.0, -1])
def test_acquire_coordinator_rejects_boolean_float_or_negative_epoch(isolated_console_graph, epoch):  # noqa: F811
    graph = isolated_console_graph
    with pytest.raises(ValueError):
        TransitionStore(graph).acquire_coordinator(expected_epoch=epoch, holder_id='local', now_utc=datetime.now(UTC).isoformat(), lease_expires_at_utc='2028-01-01T00:00:00Z', event_id='invalid-epoch', effective_world_tick=0)
