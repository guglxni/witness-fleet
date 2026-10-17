"""Measured command effects must retain actor and immutable receipt identity."""
from datetime import UTC, datetime

import pytest
from test_native_execution_window import recovery_command
from test_service_admission import control

from services.simulator.service import SimulatorService
from witness_fleet.domain import CommandIntent, DispatchEvent, canonical_json_hash


def native_event(service, *, kind, robot, parameters, effects):
    """Synthetic authority fixture exercises native effect measurement only."""
    wire = recovery_command(service).model_dump(mode='json')
    data = wire['payload']
    proposal = data['proposal']
    proposal.update(kind=kind, robot_id=robot, parameters=parameters,
                    expected_effects=effects, required_predicates=[])
    data['payload_hash'] = canonical_json_hash(proposal)
    data['authorization'].update(robot_id=robot, action_payload_hash=data['payload_hash'], valid_until_tick=2000)
    wire['payload_hash'] = canonical_json_hash(data)
    return DispatchEvent.model_validate(wire)


def test_travel_projection_rejects_terminal_sample_without_stability_window(tmp_path):
    from witness_fleet.runtime.command_effects import capture_command_effects

    service = SimulatorService(tmp_path)
    try:
        service.create_episode('travel-effect', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        service.receive(control('fence', 1, 'FENCE_INSTALL', {
            'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1},
        }))
        event = native_event(service, kind='travel', robot='scout', parameters={
            'target_x': -3.5, 'target_y': -.55, 'timeout_ticks': 2000,
            'execution_until_tick': 2000}, effects=['arrived'])
        command = CommandIntent.model_validate(event.payload)
        service.receive(event)
        service.advance(500)
        assert service.command(command.command_id)['state'] == 'CONTROLLER_DONE'
        assert capture_command_effects(service, command=command,
                                       now_utc=datetime.now(UTC)) == ()
        assert capture_command_effects(service, command=command,
                                       now_utc=datetime.now(UTC)) == ()
    finally:
        service.close()


def test_inspection_effect_requires_a_real_actor_sample(tmp_path):
    from witness_fleet.runtime.command_effects import capture_command_effects

    service = SimulatorService(tmp_path)
    try:
        service.create_episode('inspection-effect', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        service.receive(control('fence', 1, 'FENCE_INSTALL', {
            'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1},
        }))
        event = native_event(service, kind='inspect', robot='scout', parameters={
            'timeout_ticks': 100, 'execution_until_tick': 100}, effects=['inspected'])
        command = CommandIntent.model_validate(event.payload)
        service.receive(event)
        service.advance(1)
        effects = capture_command_effects(service, command=command, now_utc=datetime.now(UTC))
        assert len(effects) == 1
        assert effects[0].predicate == 'inspected'
        assert effects[0].quality['sample_world_tick'] == 0
        assert effects[0].robot_id == 'scout'
    finally:
        service.close()


@pytest.mark.parametrize('case', ['unknown', 'held', 'wrong_payload', 'stale_sample'])
def test_inspection_effect_does_not_invent_receipt_or_freshness(tmp_path, case):
    from witness_fleet.runtime.command_effects import capture_command_effects

    service = SimulatorService(tmp_path)
    try:
        service.create_episode('negative-effect', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        service.receive(control('fence', 1, 'FENCE_INSTALL', {
            'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1},
        }))
        event = native_event(service, kind='inspect', robot='scout', parameters={
            'timeout_ticks': 100, 'execution_until_tick': 100}, effects=['inspected'])
        command = CommandIntent.model_validate(event.payload)
        if case != 'unknown':
            service.receive(event)
            service.advance(1)
        if case == 'held':
            service.world.hold('operator_hold')
        elif case == 'wrong_payload':
            data = command.model_dump(mode='json')
            data['proposal']['parameters']['timeout_ticks'] = 99
            data['payload_hash'] = canonical_json_hash(data['proposal'])
            data['authorization']['action_payload_hash'] = data['payload_hash']
            command = CommandIntent.model_validate(data)
        elif case == 'stale_sample':
            service.advance(50)
        assert capture_command_effects(service, command=command, now_utc=datetime.now(UTC)) == ()
    finally:
        service.close()


def test_recovery_effect_is_actor_owned_displacement_not_peer_clearance(tmp_path):
    from witness_fleet.runtime.command_effects import capture_command_effects

    service = SimulatorService(tmp_path)
    try:
        service.create_episode('actor-owned-effects', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        service.receive(control('fence', 1, 'FENCE_INSTALL', {
            'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1},
        }))
        event = recovery_command(service)
        command = CommandIntent.model_validate(event.payload)
        service.receive(event)
        assert capture_command_effects(service, command=command, now_utc=datetime.now(UTC)) == ()
        for _ in range(2000):
            service.advance(1)
            if service.command(command.command_id)['state'] != 'RUNNING':
                break
        effects = capture_command_effects(service, command=command, now_utc=datetime.now(UTC))
        assert len(effects) == 1
        effect = effects[0]
        assert effect.robot_id == 'recovery'
        assert effect.predicate == 'obstruction_moved'
        assert effect.value is True
        assert effect.scope == {'corridor_id': 'corridor'}
        assert effect.quality['contact_count'] > 0
        assert effect.quality['measured_displacement_m'] >= .75
        assert effect.quality['command_id'] == command.command_id
        assert effect.quality['receipt_payload_hash'] == event.payload_hash
        assert effect.world_tick == service.status()['world_tick']
        assert effect.episode_id == 'actor-owned-effects'
    finally:
        service.close()
