"""An accepted revocation must physically hold the step owner before further motion."""

import math

from test_protocol_commands import command_event
from test_service_admission import control

from services.simulator.service import SimulatorService
from witness_fleet.domain import (
    CommandIntent,
    DispatchEvent,
    SkillKind,
    canonical_json_hash,
    payload_hash,
)


def travel_event():
    template = CommandIntent.model_validate(command_event(sequence=2, until=1000).payload)
    proposal = template.proposal.model_copy(update={
        'kind': SkillKind.TRAVEL, 'parameters': {'target_x': -3.5, 'target_y': -.55}})
    action_hash = payload_hash(proposal)
    authorization = template.authorization.model_copy(update={'action_payload_hash': action_hash})
    command = template.model_copy(update={'proposal': proposal, 'payload_hash': action_hash,
                                         'authorization': authorization})
    wire = command.model_dump(mode='json')
    return DispatchEvent(id='moving', sequence=2, coordinator_epoch=0, kind='COMMAND',
                         effective_world_tick=0, payload=wire, payload_hash=canonical_json_hash(wire))


def test_ordered_revocation_holds_physics_and_retains_cancelled_receipt(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('revocation-world', 'SC-001', 3)
        service.receive(control('f', 1, 'FENCE_INSTALL', {
            'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1}}))
        assert service.receive(travel_event())['command_state'] == 'RUNNING'
        service.advance(3)
        payload = {'policy_epoch': 1, 'expected_previous_policy_epoch': 0,
                   'policy_proof': {'proof_id': 'trusted-test-revocation', 'coordinator_epoch': 0}}
        event = DispatchEvent(id='revoke', sequence=3, coordinator_epoch=0,
                              kind='REVOCATION', effective_world_tick=3,
                              payload=payload, payload_hash=canonical_json_hash(payload))
        assert service.receive(event)['status'] == 'ACCEPTED'
        assert service.status()['held'] is True
        assert service.command('cmd')['state'] == 'CANCELLED'
        poses = service.status()['poses']
        service.advance(5)
        # Controlled hold allows bounded inertial settling, not a teleport stop.
        for robot, pose in service.status()['poses'].items():
            assert math.hypot(pose['x'] - poses[robot]['x'], pose['y'] - poses[robot]['y']) < .01
        assert service.status()['started_commands'] == 1
        assert service.command('cmd')['native']['status'] == 'held'
        before_retry = service.journal.identity()
        retained_event = service.event(event.id)
        # Strict HOLD rejects ingress even for an already applied event. Its
        # durable disposition remains available through the read-only receipt API.
        assert service.receive(event) == {'status': 'HOLD', 'reason_codes': ['INGRESS_HELD']}
        assert service.journal.identity() == before_retry
        assert service.event(event.id) == retained_event
        assert service.command('cmd')['state'] == 'CANCELLED'
        assert service.world.world_tick == 3
    finally:
        service.close()
    resumed = SimulatorService(tmp_path)
    try:
        assert resumed.status()['held'] is True
        assert resumed.command('cmd')['state'] == 'CANCELLED'
        assert resumed.status()['policy_epoch'] == 1
    finally:
        resumed.close()
