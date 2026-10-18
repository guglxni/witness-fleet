"""Real sensor -> deterministic policy -> journal -> native bounded execution."""

from datetime import UTC, datetime, timedelta

import pytest
from test_service_admission import control

from services.simulator.service import SimulatorService
from witness_fleet.domain import (
    ActionProposal,
    Claim,
    CommandIntent,
    DispatchEvent,
    EvidenceBundle,
    GovernanceWitness,
    SkillKind,
    VersionVector,
    canonical_json_hash,
)
from witness_fleet.policy.authorizer import authorize
from witness_fleet.runtime.sensing import capture_evidence


def recovery_command(service, *, deadline=2000, explicit=True):
    now = datetime.now(UTC)
    versions = VersionVector(graph_version=0, policy_epoch=0, coordinator_epoch=0)
    observations = capture_evidence(service, tenant_id='demo', corridor_id='corridor',
                                    release_id='release', now_utc=now)
    parameters = {'timeout_ticks': 2000, 'target_displacement_m': .75}
    if explicit:
        parameters['execution_until_tick'] = deadline
    proposal = ActionProposal(id='proposal', robot_id='recovery', task_id='task',
        kind=SkillKind.RECOVER, parameters=parameters, expected_versions=versions,
        required_predicates=('obstacle_assessed',), required_resource_ids=('corridor',),
        expected_effects=('obstruction_moved',), corridor_id='corridor')
    claim = Claim(id='claim', task_id='task', robot_id='recovery', holder_id='recovery',
        coordinator_epoch=0, fence=1, resource_fences={'corridor': 1},
        lease_expires_at_utc=now + timedelta(minutes=5),
        clock_domain='coordinator_epoch_utc_lease_v1', state='active')
    permit = GovernanceWitness(id='permit', kind='permission', decision_id='decision',
        owner_id='owner', span_id='span', corridor_id='corridor', action_kinds=(SkillKind.RECOVER,),
        robot_types=('recovery',), state='active', source_valid=True, owner_valid=True,
        approved=True, integrity_errors=())
    evidence = EvidenceBundle(observations=observations, planning_facts=(),
        governance_candidates=(permit,), integrity_errors=(), versions=versions, completeness='complete')
    auth = authorize(proposal, evidence, claim, now_tick=service.status()['world_tick'],
                     now_utc=now, robot_type='recovery')
    assert auth.status == 'ALLOW'
    assert auth.valid_until_tick == 50
    command = CommandIntent(command_id='recovery-command', proposal=proposal,
        payload_hash=canonical_json_hash(proposal), claim_id=claim.id, fence=1,
        resource_fences=claim.resource_fences, authorization_id=auth.authorization_id,
        policy_epoch=0, coordinator_epoch=0, dispatch_sequence=2, effective_world_tick=0,
        authorization=auth)
    wire = command.model_dump(mode='json')
    return DispatchEvent(id=command.command_id, sequence=2, coordinator_epoch=0,
        kind='COMMAND', effective_world_tick=0, payload=wire, payload_hash=canonical_json_hash(wire))


@pytest.fixture
def service(tmp_path):
    sim = SimulatorService(tmp_path)
    sim.create_episode('execution-window', 'SC-001', 3)
    sim.load_payload('courier', 'parcel')
    sim.receive(control('fence', 1, 'FENCE_INSTALL', {
        'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1}}))
    try:
        yield sim
    finally:
        sim.close()


def test_fresh_admission_allows_bounded_native_recovery_beyond_sensor_ttl(service):
    event = recovery_command(service)
    assert service.receive(event)['command_state'] == 'RUNNING'
    service.advance(2000)
    receipt = service.command('recovery-command')
    assert receipt['state'] == 'CONTROLLER_DONE'
    assert receipt['native']['contact_count'] > 0
    assert receipt['native']['measured_displacement_m'] >= .75
    assert service.receive(event)['status'] == 'REPLAY'
    assert service.status()['started_commands'] == 1


def test_legacy_command_retains_original_admission_ttl_timeout(service):
    service.receive(recovery_command(service, explicit=False))
    service.advance(60)
    receipt = service.command('recovery-command')
    assert receipt['state'] == 'FAILED'
    assert receipt['native']['reason'] == 'no_sufficient_physical_displacement'
    assert receipt['native']['deadline_tick'] == 50


def test_late_admission_remains_rejected_despite_later_execution_deadline(service):
    event = recovery_command(service)
    service.advance(51)
    result = service.receive(event)
    assert result['status'] == 'HOLD'
    assert 'EXPIRED_OR_EARLY_AUTHORIZATION' in result['reason_codes']
    assert service.status()['started_commands'] == 0


@pytest.mark.parametrize('deadline', [True, '2000', None, 0, 2001])
def test_untrusted_explicit_deadline_cannot_start_native_motion(service, deadline):
    wire = recovery_command(service).model_dump(mode='json')
    proposal = wire['payload']['proposal']
    proposal['parameters']['execution_until_tick'] = deadline
    proposal_hash = canonical_json_hash(proposal)
    wire['payload']['payload_hash'] = proposal_hash
    wire['payload']['authorization']['action_payload_hash'] = proposal_hash
    wire['payload_hash'] = canonical_json_hash(wire['payload'])
    event = DispatchEvent.model_validate(wire)
    result = service.receive(event)
    assert result['command_state'] == 'FAILED'
    assert service.status()['started_commands'] == 0
    assert service.receive(event)['status'] == 'REPLAY'
    assert service.status()['started_commands'] == 0


def test_short_explicit_deadline_does_not_slide_on_delayed_admission(service):
    event = recovery_command(service, deadline=100)
    service.advance(20)
    assert service.receive(event)['command_state'] == 'RUNNING'
    assert service.command(event.id)['native']['deadline_tick'] == 100
    service.advance(90)
    assert service.command(event.id)['state'] == 'FAILED'
