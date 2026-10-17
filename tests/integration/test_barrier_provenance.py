"""Exact retained barrier provenance, no native release or simulator motion."""
from datetime import UTC, datetime, timedelta

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.domain import DispatchEvent, canonical_json_hash
from witness_fleet.runtime.storage import TransitionStore


@pytest.fixture
def retained_barrier(isolated_console_graph):  # noqa: F811
    graph = isolated_console_graph
    now = datetime.now(UTC)
    store = TransitionStore(graph, holder_id='barrier-holder')
    store.acquire_coordinator(expected_epoch=0, holder_id='barrier-holder',
        now_utc=now.isoformat(), lease_expires_at_utc=(now + timedelta(minutes=5)).isoformat(),
        event_id='retained-barrier', effective_world_tick=0)
    row = store.read_outbox()[0]
    event = DispatchEvent.model_validate({key: row[key] for key in DispatchEvent.model_fields})
    return graph, event


def test_exact_retained_barrier_is_bound_to_live_holder(retained_barrier):
    from witness_fleet.runtime.barrier_provenance import validate_barrier

    graph, event = retained_barrier
    before = graph.read_version_root()
    result = validate_barrier(graph, event, holder_id='barrier-holder', now_utc=datetime.now(UTC))
    assert result == (graph.tenant_id, 'barrier-holder', event.coordinator_epoch,
                      event.payload['lease_expires_at_utc'])
    assert graph.read_version_root() == before


@pytest.mark.parametrize('case', ['unretained', 'foreign_holder', 'expired', 'wrong_tenant', 'forged_payload'])
def test_barrier_provenance_rejects_forgery_and_staleness(retained_barrier, case):
    from witness_fleet.runtime.barrier_provenance import validate_barrier

    graph, event = retained_barrier
    holder, now = 'barrier-holder', datetime.now(UTC)
    data = event.model_dump(mode='json')
    if case == 'unretained':
        data['id'] = 'absent'
    elif case == 'foreign_holder':
        holder = 'other'
    elif case == 'expired':
        now += timedelta(minutes=10)
    elif case == 'wrong_tenant':
        data['tenant_id'] = 'other'
    else:
        data['payload']['holder_id'] = 'forged'
        data['payload_hash'] = canonical_json_hash(data['payload'])
    event = DispatchEvent.model_validate(data)
    before = graph.read_version_root()
    with pytest.raises(ValueError):
        validate_barrier(graph, event, holder_id=holder, now_utc=now)
    assert graph.read_version_root() == before
