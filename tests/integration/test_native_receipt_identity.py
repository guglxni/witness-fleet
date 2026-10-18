"""An old command's physical receipt cannot become a later skill's status."""

import json
import sqlite3

from test_native_execution_window import recovery_command
from test_service_admission import control

from services.simulator.service import SimulatorService
from witness_fleet.domain import DispatchEvent, canonical_json_hash


def test_native_result_remains_bound_to_original_command_across_later_skill_and_restart(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('receipt-history', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        service.receive(control('fence', 1, 'FENCE_INSTALL', {
            'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1}}))
        event = recovery_command(service)
        service.receive(event)
        service.advance(2000)
        first = service.command(event.id)
        assert first['state'] == 'CONTROLLER_DONE'
        assert first['native']['kind'] == 'recover'
        later = event.model_dump(mode='json')
        later.update(id='inspect-command', sequence=3, effective_world_tick=2000)
        command = later['payload']
        command.update(command_id='inspect-command', dispatch_sequence=3, effective_world_tick=2000)
        command['proposal'].update(id='inspect-proposal', kind='inspect', parameters={})
        command['payload_hash'] = canonical_json_hash(command['proposal'])
        command['authorization'].update(action_payload_hash=command['payload_hash'], valid_until_tick=2100)
        later['payload_hash'] = canonical_json_hash(command)
        service.receive(DispatchEvent.model_validate(later))
        service.advance(1)
        assert service.command(event.id)['native'] == first['native']
        assert service.command(event.id)['payload_hash'] == first['payload_hash']
        service.close()
        service = SimulatorService(tmp_path)
        assert service.command(event.id)['native'] == first['native']
        assert service.command(event.id)['payload_hash'] == first['payload_hash']
    finally:
        service.close()


def test_legacy_running_checkpoint_never_aliases_later_robot_skill(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode('legacy-receipt-history', 'SC-001', 3)
    service.load_payload('courier', 'parcel')
    service.receive(control('fence', 1, 'FENCE_INSTALL', {
        'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1}}))
    event = recovery_command(service)
    assert service.receive(event)['command_state'] == 'RUNNING'
    checkpoint = service.journal.checkpoint()
    service.close()

    legacy_state = json.loads(checkpoint['state_json'])
    legacy_state.pop('native_results')
    # Simulate a later skill on the same robot being present in a legacy snapshot;
    # that skill does not prove the original command's native result.
    legacy_state['world']['skills']['recovery'] = {'kind': 'inspect', 'status': 'done'}
    with sqlite3.connect(tmp_path / 'journal.sqlite') as database:
        checkpoint_id = database.execute(
            "SELECT value FROM metadata WHERE key='latest_checkpoint_id'"
        ).fetchone()[0]
        database.execute('UPDATE checkpoints SET state_json=? WHERE checkpoint_id=?',
                         (json.dumps(legacy_state), checkpoint_id))

    service = SimulatorService(tmp_path)
    try:
        assert service.command(event.id)['state'] == 'RUNNING'
        assert 'native' not in service.command(event.id)
        service.advance(1)
        after_step = service.command(event.id)
        assert after_step['state'] == 'RUNNING'
        assert 'native' not in after_step
    finally:
        service.close()


def test_failed_native_result_remains_bound_after_later_skill_on_same_robot(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('failed-receipt-history', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        service.receive(control('fence', 1, 'FENCE_INSTALL', {
            'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1}}))
        event = recovery_command(service, deadline=50)
        service.receive(event)
        service.advance(60)
        first = service.command(event.id)
        assert first['state'] == 'FAILED'
        assert first['native']['status'] == 'failed'

        later = event.model_dump(mode='json')
        later.update(id='inspect-after-failure', sequence=3, effective_world_tick=60)
        command = later['payload']
        command.update(command_id='inspect-after-failure', dispatch_sequence=3, effective_world_tick=60)
        command['proposal'].update(id='inspect-after-failure-proposal', kind='inspect', parameters={})
        command['payload_hash'] = canonical_json_hash(command['proposal'])
        command['authorization'].update(action_payload_hash=command['payload_hash'], valid_until_tick=100)
        later['payload_hash'] = canonical_json_hash(command)
        service.receive(DispatchEvent.model_validate(later))
        service.advance(1)
        assert service.command(event.id)['native'] == first['native']
        service.close()
        service = SimulatorService(tmp_path)
        assert service.command(event.id)['native'] == first['native']
    finally:
        service.close()


def test_running_and_cancelled_native_results_survive_checkpoint_restart(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('running-receipt-history', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        service.receive(control('fence', 1, 'FENCE_INSTALL', {
            'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1}}))
        event = recovery_command(service)
        service.receive(event)
        running = service.command(event.id)
        assert running['state'] == 'RUNNING'
        assert running['native']['status'] in {'accepted', 'running'}
        service.close()

        service = SimulatorService(tmp_path)
        assert service.command(event.id)['native'] == running['native']
        revocation = control('revoke', 3, 'REVOCATION', {
            'policy_epoch': 1, 'expected_previous_policy_epoch': 0,
            'policy_proof': {'proof_id': 'trusted-test-revocation', 'coordinator_epoch': 0}})
        service.receive(revocation)
        cancelled = service.command(event.id)
        assert cancelled['state'] == 'CANCELLED'
        assert cancelled['native']['status'] == 'held'
        service.close()

        service = SimulatorService(tmp_path)
        assert service.command(event.id)['state'] == 'CANCELLED'
        assert service.command(event.id)['native'] == cancelled['native']
    finally:
        service.close()
