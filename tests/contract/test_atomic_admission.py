"""Competing admissions use the journal's authoritative transaction and built-in preflight."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from test_protocol_commands import command_event

from services.simulator.journal import Journal
from witness_fleet.domain import canonical_json_hash


def prepare(journal):
    event = command_event().model_dump(mode='json')
    journal.set_identity(coordinator_epoch=0, policy_epoch=0,
                         task_fences={'task': 1}, resource_fences={'corridor': 1})
    journal.register(event)
    journal.record_command('cmd', event['payload_hash'], 'PREPARED', event_id=event['id'])
    return event


def test_competing_admission_runs_exactly_one_committed_transition(tmp_path):
    journals = [Journal(tmp_path / 'shared.sqlite') for _ in range(2)]
    for journal in journals:
        event = prepare(journal)
    start = Barrier(2)
    def compete(journal):
        start.wait()
        return journal.admit_next(event['id'], current_tick=1)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(compete, journals))
    assert sorted(r['status'] for r in results) == ['ACCEPTED', 'REPLAY']
    assert journals[0].applied_cursor == 1
    assert journals[0].receipt('cmd')['state'] == 'ACCEPTED'
    for journal in journals:
        journal.close()


def test_hold_installed_before_admission_is_authoritative(tmp_path):
    journal = Journal(tmp_path / 'shared.sqlite')
    event = prepare(journal)
    journal.hold_for_reconciliation(1, reason='takeover')
    result = journal.admit_next(event['id'], current_tick=1)
    assert result['status'] == 'HOLD'
    assert journal.receipt('cmd')['state'] == 'PREPARED'
    assert journal.applied_cursor == 0
    journal.close()


def test_admission_rejects_validator_before_transaction_or_callback(tmp_path):
    journal = Journal(tmp_path / 'shared.sqlite')
    event = prepare(journal)
    callback_calls = []
    sql_statements = []
    journal._db.set_trace_callback(sql_statements.append)
    identity_before = journal.identity()
    receipt_before = journal.receipt('cmd')
    event_before = journal.event(event['id'])

    def impure_validator(*args):
        callback_calls.append(args)
        journal.record_command('callback-side-effect', 'sha256:side-effect', 'PREPARED')
        return {'status': 'ACCEPTED'}

    with pytest.raises(TypeError, match="unexpected keyword argument 'validator'"):
        journal.admit_next(event['id'], current_tick=1, validator=impure_validator)

    assert callback_calls == []
    assert not any(statement.lstrip().upper().startswith('BEGIN') for statement in sql_statements)
    assert journal.applied_cursor == 0
    assert journal.identity() == identity_before
    assert journal.receipt('cmd') == receipt_before
    assert journal.event(event['id']) == event_before
    assert journal.receipt('callback-side-effect')['status'] == 'NOT_FOUND'
    journal.close()


def epoch_barrier_event():
    payload = {'coordinator_epoch': 1}
    return {
        'id': 'barrier-1',
        'sequence': 1,
        'payload_hash': canonical_json_hash(payload),
        'kind': 'EPOCH_BARRIER',
        'coordinator_epoch': 1,
        'effective_world_tick': 0,
        'payload': payload,
    }


@pytest.mark.parametrize('state', ['SENT', 'UNKNOWN', 'ACCEPTED', 'RUNNING', 'CONTROLLER_DONE'])
def test_epoch_barrier_holds_without_mutation_for_unresolved_receipts(tmp_path, state):
    journal = Journal(tmp_path / f'unresolved-{state}.sqlite')
    event = epoch_barrier_event()
    journal.register(event)
    journal.record_command('cmd', 'sha256:command', state)
    identity_before = journal.identity()
    receipt_before = journal.receipt('cmd')
    event_before = journal.event(event['id'])

    result = journal.admit_next(event['id'], current_tick=0)

    assert result == {'status': 'HOLD', 'reason_codes': ['UNRESOLVED_COMMANDS']}
    assert journal.applied_cursor == 0
    assert journal.identity() == identity_before
    assert journal.receipt('cmd') == receipt_before
    assert journal.event(event['id']) == event_before
    journal.close()


def test_epoch_barrier_holds_sent_receipt_without_verified_simulator_outcome(tmp_path):
    journal = Journal(tmp_path / 'sent-barrier.sqlite')
    event = epoch_barrier_event()
    journal.register(event)
    journal.record_command('cmd', 'sha256:command', 'SENT')
    identity_before = journal.identity()
    receipt_before = journal.receipt('cmd')
    event_before = journal.event(event['id'])

    result = journal.admit_next(event['id'], current_tick=0)

    assert result == {'status': 'HOLD', 'reason_codes': ['UNRESOLVED_COMMANDS']}
    assert journal.applied_cursor == 0
    assert journal.identity() == identity_before
    assert journal.receipt('cmd') == receipt_before
    assert journal.event(event['id']) == event_before
    journal.close()
